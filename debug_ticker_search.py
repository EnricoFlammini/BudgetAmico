
import sys
import os

sys.path.append(os.getcwd())
from utils.yfinance_manager import cerca_ticker

# Prova a cercare per nome
queries = [
    "BTP 0.45",
    "BTP 2029",
    "IT0005467482", # Search by generic ISIN in the autocomplete
    "546748.MI" # Try shortened ISIN
]

for q in queries:
    print(f"--- Searching for: {q} ---")
    results = cerca_ticker(q, limit=5)
    for r in results:
        print(f"  Found: {r['ticker']} - {r['nome']} ({r['borsa']})")
