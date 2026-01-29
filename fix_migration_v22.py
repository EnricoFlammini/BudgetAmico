import os
import sys

# Aggiungi la root del progetto al path per importare i moduli
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.gestione_db import get_db_connection

def fix_migration_v22():
    print("Avvio fix migrazione v22 manuale...")
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Verifica versione attuale
            cur.execute("SELECT valore FROM InfoDB WHERE chiave = 'versione'")
            row = cur.fetchone()
            current_version = int(row['valore']) if row else 0
            print(f"Versione DB attuale: {current_version}")

            # 2. Controlla se la colonna esiste già
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='utenti' AND column_name='sospeso';
            """)
            if cur.fetchone():
                print("Colonna 'sospeso' già presente. Nessuna azione necessaria.")
            else:
                print("Colonna 'sospeso' mancante. Aggiunta in corso...")
                cur.execute("ALTER TABLE Utenti ADD COLUMN sospeso BOOLEAN DEFAULT FALSE")
                print("Colonna aggiunta con successo.")
                
            # 3. Aggiorna versione se necessario
            if current_version < 22:
                print(f"Aggiornamento versione DB da {current_version} a 22...")
                cur.execute("UPDATE InfoDB SET valore = '22' WHERE chiave = 'versione'")
                if cur.rowcount == 0:
                    cur.execute("INSERT INTO InfoDB (chiave, valore) VALUES ('versione', '22')")
            
            con.commit()
            print("Fix applicato correttamente.")
            
    except Exception as e:
        print(f"Errore durante il fix: {e}")

if __name__ == "__main__":
    fix_migration_v22()
