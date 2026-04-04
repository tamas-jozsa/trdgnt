# TICKET-060 — Connect Research Signals to Agent Prompts

**Priority:** HIGH  
**Effort:** 2 hours  
**Status:** DONE  
**Files:**
- `tradingagents/research_context.py`
- `tradingagents/graph/trading_graph.py`
- `daily_research.py`

## Problem

Research findings identify high-conviction opportunities but agents don't act on them. Example (Mar 31):
- Research flagged RTX, LMT, NOC as **"BUY - High conviction"** due to geopolitical tensions
- Trading decisions: All three got **HOLD**

Gap between research macro themes and agent execution.

## Acceptance Criteria

- [ ] Parse ticker-specific signals from research findings
- [ ] Inject strong signals into Research Manager and Risk Judge prompts
- [ ] Boost conviction weight when research aligns with agent analysis
- [ ] Log when research signal influences decision
- [ ] Handle ADD/REMOVE watchlist changes separately from trading signals

## Implementation

### 1. Update `tradingagents/research_context.py`:

```python
def parse_research_signals(findings_text: str) -> dict:
    """Extract ticker-specific BUY/SELL/HOLD signals from research findings."""
    signals = {}
    
    # Parse WATCHLIST DECISIONS table
    import re
    
    # Match pattern: | TICKER | Tier | Decision | Conviction | Reason |
    pattern = r'\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(BUY|SELL|HOLD|REDUCE)\s*\|\s*(\w+)\s*\|\s*([^|]+)\|'
    matches = re.findall(pattern, findings_text, re.IGNORECASE)
    
    for ticker, tier, decision, conviction, reason in matches:
        signals[ticker.upper()] = {
            "decision": decision.upper(),
            "conviction": conviction.upper(),
            "reason": reason.strip(),
            "tier": tier.upper()
        }
    
    return signals

def get_ticker_research_context(ticker: str, findings_file: str = None) -> dict:
    """Get research context for a specific ticker."""
    if findings_file is None:
        findings_file = get_today_findings_file()
    
    if not Path(findings_file).exists():
        return {}
    
    with open(findings_file) as f:
        findings = f.read()
    
    signals = parse_research_signals(findings)
    return signals.get(ticker.upper(), {})
```

### 2. Update `tradingagents/graph/trading_graph.py`:

```python
def build_research_injection(ticker: str) -> str:
    """Build research signal injection for agent prompts."""
    from tradingagents.research_context import get_ticker_research_context
    
    context = get_ticker_research_context(ticker)
    if not context:
        return ""
    
    decision = context.get("decision", "HOLD")
    conviction = context.get("conviction", "Medium")
    reason = context.get("reason", "")
    
    # Only inject for high-conviction signals
    if conviction in ["High", "Very High"] and decision in ["BUY", "SELL"]:
        return f"""
[RESEARCH SIGNAL]
Daily macro research indicates {decision} signal for {ticker} with {conviction} conviction.
Reason: {reason}
Consider this signal in your analysis. If you disagree, provide explicit counter-arguments.
[/RESEARCH SIGNAL]
"""
    return ""

# In run_agent() for research_manager
research_injection = build_research_injection(state["ticker"])
if research_injection:
    messages.append(SystemMessage(content=research_injection))
    logging.info(f"RESEARCH_INJECT: {state['ticker']} - {research_injection[:100]}...")
```

### 3. Update Research Manager prompt:

```python
RESEARCH_MANAGER_PROMPT = """
You are the Research Manager. Synthesize analyst reports into an investment plan.

{research_injection}  # <-- Added

OVERRIDE RULE: If research signal is provided and conflicts with your analysis,
you must explicitly state why you're disagreeing with the research signal.

Output format:
RECOMMENDATION: BUY|SELL|HOLD
CONVICTION: 1-10
...
"""
```

### 4. Update Risk Judge prompt with research context:

```python
RISK_JUDGE_PROMPT = """
You are the Risk Judge. Make the final trading decision.

Portfolio Context:
- Cash ratio: {cash_ratio:.1%}
- Research signal: {research_signal}  # <-- Added

HIGH CONVICTION ALIGNMENT: If Research Manager conviction ≥ 8 AND 
Research signal agrees (both BUY or both SELL), bias toward executing 
rather than holding unless strong risk debater consensus against.
"""
```

### 5. Add logging in `daily_research.py`:

```python
def save_research_findings(findings: str, date: str = None):
    """Save findings and log signal summary."""
    # ... existing save logic ...
    
    # Log signal summary
    signals = parse_research_signals(findings)
    buy_signals = [t for t, s in signals.items() if s["decision"] == "BUY"]
    sell_signals = [t for t, s in signals.items() if s["decision"] == "SELL"]
    
    logging.info(f"RESEARCH_SIGNALS: BUY={buy_signals}, SELL={sell_signals}")
```

## Testing

- [ ] Unit test: Parse research findings → extract correct signals
- [ ] Unit test: High conviction BUY signal → injected into prompt
- [ ] Integration test: Research BUY + Agent BUY → Trade executed
- [ ] Integration test: Research BUY + Agent SELL → Explicit override reason logged
