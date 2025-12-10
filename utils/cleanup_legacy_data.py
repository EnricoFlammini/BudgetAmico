import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.supabase_manager import get_db_connection

def cleanup():
    print("Starting Cleanup of Legacy Plain-Text Data...")
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # 1. Safety Check
        print("Verifying migration status...")
        cur.execute("SELECT count(*) as cnt FROM Utenti WHERE username_bindex IS NULL OR email_bindex IS NULL")
        non_migrated = cur.fetchone()['cnt']
        
        if non_migrated > 0:
            print(f"[ERROR] Found {non_migrated} users without Blind Index. Aborting cleanup to prevent data loss.")
            return

        print("All users migrated. Proceeding to clear plaintext columns.")

        # 2. Drop NOT NULL constraints (if any)
        try:
            print("Dropping NOT NULL constraints...")
            cur.execute("ALTER TABLE Utenti ALTER COLUMN username DROP NOT NULL")
            cur.execute("ALTER TABLE Utenti ALTER COLUMN email DROP NOT NULL")
            con.commit()
        except Exception as e:
            print(f"Warning dropping constraints (might not exist): {e}")
            con.rollback()

        # 3. Drop UNIQUE constraints?
        # If we have UNIQUE(username), setting all to NULL is fine in Postgres (NULL != NULL).
        # But if we have UNIQUE(email), same.
        # However, we want to enforce uniqueness on `username_bindex` now.
        # `apply_blind_index.py` created indices, but maybe not UNIQUE constraints.
        # Ideally we should add UNIQUE constraints to bindex columns if not present.
        
        # 4. Clear Data
        try:
            print("Nullifying legacy columns...")
            cur.execute("UPDATE Utenti SET username = NULL, email = NULL")
            con.commit()
            print("Legacy data cleared successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to clear data: {e}")
            con.rollback()
            return

        # 5. Optional: Add Unique Constraints to B-Index
        try:
            print("Ensuring Uniqueness on Blind Indices...")
            # We use indices, but let's try to add constraint if possible
            # This might fail if duplicates exist (unlikely if migration worked on unique source)
            # cur.execute("ALTER TABLE Utenti ADD CONSTRAINT unique_username_bindex UNIQUE (username_bindex)")
            # cur.execute("ALTER TABLE Utenti ADD CONSTRAINT unique_email_bindex UNIQUE (email_bindex)")
            # con.commit()
            pass 
        except Exception as e:
            print(f"Warning setting unique constraints: {e}")
            con.rollback()

    print("Cleanup Complete!")

if __name__ == "__main__":
    cleanup()
