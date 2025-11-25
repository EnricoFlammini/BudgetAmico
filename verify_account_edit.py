import os
import sys
import sqlite3
import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.crea_database import setup_database
from db.gestione_db import (
    registra_utente,
    aggiungi_conto,
    modifica_conto,
    ottieni_saldo_iniziale_conto,
    aggiorna_saldo_iniziale_conto,
    DB_FILE
)

# Use a temporary DB for testing
TEST_DB = "test_account_edit.db"
import db.gestione_db
db.gestione_db.DB_FILE = TEST_DB

def test_account_edit():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    setup_database(TEST_DB)
    
    print("--- Testing Account Edit ---")
    
    # 1. Create User
    user_id = registra_utente("testuser", "test@example.com", "password", "Test", "User")
    print(f"User created with ID: {user_id}")
    
    # 2. Create Account
    res = aggiungi_conto(user_id, "My Account", "Corrente", "IT0000000000000000000000000")
    print(f"aggiungi_conto result: {res}")
    
    if isinstance(res, tuple):
        account_id, msg = res
    else:
        account_id = res
        
    if not account_id:
        print("Failed to create account")
        return

    print(f"Account created with ID: {account_id}")
    
    # 3. Verify Initial Balance is 0
    initial_balance = ottieni_saldo_iniziale_conto(account_id)
    print(f"Initial Balance: {initial_balance}")
    assert initial_balance == 0.0
    
    # 4. Update Initial Balance
    print("Updating Initial Balance to 1000.0")
    aggiorna_saldo_iniziale_conto(account_id, 1000.0)
    
    # 5. Verify New Initial Balance
    new_balance = ottieni_saldo_iniziale_conto(account_id)
    print(f"New Initial Balance: {new_balance}")
    assert new_balance == 1000.0
    
    # 6. Update Initial Balance again
    print("Updating Initial Balance to 2000.0")
    aggiorna_saldo_iniziale_conto(account_id, 2000.0)
    
    new_balance_2 = ottieni_saldo_iniziale_conto(account_id)
    print(f"New Initial Balance 2: {new_balance_2}")
    assert new_balance_2 == 2000.0
    
    # 7. Modify Account Type
    print("Modifying Account Type to 'Risparmio'")
    res_mod = modifica_conto(account_id, user_id, "My Account Modified", "Risparmio", "IT0000000000000000000000000")
    print(f"modifica_conto result: {res_mod}")
    
    assert isinstance(res_mod, tuple)
    assert res_mod[0] is True
    
    print("--- Test Passed ---")

if __name__ == "__main__":
    try:
        test_account_edit()
    finally:
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except:
                pass
