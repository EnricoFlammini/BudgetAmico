
import os
import sys
import psycopg2

# Add the parent directory to sys.path to allow importing from db.gestione_db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection

def migrate():
    print("Inizio migrazione: Aggiunta colonne giroconto a SpeseFisse table...")
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # 1. Add is_giroconto column
            try:
                cur.execute("ALTER TABLE SpeseFisse ADD COLUMN is_giroconto BOOLEAN DEFAULT FALSE")
                print("Colonna 'is_giroconto' aggiunta.")
            except Exception as e:
                # pg8000 throws programming error for duplicates usually, or we can check specific error codes if needed.
                # But generic catch and print is robust enough for one-off migration if we assume duplicate.
                if "DuplicateColumn" in str(e) or "42701" in str(e) or "already exists" in str(e):
                    print("Colonna 'is_giroconto' già esistente. Skipping.")
                else:
                    print(f"Errore aggiunta is_giroconto: {e}")
                    # Don't rollback whole transaction for this if it's just column exists,
                    # but pg8000/postgres might invalidate transaction on any error.
                    # So ideally, we should check column existence first or run separate blocks.
                    conn.rollback()

            # 2. Add id_conto_personale_beneficiario column
            try:
                cur.execute("""
                    ALTER TABLE SpeseFisse 
                    ADD COLUMN id_conto_personale_beneficiario INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL
                """)
                print("Colonna 'id_conto_personale_beneficiario' aggiunta.")
            except Exception as e:
                if "DuplicateColumn" in str(e) or "42701" in str(e) or "already exists" in str(e):
                    print("Colonna 'id_conto_personale_beneficiario' già esistente. Skipping.")
                else:
                     print(f"Errore aggiunta id_conto_personale_beneficiario: {e}")
                     conn.rollback()

            # 3. Add id_conto_condiviso_beneficiario column
            try:
                cur.execute("""
                    ALTER TABLE SpeseFisse 
                    ADD COLUMN id_conto_condiviso_beneficiario INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL
                """)
                print("Colonna 'id_conto_condiviso_beneficiario' aggiunta.")
            except Exception as e:
                if "DuplicateColumn" in str(e) or "42701" in str(e) or "already exists" in str(e):
                    print("Colonna 'id_conto_condiviso_beneficiario' già esistente. Skipping.")
                else:
                     print(f"Errore aggiunta id_conto_condiviso_beneficiario: {e}")
                     conn.rollback()

            conn.commit()
            print("Migrazione completata con successo.")
        
    except Exception as e:
        print(f"Errore critico durante la migrazione: {e}")

if __name__ == "__main__":
    migrate()
