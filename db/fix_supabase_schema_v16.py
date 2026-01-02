
import sys
import os

# Add parent dir to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.supabase_manager import get_db_connection
import pg8000

def run_migration_v16():
    print("Starting Manual Migration to v16 for Supabase...")
    conn = None
    try:
        conn = get_db_connection()
        
        with conn as con:
            cur = con.cursor()
            
            # Add id_carta_default to Utenti
            print("Checking/Adding id_carta_default column to Utenti...")
            
            # Check if column exists first to avoid error block if not using IF NOT EXISTS (which Postgres supports though)
            # Using ADD COLUMN IF NOT EXISTS is standard in modern Postgres (v9.6+)
            
            q = "ALTER TABLE Utenti ADD COLUMN IF NOT EXISTS id_carta_default INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL"
            
            try:
                cur.execute(q)
                print(f"  Executed: {q}")
            except Exception as e:
                print(f"  Error executing query: {e}")

            # 4. Update InfoDB for AppController version check
            print("Updating InfoDB version...")
            cur.execute("CREATE TABLE IF NOT EXISTS InfoDB (chiave TEXT PRIMARY KEY, valore TEXT)")
            
            # Check if version exists
            cur.execute("SELECT valore FROM InfoDB WHERE chiave = 'versione'")
            if cur.fetchone():
                cur.execute("UPDATE InfoDB SET valore = '16' WHERE chiave = 'versione'")
            else:
                cur.execute("INSERT INTO InfoDB (chiave, valore) VALUES ('versione', '16')")
            
            print("InfoDB updated to version 16.")

            con.commit()
            print("Migration v16 committed successfully.")

    except Exception as e:
        print(f"Critical Error: {e}")
    finally:
        pass

if __name__ == "__main__":
    run_migration_v16()
