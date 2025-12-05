import os
import psycopg2
from db.supabase_manager import get_db_connection

def inspect_columns():
    tables = ['conti', 'transazioni', 'prestiti', 'asset', 'immobili', 'spesefisse', 'configurazioni']
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        for table in tables:
            print(f"\n--- {table.upper()} ---")
            try:
                cur.execute(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}'
                """)
                columns = cur.fetchall()
                for col in columns:
                    print(f"{col['column_name']} ({col['data_type']})")
            except Exception as e:
                print(f"Errore: {e}")

if __name__ == "__main__":
    inspect_columns()
