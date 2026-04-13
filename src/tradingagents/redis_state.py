"""Redis state management for inter-process coordination.

All three v2 processes (discovery, portfolio review, news reaction) use this
module to share state via Redis. Provides portfolio state, coordination,
and event queue operations.

TICKET-105
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Key prefix to namespace all trdagnt keys in Redis
KEY_PREFIX = "trdagnt:"

# Default Redis URL
DEFAULT_REDIS_URL = "redis://localhost:6379/0"

# Backup directory for JSON file persistence
DATA_DIR = Path(os.getenv("TRDAGNT_DATA_DIR", "data"))


def _get_redis_url() -> str:
    return os.getenv("REDIS_URL", DEFAULT_REDIS_URL)


def _key(name: str) -> str:
    """Prefix a key name for Redis namespacing."""
    return f"{KEY_PREFIX}{name}"


class RedisState:
    """Shared state layer backed by Redis with JSON file fallback.

    Usage::

        state = RedisState()
        state.set_position("NVDA", thesis_dict)
        positions = state.get_positions()
    """

    def __init__(self, redis_url: str | None = None, data_dir: str | Path | None = None):
        self._redis_url = redis_url or _get_redis_url()
        self._data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._redis: Any | None = None
        self._available = False
        self._connect()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Attempt to connect to Redis. Logs warning on failure."""
        try:
            import redis as redis_lib

            self._redis = redis_lib.Redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            self._redis.ping()
            self._available = True
            logger.info("Redis connected at %s", self._redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — operating without shared state", exc)
            self._available = False
            self._redis = None

    @property
    def available(self) -> bool:
        return self._available

    def ping(self) -> bool:
        """Check if Redis is reachable."""
        if not self._redis:
            return False
        try:
            return self._redis.ping()
        except Exception:
            self._available = False
            return False

    # ------------------------------------------------------------------
    # Portfolio state
    # ------------------------------------------------------------------

    def get_positions(self) -> dict[str, dict]:
        """Return all positions as {ticker: thesis_dict}."""
        if not self._available:
            return self._load_json_backup("positions")

        try:
            raw = self._redis.hgetall(_key("positions"))
            return {ticker: json.loads(data) for ticker, data in raw.items()}
        except Exception as exc:
            logger.error("Redis get_positions failed: %s", exc)
            return self._load_json_backup("positions")

    def get_position(self, ticker: str) -> dict | None:
        """Return a single position's thesis dict, or None."""
        if not self._available:
            return self._load_json_backup("positions").get(ticker)

        try:
            raw = self._redis.hget(_key("positions"), ticker)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.error("Redis get_position(%s) failed: %s", ticker, exc)
            return None

    def set_position(self, ticker: str, thesis: dict) -> None:
        """Store a position thesis dict."""
        if self._available:
            try:
                self._redis.hset(_key("positions"), ticker, json.dumps(thesis))
            except Exception as exc:
                logger.error("Redis set_position(%s) failed: %s", ticker, exc)

        # Always write JSON backup
        self._save_position_backup(ticker, thesis)

    def remove_position(self, ticker: str) -> None:
        """Remove a position (on sell)."""
        if self._available:
            try:
                self._redis.hdel(_key("positions"), ticker)
            except Exception as exc:
                logger.error("Redis remove_position(%s) failed: %s", ticker, exc)

        # Remove JSON backup
        backup_path = self._data_dir / "theses" / f"{ticker}.json"
        if backup_path.exists():
            backup_path.unlink()

    def get_portfolio_tickers(self) -> set[str]:
        """Return the set of all held ticker symbols."""
        return set(self.get_positions().keys())

    # ------------------------------------------------------------------
    # Cash and portfolio value
    # ------------------------------------------------------------------

    def get_cash(self) -> float:
        """Return current cash balance."""
        if not self._available:
            return self._load_scalar("cash", 0.0)
        try:
            val = self._redis.get(_key("cash"))
            return float(val) if val else 0.0
        except Exception:
            return 0.0

    def set_cash(self, amount: float) -> None:
        if self._available:
            try:
                self._redis.set(_key("cash"), str(amount))
            except Exception as exc:
                logger.error("Redis set_cash failed: %s", exc)
        self._save_scalar("cash", amount)

    def get_portfolio_value(self) -> float:
        if not self._available:
            return self._load_scalar("portfolio_value", 0.0)
        try:
            val = self._redis.get(_key("portfolio_value"))
            return float(val) if val else 0.0
        except Exception:
            return 0.0

    def set_portfolio_value(self, amount: float) -> None:
        if self._available:
            try:
                self._redis.set(_key("portfolio_value"), str(amount))
            except Exception as exc:
                logger.error("Redis set_portfolio_value failed: %s", exc)
        self._save_scalar("portfolio_value", amount)

    def get_sector_exposure(self) -> dict[str, float]:
        """Return sector → percentage of portfolio."""
        if not self._available:
            return self._load_json_backup("sector_exposure")
        try:
            raw = self._redis.hgetall(_key("sector_exposure"))
            return {sector: float(pct) for sector, pct in raw.items()}
        except Exception:
            return {}

    def set_sector_exposure(self, exposure: dict[str, float]) -> None:
        if self._available:
            try:
                pipe = self._redis.pipeline()
                pipe.delete(_key("sector_exposure"))
                if exposure:
                    pipe.hset(
                        _key("sector_exposure"),
                        mapping={k: str(v) for k, v in exposure.items()},
                    )
                pipe.execute()
            except Exception as exc:
                logger.error("Redis set_sector_exposure failed: %s", exc)

    # ------------------------------------------------------------------
    # Coordination
    # ------------------------------------------------------------------

    def mark_analyzed_today(self, ticker: str) -> None:
        """Mark a ticker as analyzed for today (prevents duplicate analysis)."""
        today = datetime.now().strftime("%Y-%m-%d")
        key = _key(f"analyzed:{today}")
        if self._available:
            try:
                self._redis.sadd(key, ticker)
                self._redis.expire(key, 86400 * 2)  # expire after 2 days
            except Exception as exc:
                logger.error("Redis mark_analyzed_today failed: %s", exc)

    def was_analyzed_today(self, ticker: str) -> bool:
        """Check if a ticker was already analyzed today."""
        today = datetime.now().strftime("%Y-%m-%d")
        key = _key(f"analyzed:{today}")
        if not self._available:
            return False
        try:
            return self._redis.sismember(key, ticker)
        except Exception:
            return False

    def get_analyzed_today(self) -> set[str]:
        """Return all tickers analyzed today."""
        today = datetime.now().strftime("%Y-%m-%d")
        key = _key(f"analyzed:{today}")
        if not self._available:
            return set()
        try:
            return self._redis.smembers(key)
        except Exception:
            return set()

    def set_cooldown(self, ticker: str, days: int = 7) -> None:
        """Block re-buy of a ticker for N days after stop-loss."""
        expires = (datetime.now() + timedelta(days=days)).isoformat()
        if self._available:
            try:
                self._redis.hset(_key("cooldown"), ticker, expires)
            except Exception as exc:
                logger.error("Redis set_cooldown failed: %s", exc)

        # JSON backup
        cooldowns = self._load_json_backup("cooldowns")
        cooldowns[ticker] = expires
        self._save_json_backup("cooldowns", cooldowns)

    def is_in_cooldown(self, ticker: str) -> bool:
        """Check if a ticker is in cooldown (recently stopped out)."""
        expires_str = None
        if self._available:
            try:
                expires_str = self._redis.hget(_key("cooldown"), ticker)
            except Exception:
                pass

        if not expires_str:
            cooldowns = self._load_json_backup("cooldowns")
            expires_str = cooldowns.get(ticker)

        if not expires_str:
            return False

        try:
            expires = datetime.fromisoformat(expires_str)
            return datetime.now() < expires
        except (ValueError, TypeError):
            return False

    def clear_expired_cooldowns(self) -> None:
        """Remove expired cooldown entries."""
        now = datetime.now()
        if self._available:
            try:
                all_cooldowns = self._redis.hgetall(_key("cooldown"))
                for ticker, expires_str in all_cooldowns.items():
                    try:
                        if datetime.fromisoformat(expires_str) <= now:
                            self._redis.hdel(_key("cooldown"), ticker)
                    except (ValueError, TypeError):
                        self._redis.hdel(_key("cooldown"), ticker)
            except Exception as exc:
                logger.error("Redis clear_expired_cooldowns failed: %s", exc)

    # ------------------------------------------------------------------
    # Event queues
    # ------------------------------------------------------------------

    def push_news_event(self, event: dict) -> None:
        """Push a news event for dashboard/other processes to consume."""
        if self._available:
            try:
                self._redis.rpush(_key("events:news"), json.dumps(event))
                # Keep queue bounded
                self._redis.ltrim(_key("events:news"), -1000, -1)
            except Exception as exc:
                logger.error("Redis push_news_event failed: %s", exc)

    def pop_news_events(self, count: int = 100) -> list[dict]:
        """Pop up to N news events from the queue."""
        if not self._available:
            return []
        try:
            pipe = self._redis.pipeline()
            pipe.lrange(_key("events:news"), 0, count - 1)
            pipe.ltrim(_key("events:news"), count, -1)
            results = pipe.execute()
            return [json.loads(item) for item in results[0]]
        except Exception as exc:
            logger.error("Redis pop_news_events failed: %s", exc)
            return []

    def get_recent_news_events(self, count: int = 50) -> list[dict]:
        """Peek at recent news events without consuming them."""
        if not self._available:
            return []
        try:
            items = self._redis.lrange(_key("events:news"), -count, -1)
            return [json.loads(item) for item in items]
        except Exception:
            return []

    def push_review_flag(self, ticker: str, reason: str = "") -> None:
        """Flag a ticker for accelerated portfolio review."""
        if self._available:
            try:
                entry = json.dumps({"ticker": ticker, "reason": reason,
                                    "flagged_at": datetime.now().isoformat()})
                self._redis.rpush(_key("events:review_queue"), entry)
            except Exception as exc:
                logger.error("Redis push_review_flag failed: %s", exc)

    def pop_review_flags(self) -> list[dict]:
        """Pop all flagged tickers for review."""
        if not self._available:
            return []
        try:
            pipe = self._redis.pipeline()
            pipe.lrange(_key("events:review_queue"), 0, -1)
            pipe.delete(_key("events:review_queue"))
            results = pipe.execute()
            return [json.loads(item) for item in results[0]]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # JSON file backup / restore
    # ------------------------------------------------------------------

    def _save_position_backup(self, ticker: str, thesis: dict) -> None:
        """Save a single position thesis to JSON backup."""
        backup_dir = self._data_dir / "theses"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{ticker}.json"
        try:
            backup_path.write_text(json.dumps(thesis, indent=2))
        except Exception as exc:
            logger.error("Failed to backup thesis for %s: %s", ticker, exc)

    def _load_json_backup(self, name: str) -> dict:
        """Load a dict from JSON backup files."""
        if name == "positions":
            result = {}
            theses_dir = self._data_dir / "theses"
            if theses_dir.exists():
                for f in theses_dir.glob("*.json"):
                    try:
                        result[f.stem] = json.loads(f.read_text())
                    except Exception:
                        pass
            return result

        backup_path = self._data_dir / f"{name}.json"
        if backup_path.exists():
            try:
                return json.loads(backup_path.read_text())
            except Exception:
                pass
        return {}

    def _save_json_backup(self, name: str, data: dict) -> None:
        """Save a dict to JSON backup."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        backup_path = self._data_dir / f"{name}.json"
        try:
            backup_path.write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.error("Failed to save backup %s: %s", name, exc)

    def _load_scalar(self, name: str, default: float = 0.0) -> float:
        """Load a scalar value from JSON backup."""
        data = self._load_json_backup("scalars")
        return float(data.get(name, default))

    def _save_scalar(self, name: str, value: float) -> None:
        """Save a scalar value to JSON backup."""
        data = self._load_json_backup("scalars")
        data[name] = value
        self._save_json_backup("scalars", data)

    def restore_from_backup(self) -> int:
        """Restore Redis state from JSON backup files.

        Returns:
            Number of positions restored.
        """
        if not self._available:
            logger.warning("Cannot restore — Redis not available")
            return 0

        positions = self._load_json_backup("positions")
        restored = 0
        for ticker, thesis in positions.items():
            try:
                self._redis.hset(_key("positions"), ticker, json.dumps(thesis))
                restored += 1
            except Exception as exc:
                logger.error("Failed to restore %s: %s", ticker, exc)

        if restored:
            logger.info("Restored %d positions from JSON backup", restored)
        return restored

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            try:
                self._redis.close()
            except Exception:
                pass
            self._redis = None
            self._available = False
