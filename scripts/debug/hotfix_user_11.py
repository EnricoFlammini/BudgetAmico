
import os
from dotenv import load_dotenv

# Carica .env PRIMA di importare moduli che leggono variabili d'ambiente a tempo di import
load_dotenv()

from db.gestione_db import get_db_connection, decrypt_system_data, _get_crypto_and_key
import base64
from utils.crypto_manager import CryptoManager

def hotfix_user_11_key():
    print(f"Propagazione SERVER_SECRET_KEY: {os.getenv('SERVER_SECRET_KEY') is not None}")
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Recupero la Family Key corretta dal server (Famiglia 2)
            cur.execute("SELECT server_encrypted_key FROM Famiglie WHERE id_famiglia = 2")
            fam_row = cur.fetchone()
            if not fam_row or not fam_row['server_encrypted_key']:
                print("ERRORE: Chiave server non trovata per la famiglia 2.")
                return
            
            fk_b64 = decrypt_system_data(fam_row['server_encrypted_key'])
            if not fk_b64:
                print("ERRORE: Impossibile decriptare la chiave server. Verificare SERVER_SECRET_KEY.")
                # Debugged: decrypt_system_data returns None if SYSTEM_FERNET_KEY is missing
                return
            
            # 2. Recupero la Master Key di backup dell'utente 11
            cur.execute("SELECT encrypted_master_key_backup FROM Utenti WHERE id_utente = 11")
            user_row = cur.fetchone()
            if not user_row or not user_row['encrypted_master_key_backup']:
                print("ERRORE: Backup Master Key non trovato per l'utente 11.")
                return
            
            mk_b64 = decrypt_system_data(user_row['encrypted_master_key_backup'])
            if not mk_b64:
                print("ERRORE: Impossibile decriptare il backup della Master Key dell'utente 11.")
                return
            
            # 3. Preparo il CryptoManager con la Master Key dell'utente 11
            crypto = CryptoManager()
            master_key_bytes = base64.b64decode(mk_b64)
            
            # 4. Cripto la Family Key (corretta) con la Master Key di User 11
            new_enc_fk = crypto.encrypt_data(fk_b64, master_key_bytes)
            
            # 5. Aggiorno il database
            cur.execute("""
                UPDATE Appartenenza_Famiglia 
                SET chiave_famiglia_criptata = %s 
                WHERE id_utente = 11 AND id_famiglia = 2
            """, (new_enc_fk,))
            
            con.commit()
            print("SUCCESSO: La chiave di famiglia dell'utente 11 è stata allineata con quella del server.")

    except Exception as e:
        print(f"Errore durante l'hotfix: {e}")

if __name__ == "__main__":
    hotfix_user_11_key()
