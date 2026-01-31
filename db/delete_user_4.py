import os
import sys

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection

def delete_user_4():
    print("Deleting User ID 4...")
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Hard delete from Utenti (cascades should handle the rest)
        cur.execute("DELETE FROM Utenti WHERE id_utente = 4")
        conn.commit()
        
        if cur.rowcount > 0:
            print(f"User 4 deleted successfully.")
        else:
            print("User 4 not found.")

if __name__ == "__main__":
    delete_user_4()
