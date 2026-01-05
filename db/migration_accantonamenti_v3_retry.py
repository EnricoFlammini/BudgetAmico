
import os
import sys

# Add parent directory to path
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.supabase_manager import get_db_connection

def migrate_db():
    print("Starting Migration V3 (Retry)...")
    try:
        with get_db_connection() as con:
            con.autocommit = True # Force autocommit to ensure changes persist immediately
            cur = con.cursor()
            
            print("Checking if id_conto_condiviso column exists...")
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='salvadanai' AND column_name='id_conto_condiviso';
            """)
            if cur.fetchone():
                print("Column id_conto_condiviso ALREADY EXISTS.")
            else:
                print("Column id_conto_condiviso MISSING. Adding it...")
                try:
                    cur.execute("""
                        ALTER TABLE Salvadanai 
                        ADD COLUMN id_conto_condiviso INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL;
                    """)
                    print("Column added successfully.")
                except Exception as e:
                    print(f"Error adding column: {e}")

            print("Checking if incide_su_liquidita column exists...")
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='salvadanai' AND column_name='incide_su_liquidita';
            """)
            if cur.fetchone():
                print("Column incide_su_liquidita ALREADY EXISTS.")
            else:
                print("Column incide_su_liquidita MISSING. Adding it...")
                try:
                    cur.execute("""
                        ALTER TABLE Salvadanai 
                        ADD COLUMN incide_su_liquidita BOOLEAN DEFAULT FALSE;
                    """)
                    print("Column added successfully.")
                except Exception as e:
                    print(f"Error adding column: {e}")

            print("Migration V3 Completed.")
            
    except Exception as e:
        print(f"CRITICAL MIGRATION ERROR: {e}")

if __name__ == "__main__":
    migrate_db()
