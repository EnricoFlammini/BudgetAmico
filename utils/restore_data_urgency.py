
import os
import base64
import hashlib
from dotenv import load_dotenv
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.supabase_manager import get_db_connection

# Load Env
load_dotenv()
SERVER_SECRET_KEY = os.getenv("SERVER_SECRET_KEY")

HASH_SALT = SERVER_SECRET_KEY

def compute_blind_index(value):
    if not value or not HASH_SALT: return None
    return hashlib.sha256((value.lower().strip() + HASH_SALT).encode()).hexdigest()

def get_system_fernet_key():
    srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(srv_key_bytes)

def encrypt_value(value):
    if not value: return None
    from cryptography.fernet import Fernet
    key = get_system_fernet_key()
    cipher = Fernet(key)
    return cipher.encrypt(value.encode()).decode()

def restore_data():
    print("Starting Urgent Data Restoration...")
    
    # 1. Restore User 1 (Eflammini)
    user1_username = "Eflammini"
    # Email unknown, leaving as is (restoring login via username is priority)
    
    # 2. Restore User 8 (Roberta)
    user8_username = "Roberta"
    
    users_to_restore = [
        (1, user1_username),
        (8, user8_username)
    ]
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        for uid, username in users_to_restore:
            print(f"Restoring User {uid} with username '{username}'...")
            
            u_bindex = compute_blind_index(username)
            u_enc = encrypt_value(username)
            
            # Check if currently null (just to be safe we don't overwrite if successful login happened somehow?)
            # No, we know it's null.
            
            try:
                cur.execute("""
                    UPDATE Utenti 
                    SET username_bindex = %s,
                        username_enc = %s
                    WHERE id_utente = %s
                """, (u_bindex, u_enc, uid))
                con.commit()
                print(f"User {uid} restored.")
            except Exception as e:
                print(f"Error restoring User {uid}: {e}")
                con.rollback()

if __name__ == "__main__":
    restore_data()
