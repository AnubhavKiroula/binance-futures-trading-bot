"""
orders.py — Order placement logic for Binance Futures Testnet.

Implements :class:`OrderManager` which wraps a :class:`bot.client.BinanceClient`
and provides three order placement strategies:

  - Market orders  (:meth:`OrderManager.place_market_order`)
  - Limit orders   (:meth:`OrderManager.place_limit_order`)
  - Grid orders    (:meth:`OrderManager.place_grid_order`)

Custom Exceptions
-----------------
:class:`OrderError`
    Raised whenever an individual order placement fails.  The original
    exception is always chained (``raise OrderError(...) from exc``) to
    preserve the full traceback for debugging.
"""

from __future__ import annotations

import math
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException

from bot.client import BinanceClient
from bot.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class OrderError(Exception):
    """
    Raised by :class:`OrderManager` when an order placement fails.

    Attributes
    ----------
    message : str
        Human-readable description of what went wrong.
    raw_error : Exception | None
        The original exception from the Binance client, if available.
    """

    def __init__(
        self, message: str, raw_error: Exception | None = None
    ) -> None:
        super().__init__(message)
        self.raw_error = raw_error

    def __str__(self) -> str:  # pragma: no cover
        base = super().__str__()
        if self.raw_error:
            return f"{base} | underlying error: {self.raw_error}"
        return base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _standardise_response(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a raw Binance futures order response into a canonical dict.

    The canonical schema is::

        {
            "orderId":     int,
            "symbol":      str,
            "side":        str,   # "BUY" | "SELL"
            "type":        str,   # "MARKET" | "LIMIT"
            "status":      str,   # "NEW" | "FILLED" | ...
            "price":       str,   # limit price ("0" for MARKET)
            "avgPrice":    str,   # average fill price
            "executedQty": str,   # quantity actually filled
            "origQty":     str,   # quantity requested
        }

    Parameters
    ----------
    raw:
        Raw dict returned by python-binance futures order methods.

    Returns
    -------
    dict
        Standardised response with the fields listed above.
    """
    return {
        "orderId":     raw.get("orderId", "N/A"),
        "symbol":      raw.get("symbol", ""),
        "side":        raw.get("side", ""),
        "type":        raw.get("type", ""),
        "status":      raw.get("status", ""),
        "price":       raw.get("price", "0"),
        "avgPrice":    raw.get("avgPrice", "0"),
        "executedQty": raw.get("executedQty", "0"),
        "origQty":     raw.get("origQty", "0"),
    }


# ---------------------------------------------------------------------------
# OrderManager
# ---------------------------------------------------------------------------


class OrderManager:
    """
    High-level order placement manager for Binance USDT-M Futures Testnet.

    Wraps a :class:`bot.client.BinanceClient` and provides methods for
    placing market, limit, and grid orders with full request/response logging
    and structured error handling.

    Parameters
    ----------
    client : BinanceClient
        An authenticated, testnet-configured client instance.
    """

    def __init__(self, client: BinanceClient) -> None:
        """
        Store the client reference.

        Parameters
        ----------
        client : BinanceClient
            Authenticated Binance Futures Testnet client.
        """
        self._client = client

    # ------------------------------------------------------------------
    # Market orders
    # ------------------------------------------------------------------

    def place_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> dict[str, Any]:
        """
        Place a **MARKET** order on the Binance Futures Testnet.

        The order is filled immediately at the best available market price.

        Parameters
        ----------
        symbol : str
            Trading pair, e.g. ``"BTCUSDT"``.  Should already be validated
            and uppercased.
        side : str
            ``"BUY"`` or ``"SELL"``.
        quantity : float
            Number of contracts / base-asset units to trade.

        Returns
        -------
        dict
            Standardised order response (see :func:`_standardise_response`).

        Raises
        ------
        OrderError
            If the Binance API returns an error or the request times out.
        """
        request_params = {
            "symbol":   symbol,
            "side":     side,
            "type":     "MARKET",
            "quantity": quantity,
        }

        logger.info(
            "ORDER REQUEST MARKET | symbol=%s side=%s qty=%s",
            symbol,
            side,
            quantity,
        )
        logger.debug("ORDER REQUEST full payload | %s", request_params)

        try:
            raw: dict = self._client.raw.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
            )
        except (BinanceAPIException, BinanceRequestException) as exc:
            logger.error(
                "ORDER FAILED MARKET | symbol=%s side=%s qty=%s | error=%s",
                symbol,
                side,
                quantity,
                exc,
            )
            raise OrderError(
                f"Market order failed for {symbol}: {exc}", raw_error=exc
            ) from exc

        response = _standardise_response(raw)

        logger.debug("ORDER RESPONSE MARKET raw | %s", raw)
        logger.info(
            "ORDER FILLED MARKET | orderId=%s symbol=%s status=%s "
            "executedQty=%s avgPrice=%s",
            response["orderId"],
            response["symbol"],
            response["status"],
            response["executedQty"],
            response["avgPrice"],
        )

        return response

    # ------------------------------------------------------------------
    # Limit orders
    # ------------------------------------------------------------------

    def place_limit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> dict[str, Any]:
        """
        Place a **LIMIT GTC** order on the Binance Futures Testnet.

        The order sits in the book until filled or cancelled
        (``timeInForce=GTC``).

        Parameters
        ----------
        symbol : str
            Trading pair, e.g. ``"ETHUSDT"``.
        side : str
            ``"BUY"`` or ``"SELL"``.
        quantity : float
            Number of contracts / base-asset units.
        price : float
            Limit price at which to open the position.

        Returns
        -------
        dict
            Standardised order response.

        Raises
        ------
        OrderError
            If the Binance API returns an error or the request times out.
        """
        request_params = {
            "symbol":      symbol,
            "side":        side,
            "type":        "LIMIT",
            "quantity":    quantity,
            "price":       price,
            "timeInForce": "GTC",
        }

        logger.info(
            "ORDER REQUEST LIMIT | symbol=%s side=%s qty=%s price=%s",
            symbol,
            side,
            quantity,
            price,
        )
        logger.debug("ORDER REQUEST full payload | %s", request_params)

        try:
            raw: dict = self._client.raw.futures_create_order(
                symbol=symbol,
                side=side,
                type="LIMIT",
                quantity=quantity,
                price=price,
                timeInForce="GTC",
            )
        except (BinanceAPIException, BinanceRequestException) as exc:
            logger.error(
                "ORDER FAILED LIMIT | symbol=%s side=%s qty=%s price=%s "
                "| error=%s",
                symbol,
                side,
                quantity,
                price,
                exc,
            )
            raise OrderError(
                f"Limit order failed for {symbol} @ {price}: {exc}",
                raw_error=exc,
            ) from exc

        response = _standardise_response(raw)

        logger.debug("ORDER RESPONSE LIMIT raw | %s", raw)
        logger.info(
            "ORDER PLACED LIMIT | orderId=%s symbol=%s status=%s "
            "price=%s qty=%s",
            response["orderId"],
            response["symbol"],
            response["status"],
            response["price"],
            response["origQty"],
        )

        return response

    # ------------------------------------------------------------------
    # Grid orders
    # ------------------------------------------------------------------

    def place_grid_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price_low: float,
        price_high: float,
        grid_levels: int,
    ) -> list[dict[str, Any]]:
        """
        Place a series of evenly-spaced **LIMIT GTC** orders (grid strategy).

        The total ``quantity`` is split evenly across ``grid_levels`` orders.
        Prices are distributed uniformly between ``price_low`` and
        ``price_high`` (inclusive of both endpoints).

        If an individual level fails, the error is logged and the method
        continues placing the remaining levels — partial grids are
        acceptable.

        Parameters
        ----------
        symbol : str
            Trading pair, e.g. ``"BTCUSDT"``.
        side : str
            ``"BUY"`` or ``"SELL"``.
        quantity : float
            **Total** quantity to distribute across all grid levels.
        price_low : float
            Lowest price in the grid.
        price_high : float
            Highest price in the grid.
        grid_levels : int
            Number of grid levels (i.e. individual limit orders).

        Returns
        -------
        list[dict]
            List of standardised order responses, one per successfully placed
            level.  Failed levels produce an error-status placeholder dict
            instead of raising, so the list length always equals
            ``grid_levels``.

        Raises
        ------
        OrderError
            Only raised if *all* grid levels fail (total failure).
        """
        logger.info(
            "GRID ORDER START | symbol=%s side=%s total_qty=%s "
            "low=%s high=%s levels=%s",
            symbol,
            side,
            quantity,
            price_low,
            price_high,
            grid_levels,
        )

        # Calculate per-level quantity (rounded to 6 dp to satisfy Binance)
        qty_per_level = round(quantity / grid_levels, 6)

        # Generate evenly-spaced price points
        step = (price_high - price_low) / (grid_levels - 1)
        prices = [
            round(price_low + i * step, 8) for i in range(grid_levels)
        ]

        responses: list[dict[str, Any]] = []
        failures = 0

        for level_idx, level_price in enumerate(prices, start=1):
            logger.info(
                "GRID LEVEL %d/%d | symbol=%s side=%s qty=%s price=%s",
                level_idx,
                grid_levels,
                symbol,
                side,
                qty_per_level,
                level_price,
            )

            try:
                response = self.place_limit_order(
                    symbol=symbol,
                    side=side,
                    quantity=qty_per_level,
                    price=level_price,
                )
                responses.append(response)
                logger.info(
                    "GRID LEVEL %d/%d SUCCESS | orderId=%s",
                    level_idx,
                    grid_levels,
                    response.get("orderId"),
                )

            except OrderError as exc:
                failures += 1
                logger.error(
                    "GRID LEVEL %d/%d FAILED | symbol=%s price=%s | %s",
                    level_idx,
                    grid_levels,
                    symbol,
                    level_price,
                    exc,
                )
                # Append a failure placeholder so callers can report per-level
                responses.append(
                    {
                        "orderId":     "FAILED",
                        "symbol":      symbol,
                        "side":        side,
                        "type":        "LIMIT",
                        "status":      "ERROR",
                        "price":       str(level_price),
                        "avgPrice":    "0",
                        "executedQty": "0",
                        "origQty":     str(qty_per_level),
                        "error":       str(exc),
                    }
                )

        if failures == grid_levels:
            raise OrderError(
                f"All {grid_levels} grid levels failed for {symbol}. "
                "No orders were placed. Check logs for details."
            )

        success_count = grid_levels - failures
        logger.info(
            "GRID ORDER COMPLETE | symbol=%s placed=%d/%d failed=%d",
            symbol,
            success_count,
            grid_levels,
            failures,
        )

        return responses
