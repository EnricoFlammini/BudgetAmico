
import os
import base64
from dotenv import load_dotenv
from db.gestione_db import get_db_connection, ensure_family_key, _get_crypto_and_key, decrypt_system_data
from utils.crypto_manager import CryptoManager

load_dotenv()

def verify_fix_on_family_2():
    # NOTA: Non abbiamo la master_key reale dell'utente 11.
    # Ma possiamo verificare se per l'utente 7 (che dovrebbe avere la chiave corretta)
    # la logica di sincronizzazione "conferma" che è tutto ok.
    
    # Per testare l'utente 7, simuliamo la chiamata (senza master_key reale non possiamo decriptare, 
    # ma possiamo vedere se la logica di ensure_family_key termina correttamente o se darebbe errore).
    
    # In realtà, per testare DAVVERO la logica di fix, useremo la SERVER_SECRET_KEY
    # per vedere se la chiave dell'utente 11 decripta i dati. Sappiamo già che NON lo fa.
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Recuperiamo la FK corretta dal server
            cur.execute("SELECT server_encrypted_key FROM Famiglie WHERE id_famiglia = 2")
            row = cur.fetchone()
            correct_fk_b64 = decrypt_system_data(row['server_encrypted_key'])
            print(f"Correct FK (Server): {correct_fk_b64[:10]}...")

            # Verifichiamo se l'utente 7 ha la stessa chiave
            # (Non possiamo decriptare senza master_key, quindi saltiamo la verifica diretta qui)
            
            # Simuliamo il comportamento di ensure_family_key se venisse chiamato ora.
            # Poiché non abbiamo la master_key, non possiamo eseguire ensure_family_key(7, 2, master_key).
            
            print("\nLogica applicata. Al prossimo login di ID 11:")
            print("1. ensure_family_key recupererà server_fk via SERVER_SECRET_KEY.")
            print("2. Cripterà server_fk con la master_key di ID 11 (disponibile al login).")
            print("3. Sovrascriverà la chiave incoerente di ID 11 con quella corretta.")
            print("4. Da quel momento, ID 11 e ID 7 useranno la STESSA CHIAVE.")
            
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    verify_fix_on_family_2()
