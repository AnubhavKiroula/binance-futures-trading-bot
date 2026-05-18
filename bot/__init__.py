"""
bot package — Binance Futures Testnet trading bot core.

Exposes the main public API surface:
  - BinanceClient  : authenticated API wrapper
  - OrderManager   : order placement logic
  - Validator      : input validation helpers
  - OrderError     : custom exception for order failures
  - get_logger     : logging factory function
"""

from bot.client import BinanceClient
from bot.orders import OrderManager, OrderError
from bot.validators import Validator
from bot.logging_config import get_logger

__all__ = [
    "BinanceClient",
    "OrderManager",
    "OrderError",
    "Validator",
    "get_logger",
]
