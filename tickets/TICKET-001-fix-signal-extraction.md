# TICKET-001 — Fix Signal Extraction (Critical Bug)

**Priority:** CRITICAL  
**Effort:** 30 min  
**Status:** DONE  
**File:** `tradingagents/graph/signal_processing.py`

## Problem

`SignalProcessor.process_signal()` sends the final trade decision prose to an LLM and asks it
to return `"BUY"`, `"SELL"`, or `"HOLD"`. It then returns the raw `.content` string with zero
validation. If the LLM responds with `"I recommend BUY"`, `"buy"`, `"STRONG BUY"`, or any
variation, `execute_decision()` in `alpaca_bridge.py` raises `ValueError: Unknown decision`
and the entire ticker cycle crashes silently.

## Acceptance Criteria

- [ ] Output is `.strip().upper()` before use
- [ ] Regex fallback: `re.search(r'\b(BUY|SELL|HOLD)\b', text, re.IGNORECASE)` extracts the
      signal if present anywhere in the response
- [ ] If no valid signal found after regex: log a warning and default to `"HOLD"`
- [ ] Unit test covering: exact match, lowercase, embedded in sentence, no match → HOLD

## Implementation

Edit `tradingagents/graph/signal_processing.py`:

```python
import re, logging

def process_signal(self, text: str) -> str:
    cleaned = text.strip().upper()
    for signal in ("BUY", "SELL", "HOLD"):
        if cleaned == signal:
            return signal
    match = re.search(r'\b(BUY|SELL|HOLD)\b', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    logging.warning(f"SignalProcessor: could not extract signal from: {text!r}. Defaulting to HOLD.")
    return "HOLD"
```

Add `tests/test_signal_processing.py` with unit tests.
