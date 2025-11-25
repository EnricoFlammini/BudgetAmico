import sqlite3
import os

APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'BudgetAmico')
DB_FILE = os.path.join(APP_DATA_DIR, 'budget_amico.db')

def update_schema():
    if not os.path.exists(DB_FILE):
        print(f"Database not found at {DB_FILE}")
        return

    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            
            # Check if column exists
            cur.execute("PRAGMA table_info(ContiCondivisi)")
            columns = [info[1] for info in cur.fetchall()]
            
            if "rettifica_saldo" not in columns:
                print("Adding rettifica_saldo column to ContiCondivisi...")
                cur.execute("ALTER TABLE ContiCondivisi ADD COLUMN rettifica_saldo REAL DEFAULT 0.0")
                print("Column added successfully.")
            else:
                print("Column rettifica_saldo already exists in ContiCondivisi.")
                
    except Exception as e:
        print(f"Error updating schema: {e}")

if __name__ == "__main__":
    update_schema()
