
import os
import sys
from db.supabase_manager import get_db_connection

def apply_migration():
    print("Applying crypto fields migration...")
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            with open('db/add_crypto_fields.sql', 'r') as f:
                sql = f.read()
                cur.execute(sql)
            con.commit()
            print("Migration applied successfully.")
    except Exception as e:
        print(f"Error applying migration: {e}")

if __name__ == "__main__":
    # Ensure we can import from parent directory
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    apply_migration()
