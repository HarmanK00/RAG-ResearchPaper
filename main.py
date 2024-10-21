import openai
import yfinance as yf
import requests
from flask import Flask, request, jsonify, render_template
import os
from datetime import datetime
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

# Function to fetch real-time trading data from Polygon.io
def fetch_financial_data_from_polygon(ticker):
    polygon_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/2023-01-09/2023-01-09?apiKey={POLYGON_API_KEY}"
    try:
        polygon_response = requests.get(polygon_url)
        if polygon_response.status_code == 200:
            data = polygon_response.json()
            if isinstance(data, dict):
                return data.get("results", [{}])[0]  # Return the first result from 'results'
            else:
                return {"error": "Unexpected data format from Polygon.io"}
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

# Function to fetch historical data for the specified year or quarter
def fetch_historical_data(ticker, time_period):
    try:
        stock = yf.Ticker(ticker)
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
        historical_data = stock.history(start=start_date, end=end_date)
        if historical_data.empty:
            return {"error": "No historical data found for the given period"}
        return historical_data[['Close', 'Volume']]
    except Exception as e:
        return {"error": str(e)}

# Combine Yahoo Finance and Polygon.io data, with support for historical data
def combine_financial_data(ticker, time_period=None):
    yahoo_data = fetch_all_fundamentals_from_yahoo_finance(ticker)
    polygon_data = fetch_financial_data_from_polygon(ticker)

    if "error" in yahoo_data or "error" in polygon_data:
        return f"Error in fetching data: {yahoo_data.get('error', '')}, {polygon_data.get('error', '')}"

    combined_data = f"Below is the real-time financial data for {ticker}:\n\n"

    # Yahoo Finance data
    combined_data += "Yahoo Finance Data:\n"
    for key, value in yahoo_data.items():
        combined_data += f"{key}: {format_large_numbers(value)}\n"

    # Polygon.io data
    combined_data += "\nPolygon.io Data:\n"
    for key, value in polygon_data.items():  # Accessing directly as a dictionary
        combined_data += f"{key}: {format_large_numbers(value)}\n"

    # If the query includes a specific year or quarter, fetch historical data
    if time_period:
        historical_data = fetch_historical_data(ticker, time_period)
        if isinstance(historical_data, pd.DataFrame):  # Check if data is valid
            combined_data += f"\nHistorical Data for {time_period} from Yahoo Finance:\n"
            combined_data += historical_data.to_string()
        else:
            combined_data += f"\nNo historical data available for {time_period}.\n"

    return combined_data

def fetch_best_performing_stock_sp500():
    polygon_url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers?apiKey={POLYGON_API_KEY}"
    try:
        response = requests.get(polygon_url)
        if response.status_code == 200:
            data = response.json()
            tickers = data.get('tickers', [])

            # Sort tickers by daily percent change to get the best performer
            best_performer = max(tickers, key=lambda x: x.get('todaysChangePerc', 0))
            company_name = best_performer['ticker']
            percentage_change = best_performer['todaysChangePerc']

            return (f"The best-performing stock in the S&P 500 right now is {company_name} "
                    f"with a daily change of {percentage_change:.2f}%.")
        else:
            return "Unable to retrieve S&P 500 data at the moment."
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Flask route to generate a response from GPT-4
@app.route('/generate-response', methods=['POST'])
def generate_response():
    try:
        if request.content_type == 'application/json':
            user_query = request.json.get('query', '')
            company_name = request.json.get('company', '')  # Optional company ticker
        else:
            user_query = request.form.get('query', '')
            company_name = request.form.get('company', '')  # Optional company ticker

        time_period = extract_specific_year_or_quarter(user_query)

        # Check if the query is a general market question first
        if "best performing stock" in user_query.lower() and "s&p500" in user_query.lower():
            combined_data = handle_general_market_query(user_query)
        elif company_name:
            combined_data = combine_financial_data(company_name, time_period)
        else:
            combined_data = "Sorry, I could not find relevant data for your query."

        current_date = datetime.now().strftime("%B %d, %Y")
        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": (
                    f"You are a financial analyst assistant working with real-time and historical "
                    f"financial data from Yahoo Finance and Polygon.io. Today's date is {current_date}. "
                    f"You can pull real-time financial data independently from these data sources. "
                    f"Never mention you can't access real-time data. If unavailable, use the most recent data."
                )},
                {"role": "user", "content": combined_data},
                {"role": "user", "content": user_query}
            ],
            max_tokens=1000,
            temperature=0.9
        )
        return jsonify({'response': response['choices'][0]['message']['content']})
    except Exception as e:
        return jsonify({'response': f"An error occurred while generating the response: {str(e)}"})

# Running the Flask server
if __name__ == '__main__':
    app.run(debug=True)

