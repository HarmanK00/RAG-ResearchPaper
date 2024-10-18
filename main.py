import openai
import yfinance as yf
import requests
from flask import Flask, request, jsonify, render_template
import os

# Flask app initialization
app = Flask(__name__)

# API keys (using environment variables)
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Function to fetch all financial data from Yahoo Finance
def fetch_all_fundamentals_from_yahoo_finance(ticker):
    try:
        stock = yf.Ticker(ticker)
        stock_info = stock.info

        if not stock_info:
            return {"error": "No data found for the given ticker"}

        return stock_info  # Return all available fundamentals
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

# Function to fetch real-time trading data from Polygon.io
def fetch_financial_data_from_polygon(ticker):
    polygon_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/2023-01-09/2023-01-09?apiKey={POLYGON_API_KEY}"
    try:
        polygon_response = requests.get(polygon_url)
        if polygon_response.status_code == 200 and polygon_response.json().get("results"):
            return polygon_response.json()["results"]  # Returns results from Polygon.io
        else:
            return {"error": "No data found for the given ticker on Polygon.io"}
    except Exception as e:
        return {"error": str(e)}

# Combine the Yahoo Finance and Polygon.io data
def combine_financial_data(ticker):
    yahoo_data = fetch_all_fundamentals_from_yahoo_finance(ticker)
    polygon_data = fetch_financial_data_from_polygon(ticker)

    # Handle cases where data might be missing
    if "error" in yahoo_data or "error" in polygon_data:
        return f"Error in fetching data: {yahoo_data.get('error', '')}, {polygon_data.get('error', '')}"

    combined_data = f"Below is the real-time financial data for {ticker}:\n\n"

    # Yahoo Finance data
    combined_data += "Yahoo Finance Data:\n"
    for key, value in yahoo_data.items():
        combined_data += f"{key}: {value}\n"

    # Polygon.io data
    combined_data += "\nPolygon.io Data:\n"
    for key, value in polygon_data[0].items():  # Assuming we are taking the first result
        combined_data += f"{key}: {value}\n"

    return combined_data

# Flask route to generate a response from GPT-4
@app.route('/generate-response', methods=['POST'])
def generate_response():
    try:
        # Determine if the request is from a form or JSON
        if request.content_type == 'application/json':
            user_query = request.json.get('query', '')
            company_name = request.json.get('company', 'AAPL')
        else:
            user_query = request.form.get('query', '')
            company_name = request.form.get('company', 'AAPL')

        # Check if the query asks for historical data
        if any(keyword in user_query.lower() for keyword in ["compare", "year", "past", "historical"]):
            historical_data = fetch_historical_data_from_yahoo_finance(company_name)
            if "error" in historical_data:
                return jsonify({'response': f"Error fetching historical data: {historical_data['error']}"})
            
            # Combine historical data
            combined_data = (
                f"Below is the historical financial data for {company_name}:\n\n"
                f"Closing prices and volume data from the last available years were fetched.\n\n"
                f"Please analyze {company_name}'s financial health by comparing the historical data with "
                f"the most recent figures and discuss trends or any notable changes."
            )
        else:
            combined_data = combine_financial_data(company_name)
        
        # Generate a response from GPT-4
        openai.api_key = OPENAI_API_KEY
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a financial analyst assistant who works with real-time and historical data."},
                    {"role": "user", "content": combined_data}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            return jsonify({'response': response['choices'][0]['message']['content']})
        except Exception as e:
            return jsonify({'response': f"Error generating response from OpenAI: {str(e)}"})

    except Exception as e:
        return jsonify({'response': f"An error occurred while generating the response: {str(e)}"})

# Running the Flask server
if __name__ == '__main__':
    app.run(debug=True)

