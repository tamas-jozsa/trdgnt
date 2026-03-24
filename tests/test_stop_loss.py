"""Tests for TICKET-002: automated stop-loss monitor."""

import types
from unittest.mock import MagicMock, patch
import pytest


def make_mock_position(symbol: str, qty: float, pnl_pct: float):
    """Build a mock Alpaca position object."""
    p = MagicMock()
    p.symbol = symbol
    p.qty = str(qty)
    p.unrealized_plpc = str(pnl_pct)   # e.g. "-0.20" for -20%
    return p


class TestCheckStopLosses:

    def _run(self, positions, threshold=0.15, dry_run=True):
        """Helper: patch Alpaca clients and call check_stop_losses."""
        import alpaca_bridge as ab

        mock_trading = MagicMock()
        mock_trading.get_all_positions.return_value = positions

        # Patch the lazy getter so no real Alpaca keys are needed
        with patch.object(ab, "_get_trading_client", return_value=mock_trading):
            results = ab.check_stop_losses(threshold=threshold, dry_run=dry_run)

        return results, mock_trading

    def test_no_positions_no_triggers(self):
        results, _ = self._run([])
        assert results == []

    def test_position_above_threshold_not_triggered(self):
        pos = make_mock_position("NVDA", 10, -0.05)   # -5%, threshold -15%
        results, _ = self._run([pos])
        assert results == []

    def test_position_exactly_at_threshold_triggers(self):
        pos = make_mock_position("NVDA", 10, -0.15)   # exactly -15%
        results, _ = self._run([pos], threshold=0.15)
        assert len(results) == 1
        assert results[0]["ticker"] == "NVDA"
        assert results[0]["action"] == "STOP_LOSS_TRIGGERED"

    def test_position_below_threshold_triggers(self):
        pos = make_mock_position("RCAT", 50, -0.25)   # -25%
        results, _ = self._run([pos], threshold=0.15)
        assert len(results) == 1
        assert results[0]["ticker"] == "RCAT"
        assert results[0]["pnl_pct"] == -25.0

    def test_dry_run_does_not_submit_order(self):
        pos = make_mock_position("MOS", 20, -0.30)
        results, mock_trading = self._run([pos], dry_run=True)
        assert len(results) == 1
        assert results[0]["dry_run"] is True
        mock_trading.submit_order.assert_not_called()

    def test_live_run_submits_order(self):
        pos = make_mock_position("MOS", 20, -0.30)
        mock_order = MagicMock()
        mock_order.id = "order-123"
        mock_order.status = "accepted"

        import alpaca_bridge as ab
        mock_trading = MagicMock()
        mock_trading.get_all_positions.return_value = [pos]
        mock_trading.submit_order.return_value = mock_order

        with patch.object(ab, "_get_trading_client", return_value=mock_trading):
            results = ab.check_stop_losses(threshold=0.15, dry_run=False)

        assert len(results) == 1
        assert results[0]["order_id"] == "order-123"
        mock_trading.submit_order.assert_called_once()

    def test_multiple_positions_only_bad_ones_triggered(self):
        positions = [
            make_mock_position("NVDA", 5,  -0.03),   # fine
            make_mock_position("RCAT", 50, -0.20),   # triggered
            make_mock_position("GLD",  10, +0.10),   # fine (positive)
            make_mock_position("MOS",  30, -0.16),   # triggered
        ]
        results, _ = self._run(positions, threshold=0.15)
        triggered = {r["ticker"] for r in results}
        assert triggered == {"RCAT", "MOS"}

    def test_custom_threshold(self):
        pos = make_mock_position("RCKT", 100, -0.08)   # -8%
        # With 10% threshold should NOT trigger
        results, _ = self._run([pos], threshold=0.10)
        assert results == []
        # With 5% threshold SHOULD trigger
        results, _ = self._run([pos], threshold=0.05)
        assert len(results) == 1
