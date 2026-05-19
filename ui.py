"""
Gradio web UI for the Binance Futures Testnet Trading Bot.

Provides a three-tab interface:

- Place Order: Place MARKET, LIMIT, or GRID orders using the existing
  bot.OrderManager and bot.Validator.
- Account Balance: Display futures account balances from BinanceClient.
- Order Log: Show the last 50 lines from logs/trading_bot.log.

Launch parameters: port=7860, share=False

This module is a thin UI layer only — all trading logic, validation and
API interactions are delegated to the bot package.

Usage:
    python ui.py

Requires: gradio
"""
from __future__ import annotations

import json
import logging
import os
import traceback
from typing import Any

import gradio as gr

from bot.client import BinanceClient
from bot.orders import OrderManager, OrderError
from bot.validators import Validator

# Local logger for the UI (keeps Gradio console output clean)
logger = logging.getLogger("trading_bot.ui")
logger.setLevel(logging.INFO)

# Path to the trading log used by the Order Log tab
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "trading_bot.log")

# Default symbol choices
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]


def _load_last_log_lines(path: str, max_lines: int = 50) -> str:
    """Return the last `max_lines` of a text file as a single string.

    If the file does not exist, a helpful message is returned instead.
    """
    if not os.path.exists(path):
        return f"Log file not found: {path}"

    try:
        with open(path, "r", encoding="utf-8") as fh:
            # Read file in a memory-efficient way: seek from end
            fh.seek(0, os.SEEK_END)
            filesize = fh.tell()
            block_size = 1024
            blocks = []
            lines_found = 0
            remaining = ""

            # Walk backwards in blocks until we have enough lines
            while filesize > 0 and lines_found < max_lines:
                read_size = min(block_size, filesize)
                fh.seek(filesize - read_size)
                data = fh.read(read_size)
                blocks.append(data)
                lines_found = ("".join(blocks)).count("\n")
                filesize -= read_size

            content = "".join(reversed(blocks))
            lines = content.splitlines()
            return "\n".join(lines[-max_lines:])
    except Exception as exc:  # pragma: no cover - defensive UI
        logger.exception("Failed to read log file: %s", exc)
        return f"Error reading log file: {exc}"


def _format_status(success: bool, message: str) -> str:
    """Return a compact status string with emoji for display in the UI."""
    if success:
        return f"✅ Success: {message}"
    return f"❌ Error: {message}"


def place_order_ui(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None,
    price_low: float | None,
    price_high: float | None,
    grid_levels: int,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, str]:
    """Callback for the "Place Order" button.

    Validates inputs using bot.validators.Validator and delegates order
    placement to bot.orders.OrderManager.

    Returns a tuple of (json_response, status_message) where json_response is
    either a dict (for single orders) or a list of dicts (for grid orders).
    """
    try:
        # Normalise and validate inputs
        symbol_norm = Validator.validate_symbol(symbol)
        side_norm = Validator.validate_side(side)
        order_type_norm = Validator.validate_order_type(order_type)
        qty_norm = Validator.validate_quantity(quantity)

        client = BinanceClient()
        manager = OrderManager(client)

        if order_type_norm == "MARKET":
            # MARKET ignores price
            response = manager.place_market_order(
                symbol=symbol_norm, side=side_norm, quantity=qty_norm
            )
            status = _format_status(True, f"Market order placed: {response.get('orderId')}")
            return response, status

        if order_type_norm == "LIMIT":
            prc = Validator.validate_price(price)
            response = manager.place_limit_order(
                symbol=symbol_norm, side=side_norm, quantity=qty_norm, price=prc
            )
            status = _format_status(True, f"Limit order placed: {response.get('orderId')} @ {response.get('price')}")
            return response, status

        # GRID
        low, high, levels = Validator.validate_grid_params(price_low, price_high, grid_levels)
        responses = manager.place_grid_order(
            symbol=symbol_norm,
            side=side_norm,
            quantity=qty_norm,
            price_low=low,
            price_high=high,
            grid_levels=levels,
        )
        # Count successes
        successes = sum(1 for r in responses if r.get("status") != "ERROR")
        status = _format_status(True, f"Grid placed: {successes}/{len(responses)} levels succeeded")
        return responses, status

    except ValueError as ve:
        # Validation error
        logger.warning("Validation failed in UI: %s", ve)
        return None, _format_status(False, str(ve))

    except OrderError as oe:
        # Order manager raised an OrderError (e.g., all grid levels failed)
        logger.error("Order manager error: %s", oe)
        return None, _format_status(False, str(oe))

    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error while placing order: %s", exc)
        tb = traceback.format_exc()
        return None, _format_status(False, f"Unexpected error: {exc}\n{tb}")


