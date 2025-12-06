from db.gestione_db import get_db_connection

def check_budget():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Check schema (PostgreSQL specific)
            print("Checking Budget schema...")
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'budget'
            """)
            for row in cur.fetchall():
                print(f"Column: {row['column_name']}, Type: {row['data_type']}")

            print("\nChecking Budget content...")
            cur.execute("SELECT id_budget, importo_limite FROM Budget")
            for row in cur.fetchall():
                val = row['importo_limite']
                print(f"ID: {row['id_budget']}, Importo: {val}, Type: {type(val)}")
                if isinstance(val, str) and val.startswith('gAAAAA'):
                    print("  -> ENCRYPTED!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_budget()
