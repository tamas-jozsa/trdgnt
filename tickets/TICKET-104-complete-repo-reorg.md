# TICKET-104 — Complete Repository Reorganization

**Priority:** CRITICAL  
**Effort:** 1-2 days  
**Status:** TODO  
**Related:** TICKET-090, TICKET-091, TICKET-092, TICKET-093, TICKET-095, TICKET-096

## Summary

This is the master ticket for completing the repository reorganization. The codebase currently has "two or three versions of reality" at once: old flat-root assumptions, new `apps/` assumptions, and partially introduced `data/`/Mage assumptions. This is the top engineering priority before adding more features.

## Current State Problems

1. **Split-brain data paths**: Apps write to `apps/`, dashboard reads from root
2. **Syntax errors**: `daily_research.py` won't import
3. **Broken dashboard**: Control actions target deleted files
4. **Broken tests**: Still import from old layout
5. **Duplicate code**: `scripts/` vs `apps/`
6. **Stale docs**: Still reference old structure

## Execution Order

### Phase 1: Fix Critical Issues (Do First)
1. TICKET-091 — Fix syntax error in daily_research.py
2. TICKET-090 — Fix split-brain runtime state

### Phase 2: Fix High Priority Issues
3. TICKET-093 — Fix packaging and tests
4. TICKET-092 — Fix dashboard control actions
5. TICKET-094 — Fix graph logger crashes

### Phase 3: Cleanup
6. TICKET-095 — Remove duplicate scripts
7. TICKET-096 — Update documentation
8. TICKET-097 — Fix or replace Mage

### Phase 4: Add Safety
9. TICKET-103 — Add smoke tests

## Success Criteria

- [ ] Single source of truth for all paths
- [ ] Apps and dashboard read/write same locations
- [ ] All tests pass
- [ ] Dashboard fully functional
- [ ] Documentation accurate
- [ ] No duplicate code
- [ ] Smoke tests passing

## Machine-Mind Summary

The underlying trading logic is interesting and mostly coherent. The biggest current risk is not the trading strategy; it is the half-finished repo/application reorganization. Finishing the reorg and restoring one source of truth is the top engineering priority.
