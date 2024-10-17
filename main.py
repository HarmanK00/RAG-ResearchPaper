import openai
import yfinance as yf
import requests
from flask import Flask, request, jsonify, render_template
import os
import re
from datetime import datetime

# Flask app initialization
app = Flask(__name__)

# API keys (using environment variables)
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Function to fetch company fundamentals from Yahoo Finance
def fetch_fundamentals_from_yahoo_finance(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="max")  # Fetching all available data to get historical context
        if data.empty:
            return {"error": "No data found for the given ticker"}

        pe_ratio = stock.info.get('trailingPE', "N/A")
        eps = stock.info.get('trailingEps', "N/A")
        market_cap = stock.info.get('marketCap', "N/A")

        return {
            "ticker": ticker,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "eps": eps
        }
    except Exception as e:
        return {"error": str(e)}

# Function to compare current data with previous year
def compare_with_previous_year(data, year):
    try:
        historical_data = data.get('historical_data')
        if historical_data is None:
            return "No historical data available for comparison."

        # Find data from the specified year
        year_str = str(year)
        historical_data_year = historical_data[historical_data.index.year == int(year)]
        
        if historical_data_year.empty:
            return f"No data available for the year {year}."

        avg_price_last_year = historical_data_year['Close'].mean()
        current_price = data['closing_price']

        comparison = f"Comparing Tesla's performance in {year} to its current state:\n"
        comparison += f"Average Closing Price in {year}: ${avg_price_last_year:.2f}\n"
        comparison += f"Current Closing Price: ${current_price:.2f}\n"
        
        if current_price > avg_price_last_year:
            comparison += "Tesla is performing better compared to the same period in the previous year."
        else:
            comparison += "Tesla is performing worse compared to the same period in the previous year."

        return comparison
    except Exception as e:
        return f"Error in comparing data: {str(e)}"

# Route to render the HTML form for the UI
@app.route('/')
def index():
    return render_template('index.html')

# Flask route to generate a response from ChatGPT
@app.route('/generate-response', methods=['POST'])
def generate_response():
    try:
        # Determine if the request is from a form or JSON
        if request.content_type == 'application/json':
            # Request is from Postman or JSON-based
            user_query = request.json.get('query', '')
            company_name = request.json.get('company', 'AAPL')
        else:
            # Request is from the HTML form
            user_query = request.form.get('query', '')
            company_name = request.form.get('company', 'AAPL')

        # Extract year from the user's query (if any)
        year_match = re.search(r'\b(20\d{2})\b', user_query)
        comparison_year = int(year_match.group(1)) if year_match else None

        # Fetch company fundamentals from Yahoo Finance
        yahoo_data = fetch_fundamentals_from_yahoo_finance(company_name, period="20y")
        if "error" in yahoo_data:
            return jsonify({'response': f"Error fetching data from Yahoo Finance: {yahoo_data['error']}"})

        # If a year is specified, perform comparison
        comparison_response = ""
        if comparison_year:
            comparison_response = compare_with_previous_year(yahoo_data, comparison_year)

        # Fetch real-time trading data from Polygon.io
        polygon_data = fetch_real_time_data_from_polygon(company_name)
        if "error" in polygon_data:
            return jsonify({'response': f"Error fetching data from Polygon.io: {polygon_data['error']}"})

        # Combine financial data from both sources
        combined_data = (
            f"Yahoo Finance Data for {company_name}:\n"
            f"Market Cap: {yahoo_data['market_cap']}\n"
            f"P/E Ratio: {yahoo_data['pe_ratio']}\n"
            f"Earnings Per Share (EPS): {yahoo_data['eps']}\n\n"
            f"Polygon.io Data for {company_name}:\n"
            f"Latest Closing Price: ${polygon_data['closing_price']}\n"
            f"Trading Volume: {polygon_data['volume']}\n"
            f"User Query: {user_query}\n"
        )

        # Add comparison response if available
        if comparison_response:
            combined_data += f"\n{comparison_response}\n"

        combined_data += f"\nPlease provide a detailed summary of {company_name}'s financial health, recent performance, and future market outlook based on the above data."

        # Generate a response from GPT-4
        openai.api_key = OPENAI_API_KEY
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=combined_data,
            max_tokens=1000,
            temperature=0.9
        )
        return jsonify({'response': response['choices'][0]['text'].strip()})

    except Exception as e:
        # Catch all exceptions and provide detailed error feedback
        print(f"Error during request processing: {e}")
        return jsonify({'response': f"An error occurred while generating the response: {str(e)}"})

# Running the Flask server
if __name__ == '__main__':
    app.run(debug=True)
