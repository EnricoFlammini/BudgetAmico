
import os
import sys
import base64
import hashlib
from dotenv import load_dotenv
from db.supabase_manager import get_db_connection

# Define basic hash function locally to avoid import issues
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Load Env
load_dotenv()
SERVER_SECRET_KEY = os.getenv("SERVER_SECRET_KEY")
print(f"SERVER_SECRET_KEY loaded: {bool(SERVER_SECRET_KEY)}")

HASH_SALT = SERVER_SECRET_KEY

def compute_blind_index(value):
    if not value or not HASH_SALT: return None
    return hashlib.sha256((value.lower().strip() + HASH_SALT).encode()).hexdigest()

def get_system_fernet_key():
    srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(srv_key_bytes)

def debug_user_1():
    print("\n--- Debugging User 1 ---")
    
    # Credentials to test
    test_usernames = ["Eflammini", "eflammini", "Enrico", "admin", "Admin"]
    
    # 1. Compute Blind Indexes for variations
    bindexes = {}
    for u in test_usernames:
        idx = compute_blind_index(u)
        bindexes[u] = idx
        print(f"Computed B-Index for '{u}': {idx}")

    from cryptography.fernet import Fernet
    key = get_system_fernet_key()
    cipher = Fernet(key)

    with get_db_connection() as con:
        cur = con.cursor()
        
        # 2. Get User 1 Data
        cur.execute("""
            SELECT id_utente, username, email, password_hash, 
                   username_bindex, email_bindex, 
                   username_enc, email_enc 
            FROM Utenti WHERE id_utente = 1
        """)
        row = cur.fetchone()
        
        if not row:
            print("User 1 NOT FOUND by ID.")
            return

        print(f"\nStored Data for User 1:")
        print(f"  Legacy Username: {row['username']}")
        print(f"  Legacy Email: {row['email']}")
        print(f"  Stored Username B-Index: {row['username_bindex']}")
        print(f"  Stored Email B-Index:    {row['email_bindex']}")
        
        # 3. Decrypt stored data
        try:
             dec_user = cipher.decrypt(row['username_enc'].encode()).decode() if row['username_enc'] else "None"
             dec_email = cipher.decrypt(row['email_enc'].encode()).decode() if row['email_enc'] else "None"
             print(f"  Decrypted Username: {dec_user}")
             print(f"  Decrypted Email:    {dec_email}")
             
             # Check if decrypted data matches any input bindex
             real_user_bindex = compute_blind_index(dec_user)
             real_email_bindex = compute_blind_index(dec_email)
             
             print(f"\nVerification:")
             print(f"  B-Index of Decrypted Username ({dec_user}): {real_user_bindex}")
             print(f"  Match stored? {real_user_bindex == row['username_bindex']}")
             
             print(f"  B-Index of Decrypted Email ({dec_email}): {real_email_bindex}")
             print(f"  Match stored? {real_email_bindex == row['email_bindex']}")
             
        except Exception as e:
            print(f"Decryption error: {e}")

if __name__ == "__main__":
    debug_user_1()
