from ib_insync import *
import pandas as pd
from datetime import datetime, timedelta

def get_vix_option_data(expiration, strike, right, start_date, end_date):
    # Connect to IBKR
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)  # Use 7497 for TWS paper trading, 7496 for live

    try:        
        # Define the VIX option contract
        vix_option = Option('SPY', expiration, strike, right, exchange='CBOE', currency='USD', multiplier='100')
        ib.qualifyContracts(vix_option)

        # Calculate duration
        end_datetime = datetime.strptime(end_date, '%Y%m%d')
        start_datetime = datetime.strptime(start_date, '%Y%m%d')
        duration = (end_datetime - start_datetime).days + 1
        print('duration: ', duration)
        # Request historical data
        bars = ib.reqHistoricalData(
            vix_option,
            endDateTime=end_datetime,
            durationStr=f'{duration} D',
            barSizeSetting='1 day',
            whatToShow='TRADES',  # Changed from 'MIDPOINT' to 'TRADES'
            useRTH=True,
        )
        print(bars)

        # Convert to DataFrame
        df = util.df(bars)
        
        # Filter the dataframe to include only the specified date range
        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['date'] >= start_datetime) & (df['date'] <= end_datetime)]
        
        return df

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

    finally:
        # Disconnect
        ib.disconnect()

# Example usage
if __name__ == "__main__":
    expiration = '20240923'  # Format: YYYYMMDD (adjust to a valid future date)
    strike = 566.0  # Adjust based on current VIX levels
    right = 'C'  # 'C' for Call, 'P' for Put
    start_date = '20240917'  # Adjust as needed
    end_date =   '20240919'  # Adjust as needed

    df = get_vix_option_data(expiration, strike, right, start_date, end_date)
    if df is not None:
        print(df)
    else:
        print("Failed to retrieve data.")