from db.supabase_manager import get_db_connection
from db.migration_manager import migra_database
from db.crea_database import SCHEMA_VERSION

def run_migration():
    print(f"Avvio migrazione manuale verso v{SCHEMA_VERSION}...")
    try:
        with get_db_connection() as con:
            success = migra_database(con, versione_vecchia=21, versione_nuova=22)
            if success:
                print("Migrazione completata con successo.")
            else:
                print("Migrazione fallita.")
    except Exception as e:
        print(f"Errore durante la migrazione: {e}")

if __name__ == "__main__":
    run_migration()
