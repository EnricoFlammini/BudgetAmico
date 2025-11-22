import os
import sys
import sqlite3

# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.crea_database import setup_database
from db.gestione_db import (
    registra_utente, crea_famiglia_e_admin, ottieni_utenti_senza_famiglia,
    cerca_utente_per_username, aggiungi_utente_a_famiglia, DB_FILE
)

# Use a test DB file
TEST_DB = "test_invite.db"
import db.gestione_db
db.gestione_db.DB_FILE = TEST_DB

def run_verification():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    print("1. Setting up database...")
    setup_database(TEST_DB)
    
    print("2. Creating Admin user...")
    admin_id = registra_utente("admin", "admin@test.com", "pass", "Admin", "User")
    if not admin_id:
        print("❌ Failed to create admin")
        return

    print("3. Creating Family...")
    family_id = crea_famiglia_e_admin("TestFamily", admin_id)
    if not family_id:
        print("❌ Failed to create family")
        return

    print("4. Creating Loner user (no family)...")
    loner_id = registra_utente("loner", "loner@test.com", "pass", "Loner", "User")
    if not loner_id:
        print("❌ Failed to create loner")
        return

    print("5. Testing ottieni_utenti_senza_famiglia...")
    users_without_family = ottieni_utenti_senza_famiglia()
    print(f"   Users without family: {users_without_family}")
    if "loner" in users_without_family and "admin" not in users_without_family:
        print("✅ ottieni_utenti_senza_famiglia works correctly.")
    else:
        print("❌ ottieni_utenti_senza_famiglia failed.")
        return

    print("6. Testing invitation logic (simulation)...")
    # Simulate what controller does
    user_found = cerca_utente_per_username("loner")
    if user_found and user_found['id_utente'] == loner_id:
        print("✅ User 'loner' found correctly.")
        
        print("   Adding user to family...")
        success = aggiungi_utente_a_famiglia(family_id, loner_id, "livello1")
        if success:
            print("✅ User added to family successfully.")
        else:
            print("❌ Failed to add user to family.")
            return
    else:
        print("❌ User 'loner' not found.")
        return

    print("7. Verifying user is no longer 'without family'...")
    users_without_family_after = ottieni_utenti_senza_famiglia()
    print(f"   Users without family: {users_without_family_after}")
    if "loner" not in users_without_family_after:
        print("✅ 'loner' is correctly removed from the list.")
    else:
        print("❌ 'loner' is still in the list.")
        return

    print("\n🎉 ALL TESTS PASSED!")
    
    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

if __name__ == "__main__":
    run_verification()
