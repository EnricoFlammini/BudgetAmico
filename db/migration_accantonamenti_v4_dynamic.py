
import os
import sys

# Add parent directory to path
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.supabase_manager import get_db_connection
from utils.logger import setup_logger

logger = setup_logger("MigrationAccantonamentiV4")

def migrate_db():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            logger.info("Migrating DB for Accantonamenti Dynamic (V4)...")
            
            # Add usa_saldo_totale column
            logger.info("Adding usa_saldo_totale to Salvadanai...")
            try:
                cur.execute("ALTER TABLE Salvadanai ADD COLUMN IF NOT EXISTS usa_saldo_totale BOOLEAN DEFAULT FALSE;")
            except Exception as e:
                logger.warning(f"Column usa_saldo_totale might already exist: {e}")
            
            con.commit()
            logger.info("Migration completed successfully.")
            
    except Exception as e:
        logger.error(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate_db()
