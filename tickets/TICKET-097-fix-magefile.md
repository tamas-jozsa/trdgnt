# TICKET-097 — Fix Magefile Commands and Simplify

**Priority:** MEDIUM  
**Effort:** 1-2 hours  
**Status:** TODO  
**Files:** `magefile.go`, `go.mod`, `go.sum`

## Problem

Mage is a better fit than Make for parametrized tasks, but the current Magefile has broken commands and adds non-trivial complexity. `runPython()` always prepends `apps/<script>`, so the monitor commands that try to use `-c` are broken. Also, the default target is `dashboard`, which is a surprising default for a Python trading repo. More broadly, Mage works, but it introduces a Go toolchain and `go.mod/go.sum` into an otherwise Python-only project.

## Affected Locations

- `magefile.go:55-67` — `runPython()` prepends wrong path
- `magefile.go:213-224` — broken monitor commands
- `magefile.go:22` — surprising default target

## Solution

Option A - Fix Mage:
1. Fix `runPython()` to handle different script locations
2. Fix monitor commands with `-c` flag
3. Change default target to something sensible (`run` or `help`)
4. Document Mage requirement clearly

Option B - Replace Mage:
1. Use Python-based task runner (`invoke`, `taskipy`, or plain `python -m`)
2. Remove Go toolchain dependency
3. Simplify to Python-native solution

## Acceptance Criteria

- [ ] Decide: fix Mage or replace with Python solution
- [ ] All mage targets work correctly
- [ ] Monitor commands with `-c` flag work
- [ ] Default target is sensible
- [ ] Task runner is documented
- [ ] (If replacing) Remove `go.mod`, `go.sum`, `magefile.go`
