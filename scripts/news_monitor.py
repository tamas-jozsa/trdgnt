"""
news_monitor.py
===============
Real-time news monitoring daemon that runs as an asyncio background task.

Polls Reuters, Finnhub, and Reddit every 5 minutes, uses LLM triage to
identify material news events, and triggers trading analysis for affected
tickers.

Usage (from FastAPI lifespan):
    from news_monitor import NewsMonitor
    monitor = NewsMonitor()
    asyncio.create_task(monitor.poll_loop())

Dashboard control:
    monitor.start()  # Enable polling
    monitor.stop()   # Disable polling
    monitor.get_status()  # Get current status
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo
from enum import Enum
import os

# Import existing data fetchers
from tradingagents.dataflows.reuters_utils import _fetch_sitemap
from tradingagents.dataflows.finnhub_utils import get_global_news_finnhub
from tradingagents.dataflows.reddit_utils import SUBREDDITS, USER_AGENT, REQUEST_TIMEOUT
from urllib.request import Request, urlopen
import json as json_module

from news_monitor_config import (
    NEWS_MONITOR_DIR,
    ENABLED_STATE_FILE,
    SEEN_ARTICLES_FILE,
    EVENTS_LOG_FILE,
    TRIGGERS_LOG_FILE,
    QUEUED_TRIGGERS_FILE,
    ACTIVE_ANALYSES_FILE,
    STATS_FILE,
    POLL_INTERVAL_SECONDS,
    DEDUP_WINDOW_HOURS,
    COOLDOWN_MINUTES,
    MAX_CONCURRENT_ANALYSES,
    MAX_QUEUE_SIZE,
    ENABLE_REUTERS,
    ENABLE_FINNHUB,
    ENABLE_REDDIT,
    REDDIT_SUBREDDITS,
    REDDIT_POSTS_PER_SUB,
    FINNHUB_CATEGORY,
    FINNHUB_LIMIT,
    REUTERS_HOURS_BACK,
    TRIAGE_LLM_MODEL,
    TRIAGE_MAX_TOKENS,
    TRIAGE_TEMPERATURE,
    URGENCY_HIGH,
    MIN_URGENCY_TO_TRIGGER,
    AUTO_ADD_NEW_TICKERS,
    NEW_TICKER_TIER,
    NEW_TICKER_SECTOR,
    VALIDATE_NEW_TICKERS,
    MARKET_OPEN_HOUR,
    MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR,
    MARKET_CLOSE_MINUTE,
    EXTENDED_PRE_HOUR,
    EXTENDED_POST_HOUR,
    TIMEZONE,
    ESTIMATED_TRIAGE_COST_PER_CALL,
    ANALYSIS_COST_PER_TICKER,
    PROJECT_ROOT,
    TRADING_LOGS_DIR,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class MarketState(Enum):
    OPEN = "open"
    EXTENDED = "extended"
    CLOSED = "closed"


@dataclass
class NewsItem:
    source: str
    url: str
    title: str
    summary: str
    tickers_mentioned: list[str] = field(default_factory=list)
    published_at: Optional[datetime] = None

    def hash(self) -> str:
        """Generate unique hash for dedup."""
        if self.source == "reddit":
            # For Reddit, use title + subreddit since URLs vary
            content = f"{self.source}:{self.title}"
        else:
            content = f"{self.source}:{self.url}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class TriageEvent:
    """Result of LLM triage for a single news item."""
    news_hash: str
    source: str
    title: str
    affected_tickers: list[str]
    urgency: str
    sentiment: str
    reasoning: str
    action_recommended: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "news_hash": self.news_hash,
            "source": self.source,
            "title": self.title[:200],
            "affected_tickers": self.affected_tickers,
            "urgency": self.urgency,
            "sentiment": self.sentiment,
            "reasoning": self.reasoning,
            "action_recommended": self.action_recommended,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Trigger:
    """A spawned trading analysis."""
    trigger_id: str
    tickers: list[str]
    reason: str
    news_hashes: list[str]
    pid: Optional[int] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed

    def to_dict(self) -> dict:
        return {
            "trigger_id": self.trigger_id,
            "tickers": self.tickers,
            "reason": self.reason,
            "news_hashes": self.news_hashes,
            "pid": self.pid,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
        }


@dataclass
class DailyStats:
    """Tracks daily usage stats."""
    date: str = field(default_factory=lambda: date.today().isoformat())
    polls: int = 0
    articles_seen: int = 0
    new_articles: int = 0
    high_urgency_events: int = 0
    triggers_spawned: int = 0
    tickers_analyzed: int = 0
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# NewsMonitor Class
# ---------------------------------------------------------------------------

class NewsMonitor:
    """
    Real-time news monitoring daemon.

    Runs as an asyncio background task, polling news sources every 5 minutes.
    Can be enabled/disabled via start()/stop() methods.
    """

    _instance: Optional[NewsMonitor] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.enabled = self._load_enabled_state()
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self._seen_articles: dict[str, datetime] = {}  # hash -> seen_at
        self._cooldowns: dict[str, datetime] = {}  # ticker -> last_analyzed_at
        self._active_analyses: dict[str, Trigger] = {}  # trigger_id -> Trigger
        self._queued_triggers: list[dict] = []  # Queue for off-hours
        self._current_stats = self._load_stats()
        self._last_market_state: Optional[MarketState] = None
        self._market_open_notified = False

        # Load persisted state
        self._load_seen_articles()
        self._load_queued_triggers()
        self._load_active_analyses()

    # -----------------------------------------------------------------------
    # State Persistence
    # -----------------------------------------------------------------------

    def _load_enabled_state(self) -> bool:
        """Load whether monitoring is enabled."""
        if ENABLED_STATE_FILE.exists():
            try:
                with open(ENABLED_STATE_FILE) as f:
                    data = json.load(f)
                    return data.get("enabled", True)
            except Exception:
                pass
        return True

    def _save_enabled_state(self):
        """Save enabled state to disk."""
        with open(ENABLED_STATE_FILE, "w") as f:
            json.dump({"enabled": self.enabled, "updated_at": datetime.now(timezone.utc).isoformat()}, f)

    def _load_seen_articles(self):
        """Load dedup cache from disk."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_WINDOW_HOURS)
        if SEEN_ARTICLES_FILE.exists():
            try:
                with open(SEEN_ARTICLES_FILE) as f:
                    data = json.load(f)
                    for h, ts_str in data.items():
                        ts = datetime.fromisoformat(ts_str)
                        if ts > cutoff:
                            self._seen_articles[h] = ts
            except Exception as e:
                logger.warning(f"Failed to load seen articles: {e}")

    def _save_seen_articles(self):
        """Save dedup cache to disk."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_WINDOW_HOURS)
        # Prune old entries
        self._seen_articles = {h: ts for h, ts in self._seen_articles.items() if ts > cutoff}
        with open(SEEN_ARTICLES_FILE, "w") as f:
            json.dump({h: ts.isoformat() for h, ts in self._seen_articles.items()}, f)

    def _load_queued_triggers(self):
        """Load queued triggers for off-hours processing."""
        if QUEUED_TRIGGERS_FILE.exists():
            try:
                with open(QUEUED_TRIGGERS_FILE) as f:
                    self._queued_triggers = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load queued triggers: {e}")
                self._queued_triggers = []

    def _save_queued_triggers(self):
        """Save queued triggers to disk."""
        with open(QUEUED_TRIGGERS_FILE, "w") as f:
            json.dump(self._queued_triggers, f)

    def _load_active_analyses(self):
        """Load active analysis tracking."""
        if ACTIVE_ANALYSES_FILE.exists():
            try:
                with open(ACTIVE_ANALYSES_FILE) as f:
                    data = json.load(f)
                    for tid, tdict in data.items():
                        self._active_analyses[tid] = Trigger(
                            trigger_id=tid,
                            tickers=tdict["tickers"],
                            reason=tdict["reason"],
                            news_hashes=tdict["news_hashes"],
                            pid=tdict.get("pid"),
                            started_at=datetime.fromisoformat(tdict["started_at"]),
                            status=tdict.get("status", "running"),
                        )
            except Exception as e:
                logger.warning(f"Failed to load active analyses: {e}")

    def _save_active_analyses(self):
        """Save active analysis tracking."""
        data = {tid: t.to_dict() for tid, t in self._active_analyses.items()}
        with open(ACTIVE_ANALYSES_FILE, "w") as f:
            json.dump(data, f)

    def _load_stats(self) -> DailyStats:
        """Load or initialize daily stats."""
        today = date.today().isoformat()
        if STATS_FILE.exists():
            try:
                with open(STATS_FILE) as f:
                    data = json.load(f)
                    if data.get("date") == today:
                        return DailyStats(**data)
            except Exception:
                pass
        return DailyStats(date=today)

    def _save_stats(self):
        """Save daily stats."""
        with open(STATS_FILE, "w") as f:
            json.dump(self._current_stats.to_dict(), f)

    # -----------------------------------------------------------------------
    # Control Methods
    # -----------------------------------------------------------------------

    def start(self) -> dict:
        """Enable news monitoring."""
        self.enabled = True
        self._save_enabled_state()
        logger.info("News monitor enabled")
        return {"status": "started", "enabled": True}

    def stop(self) -> dict:
        """Disable news monitoring."""
        self.enabled = False
        self._save_enabled_state()
        logger.info("News monitor disabled")
        return {"status": "stopped", "enabled": False}

    def get_status(self) -> dict:
        """Get current monitor status."""
        market_state = self._get_market_state()
        return {
            "enabled": self.enabled,
            "polling": self.running and self.enabled,
            "market_state": market_state.value,
            "last_poll_at": self._get_last_poll_time(),
            "articles_today": self._current_stats.articles_seen,
            "new_articles_today": self._current_stats.new_articles,
            "triggers_today": self._current_stats.triggers_spawned,
            "active_analyses": len(self._active_analyses),
            "queued_triggers": len(self._queued_triggers),
            "estimated_cost_today_usd": round(self._current_stats.estimated_cost_usd, 4),
        }

    def _get_last_poll_time(self) -> Optional[str]:
        """Get timestamp of last successful poll."""
        if EVENTS_LOG_FILE.exists():
            try:
                with open(EVENTS_LOG_FILE) as f:
                    lines = f.readlines()
                    if lines:
                        last = json.loads(lines[-1])
                        return last.get("timestamp")
            except Exception:
                pass
        return None

    # -----------------------------------------------------------------------
    # Main Poll Loop
    # -----------------------------------------------------------------------

    async def poll_loop(self):
        """Main polling loop - runs forever as background task."""
        self.running = True
        logger.info("News monitor poll loop started")

        while self.running:
            try:
                # Track market state changes
                current_market = self._get_market_state()
                if self._last_market_state is None:
                    self._last_market_state = current_market

                # Detect market opening (closed -> open/extended)
                market_just_opened = (
                    self._last_market_state == MarketState.CLOSED
                    and current_market in (MarketState.OPEN, MarketState.EXTENDED)
                )

                if self.enabled:
                    await self._poll_cycle()

                    # Drain queue when market opens or periodically during extended hours
                    if market_just_opened:
                        logger.info(f"Market opened ({current_market.value}), draining queue...")
                        await self._drain_queue()
                    elif current_market == MarketState.EXTENDED and self._queued_triggers:
                        # Also drain during extended hours (pre/post market trading)
                        await self._drain_queue()

                elif market_just_opened and self._queued_triggers:
                    # Even if monitor is disabled, drain queue when market opens
                    # (triggers were queued when monitor was enabled)
                    logger.info(f"Market opened, draining {len(self._queued_triggers)} queued triggers...")
                    await self._drain_queue()

                self._last_market_state = current_market

                # Check for completed analyses
                await self._check_active_analyses()

            except Exception as e:
                logger.exception(f"Error in poll cycle: {e}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _poll_cycle(self):
        """Single poll cycle: fetch, dedup, triage, trigger."""
        logger.debug("Starting poll cycle")

        # Fetch from all sources concurrently
        sources_tasks = []
        if ENABLE_REUTERS:
            sources_tasks.append(self._fetch_reuters())
        if ENABLE_FINNHUB:
            sources_tasks.append(self._fetch_finnhub())
        if ENABLE_REDDIT:
            sources_tasks.append(self._fetch_reddit())

        results = await asyncio.gather(*sources_tasks, return_exceptions=True)
        all_items: list[NewsItem] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Source fetch failed: {result}")
            else:
                all_items.extend(result)

        self._current_stats.polls += 1
        self._current_stats.articles_seen += len(all_items)

        # Deduplicate
        new_items = self._dedup_items(all_items)
        self._current_stats.new_articles += len(new_items)

        if not new_items:
            logger.debug("No new articles to process")
            self._save_stats()
            return

        logger.info(f"Found {len(new_items)} new articles to triage")

        # LLM Triage (TICKET-091 placeholder)
        # For now, basic keyword-based triage until LLM is implemented
        events = await self._triage_news(new_items)

        # Process high-urgency events
        high_urgency = [e for e in events if e.urgency == URGENCY_HIGH and e.action_recommended]
        self._current_stats.high_urgency_events += len(high_urgency)

        if high_urgency:
            logger.info(f"{len(high_urgency)} high-urgency events detected")
            await self._process_high_urgency_events(high_urgency)

        # Persist state
        self._save_seen_articles()
        self._save_stats()

    # -----------------------------------------------------------------------
    # News Fetchers
    # -----------------------------------------------------------------------

    async def _fetch_reuters(self) -> list[NewsItem]:
        """Fetch Reuters news from sitemap."""
        articles = _fetch_sitemap(hours_back=REUTERS_HOURS_BACK)
        items = []
        for a in articles:
            items.append(NewsItem(
                source="reuters",
                url=a["url"],
                title=a["title"],
                summary=a["title"][:200],
                tickers_mentioned=a.get("tickers", []),
                published_at=a["published_at"],
            ))
        return items

    async def _fetch_finnhub(self) -> list[NewsItem]:
        """Fetch Finnhub general market news."""
        news_text = get_global_news_finnhub(category=FINNHUB_CATEGORY, limit=FINNHUB_LIMIT)
        # Parse the formatted text back into items
        items = []
        # Simple parsing - Finnhub format is markdown-like
        lines = news_text.split("\n")
        current_item = None

        for line in lines:
            if line.startswith("### "):
                if current_item:
                    items.append(current_item)
                current_item = NewsItem(
                    source="finnhub",
                    url="",
                    title=line[4:].strip(),
                    summary="",
                    tickers_mentioned=[],
                )
            elif line.startswith("**Source:**") and current_item:
                # Try to extract URL from next "[Read more]" line
                pass
            elif line.startswith("[Read more]") and current_item:
                # Extract URL from markdown link
                import re
                match = re.search(r'\[Read more\]\((.+?)\)', line)
                if match:
                    current_item.url = match.group(1)
            elif line.startswith("*") and current_item and not current_item.summary:
                current_item.summary = line.strip("* ")[:200]

        if current_item:
            items.append(current_item)

        return items

    async def _fetch_reddit(self) -> list[NewsItem]:
        """Fetch hot posts from configured subreddits."""
        items = []
        for subreddit in REDDIT_SUBREDDITS:
            try:
                url = (
                    f"https://www.reddit.com/r/{subreddit}/hot.json"
                    f"?limit={REDDIT_POSTS_PER_SUB}"
                )
                req = Request(url, headers={"User-Agent": USER_AGENT})
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: urlopen(req, timeout=REQUEST_TIMEOUT).read()
                )
                data = json_module.loads(response.decode())

                for child in data.get("data", {}).get("children", []):
                    p = child.get("data", {})
                    title = p.get("title", "")
                    permalink = p.get("permalink", "")
                    url = f"https://reddit.com{permalink}"

                    # Extract cashtags from title
                    import re
                    cashtags = re.findall(r'\$([A-Z]{1,5})\b', title)

                    items.append(NewsItem(
                        source=f"reddit_{subreddit}",
                        url=url,
                        title=title[:300],
                        summary=title[:200],
                        tickers_mentioned=cashtags,
                        published_at=datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc),
                    ))
            except Exception as e:
                logger.debug(f"Reddit fetch failed for r/{subreddit}: {e}")

        return items

    # -----------------------------------------------------------------------
    # Deduplication
    # -----------------------------------------------------------------------

    def _dedup_items(self, items: list[NewsItem]) -> list[NewsItem]:
        """Filter out already-seen items."""
        new_items = []
        for item in items:
            h = item.hash()
            if h not in self._seen_articles:
                self._seen_articles[h] = datetime.now(timezone.utc)
                new_items.append(item)
        return new_items

    # -----------------------------------------------------------------------
    # LLM Triage (TICKET-091)
    # -----------------------------------------------------------------------

    async def _triage_news(self, items: list[NewsItem]) -> list[TriageEvent]:
        """
        Triage news items using LLM and return events.

        Uses OpenAI's structured output for consistent results.
        Falls back to keyword-based triage if LLM fails.
        """
        from news_monitor_triage import triage_news_batch, TriageResult
        from trading_loop import load_watchlist_overrides

        # Get current watchlist for context
        watchlist = load_watchlist_overrides()
        watchlist_tickers = list(watchlist.keys())

        # Convert NewsItems to dicts for triage module
        item_dicts = [
            {
                "source": item.source,
                "title": item.title,
                "summary": item.summary,
                "tickers_mentioned": item.tickers_mentioned,
            }
            for item in items
        ]

        # Run triage (this is a sync function that calls OpenAI)
        loop = asyncio.get_event_loop()
        triage_results: list[TriageResult] = await loop.run_in_executor(
            None,
            lambda: triage_news_batch(item_dicts, watchlist_tickers)
        )

        # Update cost tracking
        from news_monitor_triage import estimate_triage_cost
        self._current_stats.estimated_cost_usd += estimate_triage_cost(len(items))

        # Convert TriageResults to TriageEvents
        events = []
        for result in triage_results:
            if result.news_index < 0 or result.news_index >= len(items):
                continue

            item = items[result.news_index]

            event = TriageEvent(
                news_hash=item.hash(),
                source=item.source,
                title=item.title,
                affected_tickers=result.affected_tickers,
                urgency=result.urgency,
                sentiment=result.sentiment,
                reasoning=result.reasoning,
                action_recommended=result.action_recommended,
            )
            events.append(event)

            # Log event
            self._log_event(event)

        return events

    def _log_event(self, event: TriageEvent):
        """Append event to events log."""
        with open(EVENTS_LOG_FILE, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    # -----------------------------------------------------------------------
    # Event Processing
    # -----------------------------------------------------------------------

    async def _process_high_urgency_events(self, events: list[TriageEvent]):
        """Process high-urgency events: dedup tickers, check cooldowns, trigger."""
        # Collect all affected tickers
        all_tickers = set()
        ticker_reasons: dict[str, list[str]] = {}
        ticker_hashes: dict[str, list[str]] = {}

        for event in events:
            for ticker in event.affected_tickers:
                ticker = ticker.upper()
                all_tickers.add(ticker)
                if ticker not in ticker_reasons:
                    ticker_reasons[ticker] = []
                    ticker_hashes[ticker] = []
                ticker_reasons[ticker].append(event.reasoning)
                ticker_hashes[ticker].append(event.news_hash)

        # Filter out tickers on cooldown
        now = datetime.now(timezone.utc)
        cooldown_cutoff = now - timedelta(minutes=COOLDOWN_MINUTES)

        available_tickers = []
        for ticker in all_tickers:
            last_analysis = self._cooldowns.get(ticker)
            if last_analysis and last_analysis > cooldown_cutoff:
                logger.debug(f"Ticker {ticker} on cooldown, skipping")
                continue
            available_tickers.append(ticker)

        if not available_tickers:
            logger.info("All affected tickers on cooldown, no triggers")
            return

        # Check market state
        market_state = self._get_market_state()

        if market_state == MarketState.CLOSED:
            # Queue for next market open
            for ticker in available_tickers:
                self._queue_trigger(ticker, ticker_reasons[ticker], ticker_hashes[ticker])
            logger.info(f"Queued {len(available_tickers)} tickers for next market open")
            return

        # Spawn analyses (respecting max concurrent)
        await self._spawn_analyses(available_tickers, ticker_reasons, ticker_hashes)

    def _queue_trigger(self, ticker: str, reasons: list[str], hashes: list[str]):
        """Add a trigger to the off-hours queue."""
        if len(self._queued_triggers) >= MAX_QUEUE_SIZE:
            logger.warning("Queue full, dropping oldest trigger")
            self._queued_triggers.pop(0)

        self._queued_triggers.append({
            "ticker": ticker,
            "reason": "; ".join(reasons)[:500],
            "news_hashes": hashes,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save_queued_triggers()

    async def _spawn_analyses(self, tickers: list[str], reasons: dict, hashes: dict):
        """Spawn trading_loop.py processes for tickers."""
        # Group tickers to respect max concurrent
        slots_available = MAX_CONCURRENT_ANALYSES - len(self._active_analyses)

        if slots_available <= 0:
            # Queue all if no slots
            for ticker in tickers:
                self._queue_trigger(ticker, reasons[ticker], hashes[ticker])
            logger.info(f"No slots available, queued {len(tickers)} tickers")
            return

        # Take available slots
        to_spawn = tickers[:slots_available]
        to_queue = tickers[slots_available:]

        for ticker in to_queue:
            self._queue_trigger(ticker, reasons[ticker], hashes[ticker])

        # Spawn processes (batch by slot)
        for ticker in to_spawn:
            await self._spawn_single_analysis(ticker, reasons[ticker], hashes[ticker])

    async def _spawn_single_analysis(self, ticker: str, reasons: list[str], hashes: list[str]):
        """Spawn a single trading_loop.py process for a ticker."""
        trigger_id = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{ticker}"

        # Handle new ticker discovery
        is_new = await self._handle_ticker_discovery(ticker)
        if is_new:
            logger.info(f"Discovered new ticker: {ticker}")

        # Build command
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "trading_loop.py"),
            "--tickers", ticker,
            "--once",
            "--no-wait",
        ]

        try:
            # Spawn process
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=open(TRADING_LOGS_DIR / "stdout.log", "a"),
                stderr=open(TRADING_LOGS_DIR / "stderr.log", "a"),
            )

            trigger = Trigger(
                trigger_id=trigger_id,
                tickers=[ticker],
                reason="; ".join(reasons)[:500],
                news_hashes=hashes,
                pid=proc.pid,
                status="running",
            )

            self._active_analyses[trigger_id] = trigger
            self._cooldowns[ticker] = datetime.now(timezone.utc)
            self._save_active_analyses()

            # Update stats
            self._current_stats.triggers_spawned += 1
            self._current_stats.tickers_analyzed += 1
            self._current_stats.estimated_cost_usd += ANALYSIS_COST_PER_TICKER
            self._save_stats()

            # Log trigger
            with open(TRIGGERS_LOG_FILE, "a") as f:
                f.write(json.dumps(trigger.to_dict()) + "\n")

            logger.info(f"Spawned analysis for {ticker} (PID {proc.pid})")

        except Exception as e:
            logger.exception(f"Failed to spawn analysis for {ticker}: {e}")

    async def _handle_ticker_discovery(self, ticker: str) -> bool:
        """
        Handle discovery of a new ticker not on the watchlist.

        Validates the ticker using yfinance, then adds to watchlist_overrides
        with TACTICAL tier if it's a real, tradeable stock.

        Returns True if this is a new ticker that was auto-added.
        """
        from trading_loop import WATCHLIST, load_watchlist_overrides, save_watchlist_overrides

        ticker = ticker.upper().strip()

        # Check if already on watchlist (static or dynamic)
        effective = load_watchlist_overrides()
        if ticker in effective:
            return False

        if not AUTO_ADD_NEW_TICKERS:
            logger.info(f"New ticker discovered: {ticker} (auto-add disabled)")
            return True  # It's new, but we didn't add it

        # Validate ticker exists and is tradeable
        if VALIDATE_NEW_TICKERS:
            is_valid = await self._validate_ticker(ticker)
            if not is_valid:
                logger.warning(f"Discovered ticker {ticker} failed validation, skipping")
                return False

        # Add to watchlist_overrides
        today_str = date.today().isoformat()
        add_entry = {
            ticker: {
                "sector": NEW_TICKER_SECTOR,
                "tier": NEW_TICKER_TIER,
                "note": f"Auto-discovered by news monitor",
                "added_on": today_str,
                "source": "news_monitor",
            }
        }

        try:
            save_watchlist_overrides(adds=add_entry, removes=[])
            logger.info(f"Added new ticker {ticker} to watchlist as {NEW_TICKER_TIER}")
            return True
        except Exception as e:
            logger.exception(f"Failed to add ticker {ticker} to watchlist: {e}")
            return False

    async def _validate_ticker(self, ticker: str) -> bool:
        """
        Validate that a ticker symbol represents a real, tradeable stock.

        Uses yfinance to check if the ticker has valid info.
        """
        try:
            import yfinance as yf

            # Run in executor to not block
            loop = asyncio.get_event_loop()
            stock = await loop.run_in_executor(None, lambda: yf.Ticker(ticker))

            # Try to get info - this will fail or return empty for invalid tickers
            info = await loop.run_in_executor(None, lambda: stock.info)

            if not info or len(info) < 5:
                return False

            # Check for key fields that indicate a real stock
            required_fields = ["symbol", "shortName", "regularMarketPrice"]
            for field in required_fields:
                if field not in info or info[field] is None:
                    return False

            # Verify symbol matches (yfinance sometimes returns data for different ticker)
            if info.get("symbol", "").upper() != ticker:
                return False

            return True

        except Exception as e:
            logger.debug(f"Ticker validation failed for {ticker}: {e}")
            return False

    # -----------------------------------------------------------------------
    # Active Analysis Management
    # -----------------------------------------------------------------------

    async def _check_active_analyses(self):
        """Check status of active analyses and clean up completed ones."""
        to_remove = []

        for trigger_id, trigger in self._active_analyses.items():
            if trigger.pid is None:
                continue

            # Check if process is still running
            try:
                import psutil
                if not psutil.pid_exists(trigger.pid):
                    trigger.status = "completed"
                    trigger.completed_at = datetime.now(timezone.utc)
                    to_remove.append(trigger_id)
            except ImportError:
                # Fallback: try os.kill with signal 0
                try:
                    import signal
                    os.kill(trigger.pid, 0)
                except (OSError, ProcessLookupError):
                    trigger.status = "completed"
                    trigger.completed_at = datetime.now(timezone.utc)
                    to_remove.append(trigger_id)

        for tid in to_remove:
            del self._active_analyses[tid]

        if to_remove:
            self._save_active_analyses()

    # -----------------------------------------------------------------------
    # Queue Management
    # -----------------------------------------------------------------------

    async def _drain_queue(self):
        """
        Drain the queued triggers, respecting max concurrent limit.

        Called when market opens or during extended hours.
        """
        if not self._queued_triggers:
            return

        market_state = self._get_market_state()
        logger.info(f"Draining queue: {len(self._queued_triggers)} pending triggers (market: {market_state.value})")

        drained = 0
        while self._queued_triggers and len(self._active_analyses) < MAX_CONCURRENT_ANALYSES:
            item = self._queued_triggers.pop(0)
            await self._spawn_single_analysis(
                item["ticker"],
                [item["reason"]],
                item.get("news_hashes", []),
            )
            drained += 1

        self._save_queued_triggers()

        if self._queued_triggers:
            logger.info(f"Queue partially drained: {drained} processed, {len(self._queued_triggers)} remaining (waiting for slots)")
        else:
            logger.info(f"Queue fully drained: {drained} triggers processed")

    # -----------------------------------------------------------------------
    # Market Hours
    # -----------------------------------------------------------------------

    def _get_market_state(self) -> MarketState:
        """Determine current market state."""
        now = datetime.now(ZoneInfo(TIMEZONE))

        # Weekend check
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return MarketState.CLOSED

        hour_min = now.hour * 100 + now.minute

        # Regular hours: 9:30 - 16:00
        if MARKET_OPEN_HOUR * 100 + MARKET_OPEN_MINUTE <= hour_min < MARKET_CLOSE_HOUR * 100 + MARKET_CLOSE_MINUTE:
            return MarketState.OPEN

        # Extended hours: 6:00 - 9:30 and 16:00 - 20:00
        if EXTENDED_PRE_HOUR * 100 <= hour_min < MARKET_OPEN_HOUR * 100 + MARKET_OPEN_MINUTE:
            return MarketState.EXTENDED
        if MARKET_CLOSE_HOUR * 100 + MARKET_CLOSE_MINUTE <= hour_min < EXTENDED_POST_HOUR * 100:
            return MarketState.EXTENDED

        return MarketState.CLOSED


# ---------------------------------------------------------------------------
# Singleton Instance
# ---------------------------------------------------------------------------

def get_news_monitor() -> NewsMonitor:
    """Get the singleton NewsMonitor instance."""
    return NewsMonitor()
