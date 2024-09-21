from ibapi.client import *
from ibapi.wrapper import *

class DownloaderApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId: int):
        # Define the contract for AAPL stock
        aapl_contract = Contract()
        aapl_contract.symbol = "AAPL"
        aapl_contract.secType = "STK"  # Stock
        aapl_contract.exchange = "SMART"
        aapl_contract.currency = "USD"

        # Request historical data for AAPL
        self.reqHistoricalData(
            orderId, 
            aapl_contract, 
            "20230101 00:00:00 US/Eastern",  # Adjust the date and time format if needed
            "10 D",  # Time duration (10 days)
            "1 hour",  # Bar size (1 hour)
            "TRADES",  # What data to show (TRADES, BID, ASK, etc.)
            0, 1, 0, []
        )

    def historicalData(self, reqId, bar):
        to_write = f"{bar.date}, {bar.open}, {bar.high}, {bar.low}, {bar.close}\n"
        with open('AAPL_downloaded_data.csv', 'a+') as file:
            file.write(to_write)

    def historicalDataEnd(self, reqId, start, end):
        print(f"Data received. It should now be written in the CSV.")
        print(f"Started on {start}, Ended on {end}")
        self.disconnect()

# Set your socket port and client ID
socketPort = 7497  # Put your specific port here
clientId = 12

app = DownloaderApp()
app.connect("127.0.0.1", socketPort, clientId)
app.run()
