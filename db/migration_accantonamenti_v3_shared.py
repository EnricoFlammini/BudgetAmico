
import os
import sys

# Add parent directory to path
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.supabase_manager import get_db_connection
from utils.logger import setup_logger

logger = setup_logger("MigrationAccantonamentiV3")

def migrate_db():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            logger.info("Migrating DB for Accantonamenti v3 (Shared Accounts Support)...")
            
            # Add id_conto_condiviso to Salvadanai
            logger.info("Adding id_conto_condiviso to Salvadanai...")
            try:
                cur.execute("""
                    ALTER TABLE Salvadanai 
                    ADD COLUMN IF NOT EXISTS id_conto_condiviso INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL;
                """)
            except Exception as e:
                logger.warning(f"Could not add id_conto_condiviso: {e}")

            # Also ensure incide_su_liquidita exists (it was in v2, but just in case)
            try:
                cur.execute("""
                    ALTER TABLE Salvadanai 
                    ADD COLUMN IF NOT EXISTS incide_su_liquidita BOOLEAN DEFAULT FALSE;
                """)
            except Exception as e:
                logger.warning(f"Column incide_su_liquidita might already exist: {e}")

            con.commit()
            logger.info("Migration v3 completed successfully.")
            
    except Exception as e:
        logger.error(f"Error during migration v3: {e}")

if __name__ == "__main__":
    migrate_db()
