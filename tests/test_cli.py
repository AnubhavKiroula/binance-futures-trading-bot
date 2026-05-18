"""
tests/test_cli.py — Integration-style tests for cli.py using Typer's CliRunner.

All Binance API calls are mocked via unittest.mock.patch so no network
access or real credentials are needed.  Tests verify: argument parsing,
output content, exit codes, and error handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helper — a fake BinanceClient + OrderManager pair
# ---------------------------------------------------------------------------

def _make_market_response() -> dict:
    return {
        "orderId": 4812309,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "MARKET",
        "status": "FILLED",
        "price": "0",
        "avgPrice": "67412.30000",
        "executedQty": "0.01",
        "origQty": "0.01",
    }


def _make_limit_response() -> dict:
    return {
        "orderId": 2309811,
        "symbol": "ETHUSDT",
        "side": "SELL",
        "type": "LIMIT",
        "status": "NEW",
        "price": "3200.00",
        "avgPrice": "0.00000",
        "executedQty": "0.00",
        "origQty": "0.50",
    }


def _make_grid_responses(levels: int = 3) -> list[dict]:
    return [
        {
            "orderId": 1000 + i,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "status": "NEW",
            "price": str(60000 + i * 1000),
            "avgPrice": "0.00",
            "executedQty": "0.00",
            "origQty": "0.02",
        }
        for i in range(levels)
    ]


# ---------------------------------------------------------------------------
# place-order — MARKET
# ---------------------------------------------------------------------------

class TestPlaceOrderMarket:
    @patch("cli.OrderManager")
    @patch("cli.BinanceClient")
    def test_market_order_success(self, MockClient, MockManager):
        mock_mgr = MagicMock()
        mock_mgr.place_market_order.return_value = _make_market_response()
        MockManager.return_value = mock_mgr

        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "BTCUSDT",
                "--side", "BUY",
                "--type", "MARKET",
                "--quantity", "0.01",
            ],
        )

        assert result.exit_code == 0
        assert "4812309" in result.output
        assert "FILLED" in result.output
        assert "✅" in result.output

    @patch("cli.OrderManager")
    @patch("cli.BinanceClient")
    def test_market_order_shows_request_summary(self, MockClient, MockManager):
        mock_mgr = MagicMock()
        mock_mgr.place_market_order.return_value = _make_market_response()
        MockManager.return_value = mock_mgr

        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "BTCUSDT",
                "--side", "BUY",
                "--type", "MARKET",
                "--quantity", "0.01",
            ],
        )

        assert "Order Request Summary" in result.output
        assert "BTCUSDT" in result.output
        assert "MARKET" in result.output


# ---------------------------------------------------------------------------
# place-order — LIMIT
# ---------------------------------------------------------------------------

class TestPlaceOrderLimit:
    @patch("cli.OrderManager")
    @patch("cli.BinanceClient")
    def test_limit_order_success(self, MockClient, MockManager):
        mock_mgr = MagicMock()
        mock_mgr.place_limit_order.return_value = _make_limit_response()
        MockManager.return_value = mock_mgr

        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "ETHUSDT",
                "--side", "SELL",
                "--type", "LIMIT",
                "--quantity", "0.5",
                "--price", "3200",
            ],
        )

        assert result.exit_code == 0
        assert "2309811" in result.output
        assert "NEW" in result.output
        assert "✅" in result.output

    def test_limit_order_missing_price_fails(self):
        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "ETHUSDT",
                "--side", "SELL",
                "--type", "LIMIT",
                "--quantity", "0.5",
                # --price intentionally omitted
            ],
        )

        assert result.exit_code != 0
        assert "❌" in result.output


# ---------------------------------------------------------------------------
# place-order — GRID
# ---------------------------------------------------------------------------

class TestPlaceOrderGrid:
    @patch("cli.OrderManager")
    @patch("cli.BinanceClient")
    def test_grid_order_success(self, MockClient, MockManager):
        mock_mgr = MagicMock()
        mock_mgr.place_grid_order.return_value = _make_grid_responses(3)
        MockManager.return_value = mock_mgr

        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "BTCUSDT",
                "--side", "BUY",
                "--type", "GRID",
                "--quantity", "0.06",
                "--price-low", "60000",
                "--price-high", "62000",
                "--grid-levels", "3",
            ],
        )

        assert result.exit_code == 0
        assert "Grid Order Levels" in result.output
        assert "✅" in result.output

    def test_grid_order_missing_price_low_fails(self):
        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "BTCUSDT",
                "--side", "BUY",
                "--type", "GRID",
                "--quantity", "0.06",
                "--price-high", "62000",
                # --price-low omitted
            ],
        )

        assert result.exit_code != 0
        assert "❌" in result.output


# ---------------------------------------------------------------------------
# place-order — Validation failures
# ---------------------------------------------------------------------------

class TestPlaceOrderValidation:
    def test_invalid_symbol_no_usdt_suffix(self):
        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "BTCBUSD",
                "--side", "BUY",
                "--type", "MARKET",
                "--quantity", "0.01",
            ],
        )
        assert result.exit_code != 0
        assert "❌" in result.output

    def test_invalid_side(self):
        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "BTCUSDT",
                "--side", "LONG",
                "--type", "MARKET",
                "--quantity", "0.01",
            ],
        )
        assert result.exit_code != 0
        assert "❌" in result.output

    def test_invalid_order_type(self):
        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "BTCUSDT",
                "--side", "BUY",
                "--type", "STOP",
                "--quantity", "0.01",
            ],
        )
        assert result.exit_code != 0
        assert "❌" in result.output

    def test_zero_quantity_fails(self):
        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "BTCUSDT",
                "--side", "BUY",
                "--type", "MARKET",
                "--quantity", "0",
            ],
        )
        assert result.exit_code != 0
        assert "❌" in result.output

    @patch("cli.OrderManager")
    @patch("cli.BinanceClient")
    def test_order_error_shows_failure(self, MockClient, MockManager):
        from bot.orders import OrderError
        mock_mgr = MagicMock()
        mock_mgr.place_market_order.side_effect = OrderError("Binance rejected the order")
        MockManager.return_value = mock_mgr

        result = runner.invoke(
            app,
            [
                "place-order",
                "--symbol", "BTCUSDT",
                "--side", "BUY",
                "--type", "MARKET",
                "--quantity", "0.01",
            ],
        )

        assert result.exit_code != 0
        assert "❌" in result.output
        assert "Binance rejected" in result.output

    def test_missing_env_vars_shows_config_error(self):
        """When credentials are missing, EnvironmentError is caught cleanly."""
        with patch("cli.BinanceClient", side_effect=EnvironmentError("Missing API key")):
            result = runner.invoke(
                app,
                [
                    "place-order",
                    "--symbol", "BTCUSDT",
                    "--side", "BUY",
                    "--type", "MARKET",
                    "--quantity", "0.01",
                ],
            )

        assert result.exit_code != 0
        assert "❌" in result.output
        assert "Configuration error" in result.output


# ---------------------------------------------------------------------------
# balance command
# ---------------------------------------------------------------------------

class TestBalance:
    @patch("cli.BinanceClient")
    def test_balance_displays_assets(self, MockClient):
        mock_instance = MagicMock()
        mock_instance.get_account_balance.return_value = [
            {
                "asset": "USDT",
                "balance": "10000.00000000",
                "availableBalance": "9985.12340000",
                "crossUnPnl": "0.00000000",
            }
        ]
        MockClient.return_value = mock_instance

        result = runner.invoke(app, ["balance"])

        assert result.exit_code == 0
        assert "USDT" in result.output
        assert "10000" in result.output
        assert "✅" in result.output

    @patch("cli.BinanceClient")
    def test_balance_empty_shows_no_assets_message(self, MockClient):
        mock_instance = MagicMock()
        mock_instance.get_account_balance.return_value = [
            {"asset": "USDT", "balance": "0.00", "availableBalance": "0.00", "crossUnPnl": "0.00"}
        ]
        MockClient.return_value = mock_instance

        result = runner.invoke(app, ["balance"])

        assert result.exit_code == 0
        assert "No funded" in result.output

    def test_balance_missing_env_shows_config_error(self):
        with patch("cli.BinanceClient", side_effect=EnvironmentError("Missing API key")):
            result = runner.invoke(app, ["balance"])

        assert result.exit_code != 0
        assert "❌" in result.output
        assert "Configuration error" in result.output
