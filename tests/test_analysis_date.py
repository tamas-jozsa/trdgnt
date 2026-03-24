"""Tests for TICKET-024: get_analysis_date returns correct session date."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _mock_now(weekday_name: str, hour: int, minute: int = 0):
    """
    Create a mock for datetime.now(ET) for a given weekday and time.
    Weekday 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun.
    """
    # Use a known anchor date: Mon 2026-03-23
    anchor = date(2026, 3, 23)  # Monday
    days = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    delta = days[weekday_name]
    target_date = anchor + timedelta(days=delta)
    dt = datetime(target_date.year, target_date.month, target_date.day,
                  hour, minute, 0, tzinfo=ET)
    return dt


def _run(weekday: str, hour: int, minute: int = 0) -> str:
    """Patch datetime.now and call get_analysis_date()."""
    import trading_loop as tl
    mock_dt = _mock_now(weekday, hour, minute)
    with patch("trading_loop.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_dt
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        return tl.get_analysis_date()


class TestGetAnalysisDate:

    # ── After close (4:15 PM ET or later) — use TODAY ──────────────────────

    def test_tuesday_after_close_uses_today(self):
        result = _run("Tue", 16, 15)
        assert result == "2026-03-24"  # Tuesday

    def test_tuesday_late_evening_uses_today(self):
        result = _run("Tue", 20, 0)
        assert result == "2026-03-24"

    def test_wednesday_after_close_uses_today(self):
        result = _run("Wed", 17, 0)
        assert result == "2026-03-25"

    def test_thursday_after_close_uses_today(self):
        result = _run("Thu", 16, 30)
        assert result == "2026-03-26"

    def test_friday_after_close_uses_today(self):
        result = _run("Fri", 16, 20)
        assert result == "2026-03-27"  # Friday — use Friday

    def test_monday_after_close_uses_today(self):
        result = _run("Mon", 16, 15)
        assert result == "2026-03-23"  # Monday

    def test_exactly_at_close_time_uses_today(self):
        """4:15 PM exactly should trigger 'after close'."""
        result = _run("Tue", 16, 15)
        assert result == "2026-03-24"

    # ── Before close — use PREVIOUS trading day ─────────────────────────────

    def test_tuesday_before_close_uses_monday(self):
        result = _run("Tue", 9, 30)
        assert result == "2026-03-23"  # Monday

    def test_wednesday_before_close_uses_tuesday(self):
        result = _run("Wed", 14, 0)
        assert result == "2026-03-24"  # Tuesday

    def test_thursday_before_close_uses_wednesday(self):
        result = _run("Thu", 10, 0)
        assert result == "2026-03-25"  # Wednesday

    def test_friday_before_close_uses_thursday(self):
        result = _run("Fri", 12, 0)
        assert result == "2026-03-26"  # Thursday

    def test_monday_before_close_uses_friday(self):
        """Monday morning → use Friday (skip weekend)."""
        result = _run("Mon", 9, 0)
        assert result == "2026-03-20"  # previous Friday

    def test_one_minute_before_close_uses_previous(self):
        """4:14 PM — one minute before cutoff — still uses previous session."""
        result = _run("Tue", 16, 14)
        assert result == "2026-03-23"  # Monday

    # ── Weekends — always use Friday ────────────────────────────────────────

    def test_saturday_morning_uses_friday(self):
        result = _run("Sat", 9, 0)
        assert result == "2026-03-27"  # Friday

    def test_saturday_evening_uses_friday(self):
        result = _run("Sat", 20, 0)
        assert result == "2026-03-27"

    def test_sunday_morning_uses_friday(self):
        result = _run("Sun", 9, 0)
        assert result == "2026-03-27"

    def test_sunday_evening_uses_friday(self):
        result = _run("Sun", 22, 0)
        assert result == "2026-03-27"

    # ── Return type ─────────────────────────────────────────────────────────

    def test_returns_string(self):
        result = _run("Tue", 17, 0)
        assert isinstance(result, str)

    def test_returns_valid_date_format(self):
        result = _run("Tue", 17, 0)
        # Should be parseable as YYYY-MM-DD
        from datetime import date as dt
        parsed = dt.fromisoformat(result)
        assert parsed.year == 2026

    def test_never_returns_saturday(self):
        """Analysis date should never be a Saturday."""
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            for hour in [9, 16, 20]:
                result = _run(day, hour)
                d = date.fromisoformat(result)
                assert d.weekday() != 5, f"Got Saturday for {day} {hour}:00"

    def test_never_returns_sunday(self):
        """Analysis date should never be a Sunday."""
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            for hour in [9, 16, 20]:
                result = _run(day, hour)
                d = date.fromisoformat(result)
                assert d.weekday() != 6, f"Got Sunday for {day} {hour}:00"

    def test_never_returns_future_date(self):
        """Analysis date must never be in the future relative to now."""
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
            for hour in [9, 16, 20]:
                mock_dt = _mock_now(day, hour)
                import trading_loop as tl
                with patch("trading_loop.datetime") as mock_datetime:
                    mock_datetime.now.return_value = mock_dt
                    mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
                    result = tl.get_analysis_date()
                analysis = date.fromisoformat(result)
                assert analysis <= mock_dt.date(), \
                    f"Future date for {day} {hour}:00: got {result}"
