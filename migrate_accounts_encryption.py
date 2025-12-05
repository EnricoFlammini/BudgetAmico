import getpass
import sys
import os
import base64

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.gestione_db import get_db_connection, verifica_login, _get_crypto_and_key, _encrypt_if_key

def migrate_accounts(username, password):
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

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Alter Table Schema (Idempotent)
            print("Verifica schema tabella Conti...")
            columns_to_alter = ['valore_manuale', 'rettifica_saldo']
            for col in columns_to_alter:
                try:
                    # Check current type
                    cur.execute(f"""
                        SELECT data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'conti' AND column_name = '{col}'
                    """)
                    res = cur.fetchone()
                    if res and res['data_type'] != 'text':
                        print(f"Conversione colonna {col} a TEXT...")
                        cur.execute(f"ALTER TABLE Conti ALTER COLUMN {col} TYPE TEXT USING {col}::text")
                        con.commit()
                except Exception as e:
                    print(f"Errore alterazione colonna {col}: {e}")
                    con.rollback()

            # 2. Encrypt Data
            print("\nMigrazione Conti...")
            cur.execute("SELECT id_conto, nome_conto, tipo, iban, valore_manuale, rettifica_saldo FROM Conti WHERE id_utente = %s", (id_utente,))
            conti = cur.fetchall()
            
            count = 0
            for conto in conti:
                id_conto = conto['id_conto']
                
                # Encrypt fields
                updates = {}
                
                # Nome Conto
                if conto['nome_conto'] and not conto['nome_conto'].startswith("gAAAA"):
                    updates['nome_conto'] = _encrypt_if_key(conto['nome_conto'], master_key, crypto)
                
                # Tipo
                if conto['tipo'] and not conto['tipo'].startswith("gAAAA"):
                    updates['tipo'] = _encrypt_if_key(conto['tipo'], master_key, crypto)
                
                # IBAN
                if conto['iban'] and not conto['iban'].startswith("gAAAA"):
                    updates['iban'] = _encrypt_if_key(conto['iban'], master_key, crypto)
                
                # Valore Manuale
                if conto['valore_manuale'] and not str(conto['valore_manuale']).startswith("gAAAA"):
                    updates['valore_manuale'] = _encrypt_if_key(str(conto['valore_manuale']), master_key, crypto)
                
                # Rettifica Saldo
                if conto['rettifica_saldo'] and not str(conto['rettifica_saldo']).startswith("gAAAA"):
                    updates['rettifica_saldo'] = _encrypt_if_key(str(conto['rettifica_saldo']), master_key, crypto)
                
                if updates:
                    set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
                    values = list(updates.values())
                    values.append(id_conto)
                    
                    cur.execute(f"UPDATE Conti SET {set_clause} WHERE id_conto = %s", values)
                    count += 1
            
            print(f"Criptati {count} conti.")
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
    
    migrate_accounts(u, p)
