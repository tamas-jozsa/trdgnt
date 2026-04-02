"""
TICKET-073: Sector Exposure Monitoring

Monitors portfolio sector exposure and warns on concentration risk.
"""

from typing import Dict
from alpaca_bridge import get_portfolio_summary
from research_context import TICKER_SECTORS


def get_sector_exposure() -> Dict[str, float]:
    """Calculate current portfolio exposure by sector.

    Returns:
        Dict mapping sector name to percentage (0.0-1.0)
    """
    try:
        portfolio = get_portfolio_summary()
        positions = portfolio.get("positions", [])
        total_value = sum(p.get("market_value", 0) for p in positions)

        if total_value == 0:
            return {}

        exposure = {}
        for pos in positions:
            ticker = pos.get("ticker", "")
            sector = TICKER_SECTORS.get(ticker, "OTHER")
            value = pos.get("market_value", 0)
            exposure[sector] = exposure.get(sector, 0) + value

        # Convert to percentages
        return {sector: value / total_value for sector, value in exposure.items()}
    except Exception:
        return {}


def check_sector_limits(max_pct: float = 0.40) -> list[str]:
    """Check if any sector exceeds limit.

    Args:
        max_pct: Maximum allowed percentage (default 40%)

    Returns:
        List of warning messages
    """
    exposure = get_sector_exposure()
    warnings = []

    for sector, pct in sorted(exposure.items(), key=lambda x: x[1], reverse=True):
        if pct > max_pct:
            warnings.append(f"⚠️  {sector}: {pct:.1%} (exceeds {max_pct:.0%} limit)")
        else:
            warnings.append(f"   {sector}: {pct:.1%}")

    return warnings


def format_sector_report() -> str:
    """Format sector exposure for display."""
    exposure = get_sector_exposure()

    if not exposure:
        return "  No positions — sector exposure N/A"

    lines = ["  SECTOR EXPOSURE"]
    lines.append("  " + "-" * 40)

    for sector, pct in sorted(exposure.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(pct * 20)  # 20 chars = 100%
        warning = " ⚠️" if pct > 0.40 else ""
        lines.append(f"  {sector:<15} {pct:>5.1%} {bar}{warning}")

    lines.append("  " + "-" * 40)
    return "\n".join(lines)
