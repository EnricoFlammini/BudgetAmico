
import os
from dotenv import load_dotenv

# Carica PRIMA di importare moduli db
load_dotenv()

import base64
from db.gestione_db import get_db_connection, decrypt_system_data
from utils.crypto_manager import CryptoManager

def probe_keys_consistency():
    try:
        # 1. Get server_encrypted_key
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT server_encrypted_key FROM Famiglie WHERE id_famiglia = 2")
            row = cur.fetchone()
            if not row or not row['server_encrypted_key']:
                print("Server automation key not found for family 2.")
                return
            
            enc_fk = row['server_encrypted_key']
            
            # 2. Decrypt it
            fk_b64 = decrypt_system_data(enc_fk)
            if not fk_b64:
                print("Failed to decrypt server_encrypted_key. Check SERVER_SECRET_KEY.")
                return
            
            family_key_bytes = base64.b64decode(fk_b64)
            crypto = CryptoManager()

            # 3. Try to decrypt a sample transaction of User 7
            print("\n--- TEST DECRIPTAZIONE UTENTE 7 ---")
            cur.execute("""
                SELECT T.descrizione 
                FROM Transazioni T 
                JOIN Conti C ON T.id_conto = C.id_conto 
                WHERE C.id_utente = 7 AND T.descrizione LIKE 'gAAAAA%%'
                LIMIT 1
            """)
            t7 = cur.fetchone()
            if t7:
                desc = t7['descrizione']
                try:
                    res = crypto.decrypt_data(desc, family_key_bytes)
                    print(f"Utente 7 Transaction DEC SUCCESS: {res}")
                except:
                    print("Utente 7 Transaction DEC FAILED.")
            else:
                print("No encrypted transactions found for user 7.")

            # 4. Try to decrypt a sample transaction of User 11
            print("\n--- TEST DECRIPTAZIONE UTENTE 11 ---")
            cur.execute("""
                SELECT T.descrizione 
                FROM Transazioni T 
                JOIN Conti C ON T.id_conto = C.id_conto 
                WHERE C.id_utente = 11 AND T.descrizione LIKE 'gAAAAA%%'
                LIMIT 1
            """)
            t11 = cur.fetchone()
            if t11:
                desc = t11['descrizione']
                try:
                    res = crypto.decrypt_data(desc, family_key_bytes)
                    print(f"Utente 11 Transaction DEC SUCCESS: {res}")
                except:
                    print("Utente 11 Transaction DEC FAILED.")
            else:
                print("No encrypted transactions found for user 11.")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    probe_keys_consistency()
