# TICKET-024 — Fix Analysis Date (Use Today's Data After Close)

**Priority:** HIGH
**Effort:** 30 min
**Status:** TODO

## Problem

`get_analysis_date()` always returns `today - 1 day`. This means:

- Running at 4:15 PM ET on **Tuesday** → analyses **Monday's** data
- Running at 4:15 PM ET on **Friday** → analyses **Thursday's** data
- Friday's completed session is never analysed on the same day

The agents are always one trading day behind. On a day like March 24th when LITE
surged +10%, the agents analyse March 23rd (a down day) and miss the signal entirely.

## Correct Behaviour

After 4:15 PM ET (market close + 15 min), **today's completed session** is available.
The analysis date should be **today**, not yesterday.

Special cases:
- Saturday/Sunday → use Friday (no session on weekends)
- Monday before 4:15 PM → use Friday (Monday not yet closed)
- Any day before 4:15 PM → use previous trading day (market still open)

## Acceptance Criteria

- [ ] `get_analysis_date()` returns today's date when called after 4:15 PM ET
      on a weekday
- [ ] Returns previous Friday when called on Saturday, Sunday, or Monday before open
- [ ] Returns previous trading day when called before 4:15 PM on any weekday
      (market not yet closed — use yesterday's complete data)
- [ ] `--date` CLI override still works to force a specific analysis date
- [ ] Log line shows: `analysing: 2026-03-24 (today's session)` vs
      `analysing: 2026-03-23 (previous session)`
- [ ] Unit tests: assert correct date for each day/time combination
- [ ] All tests still pass

## Implementation

```python
ET = ZoneInfo("America/New_York")
AFTER_CLOSE_HOUR = 16   # 4 PM ET
AFTER_CLOSE_MIN  = 15   # 4:15 PM ET

def get_analysis_date() -> str:
    now_et = datetime.now(ET)
    today  = now_et.date()
    after_close = now_et.hour > AFTER_CLOSE_HOUR or (
        now_et.hour == AFTER_CLOSE_HOUR and now_et.minute >= AFTER_CLOSE_MIN
    )
    weekday = today.weekday()  # 0=Mon, 5=Sat, 6=Sun

    if weekday == 5:   # Saturday → Friday
        return str(today - timedelta(days=1))
    if weekday == 6:   # Sunday → Friday
        return str(today - timedelta(days=2))
    if weekday == 0 and not after_close:  # Monday before close → Friday
        return str(today - timedelta(days=3))
    if not after_close:  # Before close → yesterday
        return str(today - timedelta(days=1))
    return str(today)  # After close → today
```
