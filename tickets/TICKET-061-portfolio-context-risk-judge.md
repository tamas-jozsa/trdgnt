# TICKET-061 — Add Portfolio Context to Risk Judge

**Priority:** MEDIUM  
**Effort:** 1.5 hours  
**Status:** TODO  
**Files:**
- `tradingagents/agents/managers/risk_manager.py`
- `tradingagents/graph/trading_graph.py`
- `alpaca_bridge.py`

## Problem

Risk Judge makes decisions in isolation without considering:
- Current cash deployment level (94.8% cash is excessive)
- Sector concentration
- Recent performance of similar positions
- Overall portfolio risk exposure

This leads to overly conservative decisions when capital should be deployed.

## Acceptance Criteria

- [ ] Pass portfolio summary to Risk Judge (cash ratio, position count, sector breakdown)
- [ ] Add "deployment bias" when cash > 80%
- [ ] Add sector concentration warning when >30% in one sector
- [ ] Log portfolio context in decision reports
- [ ] Update Risk Judge prompt with portfolio-aware rules

## Implementation

### 1. Update `alpaca_bridge.py` to provide portfolio summary:

```python
def get_portfolio_summary() -> dict:
    """Get summary of current portfolio for context."""
    positions = get_positions()  # Existing function
    account = get_account()      # Existing function
    
    equity = float(account["equity"])
    cash = float(account["cash"])
    
    # Sector mapping (simplified - could be enhanced)
    SECTOR_MAP = {
        "NVDA": "Technology", "AVGO": "Technology", "AMD": "Technology",
        "ARM": "Technology", "TSM": "Technology", "MU": "Technology",
        "LITE": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
        "META": "Technology", "PLTR": "Technology", "GLW": "Technology",
        "MDB": "Technology", "NOW": "Technology", "PANW": "Technology",
        "CRWD": "Technology", "VG": "Technology", "UBER": "Technology",
        "RTX": "Defense", "LMT": "Defense", "NOC": "Defense",
        "LNG": "Energy", "XOM": "Energy", "APA": "Energy",
        "FCX": "Materials", "MP": "Materials", "CMC": "Materials",
        "NUE": "Materials", "SCCO": "Materials", "SOC": "Materials",
        "GLD": "Hedge"
    }
    
    sector_exposure = {}
    for pos in positions:
        sector = SECTOR_MAP.get(pos["ticker"], "Other")
        sector_exposure[sector] = sector_exposure.get(sector, 0) + float(pos["market_value"])
    
    # Calculate sector percentages
    sector_pct = {s: v/equity*100 for s, v in sector_exposure.items()} if equity > 0 else {}
    
    return {
        "equity": equity,
        "cash": cash,
        "cash_ratio": cash / equity if equity > 0 else 1.0,
        "position_count": len(positions),
        "sector_exposure": sector_pct,
        "max_sector": max(sector_pct, key=sector_pct.get) if sector_pct else None,
        "max_sector_pct": max(sector_pct.values()) if sector_pct else 0
    }
```

### 2. Update `tradingagents/graph/trading_graph.py`:

```python
def build_portfolio_context() -> str:
    """Build portfolio context string for Risk Judge."""
    from alpaca_bridge import get_portfolio_summary
    
    summary = get_portfolio_summary()
    
    context = f"""
[PORTFOLIO CONTEXT]
- Total Equity: ${summary['equity']:,.2f}
- Cash: ${summary['cash']:,.2f} ({summary['cash_ratio']:.1%})
- Open Positions: {summary['position_count']}
- Largest Sector: {summary['max_sector']} ({summary['max_sector_pct']:.1f}%)
"""
    
    # Add deployment bias trigger
    if summary['cash_ratio'] > 0.80:
        context += "\n⚠️ CAPITAL DEPLOYMENT ALERT: Portfolio is >80% cash. Bias toward executing high-conviction opportunities.\n"
    
    # Add sector concentration warning
    if summary['max_sector_pct'] > 30:
        context += f"\n⚠️ SECTOR CONCENTRATION: {summary['max_sector']} exposure is >30%. Consider diversification.\n"
    
    context += "[/PORTFOLIO CONTEXT]"
    
    return context

# In run_agent() for risk_manager
portfolio_context = build_portfolio_context()
messages.append(SystemMessage(content=portfolio_context))
```

### 3. Update Risk Judge prompt:

```python
RISK_JUDGE_PROMPT = """
You are the Risk Judge. Make the final trading decision considering risk/reward.

{portfolio_context}  # <-- Injected here

DECISION RULES:
1. CAPITAL DEPLOYMENT: When cash > 80%, require stronger reasons to HOLD on high-conviction setups
2. SECTOR CONCENTRATION: If adding position would push sector >40%, reduce position size
3. OPPORTUNITY COST: When cash is high, consider the cost of missing moves vs. risk of entry

OUTPUT FORMAT:
FINAL DECISION: BUY|SELL|HOLD
CONVICTION: 1-10
STOP-LOSS: $X.XX
TARGET: $X.XX
POSITION SIZE: 0.25x-2.0x
REASONING: Explain decision, referencing portfolio context if relevant
"""
```

### 4. Update decision report to include portfolio context:

```python
def save_decision_report(ticker: str, state: dict, decision: dict):
    """Save report with portfolio context."""
    report = f"""# {ticker} — {date}

## Portfolio Context (at decision time)
{state.get('portfolio_context', 'N/A')}

## Decision: {decision['action']}
...
"""
    # ... existing save logic ...
```

## Testing

- [ ] Unit test: Portfolio summary calculates cash ratio correctly
- [ ] Unit test: Cash > 80% triggers deployment alert in context
- [ ] Unit test: Sector > 30% triggers concentration warning
- [ ] Integration test: Portfolio context appears in decision report
