# 📈 Alpaca Trading Dashboard

A complete stock trading platform with automated strategies, real-time charts, and daily updates using Alpaca Paper Trading API.

## ✨ Features

- **📊 Real-time Stock Charts**: Interactive TradingView charts for detailed technical analysis
- **🤖 Automated Trading Strategies**: Opening range breakout/breakdown with bracket orders
- **📈 Technical Indicators**: RSI-14, SMA-20, and SMA-50 calculations on all stocks
- **📧 Email Notifications**: Automatic alerts for trade executions and strategy triggers
- **🗄️ Database Management**: SQLite database with relational tables for stocks, prices, and strategies
- **🌐 Web Dashboard**: FastAPI backend with Jinja2 templates and Semantic UI frontend
- **🔄 Daily Automation**: Cronjob setup for automatic data updates and strategy execution

- ## 🎯 Quick Options

### Option A: Just View the Frontend
If you want to see the dashboard interface without setting up trading visit: http://127.0.0.1:8000/

## 🚀 Complete Setup Guide (Start to Finish)

### Step 1: Get Alpaca Paper Trading API Keys (FREE)
1. **Sign up**: Go to [https://app.alpaca.markets/signup](https://app.alpaca.markets/signup)
2. **Verify email**: Check your inbox for confirmation
3. **Log in to Paper Trading**: Go to [https://app.alpaca.markets/paper/dashboard/overview](https://app.alpaca.markets/paper/dashboard/overview)
4. **Generate API Keys**: Profile → API Keys → Generate New Key
5. **Save both keys**: 
   - **API Key ID** (starts with `PK...`)
   - **Secret Key**

**Important**: You must be in the **Paper Trading** section, not Live Trading!

### Step 2: Open Terminal and Install Everything
```bash
# Open VS Code Terminal (Ctrl+` or Terminal > New Terminal)

# 1. Clone the repository
git clone https://github.com/sidyn4444/Alpaca-Stock-Trading-App.git

# 2. Navigate into the project
cd Alpaca-Stock-Trading-App

# 3. Create virtual environment
python3 -m venv venv

# 4. Activate virtual environment
# For Mac/Linux:
source venv/bin/activate
# For Windows:
# venv\Scripts\activate

# You should see (venv) in your terminal prompt now

# 5. Install each dependency ONE BY ONE (to avoid errors)
pip install fastapi==0.104.1
pip install uvicorn[standard]==0.24.0
pip install alpaca-trade-api==3.0.2
pip install pandas==2.1.3
pip install python-multipart==0.0.6
pip install Jinja2==3.1.2

# 6. Install tulipy with specific version (this one works)
pip install tulipy==0.4.0
'''

### Step 3: Configure Your API Keys
```bash
# 1. Copy the configuration template
cp config.example.py config.py

# 2. Open config.py in VS Code
# Click on config.py in the file explorer, or:
code config.py

# 3. Replace with your actual Alpaca API keys:
# - API_KEY = 'YOUR_ACTUAL_API_KEY_HERE' (starts with PK...)
# - SECRET_KEY = 'YOUR_ACTUAL_SECRET_KEY_HERE'
# - Keep API_URL as 'https://paper-api.alpaca.markets'
'''

### Step 4: Database Setup (Run IN ORDER)
```bash
# 1. Create database structure
python create_db.py

# 2. Fetch stock list from Alpaca (takes 1-2 minutes)
python populate_stocks.py

# 3. Get historical price data (takes 2-3 minutes)
python populate_prices.py

# Start the web server
uvicorn main:app --reload

# Open your browser and go to: http://localhost:8000
# You should see the stock trading dashboard!
'''

### Step 5: Set Up Daily Automation (Cronjobs) - This is optional if you want updated stocks/prices everyday otherwise just running create_db, populate_stocks, populate_prices will have data up to date

Run these commands in your terminal:

```bash
# 1. Create logs directory
mkdir -p /Users/YOUR_USERNAME/Alpaca-Stock-Trading-App/logs

# 2. Open crontab editor
crontab -e

# 3. In the Vim editor:
#    - Press 'i' to enter INSERT mode
#    - Copy and paste these 3 lines (CHANGE the path to YOUR project):

0 21 * * * cd /Users/YOUR_USERNAME/Alpaca-Stock-Trading-App && python populate_stocks.py >> /Users/YOUR_USERNAME/Alpaca-Stock-Trading-App/logs/stocks_update.log 2>&1
0 22 * * * cd /Users/YOUR_USERNAME/Alpaca-Stock-Trading-App && python populate_prices.py >> /Users/YOUR_USERNAME/Alpaca-Stock-Trading-App/logs/prices_update.log 2>&1
35 9 * * 1-5 cd /Users/YOUR_USERNAME/Alpaca-Stock-Trading-App && python opening_range_breakout.py >> /Users/YOUR_USERNAME/Alpaca-Stock-Trading-App/logs/trading.log 2>&1

#    - Press ESC to exit INSERT mode
#    - Type ':wq' and press ENTER to save and exit

# 4. Verify your cronjobs are set:
crontab -l

