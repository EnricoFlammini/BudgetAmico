import os
import secrets
from db.supabase_manager import get_db_connection
from dotenv import load_dotenv

# Load env to check if SERVER_SECRET_KEY exists
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

def update_env_file():
    key = os.getenv("SERVER_SECRET_KEY")
    if not key:
        print("Generazione nuova SERVER_SECRET_KEY...")
        new_key = secrets.token_urlsafe(32)
        
        # Append to .env
        with open(env_path, "a") as f:
            f.write(f"\nSERVER_SECRET_KEY={new_key}\n")
        print(f"SERVER_SECRET_KEY aggiunta a {env_path}")
    else:
        print("SERVER_SECRET_KEY già presente.")

def add_column():
    print("Verifica colonna encrypted_master_key_backup...")
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Check if column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='utenti' AND column_name='encrypted_master_key_backup'
            """)
            if cur.fetchone():
                print("Colonna encrypted_master_key_backup già esistente.")
            else:
                print("Aggiunta colonna encrypted_master_key_backup...")
                cur.execute("ALTER TABLE Utenti ADD COLUMN encrypted_master_key_backup TEXT")
                con.commit()
                print("Colonna aggiunta con successo.")
    except Exception as e:
        print(f"Errore durante l'aggiornamento del DB: {e}")

if __name__ == "__main__":
    update_env_file()
    add_column()
