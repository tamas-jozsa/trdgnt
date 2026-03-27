# TICKET-041 — Fix validators.py OpenAI Model Allowlist

**Priority:** LOW
**Effort:** 15min
**Status:** DONE

## Problem

`tradingagents/llm_clients/validators.py` `VALID_MODELS["openai"]` contains
only speculative future models (`gpt-5*`, `gpt-4.1*`) but **not** the models
actually used in production:

- `gpt-4o` (used as `DEEP_LLM_MODEL` default in `trading_loop.py`, `alpaca_bridge.py`)
- `gpt-4o-mini` (used as `QUICK_LLM_MODEL` default everywhere)
- `o1`, `o3`, `o4-mini` (current generation reasoning models)

This means `validate_model("openai", "gpt-4o")` returns `False`, making the
validator actively misleading for the default configuration. Since `validate_model`
is never called at runtime today, this causes no breakage — but once it is wired
into startup validation it will incorrectly reject valid models.

## Approach

Update `VALID_MODELS["openai"]` to reflect the current production OpenAI model
lineup. Keep the speculative future models commented out or remove them.

## Acceptance Criteria
- [ ] `VALID_MODELS["openai"]` includes `gpt-4o`, `gpt-4o-mini`, `gpt-4o-realtime-preview`
- [ ] `VALID_MODELS["openai"]` includes current reasoning models: `o1`, `o3`, `o1-mini`, `o4-mini`
- [ ] `validate_model("openai", "gpt-4o")` returns `True`
- [ ] `validate_model("openai", "gpt-4o-mini")` returns `True`
- [ ] `validate_model("openai", "definitely-not-real")` returns `False`
- [ ] Unit tests added/updated in an appropriate test file
- [ ] All tests pass
