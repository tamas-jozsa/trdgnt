# TICKET-065 — Implement Sector Rotation Awareness

**Priority:** MEDIUM  
**Effort:** 3 hours  
**Status:** TODO  
**Files:**
- `tradingagents/graph/trading_graph.py`
- `tradingagents/agents/managers/risk_manager.py`
- `daily_research.py`

## Problem

System holds tech positions despite research saying "bearish on tech", misses defense opportunities despite "BUY defense" signals. No sector-level risk management.

## Acceptance Criteria

- [ ] Parse sector recommendations from daily research
- [ ] Add sector bias multipliers (+size for favored, -size for avoided)
- [ ] Add sector exposure limits (>40% triggers warning)
- [ ] Research Manager considers sector macro themes
- [ ] Log sector-based sizing adjustments

## Implementation

### 1. Update `daily_research.py` to parse sector signals:

```python
def parse_sector_signals(findings_text: str) -> dict:
    """Extract sector-level BUY/SELL/HOLD/AVOID signals."""
    import re
    
    sector_signals = {}
    
    # Pattern: "SECTORS TO AVOID TODAY: Technology"
    avoid_pattern = r'SECTORS TO AVOID.*?:\s*([^\n]+)'
    avoid_match = re.search(avoid_pattern, findings_text, re.IGNORECASE)
    if avoid_match:
        sectors = [s.strip() for s in avoid_match.group(1).split(',')]
        for sector in sectors:
            sector_signals[sector.upper()] = "AVOID"
    
    # Pattern: "TOP 3 MACRO THEMES" → extract sector implications
    # e.g., "defense stocks like RTX, LMT, NOC may benefit" → DEFENSE = FAVOR
    
    # Pattern matching for sector mentions with sentiment
    sector_keywords = {
        "DEFENSE": ["defense", "military", "aerospace", "RTX", "LMT", "NOC"],
        "TECHNOLOGY": ["tech", "AI", "software", "NVDA", "MSFT", "GOOGL"],
        "ENERGY": ["oil", "energy", "LNG", "XOM"],
        "MATERIALS": ["commodities", "mining", "FCX", "MP"]
    }
    
    for sector, keywords in sector_keywords.items():
        for keyword in keywords:
            # Look for positive/negative context
            pos_pattern = rf'{keyword}.*?\b(benefit|outperform|rally|buy)\b'
            neg_pattern = rf'{keyword}.*?\b(avoid|underperform|decline|sell|bearish)\b'
            
            if re.search(pos_pattern, findings_text, re.IGNORECASE):
                sector_signals[sector] = "FAVOR"
            elif re.search(neg_pattern, findings_text, re.IGNORECASE):
                sector_signals[sector] = "AVOID"
    
    return sector_signals

def get_sector_bias(sector: str, findings_file: str = None) -> float:
    """Get bias multiplier for a sector (-0.5 to +0.5)."""
    if findings_file is None:
        findings_file = get_today_findings_file()
    
    if not Path(findings_file).exists():
        return 0.0
    
    with open(findings_file) as f:
        findings = f.read()
    
    signals = parse_sector_signals(findings)
    sector_upper = sector.upper()
    
    bias_map = {
        "FAVOR": 0.5,    # Increase position size
        "AVOID": -0.5,   # Decrease position size
        "NEUTRAL": 0.0
    }
    
    return bias_map.get(signals.get(sector_upper, "NEUTRAL"), 0.0)
```

### 2. Update `tradingagents/graph/trading_graph.py`:

```python
# Sector mapping
TICKER_SECTORS = {
    "NVDA": "TECHNOLOGY", "AVGO": "TECHNOLOGY", "AMD": "TECHNOLOGY",
    "ARM": "TECHNOLOGY", "TSM": "TECHNOLOGY", "MSFT": "TECHNOLOGY",
    "GOOGL": "TECHNOLOGY", "META": "TECHNOLOGY", "PLTR": "TECHNOLOGY",
    "RTX": "DEFENSE", "LMT": "DEFENSE", "NOC": "DEFENSE",
    "LNG": "ENERGY", "XOM": "ENERGY", "APA": "ENERGY",
    "FCX": "MATERIALS", "MP": "MATERIALS", "CMC": "MATERIALS",
    "NUE": "MATERIALS", "SCCO": "MATERIALS", "GLD": "HEDGE"
}

def get_sector_context(ticker: str) -> str:
    """Build sector context for agent prompts."""
    sector = TICKER_SECTORS.get(ticker.upper(), "OTHER")
    bias = get_sector_bias(sector)
    
    if bias == 0:
        return ""
    
    signal = "FAVORED" if bias > 0 else "AVOIDED"
    return f"""
[SECTOR CONTEXT]
{sector} sector is currently {signal} in macro research.
Position size will be adjusted by {bias:+.1f}× based on sector sentiment.
[/SECTOR CONTEXT]
"""

# In run_agent() for research_manager and risk_manager
sector_context = get_sector_context(state["ticker"])
if sector_context:
    messages.append(SystemMessage(content=sector_context))
```

### 3. Update Risk Manager to apply sector bias:

```python
def apply_sector_bias(base_size: float, ticker: str) -> float:
    """Apply sector bias to position size."""
    sector = TICKER_SECTORS.get(ticker.upper(), "OTHER")
    bias = get_sector_bias(sector)
    
    adjusted = base_size + bias
    
    # Log adjustment
    if bias != 0:
        logging.info(f"SECTOR_BIAS: {ticker} ({sector}) size {base_size:.2f}× → {adjusted:.2f}× (bias: {bias:+.1f})")
    
    return max(0.25, min(2.0, adjusted))  # Clamp to limits

# In parse_agent_decision:
base_size = parsed.get("size_multiplier", 1.0)
parsed["size_multiplier"] = apply_sector_bias(base_size, ticker)
```

### 4. Update Risk Judge prompt with sector awareness:

```python
RISK_JUDGE_PROMPT = """
You are the Risk Judge. Make the final trading decision.

{sector_context}  # <-- Injected

SECTOR RULES:
- If sector is AVOIDED: Require higher conviction to BUY, consider SELLing existing positions
- If sector is FAVORED: Bias toward deploying capital on setups in this sector
- Never exceed 40% portfolio exposure to any single sector

POSITION SIZE ADJUSTMENT:
- FAVORED sector: Can increase size up to +0.5× above normal
- AVOIDED sector: Should decrease size by -0.5× or avoid entirely
"""
```

## Testing

- [ ] Unit test: Parse sector signals from research findings
- [ ] Unit test: Tech sector AVOID → position size reduced
- [ ] Unit test: Defense sector FAVOR → position size increased
- [ ] Integration test: Sector context appears in agent prompts
