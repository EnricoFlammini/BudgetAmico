import getpass
import sys
import os

# Aggiungi la root del progetto al path per importare i moduli
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.gestione_db import get_db_connection, login_utente, _get_crypto_and_key, _encrypt_if_key, _decrypt_if_key

def migrate_accounts(username, password):
    print(f"Tentativo di login per {username}...")
    user_data = login_utente(username, password)
    
    if not user_data:
        print("Login fallito. Verifica le credenziali.")
        return

    master_key_b64 = user_data.get('master_key')
    if not master_key_b64:
        print("Nessuna master key trovata per l'utente. La crittografia non è abilitata o l'utente è legacy.")
        return

    print("Login effettuato. Master key recuperata.")
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    id_utente = user_data['id']

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # --- Migrazione Conti Personali ---
            print("Migrazione Conti Personali...")
            cur.execute("SELECT id_conto, nome_conto, iban FROM Conti WHERE id_utente = %s", (id_utente,))
            conti = cur.fetchall()
            
            count = 0
            for conto in conti:
                id_conto = conto['id_conto']
                nome_originale = conto['nome_conto']
                iban_originale = conto['iban']
                
                # Verifica se già criptato (euristica semplice: inizia con gAAAA)
                if nome_originale and nome_originale.startswith("gAAAA"):
                    print(f"Conto {id_conto} sembra già criptato. Salto.")
                    continue
                
                encrypted_nome = _encrypt_if_key(nome_originale, master_key, crypto)
                encrypted_iban = _encrypt_if_key(iban_originale, master_key, crypto) if iban_originale else None
                
                cur.execute("UPDATE Conti SET nome_conto = %s, iban = %s WHERE id_conto = %s", 
                            (encrypted_nome, encrypted_iban, id_conto))
                count += 1
            
            print(f"Criptati {count} conti personali.")
            
            con.commit()
            print("Migrazione completata con successo.")

    except Exception as e:
        print(f"Errore durante la migrazione: {e}")
        if con: con.rollback()

if __name__ == "__main__":
    if len(sys.argv) == 3:
        u = sys.argv[1]
        p = sys.argv[2]
    else:
        u = input("Username: ")
        p = getpass.getpass("Password: ")
    
    migrate_accounts(u, p)
