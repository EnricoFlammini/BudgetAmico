import os
import sys
from dotenv import load_dotenv
import psycopg2

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

SUPABASE_DB_URL = os.getenv('SUPABASE_DB_URL')

def check_data():
    if not SUPABASE_DB_URL:
        print("Error: SUPABASE_DB_URL not found.")
        return

    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        
        print("--- Checking User 1 Data ---")
        cur.execute("SELECT id_utente, username, nome, cognome, codice_fiscale, indirizzo, salt, encrypted_master_key FROM Utenti WHERE id_utente = 1")
        user = cur.fetchone()
        if user:
            print(f"ID: {user[0]}")
            print(f"Username: {user[1]}")
            print(f"Nome: {user[2]}")
            print(f"Cognome: {user[3]}")
            print(f"CF: {user[4]}")
            print(f"Indirizzo: {user[5]}")
            print(f"Salt present: {bool(user[6])}")
            print(f"Encrypted Master Key present: {bool(user[7])}")
        else:
            print("User 1 not found.")

        print("\n--- Checking Appartenenza_Famiglia for User 1 ---")
        cur.execute("SELECT id_famiglia, ruolo, chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = 1")
        families = cur.fetchall()
        for fam in families:
            print(f"Famiglia ID: {fam[0]}, Ruolo: {fam[1]}")
            print(f"Chiave Famiglia Criptata: {fam[2]}")

        print("\n--- Checking Conti Condivisi for User 1 ---")
        # Get families for user 1
        family_ids = [f[0] for f in families]
        if family_ids:
            placeholders = ','.join(['%s'] * len(family_ids))
            cur.execute(f"SELECT id_conto_condiviso, nome_conto, id_famiglia FROM ContiCondivisi WHERE id_famiglia IN ({placeholders})", tuple(family_ids))
            accounts = cur.fetchall()
            for acc in accounts:
                print(f"Conto ID: {acc[0]}, Famiglia ID: {acc[2]}")
                print(f"Nome Conto: {acc[1]}")
        else:
            print("No families found.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_data()
