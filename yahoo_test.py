import yfinance as yf

ticker = "AAPL"
stock = yf.Ticker(ticker)
data = stock.history(period="max")  # Get all available historical data

if data.empty:
    print(f"No data found for ticker: {ticker}")
else:
    print(data)

