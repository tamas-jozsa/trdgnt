# TICKET-096 — Update All Documentation Post-Reorg

**Priority:** MEDIUM  
**Effort:** 2-3 hours  
**Status:** TODO  
**Files:** `docs/README.md`, `docs/AGENTS.md`, `docs/SPEC.md`, `MAGE.md`, `dashboard/frontend/README.md`

## Problem

Docs are substantially out of date after the reorg and after the Make→Mage switch. They still reference `.env.example` at repo root, root-level `trading_loop.py`, root-level `update_positions.py`, `watch_agent.sh`, port `8080`, and even `10:00 AM ET` in places. `MAGE.md` still says the Makefile is kept for backward compatibility even though it was removed.

## Affected Locations

- `docs/README.md:87` — old file references
- `docs/README.md:116-121` — root-level scripts
- `docs/README.md:142` — old port
- `docs/README.md:183` — old paths
- `docs/README.md:239-267` — stale info
- `docs/README.md:528-533` — outdated
- `docs/AGENTS.md:65-80` — old layout
- `docs/AGENTS.md:212-218` — stale paths
- `docs/AGENTS.md:364-390` — outdated
- `docs/AGENTS.md:421-426` — wrong references
- `docs/SPEC.md:27` — old structure
- `docs/SPEC.md:693` — stale
- `docs/SPEC.md:905-931` — outdated
- `MAGE.md:105-110` — mentions removed Makefile
- `dashboard/frontend/README.md` — stock Vite template

## Solution

1. Update all file path references to new `apps/` layout
2. Fix port references: `8080` → `8888`
3. Remove/update Makefile references
4. Update or delete `dashboard/frontend/README.md` (currently stock Vite template)
5. Consolidate overlapping docs (`MIGRATION.md` + `REORGANIZATION.md`)
6. Ensure all code examples work with new structure

## Acceptance Criteria

- [ ] All docs reference `apps/` not root-level scripts
- [ ] Port `8888` documented correctly
- [ ] No references to removed Makefile
- [ ] `dashboard/frontend/README.md` is useful or removed
- [ ] Code examples in docs are copy-paste runnable
- [ ] Single source of truth for migration info
