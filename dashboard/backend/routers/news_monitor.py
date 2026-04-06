"""
news_monitor.py (dashboard router)
==================================
API endpoints for the real-time news monitor dashboard.

Provides:
- GET /api/news-monitor/status     - Current monitor status
- POST /api/news-monitor/start     - Enable monitoring
- POST /api/news-monitor/stop      - Disable monitoring
- GET /api/news-monitor/feed       - Recent triaged news events
- GET /api/news-monitor/triggers   - Trigger history
- GET /api/news-monitor/queue      - Queued triggers (off-hours)
- POST /api/news-monitor/drain     - Manually drain queue
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dashboard.backend.config import NEWS_MONITOR_DIR
from news_monitor import get_news_monitor, TriageEvent, Trigger
from news_monitor_config import (
    EVENTS_LOG_FILE,
    TRIGGERS_LOG_FILE,
    QUEUED_TRIGGERS_FILE,
)

router = APIRouter(tags=["news-monitor"])


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------

class StatusResponse(BaseModel):
    enabled: bool
    polling: bool
    market_state: str
    last_poll_at: Optional[str]
    articles_today: int
    new_articles_today: int
    triggers_today: int
    active_analyses: int
    queued_triggers: int
    estimated_cost_today_usd: float


class ControlResponse(BaseModel):
    status: str
    enabled: bool


class NewsEvent(BaseModel):
    news_hash: str
    source: str
    title: str
    affected_tickers: List[str]
    urgency: str
    sentiment: str
    reasoning: str
    action_recommended: bool
    timestamp: str


class TriggerItem(BaseModel):
    trigger_id: str
    tickers: List[str]
    reason: str
    pid: Optional[int]
    started_at: str
    completed_at: Optional[str]
    status: str


class QueueItem(BaseModel):
    ticker: str
    reason: str
    queued_at: str


class FeedResponse(BaseModel):
    events: List[NewsEvent]
    total: int


class TriggersResponse(BaseModel):
    triggers: List[TriggerItem]
    active: List[TriggerItem]
    total: int


class QueueResponse(BaseModel):
    items: List[QueueItem]
    count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Get current news monitor status."""
    monitor = get_news_monitor()
    return monitor.get_status()


@router.post("/start", response_model=ControlResponse)
async def start_monitor():
    """Enable news monitoring."""
    monitor = get_news_monitor()
    result = monitor.start()
    return ControlResponse(**result)


@router.post("/stop", response_model=ControlResponse)
async def stop_monitor():
    """Disable news monitoring."""
    monitor = get_news_monitor()
    result = monitor.stop()
    return ControlResponse(**result)


@router.get("/feed", response_model=FeedResponse)
async def get_feed(limit: int = 50, urgency: Optional[str] = None):
    """
    Get recent triaged news events.

    Query params:
        limit: Max events to return (default 50)
        urgency: Filter by urgency (HIGH, MEDIUM, LOW)
    """
    events = []

    if not EVENTS_LOG_FILE.exists():
        return FeedResponse(events=[], total=0)

    try:
        with open(EVENTS_LOG_FILE) as f:
            lines = f.readlines()

        # Parse from end (newest first)
        for line in reversed(lines):
            try:
                data = json.loads(line.strip())
                if urgency and data.get("urgency") != urgency:
                    continue
                events.append(NewsEvent(**data))
                if len(events) >= limit:
                    break
            except json.JSONDecodeError:
                continue

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read feed: {e}")

    return FeedResponse(events=events, total=len(events))


@router.get("/triggers", response_model=TriggersResponse)
async def get_triggers(limit: int = 50, active_only: bool = False):
    """
    Get trigger history.

    Query params:
        limit: Max triggers to return (default 50)
        active_only: Only return currently running triggers
    """
    monitor = get_news_monitor()

    # Get active triggers from memory
    active = []
    for trigger in monitor._active_analyses.values():
        active.append(TriggerItem(
            trigger_id=trigger.trigger_id,
            tickers=trigger.tickers,
            reason=trigger.reason,
            pid=trigger.pid,
            started_at=trigger.started_at.isoformat(),
            completed_at=trigger.completed_at.isoformat() if trigger.completed_at else None,
            status=trigger.status,
        ))

    if active_only:
        return TriggersResponse(triggers=active, active=active, total=len(active))

    # Read historical triggers from log
    historical = []
    if TRIGGERS_LOG_FILE.exists():
        try:
            with open(TRIGGERS_LOG_FILE) as f:
                lines = f.readlines()

            for line in reversed(lines):
                try:
                    data = json.loads(line.strip())
                    historical.append(TriggerItem(**data))
                    if len(historical) >= limit:
                        break
                except (json.JSONDecodeError, TypeError):
                    continue
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read triggers: {e}")

    return TriggersResponse(
        triggers=historical,
        active=active,
        total=len(historical) + len(active),
    )


@router.get("/queue", response_model=QueueResponse)
async def get_queue():
    """Get queued triggers waiting for market open."""
    items = []

    if not QUEUED_TRIGGERS_FILE.exists():
        return QueueResponse(items=[], count=0)

    try:
        with open(QUEUED_TRIGGERS_FILE) as f:
            data = json.load(f)

        for item in data:
            items.append(QueueItem(
                ticker=item["ticker"],
                reason=item["reason"],
                queued_at=item["queued_at"],
            ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read queue: {e}")

    return QueueResponse(items=items, count=len(items))


@router.post("/drain")
async def drain_queue():
    """Manually drain the queued triggers (process them now)."""
    monitor = get_news_monitor()

    if not monitor._queued_triggers:
        return {"status": "empty", "processed": 0}

    count = len(monitor._queued_triggers)
    await monitor._drain_queue_if_market_opened()

    return {"status": "draining", "processed": count}


@router.get("/stats")
async def get_stats(days: int = 7):
    """Get historical stats for the past N days."""
    from news_monitor_config import STATS_FILE

    stats = []
    cutoff = datetime.now() - timedelta(days=days)

    # Current stats file
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE) as f:
                data = json.load(f)
                stats.append(data)
        except Exception:
            pass

    # Could add historical stats files here if we archive them

    return {
        "stats": stats,
        "period_days": days,
    }
