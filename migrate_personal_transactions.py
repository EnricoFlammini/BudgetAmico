"""
Script di migrazione per convertire le Transazioni Personali 
dalla Master Key alla Family Key.

Questo renderà le transazioni personali visibili a tutti i membri della famiglia 
che possiedono la family key (come richiesto).
"""
import getpass
import base64
from db.gestione_db import get_db_connection
from utils.crypto_manager import CryptoManager

def migrate_personal_transactions():
    print("=== Migrazione Transazioni Personali -> Family Key ===\n")
    print("ATTENZIONE: Questa operazione renderà le transazioni personali dell'utente")
    print("visibili a TUTTI i membri della famiglia specificata.\n")
    
    id_famiglia = int(input("ID Famiglia: "))
    password_admin = getpass.getpass("Password Utente (proprietario dati): ")
    id_utente = int(input("ID Utente (proprietario dati): "))
    
    crypto = CryptoManager()
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # 1. Recupera chiavi Utente
        cur.execute("SELECT salt, encrypted_master_key FROM Utenti WHERE id_utente = %s", (id_utente,))
        user_row = cur.fetchone()
        if not user_row:
            print(f"[ERRORE] Utente {id_utente} non trovato")
            return
            
        salt = base64.urlsafe_b64decode(user_row['salt'].encode())
        kek = crypto.derive_key(password_admin, salt)
        enc_mk = base64.urlsafe_b64decode(user_row['encrypted_master_key'].encode())
        master_key = crypto.decrypt_master_key(enc_mk, kek)
        print(f"[OK] Master key recuperata")
        
        # 2. Recupera Family Key
        cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
        fk_enc = cur.fetchone()
        if not fk_enc or not fk_enc['chiave_famiglia_criptata']:
            print(f"[ERRORE] Family key non trovata per utente {id_utente} nella famiglia {id_famiglia}")
            return
            
        fk_b64 = crypto.decrypt_data(fk_enc['chiave_famiglia_criptata'], master_key)
        family_key = base64.b64decode(fk_b64)
        print(f"[OK] Family key recuperata")
        
        # 3. Recupera Transazioni Personali
        cur.execute("""
            SELECT T.id_transazione, T.descrizione
            FROM Transazioni T
            JOIN Conti C ON T.id_conto = C.id_conto
            WHERE C.id_utente = %s
        """, (id_utente,))
        transazioni = cur.fetchall()
        
        print(f"\n[INFO] Trovate {len(transazioni)} transazioni personali")
        
        migrated = 0
        skipped = 0
        errors = 0
        
        for t in transazioni:
            old_desc = t['descrizione']
            
            if not isinstance(old_desc, str) or not old_desc.startswith('gAAAAA'):
                skipped += 1
                continue
                
            try:
                # 1. Prova a decriptare con Master Key (vecchio standard)
                decrypted = crypto.decrypt_data(old_desc, master_key, silent=True)
                
                if decrypted == "[ENCRYPTED]":
                    # 2. Prova con Family Key (magari già migrato?)
                    check = crypto.decrypt_data(old_desc, family_key, silent=True)
                    if check != "[ENCRYPTED]":
                        # Già migrato
                        skipped += 1
                        continue
                    else:
                        print(f"  Transazione {t['id_transazione']}: IMPOSSIBILE DECRIPTARE")
                        errors += 1
                        continue
                
                # 3. Re-encrypt con Family Key
                new_enc = crypto.encrypt_data(decrypted, family_key)
                
                cur.execute("UPDATE Transazioni SET descrizione = %s WHERE id_transazione = %s", 
                           (new_enc, t['id_transazione']))
                migrated += 1
                
                if migrated % 100 == 0:
                    print(f"  ...migrated {migrated}...")
                    
            except Exception as e:
                print(f"  Errore Transazione {t['id_transazione']}: {e}")
                errors += 1
                
        con.commit()
        print(f"\n=== Migrazione Completata ===")
        print(f"Migrate: {migrated}")
        print(f"Saltate (già ok/non criptate): {skipped}")
        print(f"Errori: {errors}")

if __name__ == "__main__":
    migrate_personal_transactions()
