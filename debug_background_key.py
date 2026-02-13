import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from db.supabase_manager import get_db_connection
from db.crypto_helpers import get_server_family_key, decrypt_system_data, SERVER_SECRET_KEY, get_system_fernet_key

# Test imports that were failing
import db.gestione_obiettivi
import db.gestione_transazioni
import db.gestione_db

def debug_keys():
    print(f"DEBUG: SERVER_SECRET_KEY present? {bool(SERVER_SECRET_KEY)}")
    if SERVER_SECRET_KEY:
        print(f"DEBUG: SERVER_SECRET_KEY len: {len(SERVER_SECRET_KEY)}")
        
    sfk = get_system_fernet_key()
    print(f"DEBUG: SYSTEM_FERNET_KEY present? {bool(sfk)}")
    if sfk:
        print(f"DEBUG: SYSTEM_FERNET_KEY (b64) len: {len(sfk)}")

    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT id_famiglia, server_encrypted_key FROM Famiglie WHERE server_encrypted_key IS NOT NULL")
        rows = cur.fetchall()
        
        print(f"DEBUG: Found {len(rows)} families with server_encrypted_key.")
        
        for row in rows:
            fid = row['id_famiglia']
            enc_key = row['server_encrypted_key']
            print(f"\n--- Processing Family {fid} ---")
            print(f"Encrypted Key Prefix: {enc_key[:10]}...")
            
            # Try manual decrypt
            try:
                dec = decrypt_system_data(enc_key)
                if dec:
                    print(f"SUCCESS: Decrypted Key for Family {fid} (len={len(dec)})")
                else:
                    print(f"FAILURE: Decrypted Key is None for Family {fid}")
            except Exception as e:
                print(f"EXCEPTION: {e}")

            # Try usage of get_server_family_key
            res = get_server_family_key(fid)
            if res:
                print(f"get_server_family_key returned: SUCCESS")
            else:
                print(f"get_server_family_key returned: FAILURE")

if __name__ == "__main__":
    debug_keys()
