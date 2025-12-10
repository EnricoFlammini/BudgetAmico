import os
import base64
import hashlib
from dotenv import load_dotenv
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.supabase_manager import get_db_connection

# Load Env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

SERVER_SECRET_KEY = os.getenv("SERVER_SECRET_KEY")
if not SERVER_SECRET_KEY:
    print("[ERROR] SERVER_SECRET_KEY missing in .env. Cannot migrate.")
    exit(1)

def migrate():
    print("Starting Visible Names Migration...")
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # 1. Add Columns if not exist
        print("Adding columns...")
        columns = [
            ("nome_enc_server", "TEXT"),
            ("cognome_enc_server", "TEXT")
        ]
        
        for col, type_ in columns:
            try:
                cur.execute(f"ALTER TABLE Utenti ADD COLUMN {col} {type_}")
                print(f"Added {col}")
            except Exception as e:
                print(f"Column {col} might already exist or error: {e}")
                con.rollback()

        con.commit() # Commit DDL

    print("Migration complete! Data will be backfilled upon user login.")

if __name__ == "__main__":
    migrate()
