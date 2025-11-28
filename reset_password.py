import hashlib
from db.supabase_manager import get_db_connection

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def reset_password(username, new_password):
    print("="*60)
    print(f"RESET PASSWORD PER UTENTE: {username}")
    print("="*60)
    
    new_hash = hash_password(new_password)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Verifica se l'utente esiste
            cur.execute("SELECT id_utente FROM Utenti WHERE username = %s", (username,))
            user = cur.fetchone()
            
            if not user:
                print(f"[ERRORE] Utente '{username}' non trovato.")
                return False
                
            id_utente = user['id_utente']
            
            # Aggiorna la password
            print(f"Impostazione nuova password: '{new_password}'...")
            cur.execute("""
                UPDATE Utenti 
                SET password_hash = %s, forza_cambio_password = TRUE 
                WHERE id_utente = %s
            """, (new_hash, id_utente))
            
            con.commit()
            print(f"[SUCCESS] Password aggiornata per utente ID {id_utente}.")
            print("L'utente dovrà cambiare la password al prossimo login.")
            return True

    except Exception as e:
        print(f"[ERRORE] Errore durante il reset: {e}")
        return False

if __name__ == "__main__":
    reset_password("Eflammini", "admin123")
