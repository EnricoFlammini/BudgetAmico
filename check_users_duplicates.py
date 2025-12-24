
import os
import sys
import base64
import hashlib
from typing import Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded .env file")
except ImportError:
    print("python-dotenv not found, environment might be missing")

from db.supabase_manager import get_db_connection
from db.gestione_db import decrypt_system_data, SERVER_SECRET_KEY, _get_system_keys

print(f"k: {bool(SERVER_SECRET_KEY)}")

def check_users():
    try:
        print("--- SCHEMA INFO ---")
        with get_db_connection() as con:
            cur = con.cursor()
            # Inspect columns if it's Postgres (SupabaseManager implies it might be Postgres, but crea_database uses sqlite3?)
            # Wait, SupabaseManager usually implies Postgres. But crea_database.py imported sqlite3.
            # Let's check what get_db_connection returns.
            # If it is psycopg2 (Postgres), we query information_schema.
            # If it is sqlite3, we utilize PRAGMA.
            
            is_sqlite = False
            try:
                import sqlite3
                if isinstance(con, sqlite3.Connection):
                    is_sqlite = True
            except:
                pass

            # Since the user file mentioned SupabaseManager, it's likely Postgres.
            # But let's handle generic SQL or just Try/Except.
            
            try:
                cur.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'utenti'")
                columns = cur.fetchall()
                print("Columns in Utenti (Postgres):")
                for col in columns:
                    print(f" - {col['column_name']} ({col['data_type']}) Nullable: {col['is_nullable']}")
            except Exception as e:
                print(f"Failed to query information_schema (might be SQLite or permission denied): {e}")
                # Fallback implementation
                try: 
                    cur.execute("PRAGMA table_info(Utenti)")
                    columns = cur.fetchall()
                    print("Columns in Utenti (SQLite):")
                    for col in columns:
                        print(f" - {col}")
                except:
                    pass

            print("\n--- USER DATA ---")
            # Select columns attempting to cover both legacy and new
            # We don't know for sure if bindex/enc columns exist without the schema check, but we can try selecting them.
            # If they don't exist, this will fail. We'll be safer by selecting *
            cur.execute("SELECT * FROM Utenti")
            # fetching rows as dicts (assuming RealDictCursor or similar from get_db_connection)
            users = cur.fetchall()
            
            print(f"Total users found: {len(users)}")
            
            decrypted_users = []
            
            for u in users:
                uid = u.get('id_utente')
                
                # Try to get username/email from legacy or encrypted
                raw_username = u.get('username')
                raw_email = u.get('email')
                
                enc_username = u.get('username_enc')
                enc_email = u.get('email_enc')
                
                dec_username = raw_username
                dec_email = raw_email
                
                if enc_username:
                    d = decrypt_system_data(enc_username)
                    if d: dec_username = d + " (Decrypted)"
                
                if enc_email:
                    d = decrypt_system_data(enc_email)
                    if d: dec_email = d + " (Decrypted)"
                
                print(f"User {uid}: Username='{dec_username}', Email='{dec_email}'")
                print(f"   Legacy Username: {raw_username}")
                print(f"   Legacy Email: {raw_email}")
                print(f"   Enc Username: {enc_username}")
                print(f"   Enc Email: {enc_email}")
                print(f"   Bindex Username: {u.get('username_bindex')}")
                print(f"   Bindex Email: {u.get('email_bindex')}")
                
                decrypted_users.append({
                    'id': uid,
                    'username': dec_username.replace(" (Decrypted)", "") if dec_username else None,
                    'email': dec_email.replace(" (Decrypted)", "") if dec_email else None
                })
            
            print("\n--- ANALYSIS ---")
            test_users = [u for u in decrypted_users if u['username'] and 'test' in u['username'].lower()]
            print(f"Test Users Count: {len(test_users)}")
            for tu in test_users:
                print(f" - ID {tu['id']}: {tu['username']}")

            # Check duplicates
            seen_emails = {}
            duplicates = []
            for u in decrypted_users:
                email = u['email']
                if not email: continue
                email_lower = email.lower().strip()
                if email_lower in seen_emails:
                    duplicates.append((u, seen_emails[email_lower]))
                else:
                    seen_emails[email_lower] = u
            
            if duplicates:
                print(f"\nDUPLICATES FOUND ({len(duplicates)}):")
                for curr, prev in duplicates:
                    print(f" - User {curr['id']} is duplicate of {prev['id']} (Email: {curr['email']})")
            else:
                print("\nNo duplicates found based on Email.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_users()
