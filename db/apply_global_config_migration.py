import os
import sys

# Aggiungi la directory superiore al percorso per consentire l'importazione dei moduli
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection
from utils.logger import setup_logger

logger = setup_logger("Migration_GlobalConfig")

def apply_migration():
    print("Applicazione migrazione: Indici e Policy per Configurazioni Globali...")
    try:
        sql_file = os.path.join(os.path.dirname(__file__), 'add_global_config_index.sql')
        with open(sql_file, 'r') as f:
            sql_content = f.read()

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql_content)
            conn.commit()
            print("Migrazione applicata con successo.")
            
    except Exception as e:
        print(f"Errore durante l'applicazione della migrazione: {e}")
        logger.error(f"Migrazione fallita: {e}")

if __name__ == "__main__":
    apply_migration()
