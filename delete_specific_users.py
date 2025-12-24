
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment logic
load_dotenv()

from db.supabase_manager import get_db_connection

def delete_users():
    users_to_delete = [10, 12]
    print(f"--- DELETING USERS {users_to_delete} ---")
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # HARD DELETE
            placeholders = ','.join(['%s'] * len(users_to_delete))
            cur.execute(f"DELETE FROM Utenti WHERE id_utente IN ({placeholders})", tuple(users_to_delete))
            deleted_count = cur.rowcount
            print(f"Deleted {deleted_count} users.")
            
            con.commit()
            print("Successfully committed changes.")
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    delete_users()
