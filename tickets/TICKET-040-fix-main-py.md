# TICKET-040 — Fix or Remove main.py (Broken Dead Code)

**Priority:** MEDIUM
**Effort:** 15min
**Status:** DONE

## Problem

`main.py` is broken and misleading:
1. `config["deep_think_llm"] = "gpt-5-mini"` — not a real OpenAI model name
2. `config["quick_think_llm"] = "gpt-5-mini"` — same
3. `ta.propagate("NVDA", "2024-05-10")` — hardcoded stale date
4. Runs at import with no `if __name__ == "__main__"` guard (actually it does have one,
   but the global-level code at lines 13-30 still executes at import)

Running `python main.py` will fail immediately with an OpenAI API error because
`gpt-5-mini` is not a valid model.

## Approach

Convert `main.py` into a proper usable quick-demo that actually works:
- Replace `"gpt-5-mini"` with `os.getenv("DEEP_LLM_MODEL", "gpt-4o-mini")`
- Replace hardcoded date with `str(date.today() - timedelta(days=1))`
- Replace hardcoded ticker with a CLI arg or keep as `"NVDA"` with a comment
- Wrap everything in `main()` + `if __name__ == "__main__"` to prevent side effects at import

## Acceptance Criteria
- [ ] `main.py` runs without error when `OPENAI_API_KEY` is set (mocked in tests)
- [ ] No hardcoded model names — uses env vars with sensible defaults
- [ ] No hardcoded analysis date — uses yesterday's date dynamically
- [ ] All code inside `if __name__ == "__main__"` guard
- [ ] `ssl` monkey-patch removed from `main.py` (same issue as TICKET-035)
- [ ] Test: importing `main` does not trigger any network calls or LLM instantiation
