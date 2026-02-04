
import os
from dotenv import load_dotenv
load_dotenv()
from db.gestione_db import ottieni_tutti_i_conti_famiglia, get_db_connection

def test_card_key_format():
    print("--- Test Formato Chiave Carta ---")
    try:
        # Recuperiamo una famiglia e un utente esistente per il test (usiamo ID 2 e 7 dall'audit precedente)
        id_famiglia = 2
        id_utente = 7
        
        conti = ottieni_tutti_i_conti_famiglia(id_famiglia, id_utente)
        card_found = False
        for c in conti:
            if c['tipo'] == 'Carta':
                card_found = True
                print(f"Carta trovata: {c['nome_conto']}")
                print(f"Chiave generata: {c['id_conto']}")
                
                # Simula il parsing in transaction_dialog.py
                parts = c['id_conto'].split("_")
                print(f"Parts split: {parts}")
                if len(parts) >= 3:
                    print("SUCCESS: Il formato contiene almeno 3 parti (id_carta e id_conto).")
                else:
                    print("FAILURE: Il formato non è corretto.")
        
        if not card_found:
             print("Nessuna carta trovata per il test nella famiglia 2.")
             
    except Exception as e:
        print(f"Errore durante il test: {e}")

if __name__ == "__main__":
    test_card_key_format()
