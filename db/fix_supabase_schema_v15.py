
import sys
import os

# Add parent dir to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.supabase_manager import get_db_connection
import pg8000

def run_migration():
    print("Starting Manual Migration to v15 for Supabase...")
    conn = None
    try:
        conn = get_db_connection()
        # get_db_connection returns a context manager wrapper (SupabaseConnection or similar)
        # We need the actual connection to commit?
        # Let's see usage in gestione_db.py: "with get_db_connection() as con: cur = con.cursor() ... con.commit()"
        # So it behaves like a connection object.
        
        with conn as con:
            cur = con.cursor()
            
            # 1. Add columns to Carte (from v14)
            print("Checking/Adding columns to Carte...")
            queries_carte = [
                "ALTER TABLE Carte ADD COLUMN IF NOT EXISTS id_conto_riferimento_condiviso INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL",
                "ALTER TABLE Carte ADD COLUMN IF NOT EXISTS id_conto_contabile_condiviso INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL",
                "ALTER TABLE Carte ADD COLUMN IF NOT EXISTS giorno_addebito_tenuta_encrypted TEXT"
            ]
            
            for q in queries_carte:
                try:
                    cur.execute(q)
                    print(f"  Executed: {q[:50]}...")
                except Exception as e:
                    print(f"  Error executing {q[:50]}: {e}")

            # 2. Add columns to TransazioniCondivise (from v15)
            print("Checking/Adding columns to TransazioniCondivise...")
            queries_tc = [
                "ALTER TABLE TransazioniCondivise ADD COLUMN IF NOT EXISTS id_carta INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL",
                "ALTER TABLE TransazioniCondivise ADD COLUMN IF NOT EXISTS importo_nascosto BOOLEAN DEFAULT FALSE"
            ]
            
            for q in queries_tc:
                try:
                    cur.execute(q)
                    print(f"  Executed: {q[:50]}...")
                except Exception as e:
                    print(f"  Error executing {q[:50]}: {e}")

            # 3. Create StoricoMassimaliCarte (from v13, likely missing)
            print("Checking/Creating StoricoMassimaliCarte table...")
            query_smc = """
                CREATE TABLE IF NOT EXISTS StoricoMassimaliCarte (
                    id_storico SERIAL PRIMARY KEY,
                    id_carta INTEGER NOT NULL REFERENCES Carte(id_carta) ON DELETE CASCADE,
                    data_inizio_validita TEXT NOT NULL,
                    massimale_encrypted TEXT NOT NULL,
                    UNIQUE(id_carta, data_inizio_validita)
                );
            """
            try:
                cur.execute(query_smc)
                print("  Executed CREATE TABLE StoricoMassimaliCarte...")
            except Exception as e:
                print(f"  Error creating table: {e}")

            con.commit()
            print("Migration committed successfully.")

    except Exception as e:
        print(f"Critical Error: {e}")
    finally:
        # If conn was opened but not closed by context manager (it handles close mostly)
        pass

if __name__ == "__main__":
    run_migration()
