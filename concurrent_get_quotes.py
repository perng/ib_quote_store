import asyncio
from ib_async import *
import pandas as pd
import datetime
import nest_asyncio
import pytz
import sqlite3
import sys
import time
from get_vix import main as get_vix_main

STRIKE_PRICE_LIMIT = 100

def store_option_data(df):
    try:
        
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
        
        
        conn.commit()
        if df is not None and not df.empty:
            print(f"Data stored in SQLite. Row count: {len(df)}")

    except Exception as e:
        print(f"store_option_data: An error occurred while storing data: {str(e)}")
    finally:
        conn.close()

def get_days_back(symbol, expiration, strike, right, quote_type):
    return 2
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
        print(f"get_days_back: An error occurred while getting days_back: {str(e)}")
        return 30  # Default to 30 days if there's an error
    
    finally:
        conn.close()

async def get_option_data(ib, contract, whatToShow):
    print('get_option_data', contract)
    symbol = contract.symbol
    expiration = contract.lastTradeDateOrContractMonth
    strike = contract.strike
    exchange = contract.exchange
    right = contract.right
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

        print('contract:', option)
        bars = await ib.reqHistoricalDataAsync(
            option,
            endDateTime=end_datetime,
            durationStr=f'{days_back} D',
            barSizeSetting='1 hour',
            whatToShow=whatToShow,
            useRTH=True,
            timeout=60
        )

        df = util.df(bars)

        print("empty 1")
        if df is not None:
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
            print('number of row:', len(df))    
        return df

    except Exception as e:
        print(f"get_option_data: An error occurred: {str(e)}")
        return None


def get_option_chain(ib, symbol):
    print('get_option_chain', symbol)
    vix = Index('VIX', 'CBOE')
    print('qualifying contracts')
    ib.qualifyContracts(vix)
    print('requesting sec def opt params')
    chains = ib.reqSecDefOptParams(vix.symbol, '', vix.secType, vix.conId)
    print('filtering chains')
    return [chain for chain in chains if chain.exchange == 'CBOE']

async def get_quotes(ib, option_chains):
    print('get_quotes')
    # Import the main function from get_vix.py

    symbol = 'VIX'
    rights = ['P', 'C']
    exchanges = ['SMART', 'CBOE']   
    whatToShow = 'TRADES'
    STRIKE_PRICE_LIMIT = 100

    print('processing option chains')
    contracts = []
    for chain in option_chains:
            for expiration in chain.expirations:
                for strike in chain.strikes:
                    if strike <= STRIKE_PRICE_LIMIT:
                        for right in rights:
                                for exchange in exchanges:
                                    contract = Option(
                                                    symbol=symbol,
                                                    lastTradeDateOrContractMonth=expiration,
                                                    strike=strike,
                                                    right=right,
                                                    exchange='SMART',
                                                    currency='USD')
                                    contracts.append(contract)


    print('number of contracts:', len(contracts))
    qualified_contracts = ib.qualifyContracts(*contracts)
    print('number of quantified contracts:', len(qualified_contracts))
        
    # Create a semaphore with a limit of 50
    semaphore = asyncio.Semaphore(50)

    async def fetch_with_semaphore(task):
        async with semaphore:
            try:
                result = await task
                return result if result is not None else pd.DataFrame()  # Return an empty DataFrame if None
            except Exception as e:
                print(f"Error fetching data: {e}")
                return pd.DataFrame()  # Ret urn an empty DataFrame on error

    for i in range(0, len(qualified_contracts), 50):
        tasks = [get_option_data(ib, contract, whatToShow) for contract in qualified_contracts[i:min(i+50, len(qualified_contracts))]]    
        results = await asyncio.gather(*tasks)
        #results = [df for df in results if ]
        print('results 2', i, len(results))

        if results:
            merged_df = pd.concat(results, ignore_index=True)
            # Store the merged DataFrame
            store_option_data(merged_df)
        else:
            print("No valid results to merge.")
            
                                    
                                    
    
# Example usage
if __name__ == "__main__":
    # get_quotes()
    nest_asyncio.apply()
    symbol = 'VIX'
    ib = IB()
    
    try:
        # Attempt to connect to port 7497
        try:
            ib.connect('127.0.0.1', 7496, clientId=1)
            time.sleep(1)
            print('Connected to IB on port 7496')
        except Exception as e:
            print(f"Failed to connect on port 7497: {str(e)}. Trying port 7496...")
            # Attempt to connect to port 7496 if the first connection fails
            ib.connect('127.0.0.1', 7497, clientId=1)
            time.sleep(1)
            print('Connected to IB on port 7497')

        # Call the main function from get_vix.py
        get_vix_main()
        print('getting option chains')
        option_chains = get_option_chain(ib, symbol)

        results = asyncio.run(get_quotes(ib, option_chains))

    except Exception as e:
            print(f"main: An error occurred: {str(e)}")
    finally:
        ib.disconnect()
        print("IB connection closed.")

