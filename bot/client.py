"""
client.py — Authenticated Binance Futures Testnet client wrapper.

Wraps ``python-binance``'s synchronous :class:`binance.Client` and exposes
a clean, bot-facing API with structured DEBUG logging on every request and
response.

Environment variables required (loaded via ``python-dotenv`` before import):
  BINANCE_API_KEY    — Testnet API key
  BINANCE_API_SECRET — Testnet API secret
"""

import os
from typing import Any

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv

from bot.logging_config import get_logger

# ---------------------------------------------------------------------------
# Module-level setup
# ---------------------------------------------------------------------------

load_dotenv()
logger = get_logger(__name__)

# Binance Futures Testnet REST base URL
_TESTNET_BASE_URL = "https://testnet.binancefuture.com"


class BinanceClient:
    """
    Thin, logging-aware wrapper around the python-binance ``Client``.

    The client is pre-configured to target the **USDT-M Futures Testnet**
    (``https://testnet.binancefuture.com``).  API credentials are read
    exclusively from environment variables so that secrets are never
    present in source code.

    Attributes
    ----------
    _client : binance.Client
        The underlying python-binance client instance.

    Raises
    ------
    EnvironmentError
        If ``BINANCE_API_KEY`` or ``BINANCE_API_SECRET`` are absent from
        the environment / ``.env`` file.
    """

    def __init__(self) -> None:
        """
        Initialise the client using environment variables.

        Reads ``BINANCE_API_KEY`` and ``BINANCE_API_SECRET`` from the
        environment (populated via ``python-dotenv``).

        Raises
        ------
        EnvironmentError
            When either credential is missing or empty.
        """
        api_key = os.getenv("BINANCE_API_KEY", "").strip()
        api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

        if not api_key or not api_secret:
            raise EnvironmentError(
                "BINANCE_API_KEY and BINANCE_API_SECRET must be set in your "
                ".env file before starting the bot."
            )

        logger.debug(
            "Initialising BinanceClient | base_url=%s | key_prefix=%s…",
            _TESTNET_BASE_URL,
            api_key[:6],
        )

        self._client: Client = Client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=False,          # we point manually to the futures testnet
        )

        # Override the futures base URL to the USDT-M testnet endpoint.
        # python-binance uses FUTURES_URL internally for futures endpoints.
        self._client.FUTURES_URL = f"{_TESTNET_BASE_URL}/fapi"

        logger.info(
            "BinanceClient ready | endpoint=%s/fapi", _TESTNET_BASE_URL
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """
        Retrieve exchange info for a single futures symbol.

        Useful for validating that a symbol exists on the testnet before
        placing orders.

        Parameters
        ----------
        symbol:
            Trading pair, e.g. ``"BTCUSDT"``.

        Returns
        -------
        dict
            Raw symbol info dict from the Binance Futures exchange info
            endpoint, e.g.::

                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    ...
                }

        Raises
        ------
        BinanceAPIException
            On any API-level error (invalid symbol, rate limit, etc.).
        ValueError
            If the symbol is not found in the exchange info.
        """
        logger.debug("REQUEST get_symbol_info | symbol=%s", symbol)

        try:
            exchange_info: dict = self._client.futures_exchange_info()
        except (BinanceAPIException, BinanceRequestException) as exc:
            logger.error(
                "RESPONSE get_symbol_info FAILED | symbol=%s | error=%s",
                symbol,
                exc,
            )
            raise

        symbols: list[dict] = exchange_info.get("symbols", [])
        for sym in symbols:
            if sym.get("symbol") == symbol:
                logger.debug(
                    "RESPONSE get_symbol_info OK | symbol=%s | status=%s",
                    symbol,
                    sym.get("status"),
                )
                return sym

        raise ValueError(
            f"Symbol '{symbol}' not found on the Binance Futures Testnet. "
            "Check the symbol name and try again."
        )

    def get_account_balance(self) -> list[dict[str, Any]]:
        """
        Retrieve futures account asset balances.

        Returns
        -------
        list[dict]
            List of asset balance dicts, e.g.::

                [
                    {
                        "asset": "USDT",
                        "balance": "10000.00000000",
                        "availableBalance": "9985.12340000",
                        ...
                    },
                    ...
                ]

        Raises
        ------
        BinanceAPIException
            On any API-level error.
        """
        logger.debug("REQUEST get_account_balance")

        try:
            balances: list[dict] = self._client.futures_account_balance()
        except (BinanceAPIException, BinanceRequestException) as exc:
            logger.error(
                "RESPONSE get_account_balance FAILED | error=%s", exc
            )
            raise

        logger.debug(
            "RESPONSE get_account_balance OK | assets=%d",
            len(balances),
        )
        return balances

    # ------------------------------------------------------------------
    # Internal — expose the raw client for OrderManager usage
    # ------------------------------------------------------------------

    @property
    def raw(self) -> Client:
        """
        Return the underlying :class:`binance.Client` instance.

        Intended for use by :class:`bot.orders.OrderManager` which needs
        direct access to futures order placement methods.

        Returns
        -------
        binance.Client
        """
        return self._client
