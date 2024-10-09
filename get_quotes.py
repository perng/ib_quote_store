import asyncio
from ib_insync import *
import pandas as pd
import datetime

import pytz
import sqlite3
import sys
import time

STRIKE_PRICE_LIMIT = 100

def store_option_data(df, symbol, expiration, strike, right, quote_type):
    try:
        expiration_date = datetime.datetime.strptime(expiration, '%Y%m%d').date().isoformat()
        conn = sqlite3.connect('options.db')
        cursor = conn.cursor()
        
        if df is not None and not df.empty:
            # Convert DataFrame to list of tuples for SQLite insertion
            data_to_insert = df.to_records(index=False).tolist()
            
            # Store the data in SQLite
            cursor.executemany('''
                INSERT OR REPLACE INTO option_data (symbol, expiration, strike, right, date, open, high, low, close, volume, average, barCount, quote_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data_to_insert)
            
            latest = df['date'].max()
        else:
            latest = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Update quote_status table
        cursor.execute('''
            INSERT OR REPLACE INTO quote_status (symbol, expiration, strike, right, quote_type, latest)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, expiration_date, strike, right, quote_type, latest))
        
        conn.commit()
        if df is not None and not df.empty:
            print(f"Data stored in SQLite. Row count: {len(df)}")

    except Exception as e:
        print(f"An error occurred while storing data: {str(e)}")
    finally:
        conn.close()

def get_days_back(symbol, expiration, strike, right, quote_type):
    conn = sqlite3.connect('options.db')
    cursor = conn.cursor()
    
    try:
        expiration_date = datetime.datetime.strptime(expiration, '%Y%m%d').date().isoformat()
        
        cursor.execute('''
            SELECT latest FROM quote_status
            WHERE symbol = ? AND expiration = ? AND strike = ? AND right = ? AND quote_type = ?
        ''', (symbol, expiration_date, strike, right, quote_type))
        
        result = cursor.fetchone()
                
        if result:
            latest = datetime.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.timezone('US/Eastern'))
            current_date = datetime.datetime.now(pytz.timezone('US/Eastern'))
            # Check if current time is before 9:30 AM
            if current_date.time() < datetime.time(9, 30):
                current_date = current_date.replace(hour=16, minute=0, second=0, microsecond=0) - datetime.timedelta(days=1)
            # Check if current time is after 4:00 PM
            elif current_date.time() > datetime.time(16, 0):
                current_date = current_date.replace(hour=16, minute=0, second=0, microsecond=0)
            # Round down to the nearest hour between 10:00 AM and 4:00 PM
            elif current_date.time() > datetime.time(10, 0):
                current_date = current_date.replace(minute=0, second=0, microsecond=0)
            # Set to 9:30 AM if between 9:30 AM and 10:00 AM
            else:
                current_date = current_date.replace(hour=9, minute=30, second=0, microsecond=0)
            
            # If latest is more recent than or equal to the adjusted current date, return 0
            if latest >= current_date:
                return 0
            
            days_back = 0
            while latest.date() < current_date.date():
                if latest.weekday() < 5:  # Monday = 0, Friday = 4
                    days_back += 1
                latest += datetime.timedelta(days=1)
            
            return max(days_back, 1)  # Ensure we always request at least one day of data if there's a gap
        else:
            print('No previous data')
            return 30  # Default to 30 days if no previous data exists
    
    except Exception as e:
        print(f"An error occurred while getting days_back: {str(e)}")
        return 30  # Default to 30 days if there's an error
    
    finally:
        conn.close()

