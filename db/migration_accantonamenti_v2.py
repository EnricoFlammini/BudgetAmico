
import os
import sys

# Add parent directory to path
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.supabase_manager import get_db_connection
from utils.logger import setup_logger

logger = setup_logger("MigrationAccantonamentiV2")

def migrate_db():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            logger.info("Migrating DB for Accantonamenti 2.0...")
            
            # 1. Alter Obiettivi_Risparmio
            # Remove importo_accumulato, Add mostra_suggerimento_mensile
            logger.info("Altering Obiettivi_Risparmio...")
            try:
                cur.execute("ALTER TABLE Obiettivi_Risparmio DROP COLUMN IF EXISTS importo_accumulato;")
            except Exception as e:
                logger.warning(f"Could not drop importo_accumulato (might not exist): {e}")

            try:
                cur.execute("ALTER TABLE Obiettivi_Risparmio ADD COLUMN IF NOT EXISTS mostra_suggerimento_mensile BOOLEAN DEFAULT TRUE;")
            except Exception as e:
                logger.warning(f"Column mostra_suggerimento_mensile might already exist: {e}")
            
            # 2. Create Salvadanai Table
            logger.info("Creating table Salvadanai...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Salvadanai (
                    id_salvadanaio SERIAL PRIMARY KEY,
                    id_famiglia INTEGER REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
                    id_obiettivo INTEGER REFERENCES Obiettivi_Risparmio(id) ON DELETE CASCADE,
                    id_conto INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
                    id_asset INTEGER REFERENCES Asset(id_asset) ON DELETE SET NULL,
                    nome TEXT NOT NULL, -- Encrypted or Plain? Plan said "quota auto intesa", maybe plain is safer for filtering, but "note" encrypted.
                    importo_assegnato TEXT NOT NULL, -- Encrypted
                    incide_su_liquidita BOOLEAN DEFAULT FALSE,
                    note TEXT, -- Encrypted
                    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Enable RLS
            cur.execute("ALTER TABLE Salvadanai ENABLE ROW LEVEL SECURITY;")
            
            con.commit()
            logger.info("Migration completed successfully.")
            
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        # raise e # Don't crash hard if possible, just log

if __name__ == "__main__":
    migrate_db()