def refresh_balance_ui() -> tuple[list[list[Any]], list[str]]:
    """Callback to fetch account balances and return table rows and headers.

    Returns (rows, headers) suitable for gr.Dataframe.
    """
    try:
        client = BinanceClient()
        balances = client.get_account_balance()

        # We present a clean table with the most relevant columns
        headers = ["asset", "balance", "availableBalance"]
        rows = [
            [b.get("asset", ""), b.get("balance", ""), b.get("availableBalance", "")]
            for b in balances
        ]
        return rows, headers

    except Exception as exc:
        logger.exception("Failed to fetch balances: %s", exc)
        # Return a single-row table with the error message
        return [["ERROR", str(exc), ""]], ["asset", "balance", "availableBalance"]


def load_order_log_ui() -> str:
    """Return the last 50 lines of the trading log."""
    return _load_last_log_lines(LOG_FILE, max_lines=50)


def build_ui() -> gr.Blocks:
    """Construct and return the Gradio Blocks interface."""
    with gr.Blocks(title="Binance Futures Testnet — Trading Bot") as demo:
        gr.Markdown("# Binance Futures Testnet — Trading Bot UI")

        with gr.Tabs():
            # Place Order tab
            with gr.TabItem("Place Order"):
                with gr.Row():
                    symbol_input = gr.Dropdown(
                        choices=DEFAULT_SYMBOLS,
                        label="Symbol",
                        value=DEFAULT_SYMBOLS[0],
                        allow_custom_value=True,
                    )
                    side_input = gr.Radio(choices=["BUY", "SELL"], value="BUY", label="Side")

                with gr.Row():
                    order_type_input = gr.Radio(
                        choices=["MARKET", "LIMIT", "GRID"],
                        value="MARKET",
                        label="Order Type",
                    )

                with gr.Row():
                    qty_input = gr.Number(label="Quantity", value=0.001, precision=6)
                    price_input = gr.Number(label="Price (LIMIT only)", value=None, visible=False)

                # Grid-specific fields (each individually hideable)
                with gr.Row():
                    price_low_input = gr.Number(label="Price Low (GRID)", value=None, visible=False)
                    price_high_input = gr.Number(label="Price High (GRID)", value=None, visible=False)
                    grid_levels_slider = gr.Slider(minimum=2, maximum=20, step=1, value=5, label="Grid Levels", visible=False)

                place_btn = gr.Button("Place Order")

                with gr.Row():
                    json_out = gr.JSON(label="Response")
                    status_out = gr.Textbox(label="Status", interactive=False)

                # Dynamic visibility handler — update the price field and GRID fields
                def _on_order_type_change(order_type: str):
                    if order_type == "MARKET":
                        return (
                            gr.update(visible=False),  # price_input
                            gr.update(visible=False),  # price_low_input
                            gr.update(visible=False),  # price_high_input
                            gr.update(visible=False),  # grid_levels_slider
                        )
                    if order_type == "LIMIT":
                        return (
                            gr.update(visible=True),
                            gr.update(visible=False),
                            gr.update(visible=False),
                            gr.update(visible=False),
                        )
                    # GRID
                    return (
                        gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=True),
                        gr.update(visible=True),
                    )

                # Connect order type change to showing/hiding price and grid fields
                order_type_input.change(
                    fn=_on_order_type_change,
                    inputs=[order_type_input],
                    outputs=[price_input, price_low_input, price_high_input, grid_levels_slider],
                )

                # Connect place button
                def _on_place_click(
                    symbol, side, order_type, qty, price, price_low, price_high, grid_levels
                ):
                    result, status = place_order_ui(
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        quantity=qty,
                        price=price,
                        price_low=price_low,
                        price_high=price_high,
                        grid_levels=grid_levels,
                    )
                    # Ensure JSON component always receives serialisable data
                    return json.loads(json.dumps(result, default=str)), status

                place_btn.click(
                    fn=_on_place_click,
                    inputs=[
                        symbol_input,
                        side_input,
                        order_type_input,
                        qty_input,
                        price_input,
                        price_low_input,
                        price_high_input,
                        grid_levels_slider,
                    ],
                    outputs=[json_out, status_out],
                )

            # Account Balance tab
            with gr.TabItem("Account Balance"):
                refresh_btn = gr.Button("Refresh Balance")
                balance_df = gr.Dataframe(headers=["asset", "balance", "availableBalance"], datatype=["str", "str", "str"], interactive=False)

                refresh_btn.click(fn=refresh_balance_ui, inputs=[], outputs=[balance_df])

            # Order Log tab
            with gr.TabItem("Order Log"):
                load_btn = gr.Button("Load Recent Logs")
                log_box = gr.Textbox(label="Recent Log Lines", lines=20, interactive=False)

                load_btn.click(fn=load_order_log_ui, inputs=[], outputs=[log_box])

    return demo


if __name__ == "__main__":
    # Launch the app. Imports are local so running tests that import this
    # module won't auto-start the server.
    app = build_ui()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
