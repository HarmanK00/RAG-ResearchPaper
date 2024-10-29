import openai
import yfinance as yf
import requests
from flask import Flask, request, jsonify, render_template
import os
from datetime import datetime, timedelta
import pandas as pd
import re

# Flask app initialization
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

# API keys (using environment variables)
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Function to format large numbers for readability
def format_large_numbers(value):
    try:
        value = float(value)
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f} billion"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.2f} million"
        else:
            return f"{value:,.2f}"
    except (ValueError, TypeError):
        return value

# Function to fetch all financial data from Yahoo Finance
def fetch_all_fundamentals_from_yahoo_finance(ticker):
    try:
        stock = yf.Ticker(ticker)
        stock_info = stock.info

        if not stock_info:
            return {"error": "No data found for the given ticker"}
        return stock_info
    except Exception as e:
        return {"error": str(e)}

# Function to fetch historical trading data from Yahoo Finance
def fetch_historical_data_from_yahoo_finance(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="max")  # Fetch max period (all available data)
        if data.empty:
            return {"error": "No historical data found for the given ticker"}
        return data
    except Exception as e:
        return {"error": str(e)}


# Function to fetch the most recent real-time trading data from Polygon.io
def fetch_financial_data_from_polygon(ticker):
    polygon_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={POLYGON_API_KEY}"
    try:
        polygon_response = requests.get(polygon_url)
        if polygon_response.status_code == 200 and polygon_response.json().get("results"):
            data = polygon_response.json()["results"][0]  # Use the first result from 'results'
            return {
                "price": data.get("c", "N/A"),  # Closing price
                "volume": data.get("v", "N/A"),  # Volume
                "high": data.get("h", "N/A"),    # High price
                "low": data.get("l", "N/A"),     # Low price
                "open": data.get("o", "N/A"),    # Opening price
                "transactions": data.get("n", "N/A")  # Number of transactions
            }
        else:
            return {"error": "No data found for the given ticker on Polygon.io"}
    except Exception as e:
        return {"error": str(e)}

# Function to extract specific year or quarter from user query
def extract_specific_year_or_quarter(user_query):
    year_match = re.search(r"\b(\d{4})\b", user_query)
    if year_match:
        return year_match.group(0)
    quarter_match = re.search(r"(Q[1-4])\s(\d{4})", user_query)
    if quarter_match:
        return quarter_match.group(0)
    return None

# Function to extract specific date or keywords for historical data from user query
def extract_historical_date(user_query):
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

# Function to fetch historical data for a given year, quarter, or date
def fetch_historical_data(ticker, user_query):
    try:
        stock = yf.Ticker(ticker)
        specific_date = extract_historical_date(user_query)

        if specific_date:
            start_date = specific_date
            end_date = specific_date
        else:
            time_period = extract_specific_year_or_quarter(user_query)
            if re.match(r"\d{4}", time_period):
                start_date = f"{time_period}-01-01"
                end_date = f"{time_period}-12-31"
            elif re.match(r"(Q[1-4])\s(\d{4})", time_period):
                quarter_match = re.match(r"(Q[1-4])\s(\d{4})", time_period)
                quarter, year = quarter_match.groups()
                year = int(year)
                if quarter == "Q1":
                    start_date = f"{year}-01-01"
                    end_date = f"{year}-03-31"
                elif quarter == "Q2":
                    start_date = f"{year}-04-01"
                    end_date = f"{year}-06-30"
                elif quarter == "Q3":
                    start_date = f"{year}-07-01"
                    end_date = f"{year}-09-30"
                elif quarter == "Q4":
                    start_date = f"{year}-10-01"
                    end_date = f"{year}-12-31"
            else:
                return {"error": "No valid date period found in the query"}

        historical_data = stock.history(start=start_date, end=end_date)

        if historical_data.empty:
            return {"error": "No historical data found for the given period"}

        return historical_data[['Close', 'Volume']]
    except Exception as e:
        return {"error": str(e)}

