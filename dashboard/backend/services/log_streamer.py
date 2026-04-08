"""
WebSocket log streamer.

Tails stdout.log and broadcasts parsed events to connected clients.
"""

from __future__ import annotations

import asyncio
import re
from collections import deque
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from ..config import STDOUT_LOG_FILE

# Connected WebSocket clients
_clients: Set[WebSocket] = set()
RECENT_LOG_LIMIT = 20
TODAY_LOG_LIMIT = 5000  # Show up to 5000 lines from today's logs


def setup_websocket(app: FastAPI):
    """Register the WebSocket endpoint on the app."""

    @app.websocket("/ws/live")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        _clients.add(websocket)

        # Check for filter preferences from query params
        hide_wait = websocket.query_params.get("hide_wait") == "true"

        try:
            # Start tailing the log file
            await _tail_log(websocket, hide_wait=hide_wait)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            _clients.discard(websocket)


def _get_manual_run_logs() -> list[Path]:
    """Find any active manual run log files."""
    if not STDOUT_LOG_FILE.parent.exists():
        return []
    manual_logs = list(STDOUT_LOG_FILE.parent.glob("manual_run_*.log"))
    # Sort by modification time, newest first
    manual_logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return manual_logs[:3]  # Max 3 most recent manual runs


def _is_wait_message(msg: dict) -> bool:
    """Check if a message is a WAIT countdown message."""
    text = msg.get("text", "")
    return msg.get("type") == "wait" or "[WAIT]" in text or "Next cycle at" in text


def _read_today_log_messages(hide_wait: bool = False) -> list[dict]:
    """Read today's log messages - more comprehensive for initial load."""
    messages = []

    # Read from main stdout.log
    if STDOUT_LOG_FILE.exists():
        with open(STDOUT_LOG_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        for line in lines:
            msg = _parse_log_line(line)
            if not hide_wait or not _is_wait_message(msg):
                messages.append(msg)

    # Also read from manual run logs
    manual_logs = _get_manual_run_logs()
    for log_file in manual_logs:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        for line in lines:
            msg = _parse_log_line(line)
            if not hide_wait or not _is_wait_message(msg):
                messages.append(msg)

    return messages


async def _tail_log(websocket: WebSocket, hide_wait: bool = False):
    """Tail the stdout log and any manual run logs, send parsed messages."""
    # Send all of today's logs first so user sees complete history
    all_messages = _read_today_log_messages(hide_wait=hide_wait)

    # Limit to prevent overwhelming the client, but show much more
    display_limit = min(len(all_messages), 2000)
    if display_limit < len(all_messages):
        all_messages = all_messages[-display_limit:]

    for msg in all_messages:
        await websocket.send_json(msg)

    if not all_messages:
        await websocket.send_json({"type": "log", "text": "Waiting for log file..."})
        while not STDOUT_LOG_FILE.exists() and not _get_manual_run_logs():
            await asyncio.sleep(2)
            try:
                await websocket.receive_text()
            except Exception:
                return

    # Then continue tailing all log sources.
    last_sizes: dict[Path, int] = {}

    # Initialize positions
    manual_logs = _get_manual_run_logs()
    for log_file in [STDOUT_LOG_FILE] + manual_logs:
        if log_file.exists():
            last_sizes[log_file] = log_file.stat().st_size

    while True:
        try:
            # Refresh manual logs list (new ones may have been created)
            current_manual = _get_manual_run_logs()
            all_logs = [STDOUT_LOG_FILE] + current_manual

            for log_file in all_logs:
                if not log_file.exists():
                    continue

                if log_file not in last_sizes:
                    last_sizes[log_file] = log_file.stat().st_size
                    continue

                current_size = log_file.stat().st_size
                last_size = last_sizes[log_file]

                if current_size > last_size:
                    with open(log_file, "r", encoding="utf-8") as f:
                        f.seek(last_size)
                        new_lines = f.read()
                        last_sizes[log_file] = f.tell()

                    for line in new_lines.strip().split("\n"):
                        if not line.strip():
                            continue
                        msg = _parse_log_line(line.strip())
                        # Filter out WAIT messages if requested
                        if hide_wait and _is_wait_message(msg):
                            continue
                        await websocket.send_json(msg)

                elif current_size < last_size:
                    # File was truncated/rotated
                    last_sizes[log_file] = 0

            # Clean up old entries from last_sizes
            for old_file in list(last_sizes.keys()):
                if old_file not in all_logs and not old_file.exists():
                    del last_sizes[old_file]

            await asyncio.sleep(1)
        except WebSocketDisconnect:
            return
        except Exception:
            await asyncio.sleep(2)


def _read_recent_log_messages(limit: int) -> list[dict]:
    """Read and parse the most recent non-empty log lines."""
    return _read_recent_log_messages_from_file(STDOUT_LOG_FILE, limit)


def _read_recent_log_messages_from_file(log_file: Path, limit: int) -> list[dict]:
    """Read and parse the most recent non-empty log lines from a specific file."""
    if not log_file.exists():
        return []

    with open(log_file, "r", encoding="utf-8") as f:
        recent_lines = [line.strip() for line in deque(f, maxlen=limit) if line.strip()]

    return [_parse_log_line(line) for line in recent_lines]


def _parse_log_line(line: str) -> dict:
    """Parse a log line into a typed message."""

    # Ticker analysis start
    m = re.match(r"\[TRADINGAGENTS\] Analysing (\w+) for (\S+)", line)
    if m:
        return {"type": "ticker_progress", "ticker": m.group(1), "date": m.group(2), "status": "analysing"}

    # Trade execution
    m = re.match(r"\[ALPACA\] (BUY|SELL) ([\d.]+) shares of (\w+)", line)
    if m:
        return {"type": "trade", "action": m.group(1), "qty": float(m.group(2)), "ticker": m.group(3)}

    # Decision
    m = re.match(r"\[TRADINGAGENTS\] Decision .* (BUY|SELL|HOLD)", line)
    if m:
        return {"type": "decision", "decision": m.group(1)}

    # Stop loss
    if "[STOP-LOSS]" in line:
        return {"type": "stop_loss", "text": line}

    # Override enforcement
    if "[OVERRIDE-ENFORCE]" in line:
        return {"type": "override", "text": line}

    # Quota enforcement
    if "[QUOTA-FORCE]" in line:
        return {"type": "quota", "text": line}

    # Bypass
    if "BYPASS:" in line:
        return {"type": "bypass", "text": line}

    # Cycle markers
    if "End of cycle" in line:
        return {"type": "cycle_end", "text": line}

    # Wait lines (low priority, only send latest)
    if "[WAIT]" in line:
        return {"type": "wait", "text": line}

    # Default
    return {"type": "log", "text": line}
