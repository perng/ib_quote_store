from ib_insync import *
import concurrent.futures
import time
import asyncio
import nest_asyncio
import sys

# Apply nest_asyncio to allow nested use of asyncio
nest_asyncio.apply()

# Connect to IBKR API
ib = IB()

def attempt_connection(max_attempts=3, delay=5):
    for attempt in range(max_attempts):
        try:
            print(f"Attempting to connect (attempt {attempt + 1}/{max_attempts})...")
            ib.connect('127.0.0.1', 7496, clientId=1, timeout=30)
            print("Successfully connected to IB")
            return True
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_attempts - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("All connection attempts failed.")
                return False

if not attempt_connection():
    print("Please check that IB Gateway or TWS is running and properly configured.")
    print("Ensure that API connections are enabled and that the port (7496) is correct.")
    sys.exit(1)

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

# Collect all expiration dates and strike prices
expirations = set()
strikes = set()

for param in opt_params:
    expirations.update(param.expirations)
    strikes.update(param.strikes)

# Convert strikes to sorted list for consistency
strikes = [s for s in sorted(strikes) if 15 == s]

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
            break
        break

# Qualify contracts (resolve any ambiguities)
qualified_contracts = ib.qualifyContracts(*contracts)

# Function to request market data for a contract
def request_market_data(contract):
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Request market data
        ticker = ib.reqMktData(contract, '', False, False)
        # Wait for data to be received
        loop.run_until_complete(asyncio.sleep(2))
        # Extract desired data
        last_price = ticker.last
        bid_price = ticker.bid
        ask_price = ticker.ask
        implied_volatility = ticker.modelGreeks.impliedVol if ticker.modelGreeks else None
        print(f"{contract.localSymbol}: Last={last_price}, Bid={bid_price}, Ask={ask_price}, IV={implied_volatility}")
        # Cancel market data subscription
        ib.cancelMktData(contract)
        return {
            'contract': contract,
            'last_price': last_price,
            'bid_price': bid_price,
            'ask_price': ask_price,
            'implied_volatility': implied_volatility
        }
    except Exception as e:
        print(f"Error with {contract.localSymbol}: {e}")
        return None
    finally:
        # Close the event loop
        loop.close()

# Limit the number of threads to avoid exceeding rate limits
max_workers = 50  # Adjust this number based on your rate limit

# Use ThreadPoolExecutor for multi-threading
results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Submit tasks
    futures = {executor.submit(request_market_data, contract): contract for contract in qualified_contracts}
    # Collect results as they complete
    for future in concurrent.futures.as_completed(futures):
        result = future.result()
        if result:
            results.append(result)
        # Introduce delay to comply with rate limits
        time.sleep(0.1)  # Adjust as needed

# Disconnect from IBKR API
ib.disconnect()

# Process or save the collected data as needed
# For example, save to a CSV file
import pandas as pd

df = pd.DataFrame([{
    'Symbol': res['contract'].localSymbol,
    'Expiration': res['contract'].lastTradeDateOrContractMonth,
    'Strike': res['contract'].strike,
    'Right': res['contract'].right,
    'LastPrice': res['last_price'],
    'BidPrice': res['bid_price'],
    'AskPrice': res['ask_price'],
    'ImpliedVolatility': res['implied_volatility']
} for res in results])

df.to_csv('vix_options_data.csv', index=False)
print("Data saved to vix_options_data.csv")
