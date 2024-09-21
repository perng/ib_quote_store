from ib_insync import *
import pandas as pd
from datetime import datetime, timedelta
import pytz

def get_option_data(symbol, expiration, strike, right, days_back=90):
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)

    try:
        option = Option(symbol, expiration, strike, right, exchange='SMART', currency='USD')
        ib.qualifyContracts(option)

        end_datetime = datetime.now(pytz.timezone('US/Eastern'))
        start_datetime = end_datetime - timedelta(days=days_back)

        bars = ib.reqHistoricalData(
            option,
            endDateTime=end_datetime,
            durationStr=f'{days_back} D',
            barSizeSetting='1 hour',
            whatToShow='TRADES',
            useRTH=True,
        )

        df = util.df(bars)
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_convert('US/Eastern')
            df = df[(df['date'] >= start_datetime) & (df['date'] <= end_datetime)]
        
        return df

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

    finally:
        ib.disconnect()

# Example usage
if __name__ == "__main__":
    symbol = 'SPY'
    expiration = '20240923'  # Use a nearer expiration date
    strike = 566.0  # Use a strike price closer to current market price
    right = 'C'

    df = get_option_data(symbol, expiration, strike, right)
    if df is not None and not df.empty:
        print(df)
    else:
        print("Failed to retrieve data or no data available.")