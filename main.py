import sqlite3, config
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date

app = FastAPI()
templates = Jinja2Templates(directory = "templates")

@app.get("/")
def index(request: Request):
    # Helps to filter based on given criteria given by the html file
    stock_filter = request.query_params.get('filter', False)
    connection = sqlite3.connect(config.DB_FILE)
    # Helps to set up rows by returning each row as an object
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    if stock_filter == 'new_closing_highs':
        # Create temporary rows that include symbol, name, stock_id, close, and the date
        # Since we group by stock_id out of every row  with the stock id return the row that has the maximum close
        # If the date in the given row is the same as date given return it
        # On weekends/holidays the alpaca api does not return anything so using today's date would sometimes return nothing so use max(date) to get the latest date
        cursor.execute("""
        select * from (
            select symbol, name, stock_id, max(close), date
            from stock_price
            join stock on stock.id = stock_price.stock_id
            group by stock_id
            order by symbol
        )
        where date = (select max(date) from stock_price)
        """)
    elif stock_filter == 'new_closing_lows':
        cursor.execute("""
        select * from (
            select symbol, name, stock_id, min(close), date
            from stock_price
            join stock on stock.id = stock_price.stock_id
            group by stock_id
            order by symbol
        )
        where date = (select max(date) from stock_price)
        """)
    else:
        cursor.execute("""
            SELECT id, symbol, name FROM stock ORDER BY symbol
        """)

    # Now we can access each row by 'symbol' or 'name'
    rows = cursor.fetchall()

    # Getting the data to display the tulip indicators only for today's date
    cursor.execute("""
        select stock.symbol, stock_price.rsi_14, stock_price.sma_20, stock_price.sma_50, stock_price.close
        from stock
        join stock_price on stock_price.stock_id = stock.id
        where stock_price.date = (select max(date) from stock_price)
    """)
    indicator_rows = cursor.fetchall()
    # Better to use dictionary for quick search rather than do an if stamenet to compare between row['symbol'] and what is listed
    indicator_values = {}
    for row in indicator_rows:
        indicator_values[row['symbol']] = row
    connection.close()
    return templates.TemplateResponse("index.html", {"request": request, "stocks": rows, "indicator_values": indicator_values})

# Set up the link for this function in index.html so now when it clicks to that link it will prepare this data for it to which stock_detail.html will use to create the ui for that link
@app.get("/stock/{symbol}")
def stock_detail(request: Request, symbol):
    connection = sqlite3.connect(config.DB_FILE)
    # Helps to set up rows by returning each row as an object
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    # Now you need strategy rows for the dropdown and later in code we give id as well for the form
    cursor.execute("""
        SELECT * FROM strategy
    """)
    strategies = cursor.fetchall()
    cursor.execute("""
        SELECT id, symbol, name FROM stock WHERE symbol = ?
    """, (symbol,))

    # Now we can access each row by 'symbol' or 'name'
    row = cursor.fetchone()

    cursor.execute("""
        SELECT * FROM stock_price WHERE stock_id = ? ORDER BY date DESC
    """, (row['id'],))
    prices = cursor.fetchall()
    connection.close()
    return templates.TemplateResponse("stock_detail.html", {"request": request, "stock": row, "bars": prices, "strategies": strategies})

# This takes data in from the form of stock detail using strategy_id and stock_id and sends it to this function then redirects the page
# Note to self: Set up form in html file first then set this function up
@app.post("/apply_strategy")
def apply_strategy(strategy_id: int = Form(...), stock_id: int = Form(...)):
    connection = sqlite3.connect(config.DB_FILE)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO stock_strategy (stock_id, strategy_id)
        VALUES (?, ?)
    """, (stock_id, strategy_id))

    connection.commit()
    connection.close()
    return RedirectResponse(url=f"/strategy/{strategy_id}", status_code=303)

# Now this prepares the data needed for /strategy/{strategy_id}
@app.get("/strategy/{strategy_id}")
def strategy(request: Request, strategy_id: int):
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name
        FROM strategy
        WHERE id = ?
    """, (strategy_id,))

    strategy = cursor.fetchone()

    # Join joins together columns from different databases as a bridge and where helps filter out the rows while select selects certain columns from the filtered out rows
    # Here join is used to link together the stock ids in both databases as thats their connection that we made on purpose, now you can filter by strategy_id which is the real purpose of the query
    cursor.execute("""
        SELECT symbol, name
        FROM stock
        JOIN stock_strategy ON stock_strategy.stock_id = stock.id
        WHERE strategy_id = ?
    """, (strategy_id,))

    stocks = cursor.fetchall()
    connection.close()
    return templates.TemplateResponse(
        "strategy.html",
        {
            "request": request,
            "stocks": stocks,
            "strategy": strategy
        }
    )