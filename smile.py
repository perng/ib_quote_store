from flask import render_template, request, jsonify
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import json
import numpy as np

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

    # Create a chart for each expiration date
    for expiration in expirations:
        # Fetch option chain for the expiration
        opt = stock.option_chain(expiration)
        
        # Sort calls and puts separately
        calls = opt.calls.sort_values('strike')
        puts = opt.puts.sort_values('strike')
        
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
    return json.dumps({'symbol': symbol, 'figures': figures_data}, cls=NumpyEncoder)
