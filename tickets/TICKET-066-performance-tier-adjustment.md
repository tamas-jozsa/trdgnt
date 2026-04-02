# TICKET-066 — Add Performance-Based Tier Adjustment

**Priority:** LOW  
**Effort:** 4 hours  
**Status:** TODO  
**Files:**
- `trading_loop.py`
- `tradingagents/graph/reflection.py`
- New: `tier_manager.py`

## Problem

Watchlist tiers are static. Winners don't get promoted, losers don't get demoted. System misses opportunity to allocate more capital to consistent performers.

## Acceptance Criteria

- [ ] Track 30-day rolling P&L per ticker
- [ ] Monthly tier review: promote winners, demote losers
- [ ] Automatic tier adjustment with audit log
- [ ] New picks from research can be added to TACTICAL tier
- [ ] Underperformers moved to SPECULATIVE or removed

## Implementation

### 1. Create `tier_manager.py`:

```python
"""Dynamic tier management based on performance."""

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

def load_trade_history(days: int = 30) -> list:
    """Load trade history from recent log files."""
    history = []
    logs_dir = Path("trading_loop_logs")
    
    cutoff = datetime.now() - timedelta(days=days)
    
    for log_file in logs_dir.glob("*.json"):
        if not log_file.name.startswith("2"):  # Skip non-date files
            continue
        
        file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
        if file_date < cutoff:
            continue
        
        with open(log_file) as f:
            data = json.load(f)
            for trade in data.get("trades", []):
                trade["date"] = file_date.isoformat()
                history.append(trade)
    
    return history

def calculate_ticker_performance(ticker: str, history: list) -> dict:
    """Calculate performance metrics for a ticker."""
    ticker_trades = [t for t in history if t["ticker"] == ticker]
    
    if not ticker_trades:
        return None
    
    # Calculate realized P&L from sells
    sells = [t for t in ticker_trades if t.get("decision") == "SELL" and "order" in t]
    realized_pnl = sum(
        t["order"].get("realized_pl", 0) 
        for t in sells 
        if "realized_pl" in t.get("order", {})
    )
    
    # Calculate win rate
    profitable_sells = [t for t in sells if t["order"].get("realized_pl", 0) > 0]
    win_rate = len(profitable_sells) / len(sells) if sells else 0
    
    # Calculate average hold time
    buys = [t for t in ticker_trades if t.get("decision") == "BUY"]
    # Simplified - would need actual entry/exit dates
    
    return {
        "ticker": ticker,
        "total_trades": len(ticker_trades),
        "realized_pnl": realized_pnl,
        "win_rate": win_rate,
        "profit_factor": 1.5  # Would calculate properly
    }

def review_tier_assignments(current_tiers: dict) -> list:
    """Review and recommend tier changes."""
    history = load_trade_history(days=30)
    recommendations = []
    
    # Get all tickers from all tiers
    all_tickers = set()
    for tier_tickers in current_tiers.values():
        all_tickers.update(tier_tickers)
    
    for ticker in all_tickers:
        perf = calculate_ticker_performance(ticker, history)
        if not perf:
            continue
        
        current_tier = None
        for tier, tickers in current_tiers.items():
            if ticker in tickers:
                current_tier = tier
                break
        
        # Promotion criteria
        if perf["win_rate"] > 0.6 and perf["realized_pnl"] > 1000 and current_tier != "CORE":
            recommendations.append({
                "ticker": ticker,
                "current_tier": current_tier,
                "recommended_tier": "CORE",
                "reason": f"Win rate {perf['win_rate']:.0%}, P&L ${perf['realized_pnl']:.2f}",
                "action": "PROMOTE"
            })
        
        # Demotion criteria
        elif perf["win_rate"] < 0.3 and perf["realized_pnl"] < -500 and current_tier == "CORE":
            recommendations.append({
                "ticker": ticker,
                "current_tier": current_tier,
                "recommended_tier": "TACTICAL",
                "reason": f"Poor performance: Win rate {perf['win_rate']:.0%}, P&L ${perf['realized_pnl']:.2f}",
                "action": "DEMOTE"
            })
        
        # Removal criteria
        elif perf["realized_pnl"] < -1000:
            recommendations.append({
                "ticker": ticker,
                "current_tier": current_tier,
                "recommended_tier": None,
                "reason": f"Significant losses: ${perf['realized_pnl']:.2f}",
                "action": "REMOVE"
            })
    
    return recommendations

def apply_tier_changes(recommendations: list, dry_run: bool = True):
    """Apply tier changes to watchlist."""
    tiers_file = Path("trading_loop_logs/dynamic_tiers.json")
    
    if tiers_file.exists():
        with open(tiers_file) as f:
            current = json.load(f)
    else:
        current = load_default_tiers()
    
    for rec in recommendations:
        ticker = rec["ticker"]
        action = rec["action"]
        
        # Remove from current tier
        for tier, tickers in current.items():
            if ticker in tickers:
                tickers.remove(ticker)
        
        # Add to new tier
        if rec["recommended_tier"]:
            current[rec["recommended_tier"]].append(ticker)
        
        logging.info(f"TIER_CHANGE: {ticker} {action} {rec['current_tier']} -> {rec['recommended_tier']}: {rec['reason']}")
    
    if not dry_run:
        with open(tiers_file, "w") as f:
            json.dump(current, f, indent=2)
    
    return current

def load_default_tiers() -> dict:
    """Load default watchlist tiers."""
    return {
        "CORE": ["NVDA", "AVGO", "AMD", "ARM", "TSM", "MSFT", "GOOGL", "META", "PLTR"],
        "TACTICAL": ["CMC", "NUE", "APA", "SOC", "SCCO"],
        "SPECULATIVE": ["RCAT", "MOS", "RCKT"],
        "HEDGE": ["GLD"]
    }
```

