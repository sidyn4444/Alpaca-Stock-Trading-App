import sqlite3, config
import alpaca_trade_api as tradeapi

connection = sqlite3.connect(config.DB_FILE)
# Helps to set up rows by returning each row as an object
connection.row_factory = sqlite3.Row

cursor = connection.cursor()

cursor.execute("""
    SELECT symbol, name FROM stock
""")

# Now we can access each row by 'symbol' or 'name'
rows = cursor.fetchall()
symbols = [row['symbol'] for row in rows]

api = tradeapi.REST(
    config.API_KEY,
    config.SECRET_KEY,
    base_url = config.API_URL
)

assets = api.list_assets()
newStocksAdded = 0

for asset in assets:
    if asset.status == 'active' and asset.tradable and asset.symbol not in symbols:
        print(f"Added a new stock {asset.symbol} {asset.name}")
        cursor.execute("INSERT INTO stock (symbol, name, exchange) VALUES (?,?, ?)", (asset.symbol, asset.name, asset.exchange))
        newStocksAdded = newStocksAdded + 1
        
if newStocksAdded == 0:
        print("No new stocks added")

connection.commit()
