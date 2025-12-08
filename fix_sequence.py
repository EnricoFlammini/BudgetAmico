from db.gestione_db import get_db_connection
from db.supabase_manager import SupabaseManager

def fix_sequences():
    SupabaseManager.initialize_pool()
    print("Fixing sequences...")
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Fix Utenti sequence
            # We assume the sequence name follows the default convention: table_column_seq
            # But sometimes it might be different. Let's try the standard one.
            # If id_utente is an identity column, we might need:
            # ALTER TABLE "Utenti" ALTER COLUMN id_utente RESTART WITH ...
            
            # Let's try setval first, assuming it's a serial.
            # If it fails, we'll try the identity column approach.
            
            try:
                cur.execute("SELECT setval('utenti_id_utente_seq', (SELECT MAX(id_utente) FROM Utenti));")
                print("Utenti sequence fixed (SERIAL).")
            except Exception as e:
                con.rollback()
                print(f"Could not fix sequence using setval: {e}")
                print("Trying IDENTITY column fix...")
                
                # For IDENTITY columns
                cur.execute('SELECT MAX(id_utente) FROM Utenti')
                max_id = cur.fetchone()[0]
                if max_id is None:
                    max_id = 0
                new_val = max_id + 1
                cur.execute(f'ALTER TABLE "Utenti" ALTER COLUMN id_utente RESTART WITH {new_val}')
                print(f"Utenti sequence fixed (IDENTITY) to {new_val}.")
                
            con.commit()
            print("Done.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_sequences()
