"""
tests/test_orders.py — Unit tests for bot.orders.OrderManager

All Binance API calls are mocked; no network access required.
Tests cover: success paths, error propagation, OrderError chaining,
response standardisation, and grid partial-failure behaviour.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from bot.orders import OrderManager, OrderError, _standardise_response
from bot.client import BinanceClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client() -> MagicMock:
    """Return a MagicMock shaped like BinanceClient with a .raw property."""
    client = MagicMock(spec=BinanceClient)
    client.raw = MagicMock()
    return client


@pytest.fixture
def manager(mock_client) -> OrderManager:
    return OrderManager(mock_client)


# ---------------------------------------------------------------------------
# _standardise_response helper
# ---------------------------------------------------------------------------

class TestStandardiseResponse:
    def test_all_fields_present(self):
        raw = {
            "orderId": 123,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "status": "FILLED",
            "price": "0",
            "avgPrice": "67000.00",
            "executedQty": "0.01",
            "origQty": "0.01",
        }
        result = _standardise_response(raw)
        assert result["orderId"] == 123
        assert result["symbol"] == "BTCUSDT"
        assert result["avgPrice"] == "67000.00"
        assert result["executedQty"] == "0.01"

    def test_missing_fields_return_defaults(self):
        result = _standardise_response({})
        assert result["orderId"] == "N/A"
        assert result["symbol"] == ""
        assert result["avgPrice"] == "0"


# ---------------------------------------------------------------------------
# place_market_order
# ---------------------------------------------------------------------------

class TestPlaceMarketOrder:
    def test_success_returns_standardised_response(self, manager, mock_client):
        mock_client.raw.futures_create_order.return_value = {
            "orderId": 9001,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "status": "FILLED",
            "price": "0",
            "avgPrice": "67000.00000",
            "executedQty": "0.01",
            "origQty": "0.01",
        }

        result = manager.place_market_order("BTCUSDT", "BUY", 0.01)

        assert result["orderId"] == 9001
        assert result["status"] == "FILLED"
        assert result["executedQty"] == "0.01"
        mock_client.raw.futures_create_order.assert_called_once_with(
            symbol="BTCUSDT",
            side="BUY",
            type="MARKET",
            quantity=0.01,
        )

    def test_api_exception_raises_order_error(self, manager, mock_client):
        from binance.exceptions import BinanceAPIException
        response_mock = MagicMock()
        response_mock.status_code = 400
        response_mock.text = '{"code": -1121, "msg": "Invalid symbol."}'
        mock_client.raw.futures_create_order.side_effect = BinanceAPIException(
            response_mock, 400, '{"code": -1121, "msg": "Invalid symbol."}'
        )

        with pytest.raises(OrderError) as exc_info:
            manager.place_market_order("BADUSDT", "BUY", 0.01)

        assert exc_info.value.raw_error is not None

    def test_order_error_message_contains_symbol(self, manager, mock_client):
        from binance.exceptions import BinanceAPIException
        response_mock = MagicMock()
        response_mock.status_code = 400
        response_mock.text = '{"code": -1121, "msg": "Invalid symbol."}'
        mock_client.raw.futures_create_order.side_effect = BinanceAPIException(
            response_mock, 400, '{"code": -1121, "msg": "Invalid symbol."}'
        )

        with pytest.raises(OrderError, match="BTCUSDT"):
            manager.place_market_order("BTCUSDT", "BUY", 0.01)


# ---------------------------------------------------------------------------
# place_limit_order
# ---------------------------------------------------------------------------

class TestPlaceLimitOrder:
    def test_success_returns_standardised_response(self, manager, mock_client):
        mock_client.raw.futures_create_order.return_value = {
            "orderId": 7002,
            "symbol": "ETHUSDT",
            "side": "SELL",
            "type": "LIMIT",
            "status": "NEW",
            "price": "3200.00",
            "avgPrice": "0.00",
            "executedQty": "0.00",
            "origQty": "0.50",
        }

        result = manager.place_limit_order("ETHUSDT", "SELL", 0.5, 3200.0)

        assert result["orderId"] == 7002
        assert result["status"] == "NEW"
        assert result["price"] == "3200.00"
        mock_client.raw.futures_create_order.assert_called_once_with(
            symbol="ETHUSDT",
            side="SELL",
            type="LIMIT",
            quantity=0.5,
            price=3200.0,
            timeInForce="GTC",
        )

    def test_api_exception_raises_order_error(self, manager, mock_client):
        from binance.exceptions import BinanceAPIException
        response_mock = MagicMock()
        response_mock.status_code = 400
        response_mock.text = '{"code": -1111, "msg": "Precision is over the maximum."}'
        mock_client.raw.futures_create_order.side_effect = BinanceAPIException(
            response_mock, 400, '{"code": -1111, "msg": "Precision."}'
        )

        with pytest.raises(OrderError):
            manager.place_limit_order("ETHUSDT", "SELL", 0.5, 3200.0)


# ---------------------------------------------------------------------------
# place_grid_order
# ---------------------------------------------------------------------------

class TestPlaceGridOrder:
    def _make_order_response(self, order_id: int, price: str) -> dict:
        return {
            "orderId": order_id,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "status": "NEW",
            "price": price,
            "avgPrice": "0.00",
            "executedQty": "0.00",
            "origQty": "0.02",
        }

    def test_all_levels_placed_successfully(self, manager, mock_client):
        responses = [
            self._make_order_response(i, str(60000 + i * 1000))
            for i in range(1, 4)
        ]
        mock_client.raw.futures_create_order.side_effect = responses

        results = manager.place_grid_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.06,
            price_low=60000,
            price_high=62000,
            grid_levels=3,
        )

        assert len(results) == 3
        assert all(r["status"] == "NEW" for r in results)
        assert mock_client.raw.futures_create_order.call_count == 3

    def test_partial_failure_continues(self, manager, mock_client):
        from binance.exceptions import BinanceAPIException
        response_mock = MagicMock()
        response_mock.status_code = 400
        response_mock.text = '{"code": -1111, "msg": "Error."}'

        success_resp = self._make_order_response(1001, "60000")
        failure = BinanceAPIException(response_mock, 400, '{"code": -1111}')

        mock_client.raw.futures_create_order.side_effect = [
            success_resp,
            failure,
            self._make_order_response(1003, "62000"),
        ]

        results = manager.place_grid_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.06,
            price_low=60000,
            price_high=62000,
            grid_levels=3,
        )

        assert len(results) == 3
        assert results[0]["status"] == "NEW"
        assert results[1]["status"] == "ERROR"
        assert results[2]["status"] == "NEW"

    def test_all_levels_fail_raises_order_error(self, manager, mock_client):
        from binance.exceptions import BinanceAPIException
        response_mock = MagicMock()
        response_mock.status_code = 400
        response_mock.text = '{"code": -1111, "msg": "Error."}'
        mock_client.raw.futures_create_order.side_effect = BinanceAPIException(
            response_mock, 400, '{"code": -1111}'
        )

        with pytest.raises(OrderError, match="All"):
            manager.place_grid_order(
                symbol="BTCUSDT",
                side="BUY",
                quantity=0.06,
                price_low=60000,
                price_high=62000,
                grid_levels=3,
            )

    def test_price_distribution_correct(self, manager, mock_client):
        """Verify that grid prices are evenly distributed between low and high."""
        calls_made = []

        def capture_call(**kwargs):
            calls_made.append(kwargs["price"])
            return self._make_order_response(len(calls_made), str(kwargs["price"]))

        mock_client.raw.futures_create_order.side_effect = capture_call

        manager.place_grid_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.04,
            price_low=60000,
            price_high=62000,
            grid_levels=3,
        )

        assert calls_made[0] == pytest.approx(60000.0)
        assert calls_made[1] == pytest.approx(61000.0)
        assert calls_made[2] == pytest.approx(62000.0)

    def test_quantity_split_correctly(self, manager, mock_client):
        """Total quantity is split evenly across levels."""
        call_qtys = []

        def capture_call(**kwargs):
            call_qtys.append(kwargs["quantity"])
            return self._make_order_response(len(call_qtys), "60000")

        mock_client.raw.futures_create_order.side_effect = capture_call

        manager.place_grid_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.3,
            price_low=60000,
            price_high=62000,
            grid_levels=3,
        )

        for qty in call_qtys:
            assert qty == pytest.approx(0.1, rel=1e-5)
