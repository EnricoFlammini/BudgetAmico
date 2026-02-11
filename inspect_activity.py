from db.supabase_manager import SupabaseManager
import datetime

def inspect():
    try:
        SupabaseManager._initialize()
        with SupabaseManager.get_connection() as con:
            cur = con.cursor()
            
            print("DB CURRENT_TIMESTAMP:")
            cur.execute("SELECT CURRENT_TIMESTAMP")
            db_now = cur.fetchone()[0]
            print(f"  {db_now}")
            
            print("\nUSERS Activity:")
            cur.execute("SELECT id_utente, username, ultimo_accesso FROM Utenti ORDER BY ultimo_accesso DESC")
            users = cur.fetchall()
            for u in users:
                last = u['ultimo_accesso']
                diff = db_now - last
                print(f"  - {u['username']} (ID: {u['id_utente']}): {last} (Diff: {diff})")
            
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    inspect()
