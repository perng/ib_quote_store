from flask import render_template, request, jsonify
import yfinance as yf
import pandas as pd
import json
import numpy as np
from datetime import datetime, timedelta

def smile_route():
    return render_template('smile.html')

def get_smile_data():
    symbol = request.args.get('symbol', 'SPY')
    
    # Fetch option chain data
    stock = yf.Ticker(symbol)
    
    # Get all expiration dates
    expirations = stock.options
    if not expirations:
        return jsonify({"error": "No options data available for this symbol"})
    
    # Create a list to hold all the figures
    figures_data = []

    # Get current date
    current_date = datetime.now().date()

    # Variables to track global min and max implied volatility
    global_min_iv = float('inf')
    global_max_iv = float('-inf')

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
        
        # Update global min and max implied volatility
        global_min_iv = min(global_min_iv, calls['impliedVolatility'].min(), puts['impliedVolatility'].min())
        global_max_iv = max(global_max_iv, calls['impliedVolatility'].max(), puts['impliedVolatility'].max())
        
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

    # Add a small padding to the y-axis range
    y_min = max(0, global_min_iv - 0.05)  # Ensure y_min is not negative
    y_max = global_max_iv + 0.05

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
    return json.dumps({
        'symbol': symbol, 
        'figures': figures_data,
        'y_min': y_min,
        'y_max': y_max
    }, cls=NumpyEncoder)
