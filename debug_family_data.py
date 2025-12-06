"""Debug script to check family transaction data and user info."""
import sys
sys.path.insert(0, r"C:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo")

from db.supabase_manager import get_db_connection

def main():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get famiglia ID
            # Get user info
            cur.execute("SELECT username, nome, cognome, id_utente FROM Utenti LIMIT 5")
            print("=== UTENTI ===")
            for row in cur.fetchall():
                print(f"id_utente={row['id_utente']}, username={row['username']}, nome={repr(row['nome'])}, cognome={repr(row['cognome'])}")
            
            print("\n=== FAMIGLIE ===")
            cur.execute("SELECT id_famiglia, nome_famiglia FROM Famiglie LIMIT 5")
            for row in cur.fetchall():
                print(f"id_famiglia={row['id_famiglia']}, nome_famiglia={row['nome_famiglia']}")
            
            print("\n=== TRANSAZIONI CONDIVISE (ultime 3) ===")
            cur.execute("""
                SELECT TC.id_transazione_condivisa, TC.descrizione, TC.id_utente_autore,
                       U.username, U.nome, U.cognome
                FROM TransazioniCondivise TC
                LEFT JOIN Utenti U ON TC.id_utente_autore = U.id_utente
                ORDER BY TC.data DESC
                LIMIT 3
            """)
            for row in cur.fetchall():
                print(f"id_trans={row['id_transazione_condivisa']}, descrizione={row['descrizione'][:50] if row['descrizione'] else 'N/A'}...")
                print(f"  id_utente_autore={row['id_utente_autore']}, username={row['username']}, nome={row['nome']}, cognome={row['cognome']}")
            
            print("\n=== TRANSAZIONI PERSONALI (ultime 3) ===")
            cur.execute("""
                SELECT T.id_transazione, T.descrizione, C.id_utente,
                       U.username, U.nome, U.cognome
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Utenti U ON C.id_utente = U.id_utente
                ORDER BY T.data DESC
                LIMIT 3
            """)
            for row in cur.fetchall():
                print(f"id_trans={row['id_transazione']}, descrizione={row['descrizione'][:50] if row['descrizione'] else 'N/A'}...")
                print(f"  id_utente={row['id_utente']}, username={row['username']}, nome={row['nome']}, cognome={row['cognome']}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
