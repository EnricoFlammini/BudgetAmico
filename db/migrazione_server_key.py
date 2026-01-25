
import os
import sys

# Aggiungi la cartella superiore al path per poter importare i moduli
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.supabase_manager import get_db_connection
from utils.logger import setup_logger

logger = setup_logger("MigrazioneServerKey")

def run_migration():
    print("Avvio migrazione: Aggiunta colonna 'server_encrypted_key' alla tabella Famiglie...")
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Verifica se la colonna esiste già
            try:
                cur.execute("SELECT server_encrypted_key FROM Famiglie LIMIT 1")
                print("La colonna 'server_encrypted_key' esiste già. Nessuna modifica necessaria.")
                return
            except Exception:
                # Se l'eccezione è che la colonna non esiste, procediamo.
                # Nota: pg8000 potrebbe raisare un errore specifico, facciamo rollback per sicurezza
                con.rollback()
                pass

            # Aggiungi la colonna
            print("Aggiunta colonna in corso...")
            cur.execute("ALTER TABLE Famiglie ADD COLUMN server_encrypted_key TEXT")
            con.commit()
            print("Migrazione completata con successo! Colonna aggiunta.")
            
    except Exception as e:
        print(f"Errore critico durante la migrazione: {e}")
        logger.error(f"Errore migrazione: {e}")

if __name__ == "__main__":
    run_migration()
