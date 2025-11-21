import sqlite3
import os
import sys
from datetime import date

# Setup path to import modules
sys.path.append(os.getcwd())

from db.crea_database import setup_database
from db.gestione_db import compra_asset, aggiungi_conto, registra_utente, ottieni_portafoglio

TEST_DB = "test_debug.db"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

# Mock DB_FILE in gestione_db
import db.gestione_db
db.gestione_db.DB_FILE = TEST_DB

print("Setting up test database...")
setup_database(TEST_DB)

print("Creating user and account...")
id_utente = registra_utente("testuser", "test@example.com", "password", "Test", "User")
id_conto = aggiungi_conto(id_utente, "My Portfolio", "Investimento")

print(f"User ID: {id_utente}, Account ID: {id_conto}")

print("Buying NEW asset AAPL...")
res = compra_asset(id_conto, "AAPL", "Apple Inc.", 10, 150.0)
print(f"Result 1 (New): {res}")

portafoglio = ottieni_portafoglio(id_conto)
print(f"Portfolio after 1st buy: {portafoglio}")
if len(portafoglio) != 1 or portafoglio[0]['quantita'] != 10:
    print("FAIL: Asset not added correctly.")
    sys.exit(1)

print("Buying EXISTING asset AAPL (adding 5 more)...")
res = compra_asset(id_conto, "AAPL", "Apple Inc.", 5, 160.0)
print(f"Result 2 (Existing): {res}")

portafoglio = ottieni_portafoglio(id_conto)
print(f"Portfolio after 2nd buy: {portafoglio}")

asset = portafoglio[0]
expected_qty = 15.0
# Costo medio: (10*150 + 5*160) / 15 = (1500 + 800) / 15 = 2300 / 15 = 153.333...
expected_cost = 2300 / 15

print(f"Expected Qty: {expected_qty}, Actual: {asset['quantita']}")
print(f"Expected Cost: {expected_cost}, Actual: {asset['costo_iniziale_unitario']}")

if abs(asset['quantita'] - expected_qty) < 0.001:
    print("SUCCESS: Existing asset updated correctly.")
else:
    print("FAIL: Existing asset NOT updated.")

os.remove(TEST_DB)
