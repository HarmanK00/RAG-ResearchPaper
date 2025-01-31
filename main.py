import openai
import yfinance as yf
import requests
from flask import Flask, request, jsonify, render_template, session
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# Flask app initialization
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Enables session memory

@app.route('/')
def index():
    print("Rendering index page")
    return render_template('index.html')

# Load API Keys
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Load Global Ticker Mapping from JSON File
TICKER_MAP = {}

try:
    with open("companies.json", "r") as f:
        TICKER_MAP = json.load(f)
        print("Ticker map successfully loaded!")
except Exception as e:
    print(f"Error loading ticker map: {str(e)}")

# -----------------------------------------
# **🔹 STEP 1: REAL-TIME DATA RETRIEVAL**
# -----------------------------------------

def fetch_real_time_data_polygon(ticker):
    """Fetches real-time stock data from Polygon.io."""
    print(f"Fetching Polygon data for {ticker}")
    polygon_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={POLYGON_API_KEY}"
    try:
        response = requests.get(polygon_url)
        data = response.json().get("results", [{}])[0]
        return {
            "source": "Polygon.io",
            "price": data.get("c", "N/A"),
            "volume": data.get("v", "N/A"),
            "high": data.get("h", "N/A"),
            "low": data.get("l", "N/A"),
            "open": data.get("o", "N/A"),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {"error": str(e)}

def fetch_historical_data_from_yahoo_finance(ticker):
    """Fetches full historical stock data from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="max")  # Fetch full available historical data
        if data.empty:
            return {"error": "No historical data found"}
        return data
    except Exception as e:
        return {"error": str(e)}

# **🔹 Extract specific date or keywords for historical data from user query**
def extract_historical_date(user_query):
    """Extracts specific historical timeframes from user query."""
    if "one year ago" in user_query.lower():
        return (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    elif "six months ago" in user_query.lower():
        return (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    elif "three months ago" in user_query.lower():
        return (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    elif "last month" in user_query.lower():
        return (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    else:
        return None

def fetch_real_time_data_yahoo(ticker):
    """Fetches real-time stock data from Yahoo Finance."""
    print(f"Fetching Yahoo Finance data for {ticker}")
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        latest_data = data.iloc[-1] if not data.empty else None

        if latest_data is None:
            return {"error": "No real-time data found"}

        return {
            "source": "Yahoo Finance",
            "price": latest_data["Close"],
            "volume": latest_data["Volume"],
            "high": latest_data["High"],
            "low": latest_data["Low"],
            "open": latest_data["Open"],
            "timestamp": latest_data.name.strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {"error": str(e)}

# **🔹 Facilitator: Extract Tickers from Query**
def extract_tickers(query):
    """Extracts stock tickers from the user query using a predefined dictionary."""
    tickers = []
    print("Extracting tickers:", query)

    for company, ticker in TICKER_MAP.items():
        if company.lower() in query.lower():
            tickers.append(ticker)

    print("Extracted tickers:", tickers)
    return tickers

# **🔹 Facilitator: Collect & Validate Real-Time Data**
def collect_real_time_data(query):
    """Fetches real-time data for all detected stock tickers in a query."""
    tickers = extract_tickers(query)
    if not tickers:
        return {"error": "No valid stock ticker found in query."}

    real_time_data = {}
    for ticker in tickers:
        yahoo_data = fetch_real_time_data_yahoo(ticker)
        polygon_data = fetch_real_time_data_polygon(ticker)

        real_time_data[ticker] = {
            "Yahoo": yahoo_data if "error" not in yahoo_data else None,
            "Polygon": polygon_data if "error" not in polygon_data else None
        }

    print("Collected real-time data:", real_time_data)
    return real_time_data if real_time_data else {"error": "No real-time data available."}

# -----------------------------------------
# **🔹 STEP 2: ADVANCED ANALYTICS (AAG)**
# -----------------------------------------
def calculate_moving_averages(data):
    """Calculates moving averages."""
    return {f"SMA_{period}": data["Close"].rolling(window=period).mean().dropna().iloc[-1]
            for period in [7, 30, 90]}

def calculate_rsi(data, period=14):
    """Calculates RSI."""
    delta = data["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs)).iloc[-1]



def monte_carlo_simulation(data):
    """Runs Monte Carlo simulations for stock price forecasting."""
    returns = data['Close'].pct_change().dropna()
    mean = returns.mean()
    std_dev = returns.std()
    num_simulations = 1000
    num_days = 30
    simulations = []
    last_price = data['Close'].iloc[-1]

    for _ in range(num_simulations):
        price_series = [last_price]
        for _ in range(num_days):
            price_series.append(price_series[-1] * (1 + np.random.normal(mean, std_dev)))
        simulations.append(price_series[-1])

    return {
        "5th Percentile": np.percentile(simulations, 5),
        "50th Percentile (Median)": np.percentile(simulations, 50),
        "95th Percentile": np.percentile(simulations, 95)
    }

def calculate_beta(ticker):
    """Calculates Beta Coefficient against S&P 500 (^GSPC)."""
    try:
        stock = yf.Ticker(ticker)
        sp500 = yf.Ticker("^GSPC")
        stock_data = stock.history(period="6mo")['Close']
        sp500_data = sp500.history(period="6mo")['Close']

        if stock_data.empty or sp500_data.empty:
            return "Insufficient data for Beta calculation"

        stock_returns = stock_data.pct_change().dropna()
        sp500_returns = sp500_data.pct_change().dropna()
        beta = np.cov(stock_returns, sp500_returns)[0, 1] / np.var(sp500_returns)
        return round(beta, 3)
    except Exception as e:
        return {"error": f"Failed to calculate Beta: {str(e)}"}

def calculate_bollinger_bands(data, window=20, num_std=2):
    """Calculates Bollinger Bands."""
    rolling_mean = data["Close"].rolling(window=window).mean()
    rolling_std = data["Close"].rolling(window=window).std()
    upper_band = rolling_mean + (num_std * rolling_std)
    lower_band = rolling_mean - (num_std * rolling_std)

    return {
        "Upper Band": upper_band.iloc[-1],
        "Middle Band (SMA)": rolling_mean.iloc[-1],
        "Lower Band": lower_band.iloc[-1]
    }

# **🔹 Facilitator: Collect & Validate Advanced Analytics**
def collect_advanced_analytics(query):
    """Fetches advanced analytics for all detected stock tickers in a query."""
    tickers = extract_tickers(query)
    if not tickers:
        return {"error": "No valid stock ticker found in query."}

    analysis_data = {}

    for ticker in tickers:
        stock = yf.Ticker(ticker)
        historical_data = stock.history(period="6mo")

        if historical_data.empty:
            analysis_data[ticker] = {
                "error": "No historical data available for analytics.",
                "Beta Coefficient": "N/A",
                "Bollinger Bands": {"Upper Band": "N/A", "Lower Band": "N/A"}
            }
            continue  # Ensures missing data doesn’t break analysis

        try:
            analysis_data[ticker] = {
                "Moving Averages": calculate_moving_averages(historical_data),
                "RSI": calculate_rsi(historical_data),
                "Monte Carlo Simulation": monte_carlo_simulation(historical_data),
                "Beta Coefficient": calculate_beta(ticker),
                "Bollinger Bands": calculate_bollinger_bands(historical_data)
            }
        except Exception as e:
            analysis_data[ticker] = {
                "error": f"Analytics error: {str(e)}",
                "Beta Coefficient": "N/A",
                "Bollinger Bands": {"Upper Band": "N/A", "Lower Band": "N/A"}
            }

    print("Collected advanced analytics data:", analysis_data)
    return analysis_data


def handle_general_financial_query(user_query):
    """Handles general financial queries that do not require stock data."""
    openai.api_key = OPENAI_API_KEY

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a world-class financial analyst specializing in investment strategies, macroeconomic trends, risk management, and stock market insights. YOU MUST CREATE AN ACTIONABLE DETAILED PLAN."},
                {"role": "user", "content": user_query}
            ],
            max_tokens=750,
            temperature=0.9
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"An error occurred while handling the general query: {str(e)}"

# -----------------------------------------
# **🔹 FLASK API ROUTE**
# -----------------------------------------
@app.route('/generate-response', methods=['POST'])
def generate_response():
    try:
        user_query = request.json.get('query', '')
        tickers = extract_tickers(user_query)  # Extract potential stock tickers

        if tickers:
            # ✅ If tickers are found, process real-time stock data analysis
            real_time_data = collect_real_time_data(user_query)
            analysis_data = collect_advanced_analytics(user_query)
            ai_response = generate_financial_analysis(real_time_data, analysis_data, user_query)
        else:
            # ✅ If no tickers are found, treat it as a general financial question
            ai_response = handle_general_financial_query(user_query)

        return jsonify({'response': ai_response})
    
    except Exception as e:
        return jsonify({'response': f"An error occurred: {str(e)}"})

# -----------------------------------------
# **🔹 SYSTEM MESSAGE for GPT-4**
# -----------------------------------------

SYSTEM_MESSAGE = """
You are a world-class AI finance analyst specializing in **real-time financial analysis, market trend forecasting, and risk evaluation**.
Your goal is to provide accurate, **data-driven** financial insights using **real-time stock data** and **advanced analytics**.

📊 **Key Responsibilities**:
- **Real-Time Data Retrieval**: Always use the most up-to-date stock prices, market trends, and volume metrics.
- **Advanced Analytics**: Utilize SMA, RSI, Bollinger Bands, Monte Carlo Simulations, and Beta coefficients.
- **Market Trend Forecasting**: Identify **patterns, volatility, and risk factors** based on real-time & historical data.
- **Investment Analysis**: Offer insightful **stock recommendations & risk assessments** based on the given data.

❌ **NEVER say "I don't have access to real-time data."**  
✅ **Always analyze data from Yahoo Finance & Polygon.io to provide insights.**  
"""

def generate_financial_analysis(real_time_data, analysis_data, user_query):
    """Generates AI response using GPT-4 for multi-company analysis."""
    openai.api_key = OPENAI_API_KEY

    try:
        real_time_summary = ""
        analysis_summary = ""

        for company, data in real_time_data.items():
            if isinstance(data, dict) and "error" not in data:
                real_time_summary += (
                    f"\n📊 **{company} - Real-Time Stock Data:**\n"
                    f"🔹 **Yahoo Finance**: ${data.get('Yahoo', {}).get('price', 'N/A')} "
                    f"(as of {data.get('Yahoo', {}).get('timestamp', 'N/A')})\n"
                    f"🔹 **Polygon.io**: ${data.get('Polygon', {}).get('price', 'N/A')} "
                    f"(as of {data.get('Polygon', {}).get('timestamp', 'N/A')})\n"
                )

        for company, data in analysis_data.items():
            if isinstance(data, dict) and "error" not in data:
                analysis_summary += (
                    f"\n📈 **{company} - Advanced Analytics:**\n"
                    f"🔹 7-day SMA: ${data.get('Moving Averages', {}).get('SMA_7', 'N/A')}\n"
                    f"🔹 30-day SMA: ${data.get('Moving Averages', {}).get('SMA_30', 'N/A')}\n"
                    f"🔹 90-day SMA: ${data.get('Moving Averages', {}).get('SMA_90', 'N/A')}\n"
                    f"🔹 RSI: {data.get('RSI', 'N/A')}\n"
                    f"🔹 Beta Coefficient: {data.get('Beta Coefficient', 'N/A')}\n"
                    f"🔹 Bollinger Bands: Upper ${data.get('Bollinger Bands', {}).get('Upper Band', 'N/A')}, "
                    f"Lower ${data.get('Bollinger Bands', {}).get('Lower Band', 'N/A')}\n"
                    f"🔹 Monte Carlo Prediction (Median): ${data.get('Monte Carlo Simulation', {}).get('50th Percentile (Median)', 'N/A')}\n"
                )

        if not real_time_summary and not analysis_summary:
            return "No valid financial data was retrieved. Please check your ticker symbols or try again later."

        prompt = (
            "You are a world-class AI finance analyst. Use the following real-time stock data and analytics "
            "to provide a financial assessment. Do NOT say you don't have real-time data. "
            "Instead, base your response on the given data. \n\n"
            f"{real_time_summary}\n{analysis_summary}\n\n"
            f"User Query: {user_query}\n"
            "🔹 Provide a professional financial assessment, including trends and risk factors."
        )

        # ✅ Ensure GPT-4 is correctly prompted with structured real-time data
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )

        return response['choices'][0]['message']['content']

    except Exception as e:
        return f"An error occurred: {str(e)}"

if __name__ == '__main__':
    print("Starting Flask app")
    app.run(debug=True)
