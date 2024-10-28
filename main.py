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
        if value >= 1_000_000_000_000:
            return f"{value / 1_000_000_000_000:.2f} trillion"
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

# Function to fetch predictive estimates from Yahoo Finance
def fetch_predictive_estimates(ticker):
    try:
        stock = yf.Ticker(ticker)
        earnings_forecast = stock.earnings_forecasts

        if earnings_forecast is not None and not earnings_forecast.empty:
            next_year_estimate = earnings_forecast.iloc[-1]  # Get the latest available estimate
            return {
                "estimated_revenue": next_year_estimate.get("Revenue Estimate"),
                "estimated_eps": next_year_estimate.get("Earnings Estimate")
            }
        else:
            return {"error": "No predictive data available for the given ticker"}
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

# Function to fetch historical data for a given year or quarter
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

# Combine Yahoo Finance and Polygon.io data, with support for historical and real-time data
def combine_financial_data(ticker, time_period=None):
    current_date = datetime.now().strftime('%B %d, %Y')

    yahoo_data = fetch_all_fundamentals_from_yahoo_finance(ticker)
    polygon_data = fetch_financial_data_from_polygon(ticker)
    predictive_data = fetch_predictive_estimates(ticker)
    
    if "error" in yahoo_data:
        return f"Error in fetching Yahoo Finance data: {yahoo_data.get('error', '')}"
    
    combined_data = f"Below is the financial data for {ticker}:\n\n"
            

    # Yahoo Finance Data (historical and fundamentals)
    combined_data += f"**Yahoo Finance Data (as of {datetime.now().strftime('%B %d, %Y')}):**\n"
    for key, value in yahoo_data.items():
        combined_data += f"{key}: {format_large_numbers(value)}\n"

    # Historical Data from Yahoo Finance only
    if time_period:
        historical_data = fetch_historical_data_from_yahoo_finance(ticker)
        if isinstance(historical_data, pd.DataFrame):
            combined_data += f"\n**Historical Data for {time_period} from Yahoo Finance:**\n"
            combined_data += historical_data.to_string()
        else:
            combined_data += f"\nNo historical data available for {time_period}.\n"
    
    # Predictive Estimates from Yahoo Finance
    combined_data += "\nPredictive Estimates from Yahoo Finance:\n"
    if "error" in predictive_data:
        combined_data += "Predictive data is currently not available.\n"
    else:
        combined_data += f"Estimated Revenue: {format_large_numbers(predictive_data.get('estimated_revenue', 'N/A'))}\n"
        combined_data += f"Estimated EPS: {predictive_data.get('estimated_eps', 'N/A')}\n"
        
    # Real-Time Data from Yahoo Finance and Polygon.io
    combined_data += "\nReal-Time Data (Yahoo Finance & Polygon.io):\n"
    combined_data += f"Price (Yahoo Finance): {yahoo_data.get('regularMarketPrice', 'N/A')}\n"
    combined_data += f"Price (Polygon.io): {polygon_data.get('price', 'N/A')}\n"
    combined_data += f"Volume (Yahoo Finance): {yahoo_data.get('volume', 'N/A')}\n"
    combined_data += f"Volume (Polygon.io): {polygon_data.get('volume', 'N/A')}\n"
    combined_data += f"High (Polygon.io): {polygon_data.get('high', 'N/A')}\n"
    combined_data += f"Low (Polygon.io): {polygon_data.get('low', 'N/A')}\n"
    combined_data += f"Open (Polygon.io): {polygon_data.get('open', 'N/A')}\n"
    combined_data += f"Transactions (Polygon.io): {polygon_data.get('transactions', 'N/A')}\n"

    # Historical Data from Yahoo Finance (only)
    if time_period:
        historical_data = fetch_historical_data(ticker, time_period)
        if isinstance(historical_data, pd.DataFrame):
            combined_data += f"\nHistorical Data for {time_period} from Yahoo Finance:\n"
            combined_data += historical_data.to_string()
        else:
            combined_data += f"\nNo historical data available for {time_period}.\n"
        
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
            combined_data = combine_financial_data(ticker)
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
                        f"   - Use **Yahoo Finance** as the primary source for **real-time, historical data, and predictive** (e.g., financial statements, revenue, profit margins, balance sheets).\n"
                        f"   - Use **Polygon.io** for **real-time data** including metrics like current price, volume, VWAP, high, low, opening price, and transaction count.Ensure that Yahoo Finance data is prioritized and that Polygon.io is referenced only for additional real-time metrics.\n"
                        f"2. **Data Referencing**:\n"
                        f"   - Always describe the data as **'real-time'** or **'recently retrieved'** to emphasize the timeliness of the information.\n"
                        f"   - Do not state any inability to access real-time data. If unavailable, use the **most recent data available**, and clearly state that it is the latest data on hand.\n"
                        f"3. **Analytical Approach**:\n"
                        f"   - Your responses must be **structured, data-driven, and evidence-based**, incorporating financial metrics, historical trends, and predictive analysis.\n"
                        f"   - When discussing **financial health**, include key indicators such as **profit margins, revenue growth, debt-to-equity ratio, P/E ratio**, and other relevant metrics.\n"
                        f"   - For **comparisons** between companies or periods, ensure the analysis is **quantitative**, highlighting percentage changes, historical trends, and predictive insights.\n"
                        f"   - **Company news** from Yahoo Finance should be used to provide additional context where relevant.\n"
                        f"4. **Response Tone and Quality**:\n"
                        f"   - Provide analysis in a **professional and formal tone**, suitable for financial professionals or academic reviewers.\n"
                        f"   - Ensure that **all metrics are contextualized**—ALWAYS mention the time period the data is from and explain what each metric indicates about the company's financial performance or market position.\n"
                        f"   - Use bullet points and bold text to make key points stand out.\n"
                        f"   - **Never deviate** from the factual data retrieved. Base every insight strictly on the data from Yahoo Finance and Polygon.io, avoiding speculative commentary."
                    )
                },
                {"role": "user", "content": "\n\n".join(combined_responses)},
                {"role": "user", "content": user_query}
            ],
            max_tokens=750,
            temperature=0.5
        )
                        
        return jsonify({'response': response['choices'][0]['message']['content']})
                        
    except Exception as e:
        return jsonify({'response': f"An error occurred while generating the response: {str(e)}"})
                        
# Running the Flask server
if __name__ == '__main__':
    app.run(debug=True)

