import sys
import os
import hashlib
from db.supabase_manager import get_db_connection

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def debug_login():
    print("="*60)
    print("DEBUG LOGIN")
    print("="*60)
    
    username_input = input("Inserisci username o email: ").strip()
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            print(f"\nCercando utente: '{username_input}'...")
            
            cur.execute("""
                SELECT id_utente, username, email, password_hash 
                FROM Utenti 
                WHERE username = %s OR email = %s
            """, (username_input, username_input.lower()))
            
            user = cur.fetchone()
            
            if not user:
                print("[ERRORE] Utente non trovato nel database.")
                
                # Prova a cercare parzialmente
                print("\nRicerca parziale...")
                cur.execute("SELECT username, email FROM Utenti WHERE username ILIKE %s OR email ILIKE %s", 
                           (f"%{username_input}%", f"%{username_input}%"))
                matches = cur.fetchall()
                if matches:
                    print("Trovati utenti simili:")
                    for m in matches:
                        print(f" - Username: '{m['username']}', Email: '{m['email']}'")
                else:
                    print("Nessun utente simile trovato.")
                return

            print(f"[OK] Utente trovato: ID {user['id_utente']}")
            print(f"     Username DB: {repr(user['username'])}")
            print(f"     Email DB:    {repr(user['email'])}")
            print(f"     Hash DB:     {user['password_hash']}")
            
            password_input = input("\nInserisci password: ")
            computed_hash = hash_password(password_input)
            
            print(f"\nHash calcolato: {computed_hash}")
            
            if user['password_hash'] == computed_hash:
                print("\n[SUCCESS] Le password corrispondono!")
            else:
                print("\n[FAIL] Le password NON corrispondono.")
                print(f"       Lunghezza Hash DB: {len(user['password_hash'])}")
                print(f"       Lunghezza Hash Calcolato: {len(computed_hash)}")

    except Exception as e:
        print(f"\n[ERRORE] Eccezione durante il debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_login()