def get_option_data(ib, symbol, exchange, expiration, strike, right, whatToShow):
    days_back = get_days_back(symbol, expiration, strike, right, whatToShow)
    print(f"Days back: {days_back}")
    if days_back == 0:
        print(f"No new data to retrieve for {symbol} {exchange} {expiration} {strike} {right}. Data is up to date.")
        return None

    try:
        option = Option(symbol, expiration, strike, right, exchange=exchange, currency='USD')
        ib.qualifyContracts(option)

        end_datetime = datetime.datetime.now(pytz.timezone('US/Eastern')).replace(second=0, microsecond=0)
        if end_datetime.time() < datetime.time(9, 30):
            end_datetime = end_datetime.replace(hour=16, minute=0) - datetime.timedelta(days=1)
        elif end_datetime.time() > datetime.time(16, 0):
            end_datetime = end_datetime.replace(hour=16, minute=0)
        elif end_datetime.time() < datetime.time(10, 0):
            end_datetime = end_datetime.replace(hour=9, minute=30)
        else:
            end_datetime = end_datetime.replace(minute=0)

        start_datetime = end_datetime - datetime.timedelta(days=days_back)
        start_datetime = start_datetime.replace(hour=9, minute=30)

        bars = ib.reqHistoricalData(
            option,
            endDateTime=end_datetime,
            durationStr=f'{days_back} D',
            barSizeSetting='1 hour',
            whatToShow=whatToShow,
            useRTH=True,
            timeout=60
        )

        df = util.df(bars)

        if df is not None and not df.empty:
            df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_convert('US/Eastern')
            df = df[(df['date'] >= start_datetime) & (df['date'] <= end_datetime)]
            
            # Filter for specific times
            df = df[
                (df['date'].dt.time == datetime.time(9, 30)) |
                ((df['date'].dt.time >= datetime.time(10, 0)) & (df['date'].dt.time <= datetime.time(16, 0)))
            ]
            
            # Add columns for option details
            df['symbol'] = symbol
            df['expiration'] = pd.to_datetime(expiration).date().isoformat()
            df['strike'] = strike
            df['right'] = right
            df['quote_type'] = whatToShow
            
            df['date'] = df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            df = df[['symbol', 'expiration', 'strike', 'right', 'date', 'open', 'high', 'low', 'close', 'volume', 'average', 'barCount', 'quote_type']]
            
        return df

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None


def get_option_chain(ib, symbol):
    vix = Index('VIX', 'CBOE')
    print('qualifying contracts')
    ib.qualifyContracts(vix)
    print('requesting sec def opt params')
    chains = ib.reqSecDefOptParams(vix.symbol, '', vix.secType, vix.conId)
    print('filtering chains')
    return [chain for chain in chains if chain.exchange == 'CBOE']

def get_quotes():
    # Import the main function from get_vix.py
    from get_vix import main as get_vix_main

    symbol = 'VIX'
    rights = ['P', 'C']
    exchanges = ['SMART', 'CBOE']   
    whatToShowList = ['TRADES']
    STRIKE_PRICE_LIMIT = 100

    ib = IB()
    
    try:
        # Attempt to connect to port 7497
        try:
            ib.connect('127.0.0.1', 7497, clientId=1)
            time.sleep(1)
            print('Connected to IB on port 7497')
        except Exception as e:
            print(f"Failed to connect on port 7497: {str(e)}. Trying port 7496...")
            # Attempt to connect to port 7496 if the first connection fails
            ib.connect('127.0.0.1', 7496, clientId=1)
            time.sleep(1)
            print('Connected to IB on port 7496')

        # Call the main function from get_vix.py
        get_vix_main()
        print('getting option chains')
        option_chains = get_option_chain(ib, symbol)

        total_options = sum(len(chain.expirations) * len(chain.strikes) * len(rights) * len(whatToShowList) * len(exchanges) for chain in option_chains)
        processed_options = 0
        print('processing option chains')
        for chain in option_chains:
            for expiration in chain.expirations:
                for strike in chain.strikes:
                    if strike <= STRIKE_PRICE_LIMIT:
                        for right in rights:
                            for whatToShow in whatToShowList:
                                for exchange in exchanges:
                                    try:
                                        print('-'*40)
                                        print(f"Processing {symbol} {expiration} {strike} {right} {whatToShow}")
                                        df = get_option_data(ib, symbol, exchange, expiration, strike, right, whatToShow)
                                        store_option_data(df, symbol, expiration, strike, right, whatToShow)
                                        if df is not None and not df.empty:
                                            print(f"Data stored. Row count: {len(df)}")
                                        else:
                                            print("No new data or retrieval failed.")
                                    except Exception as e:
                                        print(f"Error processing option: {str(e)}")
                                    finally:
                                        processed_options += 1
                                                                        
                                    
                                    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        ib.disconnect()
        print("IB connection closed.")

# Example usage
if __name__ == "__main__":
    get_quotes()
