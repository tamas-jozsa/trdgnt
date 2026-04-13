# TICKET-111 — News-Specific Debate Pipeline

**Priority:** HIGH
**Effort:** 0.5 days
**Status:** TODO
**Related:** TICKET-106, TICKET-109, TICKET-112
**Spec:** docs/SPEC.md — "Process 3: News Reaction Pipeline"

## Summary

Create `src/tradingagents/news_debate.py` — a debate pipeline specifically
designed for news-driven decisions. Unlike the discovery pipeline (which
evaluates from scratch), this assesses news impact against existing theses.

## Requirements

1. **Severity classification:**
   ```python
   class NewsSeverity(Enum):
       LOW = "low"           # log only
       MEDIUM = "medium"     # 2-agent quick assessment
       HIGH = "high"         # full 12-agent debate
       CRITICAL = "critical" # immediate Risk Judge decision
   ```

2. **Triage function:**
   ```python
   def triage_news(
       news_items: list[NewsItem],
       portfolio: dict[str, ThesisRecord],
   ) -> list[TriageResult]:
   ```
   - Input: batch of news items + current portfolio with theses
   - LLM (gpt-4o-mini) classifies each item:
     - Affected portfolio tickers
     - Severity (LOW/MEDIUM/HIGH/CRITICAL)
     - Sentiment (positive/negative/mixed)
   - Portfolio context enables thesis-aware triage:
     "We hold NVDA because {thesis}. Does this news affect that thesis?"

3. **Graduated response functions:**

   a. **MEDIUM — Quick assessment:**
      ```python
      def assess_news_impact(
          ticker: str,
          thesis: ThesisRecord,
          news_summary: str,
      ) -> AssessmentResult:
      ```
      Delegates to `review_agents.run_quick_assessment()`.

   b. **HIGH — Full debate:**
      ```python
      def debate_news_impact(
          ticker: str,
          thesis: ThesisRecord,
          news_summary: str,
      ) -> DebateResult:
      ```
      Runs full 12-agent pipeline with thesis + news injected into system prompts.

   c. **CRITICAL — Immediate decision:**
      ```python
      def immediate_risk_assessment(
          ticker: str,
          thesis: ThesisRecord,
          news_summary: str,
      ) -> ImmediateResult:
      ```
      Single Risk Judge call (gpt-4o) with thesis + news context.
      Returns: decision (BUY/SELL/HOLD), conviction (1-10), reasoning.

4. **Conviction gating:**
   - All response levels return a conviction score
   - Only conviction >= 8 results in trade execution
   - Conviction 6-7 flags for accelerated portfolio review
   - Conviction < 6 logs only

5. **Thesis-aware prompting:**
   All debate/assessment prompts include:
   ```
   CURRENT POSITION:
   We hold {ticker} because: {thesis.rationale}
   Key catalysts: {thesis.key_catalysts}
   Thesis would be invalidated if: {thesis.invalidation_conditions}

   NEWS EVENT:
   {news_summary}

   QUESTION: Does this news affect our investment thesis?
   ```

## Files

- **Create:** `src/tradingagents/news_debate.py`

## Dependencies

- TICKET-106 (ThesisRecord)
- TICKET-109 (review_agents — quick assessment)
- Existing: TradingAgentsGraph, LLM clients

## Tests

- Triage with mocked LLM (all four severity levels)
- Portfolio-aware triage (only flags held tickers)
- Quick assessment (MEDIUM)
- Full debate (HIGH)
- Immediate decision (CRITICAL)
- Conviction gating (>= 8 trades, < 8 flags/logs)
