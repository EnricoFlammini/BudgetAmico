from db.supabase_manager import get_db_connection
from db.gestione_db import decrypt_system_data, SERVER_SECRET_KEY

def verify_user_automation(username="Utente1"):
    print(f"Checking automation for user: {username}")
    print(f"SERVER_SECRET_KEY present: {bool(SERVER_SECRET_KEY)}")
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # 1. Get User ID
        cur.execute("SELECT id_utente FROM Utenti WHERE username = %s", (username,))
        user = cur.fetchone()
        if not user:
            print("User not found.")
            return

        id_utente = user['id_utente']
        print(f"User ID: {id_utente}")

        # 2. Get Family ID
        cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s", (id_utente,))
        fam = cur.fetchone()
        if not fam:
            print("User does not belong to any family.")
            return

        id_famiglia = fam['id_famiglia']
        print(f"Family ID: {id_famiglia}")

        # 3. Check Protocol Status (server_encrypted_key)
        cur.execute("SELECT server_encrypted_key FROM Famiglie WHERE id_famiglia = %s", (id_famiglia,))
        row = cur.fetchone()
        
        enc_key = row['server_encrypted_key']
        print(f"Encrypted Key in DB: {enc_key if enc_key else 'NULL'}")
        
        if enc_key:
            try:
                decrypted = decrypt_system_data(enc_key)
                if decrypted:
                    print("SUCCESS: Key decrypted successfully.")
                else:
                    print("FAILURE: Decryption returned None.")
            except Exception as e:
                print(f"FAILURE: Decryption error: {e}")
        else:
            print("FAILURE: No key found in DB.")

if __name__ == "__main__":
    verify_user_automation()
