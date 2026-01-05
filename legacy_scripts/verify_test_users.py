import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.supabase_manager import get_db_connection

def list_test_users():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente, username, email FROM Utenti")
            users = cur.fetchall()
            
            test_users = []
            for u in users:
                user_str = f"{u['username']} ({u['email']})"
                if 'test' in user_str.lower():
                    test_users.append(u)
            
            print(f"Found {len(test_users)} potential 'Test' users:")
            for u in test_users:
                print(f"- ID: {u['id_utente']}, Username: {u['username']}, Email: {u['email']}")

            print(f"\nTotal users in DB: {len(users)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_test_users()
