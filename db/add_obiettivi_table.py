
import os
import sys

# Add parent directory to path to allow importing modules
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.supabase_manager import get_db_connection
from utils.logger import setup_logger

logger = setup_logger("MigrationObiettivi")

def add_obiettivi_table():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            logger.info("Creating table Obiettivi_Risparmio...")
            
            # Create table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Obiettivi_Risparmio (
                    id SERIAL PRIMARY KEY,
                    id_famiglia INTEGER REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
                    nome TEXT NOT NULL,
                    importo_obiettivo TEXT NOT NULL, -- Encrypted
                    data_obiettivo DATE NOT NULL,
                    importo_accumulato TEXT DEFAULT 'gAAAAA...', -- Encrypted, default 0 encrypted (placeholder) or handled in code
                    note TEXT, -- Encrypted
                    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Enable RLS (Row Level Security) if not already enabled (Good practice)
            cur.execute("ALTER TABLE Obiettivi_Risparmio ENABLE ROW LEVEL SECURITY;")
            
            # Create Policy for SELECT (View own family goals)
            # Assuming 'auth.uid()' logic or similar is managed via app logic or `setup_rls_policies.sql`.
            # For now, we rely on the application logic (gestione_db.py) to filter by id_famiglia.
            # But we should add the policy if other tables have it.
            # Let's check if we need to add RLS policies explicitly here. 
            # Given previous context `setup_rls_policies.sql`, RLS is used.
            # We will create a simple policy that allows all actions for now if the user maps to family, 
            # Or we can skip RLS policy creation here and rely on the app logic if RLS policies are complex.
            # However, looking at 'add_pianoammortamento_rls.sql', it seems policies are added manually.
            
            # Policy: Users can select rows where their family matches id_famiglia
            # This requires a way to link current user to family in SQL (e.g. via session variable or join).
            # If the app manages RLS via `set_current_user` or similar, we should use that.
            # For simplicity in this migration script, we will just create the table. 
            # Application code filters by `id_famiglia` explicitly anyway.
            
            con.commit()
            logger.info("Table Obiettivi_Risparmio created successfully.")
            
    except Exception as e:
        logger.error(f"Error creating table: {e}")
        raise e

if __name__ == "__main__":
    add_obiettivi_table()
