import getpass
import sys
import os
import base64

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.gestione_db import get_db_connection, verifica_login, _get_crypto_and_key, _encrypt_if_key, _decrypt_if_key

def migrate_categories(username, password):
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
            
            # --- Migrazione Categorie ---
            print("\nMigrazione Categorie...")
            cur.execute("SELECT id_categoria, nome_categoria FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
            categorie = cur.fetchall()
            
            count_cat = 0
            for cat in categorie:
                id_cat = cat['id_categoria']
                nome_originale = cat['nome_categoria']
                
                if nome_originale and nome_originale.startswith("gAAAA"):
                    print(f"Categoria {id_cat} sembra già criptata. Salto.")
                    continue
                
                encrypted_nome = _encrypt_if_key(nome_originale, family_key, crypto)
                cur.execute("UPDATE Categorie SET nome_categoria = %s WHERE id_categoria = %s", 
                            (encrypted_nome, id_cat))
                count_cat += 1
            print(f"Criptate {count_cat} categorie.")

            # --- Migrazione Sottocategorie ---
            print("\nMigrazione Sottocategorie...")
            # Join with Categorie to filter by family
            cur.execute("""
                SELECT s.id_sottocategoria, s.nome_sottocategoria 
                FROM Sottocategorie s
                JOIN Categorie c ON s.id_categoria = c.id_categoria
                WHERE c.id_famiglia = %s
            """, (id_famiglia,))
            sottocategorie = cur.fetchall()
            
            count_sub = 0
            for sub in sottocategorie:
                id_sub = sub['id_sottocategoria']
                nome_originale = sub['nome_sottocategoria']
                
                if nome_originale and nome_originale.startswith("gAAAA"):
                    print(f"Sottocategoria {id_sub} sembra già criptata. Salto.")
                    continue
                
                encrypted_nome = _encrypt_if_key(nome_originale, family_key, crypto)
                cur.execute("UPDATE Sottocategorie SET nome_sottocategoria = %s WHERE id_sottocategoria = %s", 
                            (encrypted_nome, id_sub))
                count_sub += 1
            print(f"Criptate {count_sub} sottocategorie.")
            
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
    
    migrate_categories(u, p)
