from ib_insync import IB, Stock, util
import pandas as pd

def main():
    # Create an IB instance
    ib = IB()
    print("Connecting to IBKR API")
    
    # Increase the timeout and add error handling
    try:
        ib.connect('127.0.0.1', 7497, clientId=1, timeout=5)
        print("Connected to IBKR API")
    except TimeoutError:
        print("Connection timed out. Please check if TWS/IB Gateway is running and properly configured.")
        return
    except ConnectionRefusedError:
        print("Connection refused. Please check your port number and ensure TWS/IB Gateway is accepting connections.")
        return
    except Exception as e:
        print(f"An error occurred: {e}")
        return

    # Define the stock contract
    contract = Stock('AAPL', 'SMART', 'USD')

    # Request real-time market data
    ticker = ib.reqMktData(contract, '', False, False)
    print("Requested real-time market data")
    # Wait for data
    ib.sleep(2)
    print("Received real-time market data")
    # Display real-time data
    print(f"Real-Time Data for {contract.symbol}:")
    print(f"Last Price: {ticker.last}")
    print(f"Bid Price: {ticker.bid}")
    print(f"Ask Price: {ticker.ask}")

    # Request historical data
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr='1 D',
        barSizeSetting='5 mins',
        whatToShow='MIDPOINT',
        useRTH=True
    )

    # Convert to DataFrame
    df = util.df(bars)
    print("\nHistorical Data:")
    print(df.head())

    # Disconnect
    ib.disconnect()

if __name__ == "__main__":
    main()
