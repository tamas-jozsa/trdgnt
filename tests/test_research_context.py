"""Tests for TICKET-005: research findings injection into agent context."""

import pytest
from pathlib import Path
import tempfile
import os


SAMPLE_FINDINGS = """
## RESEARCH FINDINGS — 2026-03-24

### Overall Market Sentiment: BEARISH
### VIX: 26.48 | Trend: ELEVATED

---

### TOP MACRO THEMES RIGHT NOW:
1. Iran War / Hormuz Crisis — 11M bbl/day offline; structural energy bull
2. Copper supply deficit — JPMorgan 330kt deficit confirmed
3. AI capex supercycle — SK Hynix $8B ASML order confirms demand

---

### FULL TICKER DECISION TABLE — WATCHLIST REVIEW:
| Ticker | Sector | Decision | Conviction |
|--------|--------|----------|------------|
| NVDA   | AI     | HOLD     | HIGH       |
| VG     | LNG    | BUY      | HIGH       |

---

### KEY MACRO SHIFTS SINCE LAST RESEARCH:
- Iran war escalated beyond prior context
- Private credit stress emerging

---

### SECTORS TO AVOID THIS WEEK:
1. Airlines — oil price exposure
2. Solar — rising rates + subsidies under pressure
"""


class TestLoadLatestResearchContext:

    def test_returns_empty_when_no_files(self, tmp_path):
        from tradingagents.research_context import load_latest_research_context
        result = load_latest_research_context(results_dir=str(tmp_path))
        assert result == ""

    def test_loads_most_recent_file(self, tmp_path):
        from tradingagents.research_context import load_latest_research_context

        # Create two findings files; should pick the later one
        (tmp_path / "RESEARCH_FINDINGS_2026-03-23.md").write_text("old context")
        (tmp_path / "RESEARCH_FINDINGS_2026-03-24.md").write_text(SAMPLE_FINDINGS)

        result = load_latest_research_context(results_dir=str(tmp_path))
        assert "2026-03-24" in result

    def test_extracts_macro_themes(self, tmp_path):
        from tradingagents.research_context import load_latest_research_context

        (tmp_path / "RESEARCH_FINDINGS_2026-03-24.md").write_text(SAMPLE_FINDINGS)
        result = load_latest_research_context(results_dir=str(tmp_path))

        assert "MACRO THEMES" in result.upper() or "Iran War" in result

    def test_extracts_vix(self, tmp_path):
        from tradingagents.research_context import load_latest_research_context

        (tmp_path / "RESEARCH_FINDINGS_2026-03-24.md").write_text(SAMPLE_FINDINGS)
        result = load_latest_research_context(results_dir=str(tmp_path))

        assert "VIX" in result or "26.48" in result

    def test_includes_date_header(self, tmp_path):
        from tradingagents.research_context import load_latest_research_context

        (tmp_path / "RESEARCH_FINDINGS_2026-03-24.md").write_text(SAMPLE_FINDINGS)
        result = load_latest_research_context(results_dir=str(tmp_path))

        assert "2026-03-24" in result

    def test_truncated_to_max_chars(self, tmp_path):
        from tradingagents.research_context import load_latest_research_context, MAX_CONTEXT_CHARS

        # Create a very long findings file
        huge = SAMPLE_FINDINGS + "\n" + ("X" * 10000)
        (tmp_path / "RESEARCH_FINDINGS_2026-03-24.md").write_text(huge)
        result = load_latest_research_context(results_dir=str(tmp_path))

        assert len(result) <= MAX_CONTEXT_CHARS + 100  # small buffer for truncation msg

    def test_result_is_string(self, tmp_path):
        from tradingagents.research_context import load_latest_research_context

        (tmp_path / "RESEARCH_FINDINGS_2026-03-24.md").write_text(SAMPLE_FINDINGS)
        result = load_latest_research_context(results_dir=str(tmp_path))

        assert isinstance(result, str)


class TestPropagatorMacroContext:
    """Verify macro_context is passed through Propagator."""

    def test_initial_state_includes_macro_context(self):
        from tradingagents.graph.propagation import Propagator

        p = Propagator()
        state = p.create_initial_state(
            "NVDA", "2026-03-24",
            macro_context="VIX: 26.48 | Iran war ongoing"
        )
        assert state["macro_context"] == "VIX: 26.48 | Iran war ongoing"

    def test_macro_context_defaults_to_empty(self):
        from tradingagents.graph.propagation import Propagator

        p = Propagator()
        state = p.create_initial_state("NVDA", "2026-03-24")
        assert state["macro_context"] == ""
