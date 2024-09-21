from ib_insync import IB, Stock, util
import pandas as pd

def main():
    # Create an IB instance
    ib = IB()
    print("Connecting to IBKR API")
    # Connect to IBKR API
    # ib.connect('127.0.0.1', 7496, clientId=1)
    ib.connect('127.0.0.1', 7496)
    print("Connected to IBKR API")
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
