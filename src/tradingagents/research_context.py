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

# Project root — this file lives at tradingagents/research_context.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Maximum character length to inject (keeps prompts within token budget).
# All models in use (gpt-4o, gpt-4o-mini) have 128K context windows.
# 8,000 chars ≈ 2,000 tokens — negligible vs the 100K+ typical prompt size.
# At 4,000 chars the copper/steel/geopolitical themes were being truncated.
MAX_CONTEXT_CHARS = 8000

# Section header keywords to extract — covers both manual research format
# (e.g. "TOP MACRO THEMES RIGHT NOW") and auto-generated format
# (e.g. "TOP 3 MACRO THEMES", "WATCHLIST DECISIONS")
_PRIORITY_SECTIONS = [
    # Sentiment / VIX — appears in both formats as inline ### line
    "SENTIMENT",
    "VIX",
    # Macro themes
    "MACRO THEME",        # matches "TOP 3 MACRO THEMES" and "TOP MACRO THEMES RIGHT NOW"
    "KEY MACRO",          # matches "KEY MACRO SHIFTS"
    # Ticker decisions — the most important section for agents
    "WATCHLIST DECISION", # matches "WATCHLIST DECISIONS" (auto-generated)
    "FULL TICKER",        # matches "FULL TICKER DECISION TABLE" (manual)
    "WATCHLIST CHANGE",   # matches "WATCHLIST CHANGES" (manual)
    # New picks
    "NEW PICK",           # matches "TOP 3 NEW PICKS"
    # Sectors
    "SECTOR",             # matches "SECTORS TO AVOID TODAY" and "SECTORS TO AVOID"
]


