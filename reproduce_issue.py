import yfinance as yf
import time

print("Testing yfinance import...")
try:
    ticker = yf.Ticker("MSFT")
    print(f"Ticker info retrieved: {ticker.info.get('shortName')}")
except Exception as e:
    print(f"Error: {e}")

print("Done.")
time.sleep(5)
