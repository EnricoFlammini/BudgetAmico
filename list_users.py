import sys
import os
from db.supabase_manager import get_db_connection

def list_users():
    print("="*60)
    print("LISTA UTENTI NEL DATABASE")
    print("="*60)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente, username, email, nome, cognome FROM Utenti")
            users = cur.fetchall()
            
            if not users:
                print("[AVVISO] Nessun utente trovato nel database.")
            else:
                print(f"Trovati {len(users)} utenti:")
                for user in users:
                    print(f" - ID: {user['id_utente']}")
                    print(f"   Username: '{user['username']}'")
                    print(f"   Email:    '{user['email']}'")
                    print(f"   Nome:     '{user['nome']} {user['cognome']}'")
                    print("-" * 40)

    except Exception as e:
        print(f"[ERRORE] Errore durante il listing: {e}")

if __name__ == "__main__":
    list_users()
