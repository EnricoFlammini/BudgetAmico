from db.gestione_db import get_db_connection
import sys

def add_column_if_not_exists():
    print("Inizio migrazione SpeseFisse (Postgres)...", flush=True)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Verifica se la colonna esiste già (Postgres syntax)
            # information_schema.columns stores table names in lowercase usually unless quoted.
            # But pg8000 usually handles this. Let's try flexible check.
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'spesefisse' AND column_name = 'id_carta'
            """)
            result = cursor.fetchone()
            
            if not result:
                # Try also case sensitive check just in case
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'SpeseFisse' AND column_name = 'id_carta'
                """)
                result = cursor.fetchone()

            if not result:
                print("Aggiunta colonna 'id_carta' alla tabella 'SpeseFisse'...", flush=True)
                cursor.execute("ALTER TABLE SpeseFisse ADD COLUMN id_carta INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL")
                conn.commit()
                print("Colonna aggiunta con successo.", flush=True)
            else:
                print("La colonna 'id_carta' esiste già nella tabella 'SpeseFisse'.", flush=True)
                
    except Exception as e:
        print(f"Errore durante la migrazione: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_column_if_not_exists()
