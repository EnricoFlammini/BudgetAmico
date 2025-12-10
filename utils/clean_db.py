import os
import psycopg2
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.supabase_manager import get_db_connection

def clean_database():
    print("Inizio pulizia database...")
    
    # Usa lowercase come visto nel DB
    tables_to_truncate = [
        "transazionicondivise",
        "transazioni",
        "storicopagamentirate",
        "quoteimmobili",
        "quoteprestiti",
        "partecipazionecontocondiviso",
        "storico_asset",
        "asset",
        "budget",
        "budget_storico",
        "spesefisse",
        "prestiti",
        "immobili",
        "sottocategorie",
        "categorie",
        "inviti",
        "configurazioni",
        "conticondivisi",
        "conti",
        "appartenenza_famiglia",
        "utenti",
        "famiglie"
    ]
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            for table in tables_to_truncate:
                try:
                    print(f"Svuotamento tabella {table} e dipendenze...")
                    # Usa CASCADE per eliminare i dati collegati
                    cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE;')
                except Exception as e:
                    print(f"Errore svuotamento {table}: {e}")
                    conn.rollback()
                    return

            conn.commit()
            print("Database pulito con successo!")
            
    except Exception as e:
        print(f"Errore generale: {e}")

if __name__ == "__main__":
    clean_database()
