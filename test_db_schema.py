
from db.supabase_manager import get_db_connection

def check_db():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            print("Fetching ALL accounts from 'Conti'...")
            cur.execute("SELECT id_conto, id_utente, nome_conto, icona, colore FROM Conti")
            rows = cur.fetchall()
            for row in rows:
                print(f"ID: {row['id_conto']}, User: {row['id_utente']}, Name (Enc): {row['nome_conto'][:10]}..., Icon: {row['icona']}, Color: {row['colore']}")

            print("\nFetching ALL shared accounts from 'ContiCondivisi'...")
            cur.execute("SELECT id_conto_condiviso, nome_conto, icona, colore FROM ContiCondivisi")
            rows = cur.fetchall()
            for row in rows:
                print(f"ID: {row['id_conto_condiviso']}, Name: {row['nome_conto']}, Icon: {row['icona']}, Color: {row['colore']}")

    except Exception as e:
        print(f"Error checking DB: {e}")

if __name__ == "__main__":
    check_db()