def load_latest_research_context(results_dir: str = "") -> str:
    """
    Find the most recent RESEARCH_FINDINGS_*.md file and return a condensed
    macro context string for injection into agent system prompts.

    Returns an empty string if no findings file exists.
    """
    # Default to absolute project results dir so it works from any CWD
    search_dir = Path(results_dir) if results_dir else (_PROJECT_ROOT / "results")
    findings_files = sorted(
        search_dir.glob("RESEARCH_FINDINGS_*.md"),
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
                snippet = section.strip()[:2000]
                results.append(snippet)
                break

    # If still nothing found, fall back to first 2000 chars of the whole file
    # (better than returning nothing and leaving agents context-blind)
    if not results and text.strip():
        results.append(text.strip()[:2000])

    return results


# ============================================================================
# TICKET-060: Ticker-specific research signal extraction
# ============================================================================

def parse_research_signals(findings_text: str) -> dict:
    """Extract ticker-specific BUY/SELL/HOLD signals from research findings.

    Parses the WATCHLIST DECISIONS table to get per-ticker recommendations.

    Returns:
        dict: {ticker: {"decision": "BUY|SELL|HOLD", "conviction": "High|Medium|Low", "reason": "..."}}
    """
    signals = {}

    # Match pattern: | TICKER | Tier | Decision | Conviction | Reason |
    # Example: | NVDA   | C    | HOLD     | Medium     | Market sentiment is bearish on tech. |
    pattern = r'\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(BUY|SELL|HOLD|REDUCE)\s*\|\s*(\w+)\s*\|\s*([^|]+)\|'
    matches = re.findall(pattern, findings_text, re.IGNORECASE)

    for ticker, tier, decision, conviction, reason in matches:
        ticker = ticker.upper()
        signals[ticker] = {
            "decision": decision.upper(),
            "conviction": conviction.upper(),
            "reason": reason.strip(),
            "tier": tier.upper()
        }

    return signals


def get_ticker_research_signal(ticker: str, findings_file: str = "") -> dict:
    """Get research signal for a specific ticker.

    Args:
        ticker: Stock symbol
        findings_file: Path to findings file (auto-detected if empty)

    Returns:
        dict with decision, conviction, reason or empty dict if not found
    """
    if not findings_file:
        search_dir = _PROJECT_ROOT / "results"
        findings_files = sorted(
            search_dir.glob("RESEARCH_FINDINGS_*.md"),
            reverse=True,
        )
        if not findings_files:
            return {}
        findings_file = findings_files[0]

    try:
        text = Path(findings_file).read_text(encoding="utf-8")
        signals = parse_research_signals(text)
        return signals.get(ticker.upper(), {})
    except Exception:
        return {}


def build_research_signal_prompt(ticker: str) -> str:
    """Build a prompt injection for high-conviction research signals.

    Only injects signals with High conviction to avoid noise.

    Returns:
        str: Formatted prompt section or empty string
    """
    signal = get_ticker_research_signal(ticker)
    if not signal:
        return ""

    decision = signal.get("decision", "HOLD")
    conviction = signal.get("conviction", "Medium")
    reason = signal.get("reason", "")

    # Only inject high-conviction signals (BUY or SELL with High conviction)
    if conviction in ["HIGH", "VERY HIGH"] and decision in ["BUY", "SELL"]:
        return f"""
[RESEARCH SIGNAL]
Daily macro research indicates {decision} signal for {ticker} with {conviction} conviction.
Reason: {reason}
Consider this signal in your analysis. If you disagree, provide explicit counter-arguments.
[/RESEARCH SIGNAL]
"""
    return ""


# ============================================================================
# TICKET-065: Sector rotation awareness
# ============================================================================

TICKER_SECTORS = {
    # Technology
    "NVDA": "TECHNOLOGY", "AVGO": "TECHNOLOGY", "AMD": "TECHNOLOGY",
    "ARM": "TECHNOLOGY", "TSM": "TECHNOLOGY", "MU": "TECHNOLOGY",
    "LITE": "TECHNOLOGY", "MSFT": "TECHNOLOGY", "GOOGL": "TECHNOLOGY",
    "META": "TECHNOLOGY", "PLTR": "TECHNOLOGY", "GLW": "TECHNOLOGY",
    "MDB": "TECHNOLOGY", "NOW": "TECHNOLOGY", "PANW": "TECHNOLOGY",
    "CRWD": "TECHNOLOGY", "VG": "TECHNOLOGY", "UBER": "TECHNOLOGY",
    # Defense
    "RTX": "DEFENSE", "LMT": "DEFENSE", "NOC": "DEFENSE",
    # Energy
    "LNG": "ENERGY", "XOM": "ENERGY", "APA": "ENERGY",
    # Materials
    "FCX": "MATERIALS", "MP": "MATERIALS", "CMC": "MATERIALS",
    "NUE": "MATERIALS", "SCCO": "MATERIALS", "SOC": "MATERIALS",
    # Hedge
    "GLD": "HEDGE",
}


def parse_sector_signals(findings_text: str) -> dict:
    """Extract sector-level BUY/SELL/HOLD/AVOID signals from research findings.

    Returns:
        dict: {sector: "FAVOR"|"AVOID"|"NEUTRAL"}
    """
    sector_signals = {}

    # Pattern: "SECTORS TO AVOID TODAY: Technology"
    avoid_pattern = r'SECTORS TO AVOID.*?:(.+?)(?:\n|$)'
    avoid_match = re.search(avoid_pattern, findings_text, re.IGNORECASE | re.DOTALL)
    if avoid_match:
        sectors_text = avoid_match.group(1)
        # Split by comma or "and"
        for sector in re.split(r',|\band\b', sectors_text):
            sector_clean = sector.strip().upper()
            if sector_clean:
                sector_signals[sector_clean] = "AVOID"

    # Look for favorable sector mentions in macro themes
    sector_keywords = {
        "DEFENSE": ["defense", "military", "aerospace", "RTX", "LMT", "NOC", "geopolitical"],
        "TECHNOLOGY": ["tech", "AI", "software", "semiconductor"],
        "ENERGY": ["oil", "energy", "LNG", "XOM"],
        "MATERIALS": ["commodities", "mining", "copper", "steel", "fertilizer"],
    }

    text_lower = findings_text.lower()

    for sector, keywords in sector_keywords.items():
        if sector in sector_signals:
            continue  # Already marked as AVOID

        # Look for positive context
        for keyword in keywords:
            pos_patterns = [
                rf'{keyword}.*?\b(benefit|outperform|rally|buy|favor)\b',
                rf'\b(bullish|positive)\b.*?{keyword}',
            ]
            for pattern in pos_patterns:
                if re.search(pattern, text_lower):
                    sector_signals[sector] = "FAVOR"
                    break

    return sector_signals


def get_sector_bias(ticker: str, findings_file: str = "") -> float:
    """Get bias multiplier for a ticker based on sector sentiment (-0.5 to +0.5).

    Returns:
        float: Bias multiplier (positive = favor, negative = avoid)
    """
    sector = TICKER_SECTORS.get(ticker.upper(), "OTHER")

    if not findings_file:
        search_dir = _PROJECT_ROOT / "results"
        findings_files = sorted(
            search_dir.glob("RESEARCH_FINDINGS_*.md"),
            reverse=True,
        )
        if not findings_files:
            return 0.0
        findings_file = findings_files[0]

    try:
        text = Path(findings_file).read_text(encoding="utf-8")
        signals = parse_sector_signals(text)
    except Exception:
        return 0.0

    signal = signals.get(sector, "NEUTRAL")

    bias_map = {
        "FAVOR": 0.25,    # Slightly increase position size
        "AVOID": -0.25,   # Slightly decrease position size or avoid
        "NEUTRAL": 0.0
    }

    return bias_map.get(signal, 0.0)


def build_sector_context(ticker: str) -> str:
    """Build sector context for agent prompts.

    Returns:
        str: Formatted sector context or empty string
    """
    sector = TICKER_SECTORS.get(ticker.upper(), "OTHER")
    bias = get_sector_bias(ticker)

    if bias == 0:
        return ""

    signal = "FAVORED" if bias > 0 else "AVOIDED"
    return f"""
[SECTOR CONTEXT]
{sector} sector is currently {signal} in macro research.
Position size will be adjusted by {bias:+.0%} based on sector sentiment.
[/SECTOR CONTEXT]
"""
