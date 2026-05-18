"""
cli.py — Command-line interface for the Binance Futures Trading Bot.

Entry point for all user-facing operations:

  python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
  python cli.py balance

Uses Typer for argument parsing and Rich (bundled with typer[all]) for
pretty console output.  All exceptions from the bot layer are caught here;
users never see a raw traceback.
"""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from bot.client import BinanceClient
from bot.orders import OrderManager, OrderError
from bot.validators import Validator
from bot.logging_config import get_logger

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="trading_bot",
    help=(
        "Binance USDT-M Futures Testnet trading bot.\n\n"
        "Commands: place-order, balance"
    ),
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()
err_console = Console(stderr=True, style="bold red")
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers — pretty output
# ---------------------------------------------------------------------------


def _print_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float],
    price_low: Optional[float],
    price_high: Optional[float],
    grid_levels: int,
) -> None:
    """Render a formatted 'Order Request Summary' panel to the console."""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Symbol", symbol)
    table.add_row("Side", side)
    table.add_row("Order Type", order_type)
    table.add_row("Quantity", str(quantity))

    if order_type == "LIMIT":
        table.add_row("Price (USDT)", str(price))
    elif order_type == "GRID":
        table.add_row("Price Low (USDT)", str(price_low))
        table.add_row("Price High (USDT)", str(price_high))
        table.add_row("Grid Levels", str(grid_levels))

    console.print(
        Panel(table, title="[bold yellow]Order Request Summary[/bold yellow]", border_style="yellow")
    )


def _print_single_response(response: dict) -> None:
    """Render a formatted 'Order Response' panel for a single order."""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    avg = response.get("avgPrice", "0")
    avg_display = avg if float(avg) > 0 else "N/A"

    table.add_row("Order ID", str(response.get("orderId", "N/A")))
    table.add_row("Status", response.get("status", "N/A"))
    table.add_row("Executed Qty", response.get("executedQty", "N/A"))
    table.add_row("Avg Price (USDT)", avg_display)
    table.add_row("Order Type", response.get("type", "N/A"))
    table.add_row("Side", response.get("side", "N/A"))
    table.add_row("Symbol", response.get("symbol", "N/A"))

    console.print(
        Panel(table, title="[bold green]Order Response[/bold green]", border_style="green")
    )


def _print_grid_response(responses: list[dict]) -> None:
    """Render a formatted table of all grid level responses."""
    table = Table(
        title="Grid Order Levels",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold magenta",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Order ID", style="cyan")
    table.add_column("Price (USDT)", style="yellow")
    table.add_column("Quantity", style="white")
    table.add_column("Status", style="bold")

    for idx, resp in enumerate(responses, start=1):
        status = resp.get("status", "N/A")
        status_styled = (
            f"[green]{status}[/green]"
            if status not in ("ERROR", "FAILED")
            else f"[red]{status}[/red]"
        )
        table.add_row(
            str(idx),
            str(resp.get("orderId", "N/A")),
            resp.get("price", "N/A"),
            resp.get("origQty", "N/A"),
            status_styled,
        )

    console.print(table)


def _success(message: str) -> None:
    """Print a green SUCCESS line."""
    console.print(
        typer.style(f"\n✅  {message}", fg=typer.colors.GREEN, bold=True)
    )


