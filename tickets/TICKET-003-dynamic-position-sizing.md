# TICKET-003 — Dynamic Position Sizing by Conviction Tier

**Priority:** HIGH  
**Effort:** 2h  
**Status:** DONE  
**Files:** `trading_loop.py`, `alpaca_bridge.py`

## Problem

Every ticker in the watchlist receives the same flat `$1000` allocation regardless of
conviction level, sector, or risk tier. A HIGH-conviction CORE pick and a SPECULATIVE
meme/biotech play get identical capital allocation. This is poor risk management.

## Acceptance Criteria

- [ ] Watchlist tickers have a `tier` attribute: `CORE`, `TACTICAL`, `SPECULATIVE`, `HEDGE`
- [ ] `amount` per trade is multiplied by a tier factor:
  - `CORE` → 2.0x base amount (`$2000` at default `$1000`)
  - `TACTICAL` → 1.0x (`$1000`)
  - `SPECULATIVE` → 0.4x (`$400`)
  - `HEDGE` → 0.5x (`$500`)
- [ ] Tier is inferred from the WATCHLIST dict structure (CORE_HOLDS, TACTICAL_PLAYS, etc.)
- [ ] CLI `--amount` sets the base; tiers scale from it
- [ ] Dashboard shows tier-adjusted amounts in the watchlist panel
- [ ] Unit test: assert correct amounts per tier

## Implementation

Change `WATCHLIST` in `trading_loop.py` to a structured format:
```python
WATCHLIST = {
    "NVDA": {"sector": "AI & Semiconductors", "tier": "CORE"},
    "RCAT": {"sector": "Defense / Drone Warfare", "tier": "SPECULATIVE"},
    ...
}
TIER_MULTIPLIER = {"CORE": 2.0, "TACTICAL": 1.0, "SPECULATIVE": 0.4, "HEDGE": 0.5}
```

Update all references to `WATCHLIST[ticker]` to handle the new dict format.
