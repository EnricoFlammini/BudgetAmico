import os
import sys
import sqlite3
import datetime
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.crea_database import setup_database
from db.gestione_db import (
    registra_utente,
    aggiungi_conto,
    compra_asset,
    aggiorna_prezzo_manuale_asset,
    ottieni_portafoglio,
    DB_FILE
)

# Use a temporary DB for testing
TEST_DB = "test_asset_update.db"
import db.gestione_db
db.gestione_db.DB_FILE = TEST_DB

def test_asset_update_time():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    setup_database(TEST_DB)
    
    print("--- Testing Asset Update Time ---")
    
    # 1. Create User and Account
    user_id = registra_utente("testuser", "test@example.com", "password", "Test", "User")
    account_id = aggiungi_conto(user_id, "Investments", "Investimento")
    if isinstance(account_id, tuple): account_id = account_id[0]
    print(f"User {user_id} and Account {account_id} created")
    
    # 2. Buy Asset
    compra_asset(account_id, "AAPL", "Apple Inc.", 10, 150.0)
    print("Asset AAPL bought")
    
    # 3. Verify Initial State (should be None or empty depending on implementation, but let's check)
    portfolio = ottieni_portafoglio(account_id)
    asset = portfolio[0]
    print(f"Initial Update Time: {asset.get('data_aggiornamento')}")
    
    # 4. Update Price
    print("Updating price...")
    time.sleep(1) # Ensure time difference if any
    aggiorna_prezzo_manuale_asset(asset['id_asset'], 155.0)
    
    # 5. Verify Update Time
    portfolio_new = ottieni_portafoglio(account_id)
    asset_new = portfolio_new[0]
    update_time = asset_new.get('data_aggiornamento')
    print(f"New Update Time: {update_time}")
    
    assert update_time is not None
    # Check format roughly
    datetime.datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")
    
    print("--- Test Passed ---")

if __name__ == "__main__":
    try:
        test_asset_update_time()
    finally:
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except:
                pass
