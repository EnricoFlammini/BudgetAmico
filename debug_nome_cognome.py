"""Debug script to test if nome/cognome can be decrypted with master key."""
import sys
sys.path.insert(0, r"C:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo")

from db.supabase_manager import get_db_connection
from utils.crypto_manager import CryptoManager
from db.gestione_db import _get_crypto_and_key, _decrypt_if_key
import base64

# Simulated master_key_b64 - this is what's stored in session after login
# We need to test if the decryption logic works

def main():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get test data
            cur.execute("""
                SELECT id_utente, username, nome, cognome
                FROM Utenti WHERE id_utente = 1
            """)
            user = dict(cur.fetchone())
            
            print(f"=== Testing nome/cognome decryption ===")
            print(f"Username: {user['username']}")
            print(f"nome (encrypted): {user['nome']}")
            print(f"cognome (encrypted): {user['cognome']}")
            
            # The issue is: nome and cognome are encrypted with the master_key
            # But the master_key is stored encrypted in the DB
            # When the user logs in, the password-derived key is used to decrypt master_key_encrypted
            # That decrypted master_key is then stored in the session
            
            # For this test, we can't decrypt without the actual master_key
            # But we can check if the format looks right
            
            # Check if nome starts with gAAAAA (Fernet token)
            if user['nome'].startswith('gAAAAA'):
                print(f"\nnome is a valid Fernet token (starts with gAAAAA)")
            else:
                print(f"\nnome does NOT start with gAAAAA - not encrypted or corrupted")
                
            if user['cognome'].startswith('gAAAAA'):
                print(f"cognome is a valid Fernet token (starts with gAAAAA)")
            else:
                print(f"cognome does NOT start with gAAAAA - not encrypted or corrupted")
            
            print("\n=== The issue ===")
            print("nome and cognome are encrypted with the user's master_key")
            print("To decrypt them, we need the master_key from the session")
            print("If the session has the correct master_key, decryption should work")
            print("If decryption fails, it means:")
            print("  1. master_key is wrong or not passed correctly")
            print("  2. The data was encrypted with a different key")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
