from db.gestione_db import get_db_connection

def find_encrypted_string():
    target_string = 'gAAAAABpMiZNlp965KVWYvOVteCv4F72DItdejQyBP10y7OenlNmRl-IHrVNFB0mpJyPsnWxTKI786eBHB4rQnAC3XccmXlWhw=='
    tables_columns = [
        ('Categorie', 'nome_categoria'),
        ('Sottocategorie', 'nome_sottocategoria'),
        ('Budget', 'importo_limite'),
        ('Prestiti', 'nome'),
        ('Prestiti', 'descrizione'),
        ('Immobili', 'nome'),
        ('Immobili', 'via'),
        ('Immobili', 'citta'),
        ('SpeseFisse', 'nome'),
        ('Inviti', 'email_invitato'),
        ('Conti', 'nome_conto'), # Maybe accounts are encrypted?
        ('ContiCondivisi', 'nome_conto')
    ]

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            for table, column in tables_columns:
                try:
                    query = f"SELECT {column} FROM {table} WHERE {column} = %s"
                    cur.execute(query, (target_string,))
                    if cur.fetchone():
                        print(f"FOUND in Table: {table}, Column: {column}")
                        return
                except Exception as e:
                    # Ignore errors (e.g. column doesn't exist or type mismatch)
                    pass
            print("Not found in checked tables/columns.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_encrypted_string()
