
import os
from dotenv import load_dotenv
from db.gestione_db import get_db_connection

load_dotenv()

def check_family_2_keys_and_data():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            print("--- CHIAVI FAMIGLIA 2 ---")
            cur.execute("""
                SELECT id_utente, ruolo, chiave_famiglia_criptata IS NOT NULL as has_key
                FROM Appartenenza_Famiglia
                WHERE id_famiglia = 2
            """)
            members = cur.fetchall()
            for m in members:
                print(f"Utente ID: {m['id_utente']}, Ruolo: {m['ruolo']}, Ha Chiave: {m['has_key']}")

            print("\n--- CONTI UTENTE 11 ---")
            cur.execute("SELECT id_conto, nome_conto FROM Conti WHERE id_utente = 11")
            conti_11 = cur.fetchall()
            for c in conti_11:
                print(f"Conto ID: {c['id_conto']}, Nome (Enc): {c['nome_conto'][:20]}...")
                
                # Check for transactions
                cur.execute("SELECT id_transazione, descrizione, importo FROM Transazioni WHERE id_conto = %s LIMIT 5", (c['id_conto'],))
                trans = cur.fetchall()
                print(f"  Transazioni trovate: {len(trans)}")
                for t in trans:
                    desc = t['descrizione']
                    is_enc = isinstance(desc, str) and desc.startswith("gAAAAA")
                    print(f"    ID: {t['id_transazione']}, Criptato: {is_enc}, Desc: {desc[:20]}...")

            print("\n--- TRANSAZIONI CONDIVISE FAMIGLIA 2 ---")
            cur.execute("""
                SELECT TC.id_transazione_condivisa, TC.id_utente_autore, TC.descrizione
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = 2
                LIMIT 5
            """)
            shared = cur.fetchall()
            print(f"Transazioni condivise trovate: {len(shared)}")
            for s in shared:
                desc = s['descrizione']
                is_enc = isinstance(desc, str) and desc.startswith("gAAAAA")
                print(f"    ID: {s['id_transazione_condivisa']}, Autore: {s['id_utente_autore']}, Criptato: {is_enc}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    check_family_2_keys_and_data()
