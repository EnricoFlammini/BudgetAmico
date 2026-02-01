import os
import sys

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection
from utils.logger import setup_logger

logger = setup_logger("Migration_Nascosto")

def apply_migration():
    print("Applying migration: Add nascosto to Conti...")
    try:
        sql_file = os.path.join(os.path.dirname(__file__), 'add_nascosto_column.sql')
        with open(sql_file, 'r') as f:
            sql_content = f.read()

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql_content)
            conn.commit()
            print("Migration applied successfully.")
            
    except Exception as e:
        print(f"Error applying migration: {e}")
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    apply_migration()
