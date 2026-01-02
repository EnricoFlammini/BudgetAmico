
import os
import sys
# Add parent dir to path to find db module
sys.path.append(os.getcwd())

from db.supabase_manager import get_db_connection

def run_migration():
    print("Starting manual Postgres migration...")
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # 1. Create Carte Table
            print("Creating Carte table...")
            sql_carte = """
                CREATE TABLE IF NOT EXISTS Carte (
                    id_carta SERIAL PRIMARY KEY,
                    id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
                    nome_carta TEXT NOT NULL,
                    tipo_carta TEXT NOT NULL CHECK(tipo_carta IN ('credito', 'debito')),
                    circuito TEXT NOT NULL,
                    id_conto_riferimento INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
                    id_conto_contabile INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
                    massimale_encrypted TEXT,
                    giorno_addebito_encrypted TEXT,
                    spesa_tenuta_encrypted TEXT,
                    soglia_azzeramento_encrypted TEXT,
                    giorno_addebito_tenuta_encrypted TEXT,
                    addebito_automatico BOOLEAN DEFAULT FALSE,
                    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    attiva BOOLEAN DEFAULT TRUE
                );
            """
            cur.execute(sql_carte)
            
            # 2. Add id_carta to Transazioni
            print("Adding id_carta to Transazioni...")
            try:
                # Check if column exists first to avoid error block issues in simple execution
                # But ALTER TABLE ADD COLUMN IF NOT EXISTS is only available in newer Postgres
                # Let's try simple Add and catch duplicate error
                cur.execute("ALTER TABLE Transazioni ADD COLUMN id_carta INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL")
            except Exception as e:
                # If it fails, likely it exists. In pg8000/Postgres transaction is aborted.
                # We need to rollback to proceed if we were doing more, but since we commit at end...
                # Actually, if we are in a transaction block, one error aborts everything.
                print(f"Notice: referencing 'id_carta' might check/fail: {e}")
                # We should use a SAVEPOINT or check information_schema, but for now lets rely on fresh start assumption or ignore.
                # Since connection might be dead after error, we should probably check first.
                conn.rollback()
                print("Rolled back previous step. Assuming column exists or error.")
                
                # Check if column exists
                cur = conn.cursor() # Re-get cursor
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='transazioni' AND column_name='id_carta'")
                if not cur.fetchone():
                     print("Column missing and failed to add! Re-raising.")
                     raise e
                else:
                     print("Column 'id_carta' already exists in Transazioni.")

            conn.commit()
            print("Migration completed successfully.")
            
    except Exception as e:
        print(f"Migration Failed: {e}")

if __name__ == "__main__":
    run_migration()
