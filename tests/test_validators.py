"""
tests/test_validators.py — Unit tests for bot.validators.Validator

Tests every public static method with both valid and invalid inputs.
No network calls; fully self-contained.
"""

import pytest

from bot.validators import Validator


# ---------------------------------------------------------------------------
# validate_symbol
# ---------------------------------------------------------------------------

class TestValidateSymbol:
    def test_valid_uppercase(self):
        assert Validator.validate_symbol("BTCUSDT") == "BTCUSDT"

    def test_valid_lowercase_normalised(self):
        assert Validator.validate_symbol("btcusdt") == "BTCUSDT"

    def test_valid_mixed_case(self):
        assert Validator.validate_symbol("EthUsdt") == "ETHUSDT"

    def test_valid_with_whitespace_stripped(self):
        assert Validator.validate_symbol("  BNBUSDT  ") == "BNBUSDT"

    def test_invalid_no_usdt_suffix(self):
        with pytest.raises(ValueError, match="USDT"):
            Validator.validate_symbol("BTCBUSD")

    def test_invalid_empty_string(self):
        with pytest.raises(ValueError):
            Validator.validate_symbol("")

    def test_invalid_whitespace_only(self):
        with pytest.raises(ValueError):
            Validator.validate_symbol("   ")

    def test_invalid_none_type(self):
        with pytest.raises(ValueError):
            Validator.validate_symbol(None)  # type: ignore


# ---------------------------------------------------------------------------
# validate_side
# ---------------------------------------------------------------------------

class TestValidateSide:
    def test_buy_uppercase(self):
        assert Validator.validate_side("BUY") == "BUY"

    def test_sell_uppercase(self):
        assert Validator.validate_side("SELL") == "SELL"

    def test_buy_lowercase_normalised(self):
        assert Validator.validate_side("buy") == "BUY"

    def test_sell_mixed_case_normalised(self):
        assert Validator.validate_side("Sell") == "SELL"

    def test_invalid_side(self):
        with pytest.raises(ValueError, match="BUY"):
            Validator.validate_side("LONG")

    def test_empty_side(self):
        with pytest.raises(ValueError):
            Validator.validate_side("")


# ---------------------------------------------------------------------------
# validate_order_type
# ---------------------------------------------------------------------------

class TestValidateOrderType:
    def test_market(self):
        assert Validator.validate_order_type("MARKET") == "MARKET"

    def test_limit(self):
        assert Validator.validate_order_type("limit") == "LIMIT"

    def test_grid(self):
        assert Validator.validate_order_type("Grid") == "GRID"

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="MARKET"):
            Validator.validate_order_type("STOP")

    def test_empty_type(self):
        with pytest.raises(ValueError):
            Validator.validate_order_type("")


# ---------------------------------------------------------------------------
# validate_quantity
# ---------------------------------------------------------------------------

class TestValidateQuantity:
    def test_integer_quantity(self):
        assert Validator.validate_quantity(1) == 1.0

    def test_float_quantity(self):
        assert Validator.validate_quantity(0.001) == pytest.approx(0.001)

    def test_string_quantity_parsed(self):
        assert Validator.validate_quantity("0.5") == pytest.approx(0.5)

    def test_max_decimal_places_exactly_six(self):
        assert Validator.validate_quantity(0.000001) == pytest.approx(0.000001)

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Validator.validate_quantity(0)

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Validator.validate_quantity(-1.5)

    def test_too_many_decimals_raises(self):
        with pytest.raises(ValueError, match="decimal"):
            Validator.validate_quantity(0.0000001)  # 7 decimal places

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="valid number"):
            Validator.validate_quantity("abc")


# ---------------------------------------------------------------------------
# validate_price
# ---------------------------------------------------------------------------

class TestValidatePrice:
    def test_valid_price(self):
        assert Validator.validate_price(3200.0) == pytest.approx(3200.0)

    def test_valid_price_as_string(self):
        assert Validator.validate_price("65000") == pytest.approx(65000.0)

    def test_zero_price_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Validator.validate_price(0)

    def test_negative_price_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Validator.validate_price(-100)

    def test_none_price_raises(self):
        with pytest.raises(ValueError, match="required"):
            Validator.validate_price(None)

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="valid number"):
            Validator.validate_price("free")


# ---------------------------------------------------------------------------
# validate_grid_params
# ---------------------------------------------------------------------------

class TestValidateGridParams:
    def test_valid_params(self):
        low, high, levels = Validator.validate_grid_params(60000, 65000, 5)
        assert low == pytest.approx(60000.0)
        assert high == pytest.approx(65000.0)
        assert levels == 5

    def test_min_grid_levels(self):
        _, _, levels = Validator.validate_grid_params(100, 200, 2)
        assert levels == 2

    def test_max_grid_levels(self):
        _, _, levels = Validator.validate_grid_params(100, 200, 20)
        assert levels == 20

    def test_price_low_equals_high_raises(self):
        with pytest.raises(ValueError, match="less than"):
            Validator.validate_grid_params(60000, 60000, 5)

    def test_price_low_greater_than_high_raises(self):
        with pytest.raises(ValueError, match="less than"):
            Validator.validate_grid_params(65000, 60000, 5)

    def test_grid_levels_too_low_raises(self):
        with pytest.raises(ValueError, match="between"):
            Validator.validate_grid_params(60000, 65000, 1)

    def test_grid_levels_too_high_raises(self):
        with pytest.raises(ValueError, match="between"):
            Validator.validate_grid_params(60000, 65000, 21)

    def test_string_grid_levels_parsed(self):
        _, _, levels = Validator.validate_grid_params(100, 200, "10")
        assert levels == 10

    def test_invalid_grid_levels_raises(self):
        with pytest.raises(ValueError):
            Validator.validate_grid_params(100, 200, "abc")
