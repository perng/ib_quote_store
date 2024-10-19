from flask import render_template, request, jsonify
import yfinance as yf
import pandas as pd
import json
import numpy as np
from datetime import datetime, timedelta
from functools import lru_cache, wraps
import time

def smile_route():
    return render_template('smile.html')

# Custom time-based cache decorator
def timed_lru_cache(seconds: int, maxsize: int = 128):
    def wrapper_cache(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = seconds
        func.expiration = time.time() + seconds

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if time.time() > func.expiration:
                func.cache_clear()
                func.expiration = time.time() + func.lifetime

            return func(*args, **kwargs)

        return wrapped_func

    return wrapper_cache

@timed_lru_cache(seconds=3600)  # Cache for 1 hour
def fetch_option_data(symbol):
    # Fetch option chain data
    stock = yf.Ticker(symbol)
    
    # Get all expiration dates
    expirations = stock.options
    if not expirations:
        return {"error": "No options data available for this symbol"}
    
    # Create a list to hold all the figures
    figures_data = []

    # Get current date
    current_date = datetime.now().date()

    # Create a chart for each expiration date
    for expiration in expirations:
        # Fetch option chain for the expiration
        opt = stock.option_chain(expiration)
        
        # Filter out data rows with last trade date older than 30 days
        calls = opt.calls[opt.calls['lastTradeDate'].dt.date > (current_date - timedelta(days=30))]
        puts = opt.puts[opt.puts['lastTradeDate'].dt.date > (current_date - timedelta(days=30))]
        
        # Sort calls and puts separately
        calls = calls.sort_values('strike')
        puts = puts.sort_values('strike')
        
        # Skip this expiration if no data is left after filtering
        if calls.empty and puts.empty:
            continue
        
        # Create the plot data
        figure_data = {
            'expiration': expiration,
            'calls': {
                'x': calls['strike'].tolist(),
                'y': calls['impliedVolatility'].tolist(),
            },
            'puts': {
                'x': puts['strike'].tolist(),
                'y': puts['impliedVolatility'].tolist(),
            }
        }

        figures_data.append(figure_data)

    return {'symbol': symbol, 'figures': figures_data}

def get_smile_data():
    symbol = request.args.get('symbol', 'SPY')
    
    # Fetch data (will use cached data if available and not expired)
    data = fetch_option_data(symbol)

    # Custom JSON encoder to handle NumPy types
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return super(NumpyEncoder, self).default(obj)

    # Convert all figures data to JSON using the custom encoder
    return json.dumps(data, cls=NumpyEncoder)
