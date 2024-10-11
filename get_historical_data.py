from ib_async import *
import concurrent.futures
import pandas as pd
import asyncio
import nest_asyncio
from time import sleep
from datetime import datetime, timedelta, time
import pytz

# Apply nest_asyncio to allow nested use of asyncio
nest_asyncio.apply()

# Connect to IBKR API
ib = IB()
ib.connect('127.0.0.1', 7496, clientId=1)

# Define the VIX Index
vix_index = Index(symbol='VIX', exchange='CBOE')
ib.qualifyContracts(vix_index)

# Retrieve option parameters for VIX
opt_params = ib.reqSecDefOptParams(
    underlyingSymbol=vix_index.symbol,
    futFopExchange='',
    underlyingSecType=vix_index.secType,
    underlyingConId=vix_index.conId
)

print('number of chains:', len(opt_params))

# Collect all expiration dates and strike prices
expirations = set(['20241015'])
strikes = set([10.0])

for param in opt_params:
    expirations.update(param.expirations)
    strikes.update(param.strikes)

# Convert strikes to sorted list for consistency

# Prepare option contracts for all combinations
contracts = []
rights = ['C']  # Call and Put options

for expiration in expirations:
    for strike in strikes:
        for right in rights:
            contract = Option(
                symbol='VIX',
                lastTradeDateOrContractMonth=expiration,
                strike=strike,
                right=right,
                exchange='CBOE',
                currency='USD'
            )
            contracts.append(contract)
            print('contract: ', contract)
    

# Qualify contracts (resolve any ambiguities)
qualified_contracts = ib.qualifyContracts(*contracts)
print('qualified contract', contracts[0])

# Asynchronous function to request historical data for a contract
async def request_historical_data(contract):
    try:
        # Create a new event loop for this coroutine
        end_datetime = datetime.now(pytz.timezone('US/Eastern')).replace(second=0, microsecond=0)
        if end_datetime.time() < time(9, 30):
            end_datetime = end_datetime.replace(hour=16, minute=0) - timedelta(days=1)
        elif end_datetime.time() > time(16, 0):
            end_datetime = end_datetime.replace(hour=16, minute=0)
        elif end_datetime.time() < time(10, 0):
            end_datetime = end_datetime.replace(hour=9, minute=30)
        else:
            end_datetime = end_datetime.replace(minute=0)

        # Request historical data
        bars = await ib.reqHistoricalDataAsync(
            contract,
            endDateTime=end_datetime,
            durationStr='3 D',
            barSizeSetting='1 hour',
            whatToShow='TRADES',
            useRTH=True,
            timeout=10
        )
        
        # Convert bars to a list of dictionaries
        data = [{
            'date': bar.date,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume
        } for bar in bars]
        
        print(f"Retrieved {len(data)} bars for {contract.localSymbol}")
        return {
            'contract': contract,
            'data': data
        }
    except Exception as e:
        print(f"Error with {contract.localSymbol}: {e}")
        return None

# Main asynchronous function to gather results
async def main():
    tasks = [request_historical_data(contract) for contract in qualified_contracts]
    results = await asyncio.gather(*tasks)
    return results

# Run the main function
if __name__ == "__main__":
    results = asyncio.run(main())

# Process the collected data
all_data = []
for result in results:
    contract = result['contract']
    for bar in result['data']:
        all_data.append({
            'Symbol': contract.localSymbol,
            'Expiration': contract.lastTradeDateOrContractMonth,
            'Strike': contract.strike,
            'Right': contract.right,
            'Date': bar['date'],
            'Open': bar['open'],
            'High': bar['high'],
            'Low': bar['low'],
            'Close': bar['close'],
            'Volume': bar['volume']
        })

# Create a DataFrame and save to CSV
df = pd.DataFrame(all_data)
df.to_csv('vix_options_historical_data.csv', index=False)
print("Historical data saved to vix_options_historical_data.csv")
