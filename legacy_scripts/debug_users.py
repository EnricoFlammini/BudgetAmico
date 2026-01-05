from db.gestione_db import get_db_connection
import sys

def list_users():
    print("Listing all users...", flush=True)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id_utente, username, email FROM Utenti")
            rows = cursor.fetchall()
            for row in rows:
                print(f"User: {dict(row)}", flush=True)
                
            print("-" * 20)
            print("Checking specifically for ID 16:", flush=True)
            cursor.execute("SELECT * FROM Utenti WHERE id_utente = 16")
            u16 = cursor.fetchone()
            print(f"User 16: {dict(u16) if u16 else 'NOT FOUND'}", flush=True)

    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    list_users()
