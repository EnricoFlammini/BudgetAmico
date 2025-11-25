import os
import sys
import sqlite3
import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.crea_database import setup_database
from db.gestione_db import (
    registra_utente,
    crea_famiglia_e_admin,
    crea_conto_condiviso,
    aggiungi_transazione_condivisa,
    admin_imposta_saldo_conto_condiviso,
    ottieni_dettagli_conto_condiviso,
    ottieni_conti_condivisi_utente,
    DB_FILE
)

# Use a temporary DB for testing
TEST_DB = "test_rettifica_saldo.db"
import db.gestione_db
db.gestione_db.DB_FILE = TEST_DB

def test_rettifica_saldo():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    setup_database(TEST_DB)
    
    print("--- Testing Rettifica Saldo Shared Account ---")
    
    # 1. Create User and Family
    user_id = registra_utente("admin", "admin@example.com", "password", "Admin", "User")
    fam_id = crea_famiglia_e_admin("Test Family", user_id)
    print(f"User {user_id} and Family {fam_id} created")
    
    # 2. Create Shared Account
    account_id = crea_conto_condiviso(fam_id, "Shared Cash", "Contanti", "famiglia")
    print(f"Shared Account created with ID: {account_id}")
    
    # 3. Add Transaction
    aggiungi_transazione_condivisa(user_id, account_id, datetime.date.today().strftime('%Y-%m-%d'), "Test Trans", 100.0)
    
    # 4. Verify Balance
    details = ottieni_dettagli_conto_condiviso(account_id)
    print(f"Balance after transaction: {details['saldo_calcolato']}")
    assert details['saldo_calcolato'] == 100.0
    
    # 5. Adjust Balance (Rettifica)
    print("Adjusting balance to 500.0")
    res = admin_imposta_saldo_conto_condiviso(account_id, 500.0)
    assert res is True
    
    # 6. Verify New Balance via ottieni_dettagli_conto_condiviso
    details_new = ottieni_dettagli_conto_condiviso(account_id)
    print(f"New Balance (details): {details_new['saldo_calcolato']}")
    assert details_new['saldo_calcolato'] == 500.0
    
    # 7. Verify New Balance via ottieni_conti_condivisi_utente
    list_accounts = ottieni_conti_condivisi_utente(user_id)
    # Find the account
    acc = next((a for a in list_accounts if a['id_conto'] == account_id), None)
    print(f"New Balance (list): {acc['saldo_calcolato']}")
    assert acc['saldo_calcolato'] == 500.0
    
    print("--- Test Passed ---")

if __name__ == "__main__":
    try:
        test_rettifica_saldo()
    finally:
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except:
                pass
