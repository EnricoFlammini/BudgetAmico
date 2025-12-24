
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment logic
load_dotenv()

from db.supabase_manager import get_db_connection

def fix_duplicates():
    print("--- FIXING DUPLICATES & ADDING CONSTRAINTS ---")
    
    users_to_delete = [13, 15]
    user_to_keep = 10
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. HARD DELETE DUPLICATES
            # Since these are test users created by mistake, we assume Hard Delete is preferable to clean the DB.
            # We must delete from child tables first if CASCADE is not set properly, but schema says CASCADE usually.
            # Let's verify if we need to manually delete dependencies or if ON DELETE CASCADE handles it.
            # Schema says: Appartenenza_Famiglia -> ON DELETE CASCADE
            # Conti -> ON DELETE CASCADE
            # So deleting from Utenti should be enough.
            
            print(f"Deleting users {users_to_delete}...")
            placeholders = ','.join(['%s'] * len(users_to_delete))
            cur.execute(f"DELETE FROM Utenti WHERE id_utente IN ({placeholders})", tuple(users_to_delete))
            deleted_count = cur.rowcount
            print(f"Deleted {deleted_count} users.")
            
            # 2. ADD UNIQUE CONSTRAINTS
            # Postgres: CREATE UNIQUE INDEX
            # We need to check if index already exists to avoid error, or just try/except.
            
            print("Adding UNIQUE constraints to blind index columns...")
            
            queries = [
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_utenti_username_bindex ON Utenti(username_bindex);",
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_utenti_email_bindex ON Utenti(email_bindex);"
            ]
            
            for q in queries:
                try:
                    cur.execute(q)
                    print(f"Executed: {q}")
                except Exception as e_idx:
                    print(f"Index creation warning (might already exist): {e_idx}")
            
            con.commit()
            print("Successfully committed changes.")
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    confirm = input("Are you sure you want to delete users 13, 15 and add unique constraints? (yes/no): ")
    if confirm.lower() == 'yes':
        fix_duplicates()
    else:
        print("Operation cancelled.")