# Combine Yahoo Finance and Polygon.io data, with support for historical data
def combine_financial_data(ticker, user_query):
    yahoo_data = fetch_all_fundamentals_from_yahoo_finance(ticker)
    polygon_data = fetch_financial_data_from_polygon(ticker)

    if "error" in yahoo_data or "error" in polygon_data:
        return f"Error in fetching data: {yahoo_data.get('error', '')}, {polygon_data.get('error', '')}"

    combined_data = f"Below is the real-time and historical financial data for {ticker}:\n\n"

    # Yahoo Finance Data (historical and fundamentals)
    combined_data += "Yahoo Finance Data:\n"
    for key, value in yahoo_data.items():
        combined_data += f"{key}: {format_large_numbers(value)}\n"

    # Polygon.io Data (real-time)
    combined_data += "\nPolygon.io Real-Time Data:\n"
    combined_data += f"Price: {polygon_data.get('price', 'N/A')}\n"
    combined_data += f"Volume: {polygon_data.get('volume', 'N/A')}\n"
    combined_data += f"High: {polygon_data.get('high', 'N/A')}\n"
    combined_data += f"Low: {polygon_data.get('low', 'N/A')}\n"
    combined_data += f"Open: {polygon_data.get('open', 'N/A')}\n"
    combined_data += f"Transactions: {polygon_data.get('transactions', 'N/A')}\n"

    # Historical Data from Yahoo Finance
    historical_data = fetch_historical_data(ticker, user_query)
    if isinstance(historical_data, pd.DataFrame):
        combined_data += f"\nHistorical Data from Yahoo Finance based on your query:\n"
        combined_data += historical_data.to_string()
    else:
        combined_data += f"\nNo historical data available for the specified period.\n"

    return combined_data

@app.route('/generate-response', methods=['POST'])
def generate_response():
    try:
        user_query = request.json.get('query', '')
        tickers = request.json.get('tickers', [])

        if not tickers:
            return jsonify({'response': "No ticker symbol provided. Please provide at least one valid ticker."})

        combined_responses = []
        for ticker in tickers:
            combined_data = combine_financial_data(ticker, user_query)
            combined_responses.append(combined_data)

        # Generate response with combined data
        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a financial analyst assistant designed to provide expert-level analysis using real-time and historical financial data from Yahoo Finance and Polygon.io. "
                        f"Your responses must be precise, transparent, and well-supported by quantitative data, tailored to meet the standards of Wall Street professionals. "
                        f"Today's date is {datetime.now().strftime('%B %d, %Y')}\n\n"
                        f"Your capabilities:\n"
                        f"1. **Data Sources**:\n"
                        f"   - Use **Yahoo Finance** for both **real-time** and **historical data** such as financial statements, revenue, profit margins, balance sheets, and historical stock performance.\n"
                        f"   - Use **Polygon.io** for **real-time data** including metrics like current price, volume, VWAP, high, low, opening price, and transaction count.\n"
                        f"2. **Data Referencing**:\n"
                        f"   - Always describe the data as **'real-time'** or **'recently retrieved'** to emphasize the timeliness of the information.\n"
                        f"   - If historical data is being referenced, clearly state the time period.\n"
                        f"3. **Response Tone and Quality**:\n"
                        f"   - Provide analysis in a **professional and formal tone**, suitable for financial professionals or academic reviewers.\n"
                        f"   - **Never deviate** from the factual data retrieved. Keep responses less than 9 sentences."
                    )
                },
                {"role": "user", "content": "\n\n".join(combined_responses)},
                {"role": "user", "content": user_query}
            ],
            max_tokens=750,
            temperature=0.7
        )

        return jsonify({'response': response['choices'][0]['message']['content']})

    except Exception as e:
        return jsonify({'response': f"An error occurred while generating the response: {str(e)}"})

# Running the Flask server
if __name__ == '__main__':
    app.run(debug=True)


