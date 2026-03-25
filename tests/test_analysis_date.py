"""Tests for get_analysis_date — always returns previous completed session."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _mock_now(weekday_name: str, hour: int, minute: int = 0):
    anchor = date(2026, 3, 23)  # Monday
    days = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    target_date = anchor + timedelta(days=days[weekday_name])
    return datetime(target_date.year, target_date.month, target_date.day,
                    hour, minute, 0, tzinfo=ET)


def _run(weekday: str, hour: int, minute: int = 0) -> str:
    import trading_loop as tl
    mock_dt = _mock_now(weekday, hour, minute)
    with patch("trading_loop.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_dt
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        return tl.get_analysis_date()


class TestGetAnalysisDate:

    # ── Weekdays always use PREVIOUS session (market is open at run time) ───

    def test_tuesday_uses_monday(self):
        assert _run("Tue", 10, 0) == "2026-03-23"

    def test_tuesday_any_time_uses_monday(self):
        for h in [6, 10, 14, 17, 21]:
            assert _run("Tue", h) == "2026-03-23", f"Failed at hour {h}"

    def test_wednesday_uses_tuesday(self):
        assert _run("Wed", 10, 0) == "2026-03-24"

    def test_thursday_uses_wednesday(self):
        assert _run("Thu", 10, 0) == "2026-03-25"

    def test_friday_uses_thursday(self):
        assert _run("Fri", 10, 0) == "2026-03-26"

    def test_monday_uses_friday(self):
        """Monday always uses the previous Friday."""
        assert _run("Mon", 10, 0) == "2026-03-20"

    def test_monday_any_time_uses_friday(self):
        for h in [6, 10, 14, 17, 21]:
            assert _run("Mon", h) == "2026-03-20", f"Failed at hour {h}"

    # ── Weekends always use Friday ───────────────────────────────────────────

    def test_saturday_uses_friday(self):
        assert _run("Sat", 9, 0) == "2026-03-27"

    def test_saturday_any_time_uses_friday(self):
        for h in [6, 10, 20]:
            assert _run("Sat", h) == "2026-03-27"

    def test_sunday_uses_friday(self):
        assert _run("Sun", 9, 0) == "2026-03-27"

    def test_sunday_any_time_uses_friday(self):
        for h in [6, 10, 22]:
            assert _run("Sun", h) == "2026-03-27"

    # ── Return type and invariants ───────────────────────────────────────────

    def test_returns_string(self):
        assert isinstance(_run("Tue", 10), str)

    def test_returns_valid_iso_date(self):
        result = _run("Tue", 10)
        parsed = date.fromisoformat(result)
        assert parsed.year == 2026

    def test_never_returns_saturday(self):
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            for hour in [6, 10, 17]:
                d = date.fromisoformat(_run(day, hour))
                assert d.weekday() != 5, f"Got Saturday for {day} {hour}:00"

    def test_never_returns_sunday(self):
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            for hour in [6, 10, 17]:
                d = date.fromisoformat(_run(day, hour))
                assert d.weekday() != 6, f"Got Sunday for {day} {hour}:00"

    def test_never_returns_future_date(self):
        """Analysis date must always be strictly before the run date."""
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
            for hour in [6, 10, 17]:
                mock_dt = _mock_now(day, hour)
                import trading_loop as tl
                with patch("trading_loop.datetime") as mock_datetime:
                    mock_datetime.now.return_value = mock_dt
                    mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
                    result = tl.get_analysis_date()
                analysis = date.fromisoformat(result)
                assert analysis < mock_dt.date(), \
                    f"Analysis date not before run date for {day} {hour}:00: got {result}"
