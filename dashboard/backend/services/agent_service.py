"""
Agent reasoning data service.

Reads per-ticker reports, signal overrides, and agent memory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import REPORTS_DIR, SIGNAL_OVERRIDES_FILE, MEMORY_DIR


def _load_json(path: Path) -> dict | list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def list_reports(ticker: str | None = None, date: str | None = None, limit: int = 50) -> list[dict]:
    """List available reports, sorted by date descending."""
    reports = []

    if ticker:
        ticker_dirs = [REPORTS_DIR / ticker.upper()]
    else:
        ticker_dirs = sorted(REPORTS_DIR.iterdir()) if REPORTS_DIR.exists() else []

    for ticker_dir in ticker_dirs:
        if not ticker_dir.is_dir():
            continue
        tk = ticker_dir.name
        for report_file in sorted(ticker_dir.glob("*.md"), reverse=True):
            report_date = report_file.stem
            if date and report_date != date:
                continue

            # Quick-parse decision from first few lines
            decision = ""
            conviction = 0
            try:
                text = report_file.read_text(encoding="utf-8")[:500]
                m = re.search(r"Decision:\s*(BUY|SELL|HOLD)", text, re.IGNORECASE)
                if m:
                    decision = m.group(1).upper()
                m = re.search(r"CONVICTION:\s*(\d+)", text)
                if m:
                    conviction = int(m.group(1))
            except Exception:
                pass

            reports.append({
                "ticker": tk,
                "date": report_date,
                "decision": decision,
                "conviction": conviction,
            })

    # Sort by date descending
    reports.sort(key=lambda r: r["date"], reverse=True)
    return reports[:limit]


def get_report(ticker: str, date: str) -> dict:
    """Get a full agent report, parsed into sections."""
    report_file = REPORTS_DIR / ticker.upper() / f"{date}.md"
    if not report_file.exists():
        return {"ticker": ticker, "date": date, "report_markdown": "", "sections": {}}

    text = report_file.read_text(encoding="utf-8")

    # Parse decision
    decision = ""
    conviction = 0
    m = re.search(r"Decision:\s*(BUY|SELL|HOLD)", text, re.IGNORECASE)
    if m:
        decision = m.group(1).upper()
    m = re.search(r"CONVICTION:\s*(\d+)", text)
    if m:
        conviction = int(m.group(1))

    # Split into sections by ## headings
    sections = {}
    section_map = {
        "research manager": "research_manager",
        "trader": "trader",
        "risk judge": "risk_judge",
        "bull": "bull_case",
        "bear": "bear_case",
        "market analyst": "market_analyst",
        "market analysis": "market_analyst",
        "social": "social_analyst",
        "news": "news_analyst",
        "fundamental": "fundamentals_analyst",
    }

    parts = re.split(r"\n(?=## )", text)
    for part in parts:
        first_line = part.strip().split("\n")[0].lower()
        for keyword, key in section_map.items():
            if keyword in first_line:
                sections[key] = part.strip()
                break

    # Check if this ticker had a bypass or override today
    bypass = None
    override = None
    overrides_data = _load_json(SIGNAL_OVERRIDES_FILE)
    for o in overrides_data.get("overrides", []):
        if o.get("ticker", "").upper() == ticker.upper():
            ts = o.get("timestamp", "")
            if ts.startswith(date):
                override = o
                break

    return {
        "ticker": ticker,
        "date": date,
        "decision": decision,
        "conviction": conviction,
        "report_markdown": text,
        "sections": sections,
        "bypass": bypass,
        "override": override,
    }


def get_overrides(days: int = 7, severity: str | None = None) -> dict:
    """Get signal override history."""
    data = _load_json(SIGNAL_OVERRIDES_FILE)
    if not isinstance(data, dict):
        return {"total": 0, "by_severity": {}, "overrides": []}

    overrides = data.get("overrides", [])

    if severity:
        overrides = [o for o in overrides if o.get("severity") == severity]

    # Sort by timestamp descending
    overrides.sort(key=lambda o: o.get("timestamp", ""), reverse=True)

    by_severity = {}
    for o in data.get("overrides", []):
        s = o.get("severity", "unknown")
        by_severity[s] = by_severity.get(s, 0) + 1

    return {
        "total": data.get("summary", {}).get("total", len(overrides)),
        "by_severity": by_severity,
        "overrides": overrides,
    }


def get_memory(ticker: str, agent: str | None = None, limit: int = 10) -> dict:
    """Get agent memory entries for a ticker."""
    memory_dir = MEMORY_DIR / ticker.upper()
    if not memory_dir.exists():
        return {"ticker": ticker, "agents": {}}

    agent_names = ["bull_memory", "bear_memory", "trader_memory",
                   "invest_judge_memory", "risk_manager_memory"]

    if agent:
        agent_names = [a for a in agent_names if agent in a]

    agents = {}
    for name in agent_names:
        mem_file = memory_dir / f"{name}.json"
        if not mem_file.exists():
            continue
        try:
            entries = json.loads(mem_file.read_text(encoding="utf-8"))
            if isinstance(entries, list):
                agents[name] = {
                    "count": len(entries),
                    "latest": entries[-limit:],
                }
        except Exception:
            continue

    return {"ticker": ticker, "agents": agents}
