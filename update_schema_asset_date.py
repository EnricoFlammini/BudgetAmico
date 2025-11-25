import sqlite3
import os

# Definisci il percorso del database
APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'BudgetAmico')
DB_FILE = os.path.join(APP_DATA_DIR, 'budget_amico.db')

def add_data_aggiornamento_column():
    if not os.path.exists(DB_FILE):
        print(f"Database non trovato in: {DB_FILE}")
        return

    print(f"Aggiornamento schema database in: {DB_FILE}")
    
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            
            # Controlla se la colonna esiste già
            cur.execute("PRAGMA table_info(Asset)")
            columns = [info[1] for info in cur.fetchall()]
            
            if 'data_aggiornamento' not in columns:
                print("Aggiunta colonna 'data_aggiornamento' alla tabella Asset...")
                cur.execute("ALTER TABLE Asset ADD COLUMN data_aggiornamento TEXT")
                print("Colonna aggiunta con successo.")
            else:
                print("La colonna 'data_aggiornamento' esiste già.")
                
    except Exception as e:
        print(f"Errore durante l'aggiornamento del database: {e}")

if __name__ == "__main__":
    add_data_aggiornamento_column()
