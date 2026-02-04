
import os
import base64
from dotenv import load_dotenv
from db.gestione_db import get_db_connection
from utils.crypto_manager import CryptoManager

load_dotenv()

def check_family_data_encryption(id_famiglia):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Budget
            print(f"--- ANALISI BUDGET FAMIGLIA {id_famiglia} ---")
            cur.execute("""
                SELECT B.id_budget, S.nome_sottocategoria, B.importo_limite
                FROM Budget B
                JOIN Sottocategorie S ON B.id_sottocategoria = S.id_sottocategoria
                WHERE B.id_famiglia = %s
            """, (id_famiglia,))
            budgets = cur.fetchall()
            for b in budgets:
                limite = b['importo_limite']
                is_enc = isinstance(limite, str) and limite.startswith("gAAAAA")
                print(f"  ID: {b['id_budget']}, Sottocategoria: {b['nome_sottocategoria']}, Criptato: {is_enc}")

            # 2. Transazioni Personali di membri della famiglia
            print(f"\n--- ANALISI TRANSAZIONI PERSONALI SOCI FAMIGLIA {id_famiglia} ---")
            cur.execute("""
                SELECT T.id_transazione, C.id_utente, T.descrizione, T.importo
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                LIMIT 10
            """, (id_famiglia,))
            trans = cur.fetchall()
            for t in trans:
                desc = t['descrizione']
                is_enc = isinstance(desc, str) and desc.startswith("gAAAAA")
                print(f"  ID: {t['id_transazione']}, Utente: {t['id_utente']}, Criptato: {is_enc}")

            # 3. Transazioni Condivise della famiglia
            print(f"\n--- ANALISI TRANSAZIONI CONDIVISE FAMIGLIA {id_famiglia} ---")
            cur.execute("""
                SELECT TC.id_transazione_condivisa, TC.id_utente_autore, TC.descrizione
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                LIMIT 10
            """, (id_famiglia,))
            cond = cur.fetchall()
            for c in cond:
                desc = c['descrizione']
                is_enc = isinstance(desc, str) and desc.startswith("gAAAAA")
                print(f"  ID: {c['id_transazione_condivisa']}, Autore: {c['id_utente_autore']}, Criptato: {is_enc}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    check_family_data_encryption(4)
