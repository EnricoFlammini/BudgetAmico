
import os
from dotenv import load_dotenv
load_dotenv()
from db.gestione_db import get_db_connection, decrypt_system_data

def investigate_encoding():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT encrypted_master_key_backup, username_enc FROM Utenti WHERE id_utente = 11")
            row = cur.fetchone()
            bk = row['encrypted_master_key_backup']
            u_enc = row['username_enc']
            
            print(f"Username_enc: {u_enc[:20]}...")
            print(f"Backup_enc:   {bk[:20]}...")
            
            # Try direct decryption of username
            u_dec = decrypt_system_data(u_enc)
            print(f"Username_dec: {u_dec}")
            
            # Try direct decryption of backup
            bk_dec = decrypt_system_data(bk)
            print(f"Backup_dec direct: {'SUCCESS' if bk_dec else 'FAILED'}")
            
            # Try double b64 decoding if it starts with something else
            import base64
            try:
                bk_bytes = base64.urlsafe_b64decode(bk)
                bk_dec_2 = decrypt_system_data(bk_bytes.decode())
                print(f"Backup_dec with extra b64 decode: {'SUCCESS' if bk_dec_2 else 'FAILED'}")
            except:
                print("Failed to double decode.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    investigate_encoding()
