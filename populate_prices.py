import sqlite3
import config
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import tulipy as ti
import numpy as nu
import alpaca_trade_api as tradeapi

DAYS_BACK = 100
CHUNK_SIZE = 200

def chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def main():
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # Because of the unique constraint we can use ignore to not change rows that have a given date for a stock id already
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_stock_price_unique
        ON stock_price (stock_id, date);
    """)

    # Load all stocks from DB
    cursor.execute("SELECT id, symbol FROM stock")
    rows = cursor.fetchall()

    symbols = [row["symbol"] for row in rows]
    symbols = [s for s in symbols if "/" not in s]

    # Relate the two databases using a dictionary
    stock_id_by_symbol = {row["symbol"]: row["id"] for row in rows}

    if not symbols:
        print("No symbols found in stock table.")
        return

    api = tradeapi.REST(
        config.API_KEY,
        config.SECRET_KEY,
        base_url=config.API_URL
    )

    start = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).isoformat()

    inserted = 0

    for symbol_chunk in chunked(symbols, CHUNK_SIZE):
        # Pull daily bars for this chunk
        barsets = api.get_bars(
            symbol_chunk,
            tradeapi.TimeFrame.Day,
            start=start
        )

        # Group bars by symbol (like you had before)
        bars_by_symbol = defaultdict(list)
        for bar in barsets:
            bars_by_symbol[bar.S].append(bar)

        # Insert into DB (like tutorial intent)
        for symbol, symbol_bars in bars_by_symbol.items():
            print(f"\nprocessing symbol {symbol}")

            # Sort by date so we can use[-1] to easily get latest date
            symbol_bars.sort(key=lambda b: b.t)

            stock_id = stock_id_by_symbol.get(symbol)
            if stock_id is None:
                continue

            if not symbol_bars:
                continue

            # This is the only day we want to store indicator values for (the newest day we fetched)
            latest_day = symbol_bars[-1].t.date()

            # Compute indicators ONCE for the latest day (using all closes we fetched)
            recent_closes = [bar.c for bar in symbol_bars]

            # For each bar we computed the tulip indicators of the rows
            sma_20_latest, sma_50_latest, rsi_14_latest = None, None, None
            try:
                if len(recent_closes) >= 50:
                    closes_arr = nu.array(recent_closes, dtype=float)
                    sma_20_latest = ti.sma(closes_arr, period=20)[-1]
                    sma_50_latest = ti.sma(closes_arr, period=50)[-1]
                    rsi_14_latest = ti.rsi(closes_arr, period=14)[-1]
            except Exception as e:
                print(f"{symbol}: indicator calc failed ({type(e).__name__}): {e}")
                sma_20_latest, sma_50_latest, rsi_14_latest = None, None, None

            # First we get the date for each row and only insert the tulip indicator if the date matches today and ignore if there is a row with the same stock_id/date pair because of the unique constraint we put
            for bar in symbol_bars:
                # bar.t is a datetime; store date only (matches your schema)
                day = bar.t.date()

                # Previous dates get None; only the latest day gets indicators
                if day == latest_day:
                    sma_20, sma_50, rsi_14 = sma_20_latest, sma_50_latest, rsi_14_latest
                else:
                    sma_20, sma_50, rsi_14 = None, None, None

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO stock_price
                    (stock_id, date, open, high, low, close, volume, sma_20, sma_50, rsi_14)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (stock_id, day.isoformat(), bar.o, bar.h, bar.l, bar.c, bar.v, sma_20, sma_50, rsi_14)
                )
                inserted += cursor.rowcount

            # =========================
            # NEW: keep only last DAYS_BACK days (rolling window)
            # =========================
            cutoff_date = (latest_day - timedelta(days=DAYS_BACK - 1)).isoformat()
            cursor.execute(
                """
                DELETE FROM stock_price
                WHERE stock_id = ?
                  AND date < ?
                """,
                (stock_id, cutoff_date)
            )

    connection.commit()
    connection.close()

    print(f"\nDone. Inserted {inserted} rows into stock_price.")

if __name__ == "__main__":
    main()