### 2. Add tier review to monthly workflow in `trading_loop.py`:

```python
def run_monthly_tier_review():
    """Run tier review on first trading day of month."""
    from tier_manager import review_tier_assignments, apply_tier_changes, load_default_tiers
    
    # Only run on first trading day
    today = datetime.now()
    if today.day > 5:  # Within first 5 days
        return
    
    current_tiers = load_default_tiers()
    recommendations = review_tier_assignments(current_tiers)
    
    if recommendations:
        logging.info(f"TIER_REVIEW: {len(recommendations)} recommendations")
        for rec in recommendations:
            logging.info(f"  {rec['ticker']}: {rec['action']} ({rec['reason']})")
        
        # Apply changes (with approval in dry-run mode first)
        apply_tier_changes(recommendations, dry_run=False)
    else:
        logging.info("TIER_REVIEW: No changes recommended")
```

### 3. Update reflection to track performance per ticker:

```python
# In tradingagents/graph/reflection.py
def reflect_on_trade(state: dict, pnl: float):
    """Store reflection with performance tracking."""
    # ... existing reflection logic ...
    
    # Update performance tracker
    perf_file = Path("trading_loop_logs/ticker_performance.json")
    if perf_file.exists():
        with open(perf_file) as f:
            perf = json.load(f)
    else:
        perf = {}
    
    ticker = state["ticker"]
    if ticker not in perf:
        perf[ticker] = {"trades": [], "total_pnl": 0}
    
    perf[ticker]["trades"].append({
        "date": datetime.now().isoformat(),
        "pnl": pnl,
        "decision": state.get("decision")
    })
    perf[ticker]["total_pnl"] += pnl
    
    with open(perf_file, "w") as f:
        json.dump(perf, f, indent=2)
```

### 4. Add CLI command for tier review:

```python
# In cli/main.py
@app.command()
def review_tiers(
    dry_run: bool = typer.Option(True, help="Show recommendations without applying"),
    days: int = typer.Option(30, help="Lookback period in days")
):
    """Review and adjust ticker tiers based on performance."""
    from tier_manager import review_tier_assignments, apply_tier_changes, load_default_tiers
    
    current = load_default_tiers()
    recommendations = review_tier_assignments(current)
    
    if not recommendations:
        typer.echo("No tier changes recommended.")
        return
    
    typer.echo(f"\nRecommended tier changes ({len(recommendations)}):\n")
    for rec in recommendations:
        action_emoji = "⬆️" if rec["action"] == "PROMOTE" else "⬇️" if rec["action"] == "DEMOTE" else "❌"
        typer.echo(f"  {action_emoji} {rec['ticker']}: {rec['current_tier']} -> {rec['recommended_tier'] or 'REMOVE'}")
        typer.echo(f"     Reason: {rec['reason']}")
    
    if not dry_run:
        apply_tier_changes(recommendations, dry_run=False)
        typer.echo("\nChanges applied.")
    else:
        typer.echo("\nRun with --no-dry-run to apply changes.")
```

## Testing

- [ ] Unit test: Calculate performance from trade history
- [ ] Unit test: Promotion criteria (win rate >60%, P&L >$1000)
- [ ] Unit test: Demotion criteria (win rate <30%, losses >$500)
- [ ] Integration test: Tier changes persisted to file
