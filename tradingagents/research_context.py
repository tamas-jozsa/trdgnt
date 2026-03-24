"""
research_context.py
===================
Loads the most recent MARKET_RESEARCH_PROMPT findings file and extracts
a condensed macro context string for injection into agent prompts.

The findings file is produced by running the MARKET_RESEARCH_PROMPT.md
session each day and is stored as results/RESEARCH_FINDINGS_YYYY-MM-DD.md.
"""

from __future__ import annotations

import re
from pathlib import Path


# Maximum character length to inject (keeps prompts within token budget)
MAX_CONTEXT_CHARS = 3000

# Section headers to extract (in order of priority)
_PRIORITY_SECTIONS = [
    "TOP MACRO THEMES RIGHT NOW",
    "OVERALL MARKET SENTIMENT",
    "VIX",
    "FULL TICKER DECISION TABLE",
    "WATCHLIST CHANGES",
    "SECTORS TO AVOID",
    "KEY MACRO SHIFTS",
]


def load_latest_research_context(results_dir: str = "results") -> str:
    """
    Find the most recent RESEARCH_FINDINGS_*.md file and return a condensed
    macro context string for injection into agent system prompts.

    Returns an empty string if no findings file exists.
    """
    findings_files = sorted(
        Path(results_dir).glob("RESEARCH_FINDINGS_*.md"),
        reverse=True,
    )
    if not findings_files:
        return ""

    latest = findings_files[0]
    text   = latest.read_text(encoding="utf-8")
    date   = latest.stem.replace("RESEARCH_FINDINGS_", "")

    extracted = _extract_sections(text)
    if not extracted:
        return ""

    header = f"=== DAILY MARKET RESEARCH CONTEXT (from {date}) ===\n"
    body   = "\n\n".join(extracted)
    full   = header + body

    # Truncate to stay within token budget
    if len(full) > MAX_CONTEXT_CHARS:
        full = full[:MAX_CONTEXT_CHARS] + "\n[... truncated for brevity ...]"

    return full


def _extract_sections(text: str) -> list[str]:
    """Extract relevant sections from the findings markdown.

    Handles both ## and ### heading levels so manually-written and
    auto-generated findings files are both supported.
    """
    results = []

    # Split on ## or ### headings (both levels)
    sections = re.split(r"\n(?=#{2,3}\s)", text)

    for section in sections:
        first_line = section.strip().split("\n")[0].upper()
        for keyword in _PRIORITY_SECTIONS:
            if keyword in first_line:
                snippet = section.strip()[:600]
                results.append(snippet)
                break

    # If still nothing found, fall back to first 2000 chars of the whole file
    # (better than returning nothing and leaving agents context-blind)
    if not results and text.strip():
        results.append(text.strip()[:2000])

    return results
