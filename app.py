from collections import defaultdict
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import plotly.graph_objs as go
import json
from plotly.utils import PlotlyJSONEncoder
from datetime import datetime
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from flask import Flask, jsonify
from threading import Thread
from get_quotes import get_quotes
from datetime import date

STRIKE_PRICE_MAX = 45
STRIKE_PRICE_MIN = 5

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'options.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
db = SQLAlchemy(app)

# Assuming your models are defined using db.Model
class DailyOption(db.Model):
    __tablename__ = 'daily_option'
    quote_type = db.Column(db.String(10), primary_key=True)
    symbol = db.Column(db.String(10), primary_key=True)
    expiration = db.Column(db.Date, primary_key=True)
    strike = db.Column(db.Numeric(10, 2), primary_key=True)  # Changed to Numeric
    right = db.Column(db.String(1), primary_key=True)
    date = db.Column(db.DateTime, primary_key=True)
    open = db.Column(db.Numeric(10, 2))  # Changed to Numeric
    high = db.Column(db.Numeric(10, 2))  # Changed to Numeric
    low = db.Column(db.Numeric(10, 2))  # Changed to Numeric
    close = db.Column(db.Numeric(10, 2))  # Changed to Numeric
    volume = db.Column(db.Integer)

class VixData(db.Model):
    __tablename__ = 'vix_data'

    symbol = db.Column(db.String, primary_key=True)
    date = db.Column(db.String, primary_key=True)
    open = db.Column(db.Numeric(10, 2))
    high = db.Column(db.Numeric(10, 2))
    low = db.Column(db.Numeric(10, 2))
    close = db.Column(db.Numeric(10, 2))
    volume = db.Column(db.Integer)
    average = db.Column(db.Numeric(10, 2))
    barCount = db.Column(db.Integer)

    def __repr__(self):
        return f"<VixData(symbol='{self.symbol}', date='{self.date}', close={self.close})>"

@app.route('/')
def index():
    # Fetch unique values for dropdowns
    quote_types = db.session.query(DailyOption.quote_type.distinct()).all()
    symbols = db.session.query(DailyOption.symbol.distinct()).all()
    # Fetch expirations and filter out past dates
    today = date.today()
    expirations = db.session.query(DailyOption.expiration.distinct()).filter(DailyOption.expiration >= today).all()
    expiration_dates = [exp[0].strftime('%Y-%m-%d') for exp in expirations]
    
    expiration_dates = [exp[0].strftime('%Y-%m-%d') for exp in expirations]
    strikes = db.session.query(DailyOption.strike.distinct()).all()
    rights = db.session.query(DailyOption.right.distinct()).all()

    return render_template('index.html', symbols=symbols,
                           expirations=expiration_dates, strikes=strikes, rights=rights)

import numpy as np

@app.route('/get_chart_data')
def get_chart_data():
    symbol = request.args.get('symbol')
    expiration = request.args.get('expiration')
    strike = request.args.get('strike')
    right = request.args.get('right')

    print(f"Fetching data for: {symbol}, {expiration}, {strike}, {right}")  # Debug print

    # Query the daily_option view using SQLAlchemy ORM
    data = db.session.query(DailyOption.date, DailyOption.open, DailyOption.high, DailyOption.low, DailyOption.close) \
        .filter(DailyOption.symbol == symbol,
                DailyOption.expiration == expiration,
                DailyOption.strike == strike,
                DailyOption.right == right,
                # DailyOption.strike >= STRIKE_PRICE_MIN,
                # DailyOption.strike <= STRIKE_PRICE_MAX
                 ).all()

    print(f"Data points fetched: {len(data)}")  # Debug print

    # Convert to a list of dictionaries for D3.js
    result = [{'date': d[0].isoformat(), 'open': d[1], 'high': d[2], 'low': d[3], 'close': d[4]} for d in data]

    return jsonify(result)

