from ib_insync import *
import pandas as pd
from datetime import datetime, timedelta
import pytz
import sqlite3

def get_vix_data(ib):
    vix = Index('VIX', 'CBOE')
    ib.qualifyContracts(vix)

    end_datetime = datetime.now(pytz.timezone('US/Eastern'))
    start_datetime = end_datetime - timedelta(days=30)  # Get data for the last day

    bars = ib.reqHistoricalData(
        vix,
        endDateTime=end_datetime,
        durationStr='30 D',
        barSizeSetting='1 hour',
        whatToShow='TRADES',
        useRTH=True,
        timeout=10
    )

    if bars:
        df = util.df(bars)
        df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_convert('US/Eastern')
        df = df[(df['date'] >= start_datetime) & (df['date'] <= end_datetime)]
        df['date'] = df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df['symbol'] = 'VIX'  # Add the symbol column
        return df
    else:
        return None

def store_vix_data(df):
    if df is None or df.empty:
        print("No VIX data to store.")
        return

    conn = sqlite3.connect('options.db')
    cursor = conn.cursor()

    try:
        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vix_data (
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                average REAL,
                barCount INTEGER,
                PRIMARY KEY (symbol, date)
            )
        ''')

        # Insert data
        df.to_sql('vix_data', conn, if_exists='replace', index=False)

        conn.commit()
        print(f"VIX data stored successfully. Rows added: {len(df)}")
    except Exception as e:
        print(f"An error occurred while storing VIX data: {str(e)}")
    finally:
        conn.close()

def main():
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7496, clientId=23)
        vix_data = get_vix_data(ib)
        if vix_data is not None:
            # print(vix_data)
            store_vix_data(vix_data)
            print("VIX quote stored")
        else:
            print("Failed to retrieve VIX data.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        ib.disconnect()
        print("IB connection closed.")

if __name__ == "__main__":
    main()