
import os
import datetime
from dotenv import load_dotenv
from db.gestione_db import get_db_connection

load_dotenv()

def check_trans_feb_2026():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            print("--- TRANSAZIONI UTENTE 11 - FEBBRAIO 2026 ---")
            cur.execute("""
                SELECT T.id_transazione, T.data, T.descrizione, T.importo, C.nome_conto
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                WHERE C.id_utente = 11 AND T.data LIKE '2026-02-%%'
            """)
            trans = cur.fetchall()
            print(f"Totale transazioni: {len(trans)}")
            for t in trans:
                print(f"  ID: {t['id_transazione']}, Data: {t['data']}, Importo: {t['importo']}")

            print("\n--- TRANSAZIONI UTENTE 7 - FEBBRAIO 2026 ---")
            cur.execute("""
                SELECT T.id_transazione, T.data, T.descrizione, T.importo, C.nome_conto
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                WHERE C.id_utente = 7 AND T.data LIKE '2026-02-%%'
            """)
            trans7 = cur.fetchall()
            print(f"Totale transazioni: {len(trans7)}")
            for t in trans7:
                 print(f"  ID: {t['id_transazione']}, Data: {t['data']}, Importo: {t['importo']}")

            print("\n--- BUDGET FAMIGLIA 2 ---")
            cur.execute("""
                SELECT B.id_budget, S.nome_sottocategoria, B.importo_limite
                FROM Budget B
                JOIN Sottocategorie S ON B.id_sottocategoria = S.id_sottocategoria
                WHERE B.id_famiglia = 2
            """)
            budgets = cur.fetchall()
            print(f"Righe budget: {len(budgets)}")
            for b in budgets:
                print(f"  ID: {b['id_budget']}, Sotto: {b['nome_sottocategoria']}, Val: {b['importo_limite'][:20]}...")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    check_trans_feb_2026()
