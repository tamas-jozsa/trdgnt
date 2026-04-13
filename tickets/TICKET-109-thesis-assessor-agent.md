# TICKET-109 — Thesis Assessor Review Agent

**Priority:** HIGH
**Effort:** 0.5 days
**Status:** TODO
**Related:** TICKET-106, TICKET-110
**Spec:** docs/SPEC.md — "Review Agent: Thesis Assessor"

## Summary

Create `src/tradingagents/review_agents.py` — a lightweight agent pipeline for
portfolio reviews. Unlike the full 12-agent debate, this uses 2-3 agents to
check if an existing thesis still holds.

## Requirements

1. **Thesis Assessor agent:**
   - Model: `gpt-4o` (decision-tier — same as Research Manager)
   - Input: original thesis + analyst updates + P&L + hold duration
   - Structured output:
     ```
     VERDICT: INTACT | WEAKENING | BROKEN
     CONFIDENCE: 1-10
     REASONING: <2-3 sentences>
     THESIS_UPDATE: <modifications if any>
     ACTION: HOLD | TIGHTEN_STOP | FLAG_FOR_DEBATE | SELL
     STOP_LOSS_UPDATE: <new stop price if tightening>
     ```

2. **Review pipeline function:**
   ```python
   def run_review(
       ticker: str,
       thesis: ThesisRecord,
       config: dict = None,
   ) -> ReviewResult:
   ```

   Pipeline:
   a. Run Market Analyst (reuse existing) — current technicals
   b. Run Fundamentals Analyst (reuse existing) — latest data
   c. Run Thesis Assessor with thesis context + analyst outputs
   d. Parse structured output → ReviewResult

3. **ReviewResult dataclass:**
   ```python
   @dataclass
   class ReviewResult:
       ticker: str
       verdict: Literal["intact", "weakening", "broken"]
       confidence: int
       reasoning: str
       thesis_update: str | None
       action: str  # HOLD, TIGHTEN_STOP, FLAG_FOR_DEBATE, SELL
       stop_loss_update: float | None
   ```

4. **Quick assessment function** (for news MEDIUM severity):
   ```python
   def run_quick_assessment(
       ticker: str,
       thesis: ThesisRecord,
       news_summary: str,
   ) -> AssessmentResult:
   ```

   Uses only Bull + Bear analyst debate on the specific news item,
   in the context of the thesis. Returns assessment without trade decision.

5. **System prompt for Thesis Assessor:**
   - Includes the original thesis (rationale, catalysts, invalidation conditions)
   - Current position data (entry price, P&L, days held)
   - Explicit instruction: "Your job is to assess if the thesis still holds,
     NOT to re-debate the investment from scratch"
   - Bias toward INTACT unless clear evidence of deterioration

## Files

- **Create:** `src/tradingagents/review_agents.py`

## Dependencies

- TICKET-106 (ThesisRecord model)
- Existing: Market Analyst, Fundamentals Analyst agents + tools

## Tests

- Thesis Assessor with mocked LLM responses
- Parse structured output (all three verdicts)
- Quick assessment with news context
- System prompt includes thesis correctly
