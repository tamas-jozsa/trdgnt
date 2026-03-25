"""
market_data_tools.py
====================
Additional market data tools using yfinance:

- get_options_flow(ticker)     — put/call ratio, unusual activity (TICKET-031)
- get_earnings_calendar(ticker) — next earnings date + estimates (TICKET-032)
- get_analyst_targets(ticker)  — Wall Street consensus price targets (TICKET-033)

All functions return formatted strings for LLM consumption.
All fall back gracefully to empty string on any error.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TICKET-031: Options Flow
# ---------------------------------------------------------------------------

def get_options_flow(ticker: str) -> str:
    """
    Fetch options chain data for the nearest expiry and compute put/call
    volume ratio, OI ratio, and flag unusual activity.

    Args:
        ticker: Stock ticker symbol (e.g. "NVDA")

    Returns:
        Formatted options flow summary, or empty string if unavailable.
    """
    try:
        import yfinance as yf
        import pandas as pd

        t = yf.Ticker(ticker)
        expiries = t.options
        if not expiries:
            return ""

        # Use nearest expiry
        nearest = expiries[0]
        chain = t.option_chain(nearest)
        calls = chain.calls
        puts  = chain.puts

        if calls.empty or puts.empty:
            return ""

        # Volume ratios (use 0 for NaN)
        call_vol = calls["volume"].fillna(0).sum()
        put_vol  = puts["volume"].fillna(0).sum()
        call_oi  = calls["openInterest"].fillna(0).sum()
        put_oi   = puts["openInterest"].fillna(0).sum()

        if call_vol == 0:
            return ""

        pc_vol_ratio = round(put_vol / call_vol, 2) if call_vol > 0 else None
        pc_oi_ratio  = round(put_oi  / call_oi,  2) if call_oi  > 0 else None

        # Unusual activity: top call and put by volume vs avg
        avg_call_vol = calls["volume"].fillna(0).mean()
        avg_put_vol  = puts["volume"].fillna(0).mean()

        unusual = []
        for _, row in calls.nlargest(3, "volume").iterrows():
            v = row.get("volume", 0) or 0
            if avg_call_vol > 0 and v > avg_call_vol * 3:
                ratio = round(v / avg_call_vol, 1)
                unusual.append(
                    f"  CALL ${row['strike']:.0f} strike — {v:,.0f} contracts "
                    f"({ratio}x avg) ⚡"
                )

        for _, row in puts.nlargest(3, "volume").iterrows():
            v = row.get("volume", 0) or 0
            if avg_put_vol > 0 and v > avg_put_vol * 3:
                ratio = round(v / avg_put_vol, 1)
                unusual.append(
                    f"  PUT  ${row['strike']:.0f} strike — {v:,.0f} contracts "
                    f"({ratio}x avg) ⚠️"
                )

        # IV from ATM options (closest strike to last price)
        last_price = t.fast_info.last_price or 0
        if last_price > 0:
            calls["dist"] = abs(calls["strike"] - last_price)
            atm_iv = calls.nsmallest(1, "dist")["impliedVolatility"].values
            iv_str = f"{atm_iv[0]*100:.1f}%" if len(atm_iv) > 0 and atm_iv[0] > 0 else "N/A"
        else:
            iv_str = "N/A"

        sentiment = (
            "BULLISH (more calls than puts)"  if pc_vol_ratio is not None and pc_vol_ratio < 0.7 else
            "BEARISH (more puts than calls)"  if pc_vol_ratio is not None and pc_vol_ratio > 1.3 else
            "NEUTRAL"
        )

        lines = [
            f"## Options Flow for {ticker} (nearest expiry: {nearest})",
            f"- Put/Call Volume Ratio: {pc_vol_ratio} — {sentiment}",
            f"- Put/Call OI Ratio:     {pc_oi_ratio}",
            f"- ATM Implied Volatility: {iv_str}",
            f"  (elevated IV = market expects a big move)",
        ]
        if unusual:
            lines.append("- Unusual activity:")
            lines.extend(unusual)
        else:
            lines.append("- No unusual options activity detected")

        return "\n".join(lines)

    except Exception as e:
        logger.debug("Options flow failed for %s: %s", ticker, e)
        return ""


# ---------------------------------------------------------------------------
# TICKET-032: Earnings Calendar
# ---------------------------------------------------------------------------

def get_earnings_calendar(ticker: str) -> str:
    """
    Fetch the next earnings date, EPS/revenue estimates, and last quarter
    earnings surprise for a ticker.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Formatted earnings calendar string, or empty string if unavailable.
    """
    try:
        import yfinance as yf

        t = yf.Ticker(ticker)
        cal = t.calendar  # dict or None

        lines = [f"## Earnings Calendar for {ticker}"]

        # Next earnings date
        earnings_date = None
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed is not None:
                if hasattr(ed, "__iter__") and not isinstance(ed, str):
                    ed_list = list(ed)
                    earnings_date = ed_list[0] if ed_list else None
                else:
                    earnings_date = ed

        if earnings_date is not None:
            try:
                if hasattr(earnings_date, "date"):
                    ed_date = earnings_date.date()
                else:
                    ed_date = date.fromisoformat(str(earnings_date)[:10])
                days_away = (ed_date - date.today()).days
                flag = " ⚠️ BINARY RISK EVENT" if 0 <= days_away <= 7 else ""
                lines.append(
                    f"- Next earnings: {ed_date} (in {days_away} days){flag}"
                )
            except Exception:
                lines.append(f"- Next earnings: {earnings_date}")
        else:
            lines.append("- Next earnings: Not available")

        # EPS + Revenue estimates
        if isinstance(cal, dict):
            eps_est = cal.get("EPS Estimate")
            rev_est = cal.get("Revenue Estimate")
            if eps_est is not None:
                lines.append(f"- EPS estimate:     ${eps_est:.2f}")
            if rev_est is not None:
                rev_b = rev_est / 1e9 if rev_est > 1e8 else rev_est / 1e6
                unit = "B" if rev_est > 1e8 else "M"
                lines.append(f"- Revenue estimate: ${rev_b:.2f}{unit}")

        # Last earnings surprise
        try:
            hist = t.earnings_history
            if hist is not None and not hist.empty:
                last = hist.iloc[-1]
                surprise_pct = last.get("surprisePercent", None)
                if surprise_pct is not None:
                    direction = "beat" if surprise_pct >= 0 else "missed"
                    lines.append(
                        f"- Last quarter: {direction} by "
                        f"{abs(surprise_pct)*100:.1f}% "
                        f"({'+'if surprise_pct>=0 else ''}{surprise_pct*100:.1f}%)"
                    )
        except Exception:
            pass

        return "\n".join(lines)

    except Exception as e:
        logger.debug("Earnings calendar failed for %s: %s", ticker, e)
        return ""


# ---------------------------------------------------------------------------
# TICKET-033: Analyst Price Targets
# ---------------------------------------------------------------------------

def get_analyst_targets(ticker: str) -> str:
    """
    Fetch Wall Street analyst consensus price targets and recommendation.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Formatted analyst consensus string, or empty string if unavailable.
    """
    try:
        import yfinance as yf

        t = yf.Ticker(ticker)
        info = t.info

        target_mean  = info.get("targetMeanPrice")
        target_high  = info.get("targetHighPrice")
        target_low   = info.get("targetLowPrice")
        rec_mean     = info.get("recommendationMean")   # 1=StrongBuy, 5=StrongSell
        rec_key      = info.get("recommendationKey", "").upper().replace("_", " ")
        n_analysts   = info.get("numberOfAnalystOpinions", 0)
        last_price   = info.get("currentPrice") or info.get("regularMarketPrice")

        if not target_mean or not last_price:
            return ""

        upside_mean = round((target_mean - last_price) / last_price * 100, 1)
        upside_high = round((target_high - last_price) / last_price * 100, 1) if target_high else None
        upside_low  = round((target_low  - last_price) / last_price * 100, 1) if target_low  else None

        rec_label = rec_key if rec_key else "N/A"
        if rec_mean:
            rec_label += f" (score: {rec_mean:.1f}/5)"

        lines = [
            f"## Analyst Consensus for {ticker} ({n_analysts} analysts)",
            f"- Recommendation: {rec_label}",
            f"- Current price:  ${last_price:.2f}",
            f"- Price targets:  Low ${target_low:.2f} / Mean ${target_mean:.2f} / High ${target_high:.2f}"
            if target_low and target_high else
            f"- Mean price target: ${target_mean:.2f}",
            f"- Upside to mean target:  {upside_mean:+.1f}%",
        ]
        if upside_high is not None:
            lines.append(f"- Upside to high target:  {upside_high:+.1f}%")
        if upside_low is not None:
            lines.append(f"- Downside to low target: {upside_low:+.1f}%")

        # Flag if stock is well above analyst targets (warning sign)
        if upside_mean < -10:
            lines.append("⚠️ Stock is trading ABOVE analyst mean target — may be overvalued vs consensus")
        elif upside_mean > 30:
            lines.append("✅ Significant upside to analyst consensus target")

        return "\n".join(lines)

    except Exception as e:
        logger.debug("Analyst targets failed for %s: %s", ticker, e)
        return ""
