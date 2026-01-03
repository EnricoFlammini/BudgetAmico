from db.gestione_db import get_db_connection, _get_crypto_and_key, _decrypt_if_key, ottieni_prima_famiglia_utente
from utils.crypto_manager import CryptoManager
import base64

def debug():
    print("Inizio Debug...")
    with get_db_connection() as con:
        cur = con.cursor()
        
        # 1. Trova utente (assume 1 utente o specifico)
        cur.execute("SELECT id_utente, nome, encrypted_master_key, salt FROM Utenti LIMIT 1")
        user = cur.fetchone()
        if not user:
            print("Nessun utente trovato.")
            return

        print(f"Utente trovato: {user['id_utente']}")
        
        # 2. Recupera Master Key (Simulata - non abbiamo la password qui per decryptare la MK dal DB!)
        # Abbiamo bisogno della password per derivare la KEK e decriptare la MK.
        # Oppure usiamo la MK dalla sessione se stessimo nell'app, ma qui siamo in script.
        # PROBLEMA: Non posso decriptare la Master Key senza la password dell'utente.
        
        # SOLUZIONE: Posso ispezionare il valore RAW nel DB per vedere se inizia con gAAAAA.
        # E posso verificare se con la MK (che non ho) funzionerebbe... no.
        
        # Alternative:
        # Stampo solo il valore RAW.
        
        cur.execute("SELECT id_carta FROM Carte WHERE nome_carta LIKE '%Trade Republic%'")
        carta = cur.fetchone()
        if not carta:
             print("Carta Trade Republic non trovata via query. Cerco tutte le carte.")
             cur.execute("SELECT id_carta, nome_carta FROM Carte")
             carte = cur.fetchall()
             for c in carte:
                 print(f"Carta: {c['nome_carta']} ID: {c['id_carta']}")
             if not carte: return
             id_carta = carte[0]['id_carta']
        else:
             id_carta = carta['id_carta']
             print(f"Carta trovata: ID {id_carta}")

        cur.execute("SELECT id_transazione, data, descrizione FROM Transazioni WHERE id_carta = %s ORDER BY data DESC LIMIT 5", (id_carta,))
        transazioni = cur.fetchall()
        
        print(f"Ultime 5 transazioni carta {id_carta}:")
        for t in transazioni:
            raw_desc = t['descrizione']
            print(f"ID: {t['id_transazione']} Data: {t['data']}")
            print(f"RAW Descrizione: {raw_desc}")
            if raw_desc and raw_desc.startswith("gAAAAA"):
                 print("  -> Sembra un token Fernet valido.")
            else:
                 print("  -> NON sembra un token Fernet (o è plain text).")

if __name__ == "__main__":
    debug()
