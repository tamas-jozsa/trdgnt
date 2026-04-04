# TICKET-064 — Add Conviction Mismatch Dashboard

**Priority:** LOW  
**Effort:** 2 hours  
**Status:** DONE  
**Files:**
- `watch_agent.sh`
- `trading_loop_logs/` (read existing reports)

## Problem

No visibility into when Risk Judge overrides upstream signals. Mismatches like:
- Research Manager: BUY (8)
- Risk Judge: HOLD (6)

Are buried in individual report files. Need dashboard visibility.

## Acceptance Criteria

- [ ] Parse recent reports for conviction mismatches
- [ ] Add "Override Alerts" section to `watch_agent.sh`
- [ ] Show: Ticker | Research | Risk Judge | Override Type
- [ ] Highlight when high-conviction signals are overridden
- [ ] Update every refresh cycle

## Implementation

### 1. Create conviction analyzer script `analyze_conviction.py`:

```python
#!/usr/bin/env python3
"""Analyze conviction mismatches from recent reports."""

import re
import json
from pathlib import Path
from datetime import datetime

def parse_report_for_convictions(report_path: str) -> dict:
    """Extract conviction scores from a report file."""
    with open(report_path) as f:
        content = f.read()
    
    ticker = Path(report_path).parent.name
    
    # Extract Research Manager conviction
    rm_match = re.search(r'CONVICTION:\s*(\d+)', content)
    rm_conviction = int(rm_match.group(1)) if rm_match else None
    
    # Extract Research Manager recommendation
    rm_rec_match = re.search(r'RECOMMENDATION:\s*(BUY|SELL|HOLD)', content, re.IGNORECASE)
    rm_recommendation = rm_rec_match.group(1).upper() if rm_rec_match else None
    
    # Extract Risk Judge conviction
    rj_match = re.search(r'Risk Judge.*?CONVICTION:\s*(\d+)', content, re.DOTALL)
    rj_conviction = int(rj_match.group(1)) if rj_match else None
    
    # Extract Risk Judge final decision
    rj_dec_match = re.search(r'FINAL DECISION:\s*\*\*(BUY|SELL|HOLD)\*\*', content, re.IGNORECASE)
    rj_decision = rj_dec_match.group(1).upper() if rj_dec_match else None
    
    return {
        "ticker": ticker,
        "research_manager": {
            "recommendation": rm_recommendation,
            "conviction": rm_conviction
        },
        "risk_judge": {
            "decision": rj_decision,
            "conviction": rj_conviction
        },
        "mismatch": rm_recommendation != rj_decision if rm_recommendation and rj_decision else False,
        "high_conviction_override": (
            rm_conviction >= 8 and 
            rm_recommendation != rj_decision and
            rj_decision == "HOLD"
        )
    }

def get_recent_mismatches(days: int = 1) -> list:
    """Get conviction mismatches from recent reports."""
    reports_dir = Path("trading_loop_logs/reports")
    mismatches = []
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    for ticker_dir in reports_dir.iterdir():
        if not ticker_dir.is_dir():
            continue
        
        report_file = ticker_dir / f"{date_str}.md"
        if report_file.exists():
            data = parse_report_for_convictions(str(report_file))
            if data["mismatch"]:
                mismatches.append(data)
    
    # Sort: high conviction overrides first
    mismatches.sort(key=lambda x: (not x["high_conviction_override"], x["ticker"]))
    
    return mismatches

def format_mismatch_table(mismatches: list) -> str:
    """Format mismatches for dashboard display."""
    if not mismatches:
        return "  No conviction mismatches today ✓"
    
    lines = ["  Ticker    Research    →    Risk Judge    Type"]
    lines.append("  " + "-" * 50)
    
    for m in mismatches:
        rm = m["research_manager"]
        rj = m["risk_judge"]
        
        type_indicator = "🚨 HIGH" if m["high_conviction_override"] else "⚠️"
        
        line = f"  {m['ticker']:<8} {rm['recommendation']:>4}({rm['conviction']}) → {rj['decision']:>4}({rj['conviction']})  {type_indicator}"
        lines.append(line)
    
    return "\n".join(lines)

if __name__ == "__main__":
    mismatches = get_recent_mismatches()
    print(format_mismatch_table(mismatches))
```

### 2. Update `watch_agent.sh`:

Add to the dashboard output:

```bash
#!/bin/bash

# ... existing code ...

show_dashboard() {
    clear
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           TrdAgnt Dashboard — $(date '+%Y-%m-%d %H:%M:%S')            ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    
    # ... existing sections ...
    
    # NEW: Conviction Mismatch Alerts
    echo ""
    echo "┌─ Conviction Override Alerts ─────────────────────────────────┐"
    python3 analyze_conviction.py 2>/dev/null || echo "  (analyzer not available)"
    echo "└──────────────────────────────────────────────────────────────┘"
    
    # ... rest of dashboard ...
}

# ... rest of script ...
```

### 3. Make analyzer executable and add to requirements:

```bash
chmod +x analyze_conviction.py
```

## Testing

- [ ] Run analyzer → shows today's mismatches correctly
- [ ] Dashboard displays override alerts section
- [ ] High-conviction overrides are highlighted
- [ ] No errors when no reports exist
