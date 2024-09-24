import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import plotly.graph_objs as go
import json
from plotly.utils import PlotlyJSONEncoder

app = Flask(__name__)
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'options.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
db = SQLAlchemy(app)

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

@app.route('/')
def index():
    # Fetch unique values for dropdowns
    quote_types = db.session.query(DailyOption.quote_type.distinct()).all()
    symbols = db.session.query(DailyOption.symbol.distinct()).all()
    expirations = db.session.query(DailyOption.expiration.distinct()).all()
    strikes = db.session.query(DailyOption.strike.distinct()).all()
    rights = db.session.query(DailyOption.right.distinct()).all()

    return render_template('index.html', symbols=symbols,
                           expirations=expirations, strikes=strikes, rights=rights)

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
                DailyOption.right == right).all()

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

if __name__ == '__main__':
    app.run(debug=True)
