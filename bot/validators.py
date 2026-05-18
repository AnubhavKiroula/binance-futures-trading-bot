"""
validators.py — Input validation logic for the trading bot.

All validation is exposed as static methods on :class:`Validator`.
Each method raises :class:`ValueError` with a human-readable message on
failure and returns the normalised / coerced value on success so that
callers receive clean data.
"""

from __future__ import annotations

from bot.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_SIDES = {"BUY", "SELL"}
_VALID_ORDER_TYPES = {"MARKET", "LIMIT", "GRID"}
_MIN_GRID_LEVELS = 2
_MAX_GRID_LEVELS = 20
_MAX_QTY_DECIMALS = 6


class Validator:
    """
    Stateless collection of input validators for trading parameters.

    All methods are ``@staticmethod`` so they can be called without
    instantiating the class::

        from bot.validators import Validator

        symbol = Validator.validate_symbol("btcusdt")      # → "BTCUSDT"
        side   = Validator.validate_side("buy")            # → "BUY"
    """

    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """
        Validate and normalise a futures trading symbol.

        Rules
        -----
        - Must be a non-empty string.
        - Converted to uppercase for comparison.
        - Must end with ``"USDT"`` (USDT-M futures only).

        Parameters
        ----------
        symbol:
            Raw symbol string from user input, e.g. ``"btcusdt"``.

        Returns
        -------
        str
            Uppercased symbol, e.g. ``"BTCUSDT"``.

        Raises
        ------
        ValueError
            If the symbol is empty or does not end with ``USDT``.
        """
        if not symbol or not isinstance(symbol, str):
            raise ValueError(
                "Symbol must be a non-empty string (e.g. 'BTCUSDT')."
            )

        normalised = symbol.strip().upper()

        if not normalised:
            raise ValueError(
                "Symbol must be a non-empty string (e.g. 'BTCUSDT')."
            )

        if not normalised.endswith("USDT"):
            raise ValueError(
                f"Invalid symbol '{normalised}'. "
                "Only USDT-M perpetual futures are supported "
                "(symbol must end with 'USDT', e.g. 'BTCUSDT')."
            )

        logger.debug("validate_symbol OK | raw=%r → %r", symbol, normalised)
        return normalised

    @staticmethod
    def validate_side(side: str) -> str:
        """
        Validate and normalise an order side.

        Parameters
        ----------
        side:
            ``"BUY"`` or ``"SELL"`` (case-insensitive).

        Returns
        -------
        str
            Uppercased side: ``"BUY"`` or ``"SELL"``.

        Raises
        ------
        ValueError
            If the side is not ``BUY`` or ``SELL``.
        """
        if not side or not isinstance(side, str):
            raise ValueError("Side must be 'BUY' or 'SELL'.")

        normalised = side.strip().upper()

        if normalised not in _VALID_SIDES:
            raise ValueError(
                f"Invalid side '{side}'. Must be one of: "
                + ", ".join(sorted(_VALID_SIDES))
                + "."
            )

        logger.debug("validate_side OK | raw=%r → %r", side, normalised)
        return normalised

    @staticmethod
    def validate_order_type(order_type: str) -> str:
        """
        Validate and normalise an order type.

        Parameters
        ----------
        order_type:
            ``"MARKET"``, ``"LIMIT"``, or ``"GRID"`` (case-insensitive).

        Returns
        -------
        str
            Uppercased order type.

        Raises
        ------
        ValueError
            If the type is not one of the supported values.
        """
        if not order_type or not isinstance(order_type, str):
            raise ValueError(
                "Order type must be one of: MARKET, LIMIT, GRID."
            )

        normalised = order_type.strip().upper()

        if normalised not in _VALID_ORDER_TYPES:
            raise ValueError(
                f"Invalid order type '{order_type}'. Must be one of: "
                + ", ".join(sorted(_VALID_ORDER_TYPES))
                + "."
            )

        logger.debug(
            "validate_order_type OK | raw=%r → %r", order_type, normalised
        )
        return normalised

    @staticmethod
    def validate_quantity(quantity: float | int | str) -> float:
        """
        Validate an order quantity.

        Rules
        -----
        - Must be convertible to ``float``.
        - Must be strictly positive (``> 0``).
        - Must have at most 6 decimal places.

        Parameters
        ----------
        quantity:
            The desired order quantity.

        Returns
        -------
        float
            The validated quantity as a Python float.

        Raises
        ------
        ValueError
            If the quantity fails any of the rules above.
        """
        try:
            qty = float(quantity)
        except (TypeError, ValueError):
            raise ValueError(
                f"Quantity '{quantity}' is not a valid number."
            )

        if qty <= 0:
            raise ValueError(
                f"Quantity must be a positive number greater than 0 "
                f"(got {qty})."
            )

        # Check decimal places by inspecting the string representation
        qty_str = f"{qty:.10f}".rstrip("0")
        if "." in qty_str:
            decimals = len(qty_str.split(".")[1])
            if decimals > _MAX_QTY_DECIMALS:
                raise ValueError(
                    f"Quantity '{qty}' has {decimals} decimal places. "
                    f"Maximum allowed is {_MAX_QTY_DECIMALS}."
                )

        logger.debug("validate_quantity OK | value=%s", qty)
        return qty

    @staticmethod
    def validate_price(price: float | int | str | None) -> float:
        """
        Validate an order price.

        Rules
        -----
        - Must not be ``None`` or missing (callers are responsible for
          checking optionality before calling this method).
        - Must be convertible to ``float``.
        - Must be strictly positive (``> 0``).

        Parameters
        ----------
        price:
            The desired limit/grid price.

        Returns
        -------
        float
            The validated price as a Python float.

        Raises
        ------
        ValueError
            If the price is ``None``, non-numeric, or non-positive.
        """
        if price is None:
            raise ValueError(
                "Price is required for LIMIT and GRID orders."
            )

        try:
            prc = float(price)
        except (TypeError, ValueError):
            raise ValueError(
                f"Price '{price}' is not a valid number."
            )

        if prc <= 0:
            raise ValueError(
                f"Price must be a positive number greater than 0 "
                f"(got {prc})."
            )

        logger.debug("validate_price OK | value=%s", prc)
        return prc

    @staticmethod
    def validate_grid_params(
        price_low: float | int | str,
        price_high: float | int | str,
        grid_levels: int | str,
    ) -> tuple[float, float, int]:
        """
        Validate grid order parameters.

        Rules
        -----
        - ``price_low`` and ``price_high`` must each pass
          :meth:`validate_price`.
        - ``price_low`` must be strictly less than ``price_high``.
        - ``grid_levels`` must be an integer between
          :data:`_MIN_GRID_LEVELS` (2) and :data:`_MAX_GRID_LEVELS` (20).

        Parameters
        ----------
        price_low:
            Lower bound of the grid price range.
        price_high:
            Upper bound of the grid price range.
        grid_levels:
            Number of grid levels (orders) to create.

        Returns
        -------
        tuple[float, float, int]
            ``(price_low, price_high, grid_levels)`` as native Python types.

        Raises
        ------
        ValueError
            If any parameter violates the rules above.
        """
        low = Validator.validate_price(price_low)
        high = Validator.validate_price(price_high)

        if low >= high:
            raise ValueError(
                f"price_low ({low}) must be strictly less than "
                f"price_high ({high})."
            )

        try:
            levels = int(grid_levels)
        except (TypeError, ValueError):
            raise ValueError(
                f"grid_levels '{grid_levels}' is not a valid integer."
            )

        if not (_MIN_GRID_LEVELS <= levels <= _MAX_GRID_LEVELS):
            raise ValueError(
                f"grid_levels must be between {_MIN_GRID_LEVELS} and "
                f"{_MAX_GRID_LEVELS} (got {levels})."
            )

        logger.debug(
            "validate_grid_params OK | low=%s high=%s levels=%s",
            low,
            high,
            levels,
        )
        return low, high, levels
