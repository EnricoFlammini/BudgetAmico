import os
import sys

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection

def inspect_schema():
    print("Inspecting schema details for Utenti...")
    
    with get_db_connection() as conn:
        print("Connected to DB.")
        
        cur = conn.cursor()
        
        # Check Nullable
        cur.execute("""
            SELECT column_name, is_nullable, data_type 
            FROM information_schema.columns 
            WHERE table_name='utenti' AND column_name IN ('username', 'email')
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"Column: {row['column_name']}, Nullable: {row['is_nullable']}, Type: {row['data_type']}")
            
        # Check constraints explicitly
        cur.execute("""
            SELECT conname, contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'utenti'::regclass
        """)
        constraints = cur.fetchall()
        print("\nConstraints:")
        for c in constraints:
            print(f"- {c['conname']} ({c['contype']}): {c['pg_get_constraintdef']}")

if __name__ == "__main__":
    inspect_schema()