def _failure(message: str) -> None:
    """Print a red FAILURE line."""
    console.print(
        typer.style(f"\n❌  {message}", fg=typer.colors.RED, bold=True)
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command(name="place-order")
def place_order(
    symbol: str = typer.Option(
        ...,
        "--symbol",
        help="Trading pair, e.g. BTCUSDT",
        show_default=False,
    ),
    side: str = typer.Option(
        ...,
        "--side",
        help="BUY or SELL",
        show_default=False,
    ),
    order_type: str = typer.Option(
        ...,
        "--type",
        help="MARKET, LIMIT, or GRID",
        show_default=False,
    ),
    quantity: float = typer.Option(
        ...,
        "--quantity",
        help="Order quantity (base asset)",
        show_default=False,
    ),
    price: Optional[float] = typer.Option(
        None,
        "--price",
        help="Limit price in USDT (required for LIMIT and GRID)",
    ),
    price_low: Optional[float] = typer.Option(
        None,
        "--price-low",
        help="Lower price bound (required for GRID)",
    ),
    price_high: Optional[float] = typer.Option(
        None,
        "--price-high",
        help="Upper price bound (required for GRID)",
    ),
    grid_levels: int = typer.Option(
        5,
        "--grid-levels",
        help="Number of grid levels, 2–20 (GRID only)",
        min=2,
        max=20,
    ),
) -> None:
    """
    Place a MARKET, LIMIT, or GRID order on the Binance Futures Testnet.

    [bold]Examples:[/bold]

      Market BUY 0.01 BTC:
        python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

      Limit SELL 0.5 ETH at 3200 USDT:
        python cli.py place-order --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.5 --price 3200

      Grid BUY 0.1 BTC across 5 levels (60000–65000 USDT):
        python cli.py place-order --symbol BTCUSDT --side BUY --type GRID --quantity 0.1 --price-low 60000 --price-high 65000 --grid-levels 5
    """
    logger.info(
        "CLI place-order invoked | symbol=%s side=%s type=%s qty=%s",
        symbol, side, order_type, quantity,
    )

    try:
        # ----------------------------------------------------------------
        # Validate all inputs before touching the network
        # ----------------------------------------------------------------
        symbol = Validator.validate_symbol(symbol)
        side = Validator.validate_side(side)
        order_type = Validator.validate_order_type(order_type)
        quantity = Validator.validate_quantity(quantity)

        if order_type == "LIMIT":
            if price is None:
                raise ValueError(
                    "A --price is required for LIMIT orders."
                )
            price = Validator.validate_price(price)

        elif order_type == "GRID":
            if price_low is None or price_high is None:
                raise ValueError(
                    "--price-low and --price-high are both required for GRID orders."
                )
            price_low, price_high, grid_levels = Validator.validate_grid_params(
                price_low, price_high, grid_levels
            )

        # ----------------------------------------------------------------
        # Print request summary
        # ----------------------------------------------------------------
        _print_request_summary(
            symbol, side, order_type, quantity,
            price, price_low, price_high, grid_levels,
        )

        # ----------------------------------------------------------------
        # Execute order(s)
        # ----------------------------------------------------------------
        client = BinanceClient()
        manager = OrderManager(client)

        if order_type == "MARKET":
            response = manager.place_market_order(symbol, side, quantity)
            _print_single_response(response)
            _success(
                f"Market {side} order placed successfully! "
                f"orderId={response['orderId']}  status={response['status']}"
            )

        elif order_type == "LIMIT":
            response = manager.place_limit_order(symbol, side, quantity, price)
            _print_single_response(response)
            _success(
                f"Limit {side} order placed successfully! "
                f"orderId={response['orderId']}  status={response['status']}"
            )

        elif order_type == "GRID":
            responses = manager.place_grid_order(
                symbol, side, quantity, price_low, price_high, grid_levels
            )
            _print_grid_response(responses)

            placed = sum(1 for r in responses if r.get("status") != "ERROR")
            failed = len(responses) - placed

            if failed == 0:
                _success(
                    f"Grid order complete — {placed}/{grid_levels} levels placed."
                )
            else:
                console.print(
                    typer.style(
                        f"\n⚠️   Grid order partial — {placed}/{grid_levels} levels placed, "
                        f"{failed} failed. Check logs for details.",
                        fg=typer.colors.YELLOW,
                        bold=True,
                    )
                )

    except ValueError as exc:
        logger.warning("Validation error: %s", exc)
        _failure(f"Validation error: {exc}")
        raise typer.Exit(code=1)

    except OrderError as exc:
        logger.error("Order failed: %s", exc)
        _failure(f"Order failed: {exc}")
        raise typer.Exit(code=1)

    except EnvironmentError as exc:
        logger.error("Configuration error: %s", exc)
        _failure(f"Configuration error: {exc}")
        raise typer.Exit(code=1)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during place-order")
        _failure(f"Unexpected error: {exc}")
        raise typer.Exit(code=1)


@app.command(name="balance")
def balance() -> None:
    """
    Display current USDT-M Futures Testnet account balances.

    Only assets with a non-zero balance are shown.  Run this command to
    confirm your testnet wallet is funded before placing orders.

    [bold]Example:[/bold]

      python cli.py balance
    """
    logger.info("CLI balance invoked")

    try:
        client = BinanceClient()
        raw_balances = client.get_account_balance()

        # Filter to non-zero balances for readability
        active = [b for b in raw_balances if float(b.get("balance", 0)) != 0]

        if not active:
            console.print(
                Panel(
                    "[dim]No funded assets found on the Futures Testnet.[/dim]",
                    title="[bold yellow]Account Balance[/bold yellow]",
                    border_style="yellow",
                )
            )
            return

        table = Table(
            box=box.ROUNDED,
            show_lines=True,
            header_style="bold cyan",
        )
        table.add_column("Asset", style="bold white", no_wrap=True)
        table.add_column("Wallet Balance", style="yellow", justify="right")
        table.add_column("Available Balance", style="green", justify="right")
        table.add_column("Unrealised PnL", style="magenta", justify="right")

        for asset in active:
            table.add_row(
                asset.get("asset", ""),
                asset.get("balance", "0"),
                asset.get("availableBalance", "0"),
                asset.get("crossUnPnl", "0"),
            )

        console.print(
            Panel(
                table,
                title="[bold yellow]Account Balance — Binance Futures Testnet[/bold yellow]",
                border_style="yellow",
            )
        )
        _success("Balance fetched successfully.")

    except EnvironmentError as exc:
        logger.error("Configuration error: %s", exc)
        _failure(f"Configuration error: {exc}")
        raise typer.Exit(code=1)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during balance fetch")
        _failure(f"Unexpected error: {exc}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
