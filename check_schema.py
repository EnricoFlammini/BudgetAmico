from db.gestione_db import get_db_connection

def check_schema():
    print("--- Checking Schema ---")
    with get_db_connection() as con:
        cur = con.cursor()
        
        print("\nCategorie:")
        cur.execute("SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name = 'categorie'")
        for row in cur.fetchall():
            print(f"  {row['column_name']}: {row['data_type']} ({row['character_maximum_length']})")

        print("\nSottocategorie:")
        cur.execute("SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name = 'sottocategorie'")
        for row in cur.fetchall():
            print(f"  {row['column_name']}: {row['data_type']} ({row['character_maximum_length']})")

if __name__ == "__main__":
    check_schema()
