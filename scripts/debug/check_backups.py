
import os
from dotenv import load_dotenv
load_dotenv()
from db.gestione_db import get_db_connection

def check_backups():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente, encrypted_master_key_backup IS NOT NULL as has_backup FROM Utenti WHERE id_utente IN (7, 11)")
            rows = cur.fetchall()
            for r in rows:
                print(f"Utente {r['id_utente']}: Has Backup = {r['has_backup']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_backups()
