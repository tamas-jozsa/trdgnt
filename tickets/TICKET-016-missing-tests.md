# TICKET-016 — Missing Test Coverage

**Priority:** MEDIUM
**Effort:** 1h
**Status:** DONE
**Files:** `tests/`

## Problem

Several acceptance criteria from earlier tickets lack tests:

1. **TICKET-003**: No test for `tier_amount()` correctness per tier
2. **TICKET-004**: `TradingAgentsGraph.load_memories()` not tested at graph level
3. **TICKET-011**: No test asserting `reflect_and_remember()` is called post-trade
4. **`test_position_context.py:17`**: Dead conditional in mock patch — always takes
   the `else` branch; the `if hasattr` check is never True

## Acceptance Criteria

- [ ] `test_tier_amount()`: assert CORE=2x, TACTICAL=1x, SPECULATIVE=0.4x, HEDGE=0.5x
- [ ] `test_load_memories_from_dir()`: write JSON files to tmp_path, call
      `ta.load_memories(tmp_path)`, assert all 5 agent memory doc counts > 0
- [ ] `test_reflect_called_after_trade()`: mock `ta.reflect_and_remember`, run
      `analyse_and_trade()` with a simulated prior position, assert mock was called
- [ ] Fix dead conditional in `test_position_context.py` — simplify to direct patch
- [ ] All 4 new tests pass
