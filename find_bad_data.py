"""
Script di debug per identificare quale dato è criptato con la chiave sbagliata.
"""
import base64
from db.gestione_db import get_db_connection
from utils.crypto_manager import CryptoManager
import getpass

def find_bad_data():
    id_famiglia = int(input("ID Famiglia: "))
    password_admin = getpass.getpass("Password Admin (utente 1): ")
    
    crypto = CryptoManager()
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # Get admin master key
        cur.execute("SELECT salt, encrypted_master_key FROM Utenti WHERE id_utente = 1")
        admin = cur.fetchone()
        salt = base64.urlsafe_b64decode(admin['salt'].encode())
        kek = crypto.derive_key(password_admin, salt)
        enc_mk = base64.urlsafe_b64decode(admin['encrypted_master_key'].encode())
        admin_master_key = crypto.decrypt_master_key(enc_mk, kek)
        
        # Get admin's family key
        cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = 1 AND id_famiglia = %s", (id_famiglia,))
        fk_enc = cur.fetchone()
        fk_b64 = crypto.decrypt_data(fk_enc['chiave_famiglia_criptata'], admin_master_key)
        family_key = base64.b64decode(fk_b64)
        print(f"[INFO] Family key: {family_key[:10].hex()}...")
        
        # Now find the problematic encrypted data
        # From the logs: 'gAAAAABpNV3igdtVlB5go2DT9HK2s_zUw-fHDV8wev9D_mITClZ84HdYsuUnm_nBJQ5ds26Ges2viHLVuGRY5BjxwgpI1-jMeQ=='
        # This is one of the encrypted values that fails
        
        test_data = 'gAAAAABpNV3igdtVlB5go2DT9HK2s_zUw-fHDV8wev9D_mITClZ84HdYsuUnm_nBJQ5ds26Ges2viHLVuGRY5BjxwgpI1-jMeQ=='
        
        print(f"\n[TEST] Trying to decrypt test data with family_key...")
        try:
            result = crypto.decrypt_data(test_data, family_key)
            print(f"[SUCCESS] Decrypted with family_key: {result}")
        except Exception as e:
            print(f"[FAILED] Family key failed: {e}")
        
        print(f"\n[TEST] Trying to decrypt test data with admin master_key...")
        try:
            result = crypto.decrypt_data(test_data, admin_master_key)
            print(f"[SUCCESS] Decrypted with admin master_key: {result}")
        except Exception as e:
            print(f"[FAILED] Admin master key failed: {e}")
        
        # Search for this data in the database
        print(f"\n[SEARCH] Looking for this encrypted data in the database...")
        
        # Check Configurazioni
        cur.execute("SELECT * FROM Configurazioni WHERE valore LIKE %s", (test_data[:30] + '%',))
        results = cur.fetchall()
        if results:
            print(f"[FOUND in Configurazioni]:")
            for r in results:
                print(f"  chiave={r['chiave']}, id_famiglia={r.get('id_famiglia')}")
                
        # Check BudgetMensili
        cur.execute("SELECT * FROM BudgetMensili WHERE id_famiglia = %s", (id_famiglia,))
        budget_results = cur.fetchall()
        for budget in budget_results:
            for key, value in budget.items():
                if isinstance(value, str) and value.startswith('gAAAAA') and value[:30] == test_data[:30]:
                    print(f"[FOUND in BudgetMensili] Column: {key}")
                    
        # Check Categorie
        cur.execute("SELECT * FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
        cat_results = cur.fetchall()
        for cat in cat_results:
            for key, value in cat.items():
                if isinstance(value, str) and value.startswith('gAAAAA') and value[:30] == test_data[:30]:
                    print(f"[FOUND in Categorie] Column: {key}, id_categoria={cat['id_categoria']}")

if __name__ == "__main__":
    find_bad_data()
