import os
import base64
import hashlib
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from db.supabase_manager import get_db_connection

# Load Env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

SERVER_SECRET_KEY = os.getenv("SERVER_SECRET_KEY")
if not SERVER_SECRET_KEY:
    print("[ERROR] SERVER_SECRET_KEY missing in .env. Cannot migrate.")
    exit(1)

# Derive Keys
def get_derived_keys():
    # 1. Hashing Salt/Pepper (Use Key directly)
    hash_salt = SERVER_SECRET_KEY
    
    # 2. Encryption Key (Fernet)
    # Derive a 32-byte key from SERVER_SECRET_KEY for Fernet
    srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
    srv_fernet_key_b64 = base64.urlsafe_b64encode(srv_key_bytes)
    return hash_salt, srv_fernet_key_b64

HASH_SALT, FERNET_KEY = get_derived_keys()
cipher = Fernet(FERNET_KEY)

def compute_blind_index(value):
    if not value: return None
    # Blind Index = HMAC-SHA256 or just SHA256(value + salt)
    return hashlib.sha256((value.lower().strip() + HASH_SALT).encode()).hexdigest()

def encrypt_value(value):
    if not value: return None
    return cipher.encrypt(value.encode()).decode()

def migrate():
    print("Starting Blind Index Migration...")
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # 1. Add Columns if not exist
        print("Adding columns...")
        columns = [
            ("username_bindex", "TEXT"),
            ("email_bindex", "TEXT"),
            ("username_enc", "TEXT"),
            ("email_enc", "TEXT")
        ]
        
        for col, type_ in columns:
            try:
                cur.execute(f"ALTER TABLE Utenti ADD COLUMN {col} {type_}")
                print(f"Added {col}")
            except Exception as e:
                print(f"Column {col} might already exist or error: {e}")
                con.rollback()

        con.commit() # Commit DDL

        # 2. Iterate and Update
        print("Migrating data...")
        cur.execute("SELECT id_utente, username, email FROM Utenti")
        users = cur.fetchall()
        
        for u in users:
            uid = u['id_utente']
            username = u['username']
            email = u['email']
            
            print(f"Migrating user {uid}...")
            
            u_bindex = compute_blind_index(username)
            e_bindex = compute_blind_index(email)
            
            u_enc = encrypt_value(username)
            e_enc = encrypt_value(email)
            
            # Update
            try:
                cur.execute("""
                    UPDATE Utenti 
                    SET username_bindex = %s,
                        email_bindex = %s,
                        username_enc = %s,
                        email_enc = %s
                    WHERE id_utente = %s
                """, (u_bindex, e_bindex, u_enc, e_enc, uid))
                con.commit()
            except Exception as e:
                print(f"Error updating user {uid}: {e}")
                con.rollback()
                
        # 3. Create Indices (Optional but recommended for performance)
        try:
            print("Creating indices...")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_username_bindex ON Utenti (username_bindex)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_email_bindex ON Utenti (email_bindex)")
            con.commit()
        except Exception as e:
            print(f"Index creation warning: {e}")
            con.rollback()

    print("Migration complete!")

if __name__ == "__main__":
    migrate()