@app.route('/check_db')
def check_db():
    try:
        # Print the database URL and current working directory
        print("Database URL:", app.config['SQLALCHEMY_DATABASE_URI'])
        print("Current Working Directory:", os.getcwd())

        # Query the database to check if the table exists and fetch some data
        data = db.session.query(DailyOption).limit(5).all()
        if data:
            return jsonify({"status": "success", "data": [d.symbol for d in data]})
        else:
            return jsonify({"status": "success", "data": "No data found in the table."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get_option_chain')
def get_option_chain():
    expiration = request.args.get('expiration')
    symbol = request.args.get('symbol')
    quote_type = request.args.get('quote_type')

    option_chain_data = get_option_chain_data(symbol, expiration, quote_type)
    print(option_chain_data)
    df = pd.DataFrame(option_chain_data)
    

    # Add this line to get the current date and time
    quote_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Convert to float if possible, otherwise keep as is
    strike_prices = [float(x) if isinstance(x, (int, float, str)) and x != '' else x for x in df['strike'].tolist()]
    call_prices = [float(x) if isinstance(x, (int, float, str)) and x != '' else x for x in df['callLastPrice'].tolist()]
    put_prices = [float(x) if isinstance(x, (int, float, str)) and x != '' else x for x in df['putLastPrice'].tolist()]
    
    result = {
        'strikePrices': strike_prices,
        'callPrices': call_prices,
        'putPrices': put_prices,
        'callVolumes': df['callVolume'].tolist(),
        'putVolumes': df['putVolume'].tolist(),
        'vixValue': get_current_vix_value(),
        'quoteDate': quote_date
    }
    
    app.logger.info(f"Sending data: {result}")  # Log the data being sent
    
    return jsonify(result)

class OptionDayQuote:
    def __init__(self, strike=0, call=0, put=0, call_volume=0, put_volume=0):
        self.strike = strike
        self.call = call
        self.put = put
        self.call_volume = call_volume
        self.put_volume = put_volume
    def __repr__(self):
        return f"<OptionDayQuote(strike={self.strike}, call={self.call}, put={self.put}, call_volume={self.call_volume}, put_volume={self.put_volume})>\n"

def get_option_chain_data(symbol, expiration, quote_type):
    print(f"Fetching option chain data for: symbol={symbol}, expiration={expiration}, quote_type={quote_type}")
    print(f"STRIKE_PRICE_MIN={STRIKE_PRICE_MIN}, STRIKE_PRICE_MAX={STRIKE_PRICE_MAX}")

    ## get the last date in the database of the symbol, expiration, quote_type 
    last_date_query = DailyOption.query.filter(
        DailyOption.symbol == symbol,
        DailyOption.expiration == expiration,
        DailyOption.quote_type == quote_type
    ).order_by(DailyOption.date.desc())
    
    print("Last date query:", last_date_query)
    last_date = last_date_query.first()
    print('last_date object:', last_date)
    
    if last_date is None:
        print("No matching data found for the given criteria.")
        return []
    
    last_date = last_date.date.strftime('%Y-%m-%d')  
    print('Last date:', last_date)


    options_query = DailyOption.query.filter(
        DailyOption.symbol == symbol,
        DailyOption.date == last_date,  
        DailyOption.expiration == expiration,
        DailyOption.quote_type == quote_type,
        DailyOption.strike >= STRIKE_PRICE_MIN,
        DailyOption.strike <= STRIKE_PRICE_MAX
    ).order_by(DailyOption.strike.asc())
    
    print("Options query:", options_query)
    options = options_query.all()
    print('Number of options found:', len(options))
    print('First few options:', options[:5] if options else 'None')

    option_chain = defaultdict(OptionDayQuote)
    for option in options:
        o = option_chain[option.strike] 
        o.strike = option.strike
        if option.right == 'C':
            o.call = option.close
            o.call_volume = option.volume            
        else:
            o.put = option.close
            o.put_volume = option.volume            

    print("Number of items in option_chain:", len(option_chain))
    print("First few items in option_chain:", list(option_chain.items())[:5])

    options = option_chain.values()
    options = sorted(options, key=lambda x: x.strike)
    print("Number of final options:", len(options))
    print("First few final options:", options[:5])

    return [
        {
            'strike': option.strike,
            'callLastPrice': option.call,
            'putLastPrice': option.put,
            'callVolume': option.call_volume,
            'putVolume': option.put_volume
        }
        for option in options
    ]

def get_current_vix_value():
    latest_vix = VixData.query.order_by(VixData.date.desc()).first()
    return latest_vix.close if latest_vix else None

@app.route('/option_calculator', methods=['GET', 'POST'])
def option_calculator():
    if request.method == 'POST':
        # Process form data
        stock = request.form.get('stock')
        shares = int(request.form.get('shares'))
        options = []
        
        # Process options data
        for i in range(10):  # Assume max 10 options
            strike = request.form.get(f'strike_{i}')
            if strike:
                options.append({
                    'strike': float(strike),
                    'type': request.form.get(f'type_{i}'),
                    'position': request.form.get(f'position_{i}'),
                    'price': float(request.form.get(f'price_{i}')),
                    'contracts': int(request.form.get(f'contracts_{i}'))
                })
        
        # Calculate profit/loss chart data
        chart_data = calculate_profit_loss(stock, shares, options)
        
        return jsonify(chart_data)
    
    return render_template('option_calculator.html')

def calculate_profit_loss(stock, shares, options):
    # Generate a range of potential stock prices
    min_price = min(option['strike'] for option in options) * 0.5
    max_price = max(option['strike'] for option in options) * 1.5
    stock_prices = np.linspace(min_price, max_price, 100)
    
    profits = []
    for price in stock_prices:
        profit = (price - float(stock)) * shares
        for option in options:
            if option['type'] == 'call':
                option_profit = max(0, price - option['strike']) - option['price']
            else:  # put
                option_profit = max(0, option['strike'] - price) - option['price']
            
            if option['position'] == 'short':
                option_profit = -option_profit
            
            profit += option_profit * 100 * option['contracts']  # 100 shares per contract
        profits.append(profit)
    
    return {
        'stockPrices': stock_prices.tolist(),
        'profits': profits
    }

@app.route('/start_get_quotes', methods=['POST'])
def start_get_quotes():
    get_quotes()

if __name__ == '__main__':
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)
