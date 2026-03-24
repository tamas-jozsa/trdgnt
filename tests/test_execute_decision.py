"""
Tests for execute_decision() and get_latest_price() in alpaca_bridge.py.

All Alpaca API calls are mocked — no real network calls or paper trades placed.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_order(order_id="ord-123", qty=5.0, status="accepted"):
    o = MagicMock()
    o.id     = order_id
    o.qty    = str(qty)
    o.status = status
    return o


def _make_account(cash=10_000.0):
    a = MagicMock()
    a.cash = str(cash)
    return a


def _patch_price(price: float):
    """Patch get_latest_price to return a fixed value."""
    import alpaca_bridge as ab
    return patch.object(ab, "get_latest_price", return_value=price)


def _patch_clients(tc=None, dc=None):
    """Patch both lazy client getters."""
    import alpaca_bridge as ab
    mock_tc = tc or MagicMock()
    mock_dc = dc or MagicMock()
    return (
        patch.object(ab, "_get_trading_client", return_value=mock_tc),
        patch.object(ab, "_get_data_client",    return_value=mock_dc),
        mock_tc,
        mock_dc,
    )


# ---------------------------------------------------------------------------
# execute_decision — HOLD
# ---------------------------------------------------------------------------

class TestExecuteDecisionHold:

    def test_hold_returns_hold_action(self):
        from alpaca_bridge import execute_decision
        result = execute_decision("NVDA", "HOLD", 1000.0)
        assert result["action"] == "HOLD"
        assert result["ticker"] == "NVDA"

    def test_hold_lowercase_normalised(self):
        from alpaca_bridge import execute_decision
        result = execute_decision("NVDA", "hold", 1000.0)
        assert result["action"] == "HOLD"

    def test_hold_places_no_order(self):
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        with patch.object(ab, "_get_trading_client", return_value=mock_tc):
            ab.execute_decision("NVDA", "HOLD", 1000.0)
        mock_tc.submit_order.assert_not_called()


# ---------------------------------------------------------------------------
# execute_decision — BUY
# ---------------------------------------------------------------------------

class TestExecuteDecisionBuy:

    def _run_buy(self, price=100.0, cash=10_000.0, amount=1000.0, ticker="NVDA"):
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_tc.get_account.return_value = _make_account(cash)
        mock_order = _make_order(qty=round(min(amount, cash) / price, 6))
        mock_tc.submit_order.return_value = mock_order

        with _patch_price(price), \
             patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = ab.execute_decision(ticker, "BUY", amount)

        return result, mock_tc

    def test_buy_submits_order(self):
        result, mock_tc = self._run_buy()
        mock_tc.submit_order.assert_called_once()

    def test_buy_returns_correct_action(self):
        result, _ = self._run_buy()
        assert result["action"] == "BUY"

    def test_buy_returns_order_id(self):
        result, _ = self._run_buy()
        assert result["order_id"] == "ord-123"

    def test_buy_qty_calculated_correctly(self):
        # $1000 at $100/share = 10 shares
        result, _ = self._run_buy(price=100.0, cash=10_000.0, amount=1000.0)
        assert result["qty"] == pytest.approx(10.0, abs=0.01)

    def test_buy_capped_by_available_cash(self):
        # Amount $2000 but only $500 cash — should buy $500 worth
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_tc.get_account.return_value = _make_account(500.0)
        mock_order = _make_order(qty=5.0)
        mock_tc.submit_order.return_value = mock_order

        with _patch_price(100.0), \
             patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = ab.execute_decision("NVDA", "BUY", 2000.0)

        # qty should be 500/100 = 5 shares, not 2000/100 = 20
        call_args = mock_tc.submit_order.call_args[0][0]
        assert float(call_args.qty) == pytest.approx(5.0, abs=0.01)

    def test_buy_skipped_when_no_cash(self):
        result, mock_tc = self._run_buy(cash=0.0, amount=1000.0)
        assert result["action"] == "SKIPPED"
        assert result["reason"] == "insufficient_cash"
        mock_tc.submit_order.assert_not_called()

    def test_buy_skipped_when_cash_below_1(self):
        result, mock_tc = self._run_buy(cash=0.50, amount=1000.0)
        assert result["action"] == "SKIPPED"
        mock_tc.submit_order.assert_not_called()

    def test_buy_raises_when_price_zero(self):
        import alpaca_bridge as ab
        with _patch_price(0.0):
            with pytest.raises(ValueError, match="valid price"):
                ab.execute_decision("NVDA", "BUY", 1000.0)

    def test_buy_order_is_market_day(self):
        """Verify the order is a DAY market order."""
        from alpaca.trading.enums import OrderSide, TimeInForce
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_tc.get_account.return_value = _make_account(10_000.0)
        mock_tc.submit_order.return_value = _make_order()

        with _patch_price(100.0), \
             patch.object(ab, "_get_trading_client", return_value=mock_tc):
            ab.execute_decision("NVDA", "BUY", 1000.0)

        req = mock_tc.submit_order.call_args[0][0]
        assert req.side == OrderSide.BUY
        assert req.time_in_force == TimeInForce.DAY


# ---------------------------------------------------------------------------
# execute_decision — SELL
# ---------------------------------------------------------------------------

class TestExecuteDecisionSell:

    def _run_sell(self, held=10.0, price=100.0, amount=1000.0, ticker="NVDA"):
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_order = _make_order(qty=min(held, round(amount / price, 6)))
        mock_tc.submit_order.return_value = mock_order

        with _patch_price(price), \
             patch.object(ab, "shares_held", return_value=held), \
             patch.object(ab, "_get_trading_client", return_value=mock_tc):
            result = ab.execute_decision(ticker, "SELL", amount)

        return result, mock_tc

    def test_sell_submits_order(self):
        result, mock_tc = self._run_sell()
        mock_tc.submit_order.assert_called_once()

    def test_sell_returns_correct_action(self):
        result, _ = self._run_sell()
        assert result["action"] == "SELL"

    def test_sell_returns_order_id(self):
        result, _ = self._run_sell()
        assert result["order_id"] == "ord-123"

    def test_sell_skipped_when_no_position(self):
        result, mock_tc = self._run_sell(held=0.0)
        assert result["action"] == "SKIPPED"
        assert result["reason"] == "no_position"
        mock_tc.submit_order.assert_not_called()

    def test_sell_qty_limited_to_held_shares(self):
        """If amount would sell more than held, only sell what we have."""
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_tc.submit_order.return_value = _make_order(qty=3.0)

        # Hold 3 shares @ $100, amount = $10000 (would be 100 shares)
        # Should only sell 3 shares
        with _patch_price(100.0), \
             patch.object(ab, "shares_held", return_value=3.0), \
             patch.object(ab, "_get_trading_client", return_value=mock_tc):
            ab.execute_decision("NVDA", "SELL", 10_000.0)

        req = mock_tc.submit_order.call_args[0][0]
        assert float(req.qty) == pytest.approx(3.0, abs=0.001)

    def test_sell_order_is_market_day(self):
        from alpaca.trading.enums import OrderSide, TimeInForce
        import alpaca_bridge as ab
        mock_tc = MagicMock()
        mock_tc.submit_order.return_value = _make_order()

        with _patch_price(100.0), \
             patch.object(ab, "shares_held", return_value=10.0), \
             patch.object(ab, "_get_trading_client", return_value=mock_tc):
            ab.execute_decision("NVDA", "SELL", 1000.0)

        req = mock_tc.submit_order.call_args[0][0]
        assert req.side == OrderSide.SELL
        assert req.time_in_force == TimeInForce.DAY

    def test_sell_raises_when_price_zero(self):
        import alpaca_bridge as ab
        with _patch_price(0.0), \
             patch.object(ab, "shares_held", return_value=10.0):
            with pytest.raises(ValueError, match="valid price"):
                ab.execute_decision("NVDA", "SELL", 1000.0)


# ---------------------------------------------------------------------------
# execute_decision — invalid decision
# ---------------------------------------------------------------------------

class TestExecuteDecisionInvalid:

    def test_unknown_decision_raises(self):
        import alpaca_bridge as ab
        with _patch_price(100.0):
            with pytest.raises(ValueError, match="Unknown decision"):
                ab.execute_decision("NVDA", "YOLO", 1000.0)

    def test_empty_decision_raises(self):
        import alpaca_bridge as ab
        with _patch_price(100.0):
            with pytest.raises(ValueError, match="Unknown decision"):
                ab.execute_decision("NVDA", "", 1000.0)


# ---------------------------------------------------------------------------
# get_latest_price — fallback chain
# ---------------------------------------------------------------------------

class TestGetLatestPrice:

    def test_returns_ask_price_when_available(self):
        import alpaca_bridge as ab
        mock_quote = MagicMock()
        mock_quote.ask_price = 174.92
        mock_quote.bid_price = 174.80

        mock_dc = MagicMock()
        mock_dc.get_stock_latest_quote.return_value = {"NVDA": mock_quote}

        with patch.object(ab, "_get_data_client", return_value=mock_dc):
            price = ab.get_latest_price("NVDA")

        assert price == pytest.approx(174.92)

    def test_falls_back_to_bid_when_ask_is_zero(self):
        import alpaca_bridge as ab
        mock_quote = MagicMock()
        mock_quote.ask_price = 0.0
        mock_quote.bid_price = 174.80

        mock_dc = MagicMock()
        mock_dc.get_stock_latest_quote.return_value = {"NVDA": mock_quote}

        with patch.object(ab, "_get_data_client", return_value=mock_dc):
            price = ab.get_latest_price("NVDA")

        assert price == pytest.approx(174.80)

    def test_falls_back_to_last_trade_when_quote_zero(self):
        import alpaca_bridge as ab
        mock_quote = MagicMock()
        mock_quote.ask_price = 0.0
        mock_quote.bid_price = 0.0

        mock_trade = MagicMock()
        mock_trade.price = 174.50

        mock_dc = MagicMock()
        mock_dc.get_stock_latest_quote.return_value = {"NVDA": mock_quote}
        mock_dc.get_stock_latest_trade.return_value = {"NVDA": mock_trade}

        with patch.object(ab, "_get_data_client", return_value=mock_dc):
            price = ab.get_latest_price("NVDA")

        assert price == pytest.approx(174.50)

    def test_falls_back_to_yfinance_when_alpaca_fails(self):
        import alpaca_bridge as ab

        mock_dc = MagicMock()
        mock_dc.get_stock_latest_quote.side_effect = Exception("API error")
        mock_dc.get_stock_latest_trade.side_effect = Exception("API error")

        mock_fast_info = MagicMock()
        mock_fast_info.last_price = 173.00

        with patch.object(ab, "_get_data_client", return_value=mock_dc), \
             patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.fast_info = mock_fast_info
            price = ab.get_latest_price("NVDA")

        assert price == pytest.approx(173.00)

    def test_returns_zero_when_all_sources_fail(self):
        import alpaca_bridge as ab

        mock_dc = MagicMock()
        mock_dc.get_stock_latest_quote.side_effect = Exception("fail")
        mock_dc.get_stock_latest_trade.side_effect = Exception("fail")

        with patch.object(ab, "_get_data_client", return_value=mock_dc), \
             patch("yfinance.Ticker", side_effect=Exception("fail")):
            price = ab.get_latest_price("NVDA")

        assert price == 0.0


# ---------------------------------------------------------------------------
# Integration: full BUY → SELL round-trip (mocked)
# ---------------------------------------------------------------------------

class TestBuySellRoundTrip:

    def test_buy_then_sell_cycle(self):
        """
        Simulate a full cycle: BUY 10 shares, then SELL them.
        Verifies both order directions are submitted with correct quantities.
        """
        import alpaca_bridge as ab
        from alpaca.trading.enums import OrderSide

        buy_order  = _make_order(order_id="buy-001",  qty=10.0, status="filled")
        sell_order = _make_order(order_id="sell-001", qty=10.0, status="filled")

        mock_tc = MagicMock()
        mock_tc.get_account.return_value = _make_account(cash=10_000.0)
        mock_tc.submit_order.side_effect = [buy_order, sell_order]

        with _patch_price(100.0), \
             patch.object(ab, "_get_trading_client", return_value=mock_tc), \
             patch.object(ab, "shares_held", return_value=10.0):

            buy_result  = ab.execute_decision("NVDA", "BUY",  1000.0)
            sell_result = ab.execute_decision("NVDA", "SELL", 1000.0)

        assert buy_result["action"]  == "BUY"
        assert sell_result["action"] == "SELL"
        assert buy_result["order_id"]  == "buy-001"
        assert sell_result["order_id"] == "sell-001"

        calls = mock_tc.submit_order.call_args_list
        assert calls[0][0][0].side == OrderSide.BUY
        assert calls[1][0][0].side == OrderSide.SELL
