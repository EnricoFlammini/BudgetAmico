from db.gestione_db import get_db_connection

def check_categories():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            print("Checking Categorie...")
            cur.execute("SELECT id_categoria, nome_categoria FROM Categorie")
            for row in cur.fetchall():
                if row['nome_categoria'].startswith('gAAAAA'):
                    print(f"Encrypted Category: ID {row['id_categoria']}, Name: {row['nome_categoria'][:20]}...")
            
            print("Checking Sottocategorie...")
            cur.execute("SELECT id_sottocategoria, nome_sottocategoria FROM Sottocategorie")
            for row in cur.fetchall():
                if row['nome_sottocategoria'].startswith('gAAAAA'):
                    print(f"Encrypted Subcategory: ID {row['id_sottocategoria']}, Name: {row['nome_sottocategoria'][:20]}...")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_categories()
