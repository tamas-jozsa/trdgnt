"""
WebSocket log streamer.

Tails stdout.log and broadcasts parsed events to connected clients.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from ..config import STDOUT_LOG_FILE

# Connected WebSocket clients
_clients: Set[WebSocket] = set()


def setup_websocket(app: FastAPI):
    """Register the WebSocket endpoint on the app."""

    @app.websocket("/ws/live")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        _clients.add(websocket)
        try:
            # Start tailing the log file
            await _tail_log(websocket)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            _clients.discard(websocket)


async def _tail_log(websocket: WebSocket):
    """Tail the stdout log and send parsed messages."""
    if not STDOUT_LOG_FILE.exists():
        await websocket.send_json({"type": "log", "text": "Waiting for log file..."})
        # Wait for file to appear
        while not STDOUT_LOG_FILE.exists():
            await asyncio.sleep(2)
            try:
                await websocket.receive_text()  # Check if still connected
            except Exception:
                return

    # Seek to end of file
    with open(STDOUT_LOG_FILE, "r") as f:
        f.seek(0, 2)  # Seek to end
        last_size = f.tell()

    while True:
        try:
            current_size = STDOUT_LOG_FILE.stat().st_size
            if current_size > last_size:
                with open(STDOUT_LOG_FILE, "r") as f:
                    f.seek(last_size)
                    new_lines = f.read()
                    last_size = f.tell()

                for line in new_lines.strip().split("\n"):
                    if not line.strip():
                        continue
                    msg = _parse_log_line(line.strip())
                    await websocket.send_json(msg)

            elif current_size < last_size:
                # File was truncated/rotated
                last_size = 0

            await asyncio.sleep(1)
        except WebSocketDisconnect:
            return
        except Exception:
            await asyncio.sleep(2)


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
