# TICKET-074 — Clean Legacy Watchlist Data

**Priority:** LOW  
**Effort:** 1 hour  
**Status:** TODO  
**Files:**
- `trading_loop_logs/watchlist_overrides.json`

## Problem

Some watchlist override entries have `added_on: "1970-01-01"` (Unix epoch default). This is legacy data that needs cleanup.

## Solution

Add validation and cleanup to watchlist loading.

## Acceptance Criteria

- [ ] Detect entries with epoch dates
- [ ] Update to current date or reasonable default
- [ ] Log cleanup actions
- [ ] Add validation to prevent future bad data

## Implementation

```python
def clean_watchlist_overrides(overrides: dict) -> dict:
    """Clean legacy watchlist override data."""
    epoch_date = "1970-01-01"
    today = datetime.now().strftime("%Y-%m-%d")
    
    cleaned = {}
    for ticker, info in overrides.items():
        if info.get("added_on") == epoch_date:
            print(f"[CLEANUP] Fixing epoch date for {ticker}")
            info["added_on"] = today
        cleaned[ticker] = info
    
    return cleaned
```

## Testing

- [ ] Unit test: Epoch date detected and updated
- [ ] Unit test: Valid dates unchanged
