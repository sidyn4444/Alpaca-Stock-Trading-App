# Intraday Trading App

**Automated intraday stock trading, fully unattended** — screens every tradable US equity
for setups, runs four strategies on a five-minute schedule while the market is open, and
closes every position before the day ends. Trades a paper account, not real money.

[![tests](https://github.com/sidyn4444/Intraday-Trading-App/actions/workflows/tests.yml/badge.svg)](https://github.com/sidyn4444/Intraday-Trading-App/actions/workflows/tests.yml)

A FastAPI dashboard that screens roughly 10K tradable symbols across 8 technical filters, plus a cron-driven Python bot that runs four intraday strategies and submits bracket orders through the Alpaca paper trading API.

Paper trading only (`paper-api.alpaca.markets`). No real capital is being used. The deployed build was read-only (`READ_ONLY=true` env flag disables the strategy-assignment POST) and read from a bundled snapshot SQLite seeded with about 50 tickers. The trading bot runs locally with the full database.

## The problem

There are thousands of stocks on US exchanges. On any given day only a few are doing
something worth trading — sitting at a new high, oversold, breaking out of the range they
opened in. Checking for that by hand means opening a lot of charts.

Timing makes it harder. An opening-range strategy only works in the first few minutes after
the market opens, so a setup is usually gone by the time you find it manually.

There are also two things you have to get right on every trade: set the exit when you enter,
and close the position before the day ends. Missing either one leaves you holding a position
overnight.

This project handles all of it on a schedule. It refreshes price data for every tradable symbol
each evening, checks the stocks assigned to a strategy every five minutes while the market is
open, submits each entry with its take-profit and stop-loss already attached, and closes
everything 30 minutes before the close.

## Components

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app. Routes: stock browser with 8 filter modes, per-stock detail with daily bars, strategy assignment (POST), per-strategy view, live order list from Alpaca. |
| `create_db.py` | SQLite schema. Tables: `stock`, `stock_price`, `strategy`, `stock_strategy`. |
| `populate_stocks.py` | Seeds `stock` from Alpaca's tradable assets endpoint. |
| `populate_prices.py` | Seeds `stock_price` with daily bars and tulipy-computed RSI-14, SMA-20, SMA-50. |
| `opening_range_breakout.py` | Long on break above the 15-min opening range. Bracket order with 1× range take-profit and 1× range stop-loss. |
| `opening_range_breakdown.py` | Short on break below the 15-min opening range. Same bracket structure. |
| `bollinger_bands.py` | Mean reversion long: enters on cross back above the lower 20-period band. |
| `bollinger_bands_short.py` | Mean reversion short: enters on cross back below the upper 20-period band. |
| `daily_close.py` | Calls `api.cancel_all_orders()` then `api.close_all_positions()`. Scheduled at 15:30 ET. |
| `helpers.py` | `calculate_quantity(price)` returns `math.floor(10000 / price)`. Used by all four strategies. |

## Architecture

```
                  ┌─────────────────────────────────────────┐
                  │              cron scheduler             │
                  └─────┬──────────────────────────┬────────┘
                        │                          │
               Mon-Fri 9:46-15:25 ET        Sundays 21:00 ET
                 every 5 minutes              + Daily 17:00
                        │                          │
                        ▼                          ▼
              ┌──────────────────┐       ┌──────────────────┐
              │ Strategy scripts │       │ populate_stocks  │
              │   (4 of them)    │       │ populate_prices  │
              └────────┬─────────┘       └────────┬─────────┘
                       │                          │
                       ▼                          ▼
              ┌──────────────────┐       ┌──────────────────┐
              │   Alpaca REST    │       │     SQLite       │
              │  (paper trading) │◀──────│    (app.db)      │
              └────────┬─────────┘       └────────┬─────────┘
                       │                          │
                       │                          ▼
                       │              ┌──────────────────────┐
                       │              │  FastAPI dashboard   │
                       └─────────────▶│  (Jinja2 templates)  │
                                      └──────────────────────┘
```

## Setup

Use Python 3.10 for the full local install — `tulipy` is a C extension that does not build
on 3.11+. The dashboard, the test suite, and the deployed image all run on Python 3.12. You
also need an Alpaca paper trading account and, optionally, a Gmail [app password](https://support.google.com/accounts/answer/185833) for fill notifications. The strategy scripts use stdlib `smtplib` — if SMTP credentials are missing, the scripts skip the email notifications.

```bash
git clone https://github.com/sidyn4444/Intraday-Trading-App.git
cd Intraday-Trading-App

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and input:
#   ALPACA_API_KEY, ALPACA_SECRET_KEY    from the Alpaca paper dashboard
#   DB_FILE                              absolute path to app.db
#   EMAIL_ADDRESS, EMAIL_PASSWORD        Gmail + app password (optional)

python create_db.py
python populate_stocks.py
python populate_prices.py

uvicorn main:app --reload
```

Config is loaded from environment variables via [`python-dotenv`](https://github.com/theskumar/python-dotenv) — the `.env` file is gitignored so that real credentials don't reach GitHub. In production the cloud platform's secret store gives the same variables without a file (see [Deployment](#deployment)).

## Deployment

The dashboard was deployed on Railway as a Docker container. The setup:

- **Hosting**: [Railway](https://railway.com) — auto-deployed from the `main` branch
- **Container**: `Dockerfile` in this repo builds a `python:3.12-slim` image, installs `requirements-prod.txt` (no `tulipy` since only the strategy scripts use it, and those run locally)
- **Database**: bundled `app-demo.db` seeded with around 50 well-known tickers and 100 days of synthetic OHLC. The real `app.db` (10K stocks, 100MB+) is gitignored and never deployed
- **Read-only mode**: `READ_ONLY=true` env flag disables `POST /apply_strategy` so visitors can't change anything
- **Secrets**: Railway's secret store injected `ALPACA_*`, `DB_FILE`, and `READ_ONLY` into the container's environment before `uvicorn` started

The deployed dashboard was for portfolio demonstration. The trading bot runs locally on cron because it and the dashboard share the same SQLite file. A v2 upgrade would migrate to PostgreSQL on Railway with scheduled jobs.

## Continuous integration

[`tests.yml`](.github/workflows/tests.yml) runs on every push to `main`:

- **`pytest`** — full 41-test suite under Python 3.12
- **`docker-build`** — verifies that the `Dockerfile` still builds

Both need to pass for the badge at the top of this README to stay green.

## Scheduling

Strategies run via cron. Cron has no clean expression for "every 5 minutes from 9:46 to 15:25 ET," so each strategy is three lines:

```cron
46,51,56 9 * * 1-5            /abs/path/venv/bin/python opening_range_breakout.py
*/5 10-14 * * 1-5             /abs/path/venv/bin/python opening_range_breakout.py
0,5,10,15,20,25 15 * * 1-5    /abs/path/venv/bin/python opening_range_breakout.py
```

Repeat for the other three strategies. Schedule `daily_close.py` at `30 15 * * 1-5`. The 5-minute gap between the last strategy run (15:25) and the daily close (15:30) prevents a strategy entry from opening a position after the close-out script has already run.

`populate_stocks.py` runs weekly (Sundays 21:00), `populate_prices.py` daily (Mon-Fri 17:00).

Cron's PATH does not include the venv, so every entry must reference `venv/bin/python` by absolute path.

## Risk controls

- **Position sizing**: `helpers.calculate_quantity(price)` caps each entry at ~$10K regardless of share price. A hardcoded `qty=100` on a $3K share would tie up $300K of buying power.
- **Bracket orders**: every entry submits with `take_profit` and `stop_loss` legs in the same `api.submit_order()` call. Alpaca cancels the other leg as soon as one of them fills.
- **End-of-day flatten**: `daily_close.py` cancels open orders and closes all positions at 15:30 ET. Nothing is held overnight.

## Stack

**Backend**: Python 3.12 · FastAPI · uvicorn · SQLite · alpaca-trade-api · pandas · NumPy ·
smtplib for trade alerts · tulipy for indicator math (local only, needs Python 3.10)
**Frontend**: HTML5 · CSS3 · Jinja2 · Semantic UI
**Deployment**: Docker · Railway · cron · python-dotenv
**Quality**: pytest · GitHub Actions CI

## Disclaimer

This code trades against `paper-api.alpaca.markets` so it does not use real money. Use real money at your own risk.

