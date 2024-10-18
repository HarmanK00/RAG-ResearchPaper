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

# Function to fetch all available company metrics from Yahoo Finance
def fetch_all_fundamentals_from_yahoo_finance(ticker):
    try:
        stock = yf.Ticker(ticker)
        stock_info = stock.info

        if not stock_info:
            return {"error": "No data found for the given ticker"}

        # Return the entire dictionary of metrics
        return stock_info
    except Exception as e:
        return {"error": str(e)}

# Function to fetch real-time financial metrics from Polygon.io
def fetch_financial_data_from_polygon(ticker):
    polygon_url = f"https://api.polygon.io/vX/reference/financials?ticker={ticker}&limit=1&apiKey={POLYGON_API_KEY}"
    
    try:
        response = requests.get(polygon_url)
        if response.status_code == 200:
            polygon_data = response.json()
            return polygon_data['results'] if 'results' in polygon_data else {"error": "No data found"}
        else:
            return {"error": f"Error fetching data from Polygon.io: {response.status_code}"}
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
            # Request is from Postman or JSON-based
            user_query = request.json.get('query', '')
            company_name = request.json.get('company', 'AAPL')
        else:
            # Request is from the HTML form
            user_query = request.form.get('query', '')
            company_name = request.form.get('company', 'AAPL')

        # Combine financial data from both Yahoo Finance and Polygon.io
        combined_data = combine_financial_data(company_name)

        # Generate a response from GPT-4
        openai.api_key = OPENAI_API_KEY
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": (
                        "You are a financial analyst assistant that provides real-time financial analysis "
                        "using up-to-date data from Yahoo Finance and Polygon.io. Analyze and summarize the data."
                    )},
                    {"role": "user", "content": f"Here is the real-time data for {company_name}:\n{combined_data}\n\n{user_query}"}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            return jsonify({'response': response['choices'][0]['message']['content']})
        except Exception as e:
            return jsonify({'response': f"Error generating response from GPT-4: {str(e)}"})

    except Exception as e:
        # Catch all exceptions and provide detailed error feedback
        print(f"Error during request processing: {e}")
        return jsonify({'response': f"An error occurred while generating the response: {str(e)}"})

# Running the Flask server
if __name__ == '__main__':
    app.run(debug=True)

