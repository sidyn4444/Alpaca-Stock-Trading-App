# Intraday Trading App

**Automated intraday stock trading** — screens about 10K US stocks against 8 filters, runs
four strategies on a five-minute schedule while the market is open, and closes every position
before the day ends. Paper account, not real money.

[![tests](https://github.com/sidyn4444/Intraday-Trading-App/actions/workflows/tests.yml/badge.svg)](https://github.com/sidyn4444/Intraday-Trading-App/actions/workflows/tests.yml)

A FastAPI dashboard for browsing the screens and assigning stocks to strategies, plus automated Python scripts on cron that place the orders through the Alpaca paper trading API.

Paper trading only (`paper-api.alpaca.markets`), so no real money. The deployed build was read-only — `READ_ONLY=true` turns off the strategy-assignment POST — and read from a small bundled SQLite file with about 50 tickers. The bot runs locally with the full database.

## The problem

There are thousands of stocks on US exchanges, and on any given day only a few are doing
something worth trading — a new high, oversold, breaking out of the range they opened in.
Finding those by hand means opening a lot of charts.

Timing makes it harder. An opening-range setup only lasts a few minutes after the open, so
it's usually gone by the time you find it manually. And on every trade you have to set the
exit when you enter and close the position before the day ends, or you hold it overnight.

This project does that on a schedule: refresh prices each evening, check the assigned stocks
every five minutes while the market is open, submit each entry with its take-profit and
stop-loss attached, and close everything 30 minutes before the close.

## Components

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app. Stock browser with 8 filters, per-stock detail, strategy assignment, per-strategy view, and an order list pulled from Alpaca. |
| `create_db.py` | SQLite schema. Tables: `stock`, `stock_price`, `strategy`, `stock_strategy`. |
| `populate_stocks.py` | Populates `stock` from Alpaca's list of tradable assets. |
| `populate_prices.py` | Populates `stock_price` with daily prices, plus tulipy-computed RSI-14, SMA-20, and SMA-50. |
| `opening_range_breakout.py` | Buys when a stock breaks above the price range it traded in during its first 15 minutes. Exits the same distance above the entry for a gain, or the same distance below it to cap the loss. |
| `opening_range_breakdown.py` | The reverse: bets on the price falling when it drops below that first-15-minute range. Same exits. |
| `bollinger_bands.py` | Buys a stock that fell unusually far below its recent average price and has started climbing back toward it. |
| `bollinger_bands_short.py` | Bets on a fall after a stock climbs unusually far above its recent average price and starts dropping back. |
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
- **Container**: `Dockerfile` builds a `python:3.12-slim` image from `requirements-prod.txt`, which leaves out `tulipy` — only the local strategy scripts need it
- **Database**: bundled `app-demo.db` with about 50 tickers and 100 days of fake prices. The real `app.db` (10K stocks, 100MB+) is gitignored and never deployed
- **Read-only mode**: `READ_ONLY=true` env flag disables `POST /apply_strategy` so visitors can't change anything
- **Secrets**: Railway's secret store set `ALPACA_*`, `DB_FILE`, and `READ_ONLY` as environment variables in the container

The deployed dashboard was just to show the project. The bot runs locally on cron because it and the dashboard share the same SQLite file. A v2 would move to PostgreSQL on Railway with scheduled jobs.

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

