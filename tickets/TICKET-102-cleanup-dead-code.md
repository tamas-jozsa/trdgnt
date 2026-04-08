# TICKET-102 — Cleanup Dead Code and Empty Packages

**Priority:** LOW  
**Effort:** 1 hour  
**Status:** TODO  
**Files:** `src/tradingagents/core/`, `apps/__init__.py`, `src/tradingagents/__init__.py`, `src/tradingagents/llm_clients/TODO.md`

## Problem

There are empty packages and unused files that clutter the codebase:

- `src/tradingagents/core/` looks like a planned abstraction that never happened; right now it is effectively dead scaffolding
- `apps/__init__.py` currently adds little value
- `src/tradingagents/__init__.py` is empty
- `src/tradingagents/llm_clients/TODO.md` may be fine as a note, but it is not integrated into any workflow

## Solution

1. Either populate `src/tradingagents/core/` with actual code OR remove it
2. Remove empty `__init__.py` files if not needed
3. Convert `TODO.md` to actual issues or remove
4. Clean up any other empty/unused modules

## Acceptance Criteria

- [ ] Decision made: populate or remove `core/`
- [ ] Empty `__init__.py` files removed (if safe)
- [ ] `TODO.md` converted to tickets or removed
- [ ] No empty placeholder packages
