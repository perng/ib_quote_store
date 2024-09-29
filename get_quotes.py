import asyncio
from ib_insync import *
import pandas as pd
from datetime import datetime, timedelta
import pytz
import sqlite3
import sys
import time

STRIKE_PRICE_LIMIT = 100

def store_option_data(df, symbol, expiration, strike, right, quote_type):
    try:
        expiration_date = datetime.strptime(expiration, '%Y%m%d').date().isoformat()
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
            latest = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
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
        # Convert expiration to the format used in the database
        expiration_date = datetime.strptime(expiration, '%Y%m%d').date().isoformat()
        
        # Get the latest date from quote_status
        cursor.execute('''
            SELECT latest FROM quote_status
            WHERE symbol = ? AND expiration = ? AND strike = ? AND right = ? AND quote_type = ?
        ''', (symbol, expiration_date, strike, right, quote_type))
        
        result = cursor.fetchone()
                
        if result:
            latest = datetime.strptime(result[0] , '%Y-%m-%d %H:%M:%S') + timedelta(days=1)
            print(f"Latest date: {latest}")
            current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) 
            days_back = 0
            while latest.date() < current_date.date():
                if latest.weekday() < 5:  # Monday = 0, Friday = 4
                    days_back += 1
                latest += timedelta(days=1)
            
            return days_back  # Ensure we always request at least one day of data
        else:
            print('no previous data\n')
            return 30  # Default to 30 days if no previous data exists
    
    except Exception as e:
        print(f"An error occurred while getting days_back: {str(e)}\n")
        return 30  # Default to 30 days if there's an error
    
    finally:
        conn.close()

def get_option_data(ib, symbol, exchange,expiration, strike, right, whatToShow):
    days_back = get_days_back(symbol, expiration, strike, right, whatToShow)  # Assuming 'TRADES' as default quote_type
    print(f"Days back: {days_back}")
    if days_back == 0:
        print(f"No new data to retrieve for {symbol} {exchange} {expiration} {strike} {right}. Data is up to date.")
        return None

    try:
        option = Option(symbol, expiration, strike, right, exchange=exchange, currency='USD')
        ib.qualifyContracts(option)

        end_datetime = datetime.now(pytz.timezone('US/Eastern'))
        start_datetime = end_datetime - timedelta(days=days_back)
        bars = ib.reqHistoricalData(
            option,
            endDateTime=end_datetime,
            durationStr=f'{days_back} D',
            barSizeSetting='1 hour',
            whatToShow=whatToShow,
            useRTH=True,
            timeout=5
        )

        df = util.df(bars)

        # sys.exit()
        if df is not None:
            df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_convert('US/Eastern')
            df = df[(df['date'] >= start_datetime) & (df['date'] <= end_datetime)]
            
            # Add columns for option details
            df['symbol'] = symbol
            df['expiration'] = pd.to_datetime(expiration).date().isoformat()
            df['strike'] = strike
            df['right'] = right
            df['quote_type'] = whatToShow  # Add the new column
            
            # Convert date column to ISO format string
            df['date'] = df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Ensure all required columns are present and in the correct order
            df = df[['symbol', 'expiration', 'strike', 'right', 'date', 'open', 'high', 'low', 'close', 'volume', 'average', 'barCount', 'quote_type']]
            
            # print(df)
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
        ib.connect('127.0.0.1', 7497, clientId=1)
        time.sleep(1)
        
        # Call the main function from get_vix.py
        # get_vix_main(ib)
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