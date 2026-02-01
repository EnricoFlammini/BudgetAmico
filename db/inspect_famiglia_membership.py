import os
import sys

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection

def inspect_famiglia_membership():
    print("Inspecting Appartenenza_Famiglia table...")
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'appartenenza_famiglia'
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"Column: {row['column_name']}, Type: {row['data_type']}, Nullable: {row['is_nullable']}")

if __name__ == "__main__":
    inspect_famiglia_membership()
