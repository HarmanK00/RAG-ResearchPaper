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

# Function to fetch company fundamentals from Yahoo Finance
def fetch_fundamentals_from_yahoo_finance(ticker):
    try:
        stock = yf.Ticker(ticker)
        stock_info = stock.info

        if not stock_info:
            return {"error": "No data found for the given ticker"}

        pe_ratio = stock_info.get('trailingPE', "N/A")
        eps = stock_info.get('trailingEps', "N/A")
        market_cap = stock_info.get('marketCap', "N/A")

        return {
            "ticker": ticker,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "eps": eps
        }
    except Exception as e:
        return {"error": str(e)}

# Function to fetch real-time trading data from Polygon.io
def fetch_real_time_data_from_polygon(ticker):
    polygon_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/2023-01-09/2023-01-09?apiKey={POLYGON_API_KEY}"
    try:
        polygon_response = requests.get(polygon_url)
        if polygon_response.status_code == 200 and polygon_response.json().get("results"):
            polygon_data = polygon_response.json()
            closing_price = polygon_data["results"][0].get("c", "N/A")
            volume = polygon_data["results"][0].get("v", "N/A")
            return {
                "closing_price": closing_price,
                "volume": volume
            }
        else:
            return {"error": "No data found for the given ticker on Polygon.io"}
    except Exception as e:
        return {"error": str(e)}

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

        # Fetch company fundamentals from Yahoo Finance
        yahoo_data = fetch_fundamentals_from_yahoo_finance(company_name)
        if "error" in yahoo_data:
            return jsonify({'response': f"Error fetching data from Yahoo Finance: {yahoo_data['error']}"})

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
            f"Please provide a detailed summary of {company_name}'s financial health, recent performance, and future market outlook based on the above data."
        )

        # Generate a response from GPT-4
        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a financial analyst assistant."},
                {"role": "user", "content": combined_data}
            ],
            max_tokens=1000,
            temperature=0.9
        )
        return jsonify({'response': response['choices'][0]['message']['content']})

    except Exception as e:
        # Catch all exceptions and provide detailed error feedback
        print(f"Error during request processing: {e}")
        return jsonify({'response': f"An error occurred while generating the response: {str(e)}"})

# Running the Flask server
if __name__ == '__main__':
    app.run(debug=True)

