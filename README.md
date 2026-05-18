# Binance Futures Trading Bot

A production-quality Python trading bot for the **Binance USDT-M Futures Testnet**.
Features a clean CLI interface, a Gradio web UI, market/limit/grid order placement,
structured logging, and rigorous input validation — all built with readability and
maintainability in mind.

---

## 1. Project Overview

| Feature | Details |
|---------|---------|
| Exchange | Binance Futures Testnet (USDT-M Perpetuals) |
| Base URL | `https://testnet.binancefuture.com` |
| Order types | Market, Limit (GTC), Grid (multi-level Limit) |
| Interfaces | CLI (`typer`) · Gradio web UI |
| Logging | Rotating file (DEBUG+) + console (INFO+) |
| Auth | `.env` file — credentials never hardcoded |

---

## 2. Setup

### Prerequisites
- Python 3.11+
- A [Binance Futures Testnet](https://testnet.binancefuture.com) account with API keys

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/binance-futures-trading-bot.git
cd binance-futures-trading-bot

# 2. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Open .env in your editor and replace the placeholder values:
#   BINANCE_API_KEY=<your testnet key>
#   BINANCE_API_SECRET=<your testnet secret>
```

---

## 3. Running the CLI

```bash
# Market BUY — buy 0.01 BTC at the current market price
python cli.py place-order \
  --symbol BTCUSDT \
  --side BUY \
  --type MARKET \
  --quantity 0.01

# Limit SELL — sell 0.5 ETH at 3200 USDT
python cli.py place-order \
  --symbol ETHUSDT \
  --side SELL \
  --type LIMIT \
  --quantity 0.5 \
  --price 3200

# Grid BUY — spread 0.1 BTC across 5 limit orders between 60000–65000 USDT
python cli.py place-order \
  --symbol BTCUSDT \
  --side BUY \
  --type GRID \
  --quantity 0.1 \
  --price-low 60000 \
  --price-high 65000 \
  --grid-levels 5

# Check account balance
python cli.py balance
```

---

## 4. Running the Gradio UI

```bash
python ui.py
```

Open your browser at **http://localhost:7860**.

The UI has three tabs:

| Tab | Purpose |
|-----|---------|
| **Place Order** | Submit market, limit, or grid orders with live field toggling |
| **Account Balance** | View current USDT-M testnet asset balances |
| **Order Log** | Inspect the last 50 lines of `logs/trading_bot.log` |

---

## 5. Project Structure

```
binance-futures-trading-bot/
│
├── bot/                        ← Core library (feature/core-bot)
│   ├── __init__.py             ← Public API surface
│   ├── client.py               ← BinanceClient — authenticated API wrapper
│   ├── orders.py               ← OrderManager — market / limit / grid logic
│   ├── validators.py           ← Validator — static input validation helpers
│   └── logging_config.py       ← get_logger() factory + handler setup
│
├── cli.py                      ← Typer CLI entry point (feature/cli)
├── ui.py                       ← Gradio web UI entry point (feature/gradio-ui)
│
├── logs/
│   ├── .gitkeep                ← Keeps the directory tracked by git
│   ├── trading_bot.log         ← Runtime log (gitignored)
│   ├── market_order_sample.log ← Sample MARKET order log
│   └── limit_order_sample.log  ← Sample LIMIT order log
│
├── .env.example                ← Credential template (safe to commit)
├── .env                        ← Your actual credentials (gitignored)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 6. Assumptions & Notes

- **Testnet only** — the bot targets `https://testnet.binancefuture.com`.
  Do **not** use production API keys; the testnet URL rejects them.

- **USDT-M perpetuals** — the `Validator.validate_symbol()` method enforces
  that every symbol ends with `USDT`.  Coin-M (coin-margined) contracts are
  not supported.

- **Grid order partial failure** — if individual grid levels fail (e.g. price
  outside tick-size range), the error is logged and the remaining levels are
  still placed.  A total failure (all levels fail) raises `OrderError`.

- **Quantity precision** — quantities are validated to a maximum of 6 decimal
  places.  Binance enforces per-symbol `stepSize` rules; if your quantity
  violates the exchange filter, the API will return a `400` error with a clear
  message.

- **python-binance version** — tested with `python-binance >= 1.0.19`.
  The `futures_create_order` and `futures_account_balance` methods map to
  the `/fapi/v1/order` and `/fapi/v2/balance` REST endpoints respectively.

---

## 7. Log File Locations

| File | Description |
|------|-------------|
| `logs/trading_bot.log` | Live runtime log (DEBUG+, rotates at 5 MB, keeps 3 backups) |
| `logs/trading_bot.log.1` | First rotation backup |
| `logs/market_order_sample.log` | Sample successful MARKET order log |
| `logs/limit_order_sample.log` | Sample successful LIMIT order log |

Log format:
```
YYYY-MM-DD HH:MM:SS | LEVEL    | module.name | message
```

Example:
```
2026-05-18 14:01:03 | INFO     | bot.orders | ORDER FILLED MARKET | orderId=4812309 symbol=BTCUSDT status=FILLED executedQty=0.01 avgPrice=67412.30000
```
