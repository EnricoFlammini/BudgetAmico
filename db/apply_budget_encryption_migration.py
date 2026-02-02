
import os
import sys

# Aggiungi la directory superiore al path per caricare i moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.supabase_manager import get_db_connection
from utils.logger import setup_logger

logger = setup_logger("MigrationBudget")

def apply_migration():
    """
    Converte le colonne importo_limite e importo_speso in TEXT 
    per supportare la memorizzazione di dati criptati.
    """
    logger.info("Inizio migrazione colonne budget a TEXT...")
    
    queries = [
        # Tabella Budget
        "ALTER TABLE Budget ALTER COLUMN importo_limite TYPE TEXT;",
        
        # Tabella Budget_Storico
        "ALTER TABLE Budget_Storico ALTER COLUMN importo_limite TYPE TEXT;",
        "ALTER TABLE Budget_Storico ALTER COLUMN importo_speso TYPE TEXT;"
    ]
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            for query in queries:
                try:
                    logger.info(f"Esecuzione: {query}")
                    cur.execute(query)
                except Exception as e:
                    if "already" in str(e).lower() or "not exist" in str(e).lower():
                        logger.warning(f"Salto query (possibile già applicata): {e}")
                    else:
                        raise e
            
            con.commit()
            logger.info("✅ Migrazione completata con successo.")
            return True
            
    except Exception as e:
        logger.error(f"❌ Errore durante la migrazione: {e}")
        return False

if __name__ == "__main__":
    apply_migration()
