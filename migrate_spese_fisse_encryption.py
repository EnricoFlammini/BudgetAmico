import getpass
import sys
import os
import base64

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.gestione_db import get_db_connection, verifica_login, _get_crypto_and_key, _encrypt_if_key, _decrypt_if_key

def migrate_spese_fisse(username, password):
    print(f"Tentativo di login per {username}...")
    user_data = verifica_login(username, password)
    
    if not user_data:
        print("Login fallito. Verifica le credenziali.")
        return

    master_key_b64 = user_data.get('master_key')
    if not master_key_b64:
        print("Nessuna master key trovata per l'utente.")
        return

    print("Login effettuato. Master key recuperata.")
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    id_utente = user_data['id']

    # Get Family Key
    family_key = None
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia, chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s LIMIT 1", (id_utente,))
            fam_row = cur.fetchone()
            if fam_row and fam_row['chiave_famiglia_criptata']:
                family_key_b64 = crypto.decrypt_data(fam_row['chiave_famiglia_criptata'], master_key)
                family_key = base64.b64decode(family_key_b64)
                id_famiglia = fam_row['id_famiglia']
                print(f"Chiave famiglia recuperata per famiglia ID {id_famiglia}.")
            else:
                print("Nessuna famiglia o chiave famiglia trovata.")
                return
    except Exception as e:
        print(f"Errore recupero chiave famiglia: {e}")
        return

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # --- Migrazione Spese Fisse ---
            print("\nMigrazione Spese Fisse...")
            cur.execute("SELECT id_spesa_fissa, nome FROM SpeseFisse WHERE id_famiglia = %s", (id_famiglia,))
            spese = cur.fetchall()
            
            count = 0
            for spesa in spese:
                id_spesa = spesa['id_spesa_fissa']
                nome_originale = spesa['nome']
                
                if nome_originale and nome_originale.startswith("gAAAA"):
                    print(f"Spesa Fissa {id_spesa} sembra già criptata. Salto.")
                    continue
                
                encrypted_nome = _encrypt_if_key(nome_originale, family_key, crypto)
                cur.execute("UPDATE SpeseFisse SET nome = %s WHERE id_spesa_fissa = %s", 
                            (encrypted_nome, id_spesa))
                count += 1
            print(f"Criptate {count} spese fisse.")
            
            con.commit()
            print("\nMigrazione completata con successo.")

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
    
    migrate_spese_fisse(u, p)
