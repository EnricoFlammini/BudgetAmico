import base64
from db.gestione_db import get_db_connection, _get_crypto_and_key, _decrypt_if_key

def debug_shared_encryption():
    print("--- Debug Shared Encryption ---")
    
    # 1. Get User
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT id_utente, username FROM Utenti LIMIT 1")
        user = cur.fetchone()
        
    if not user:
        print("No user found.")
        return

    id_utente = user['id_utente']
    username = user['username']
    # We assume the session has the master key, but here we can't access session.
    # However, for the user "Enrico", we might be able to get it if we knew the password, but we don't.
    # Wait, the previous debug script showed "Master Key present: False (Session only)".
    # So we can't easily decrypt with Master Key in this script unless we mock it or if the user provides it.
    # BUT, we can check if the data in DB looks encrypted.
    
    print(f"User: {username} (ID: {id_utente})")

    # 2. Get Shared Accounts
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT cc.id_conto_condiviso, cc.nome_conto, cc.id_famiglia
            FROM ContiCondivisi cc
            JOIN PartecipazioneContoCondiviso pcc ON cc.id_conto_condiviso = pcc.id_conto_condiviso
            WHERE pcc.id_utente = %s
        """, (id_utente,))
        shared_accounts = cur.fetchall()
        
    print(f"\nFound {len(shared_accounts)} shared accounts for user.")
    
    for acc in shared_accounts:
        print(f"ID: {acc['id_conto_condiviso']}, Name (Raw): {acc['nome_conto']}, Family ID: {acc['id_famiglia']}")
        
        # Check if it looks like a Fernet token (starts with gAAAAA)
        if acc['nome_conto'].startswith('gAAAAA'):
            print("  -> Name is ENCRYPTED")
        else:
            print("  -> Name is PLAIN TEXT")

    # 3. Check Family Key
    if shared_accounts:
        id_famiglia = shared_accounts[0]['id_famiglia']
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND id_utente = %s", (id_famiglia, id_utente))
            row = cur.fetchone()
            if row and row['chiave_famiglia_criptata']:
                print(f"  -> Family Key Encrypted found for Family {id_famiglia}")
            else:
                print(f"  -> NO Family Key found for Family {id_famiglia}")

if __name__ == "__main__":
    debug_shared_encryption()
