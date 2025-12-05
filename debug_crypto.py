"""Debug script to test decryption of user names."""
import sys
sys.path.insert(0, r"C:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo")

from db.supabase_manager import get_db_connection
from utils.crypto_manager import CryptoManager
import base64

def main():
    # First, get the encrypted master_key from the database for user 1
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get user's encrypted key info
            cur.execute("""
                SELECT id_utente, username, nome, cognome, master_key_encrypted, salt
                FROM Utenti WHERE id_utente = 1
            """)
            user = dict(cur.fetchone())
            print(f"User: {user['username']}")
            print(f"Encrypted nome: {user['nome'][:50]}...")
            print(f"Encrypted cognome: {user['cognome'][:50]}...")
            print(f"master_key_encrypted: {user['master_key_encrypted'][:50] if user['master_key_encrypted'] else 'None'}...")
            print(f"salt: {user['salt'][:50] if user['salt'] else 'None'}...")
            
            # Now test decryption manually
            # The password-derived key is needed to decrypt master_key_encrypted
            # We can't test that without knowing the password
            
            # But we can check what's happening in the app
            # The master_key is stored in session after login
            # Let's check if there's family key info
            cur.execute("""
                SELECT AF.id_famiglia, AF.chiave_famiglia_criptata
                FROM Appartenenza_Famiglia AF
                WHERE AF.id_utente = 1
            """)
            membership = dict(cur.fetchone())
            print(f"\nFamily membership:")
            print(f"id_famiglia: {membership['id_famiglia']}")
            print(f"chiave_famiglia_criptata: {membership['chiave_famiglia_criptata'][:50] if membership['chiave_famiglia_criptata'] else 'None'}...")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
