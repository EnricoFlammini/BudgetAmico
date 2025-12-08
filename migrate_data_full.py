"""
Script di migrazione per ri-criptare TransazioniCondivise e BudgetMensili
dalla master_key dell'admin alla family_key.

Questo completa la migrazione precedente (che copriva solo la tabella Budget).
"""
import getpass
import base64
from db.gestione_db import get_db_connection
from utils.crypto_manager import CryptoManager

def migrate_family_data_encryption():
    print("=== Migrazione Dati Famiglia (Transazioni/Storico): da Master Key a Family Key ===\n")
    
    id_famiglia = int(input("ID Famiglia: "))
    password_admin = getpass.getpass("Password Admin (autore dei dati): ")
    id_admin = int(input("ID Admin (autore dei dati): "))
    
    crypto = CryptoManager()
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # 1. Recupera chiavi Admin
        cur.execute("SELECT salt, encrypted_master_key FROM Utenti WHERE id_utente = %s", (id_admin,))
        admin = cur.fetchone()
        if not admin:
            print(f"[ERRORE] Utente {id_admin} non trovato")
            return
            
        salt = base64.urlsafe_b64decode(admin['salt'].encode())
        kek = crypto.derive_key(password_admin, salt)
        enc_mk = base64.urlsafe_b64decode(admin['encrypted_master_key'].encode())
        admin_master_key = crypto.decrypt_master_key(enc_mk, kek)
        print(f"[OK] Master key admin recuperata")
        
        # 2. Recupera Family Key Admin
        cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_admin, id_famiglia))
        fk_enc = cur.fetchone()
        if not fk_enc or not fk_enc['chiave_famiglia_criptata']:
            print(f"[ERRORE] Family key non trovata per admin {id_admin} nella famiglia {id_famiglia}")
            return
            
        fk_b64 = crypto.decrypt_data(fk_enc['chiave_famiglia_criptata'], admin_master_key)
        family_key = base64.b64decode(fk_b64)
        print(f"[OK] Family key recuperata")
        
        # --- MIGRAZIONE TransazioniCondivise ---
        print(f"\n--- Migrazione TransazioniCondivise ---")
        cur.execute("""
            SELECT tc.id_transazione_condivisa, tc.descrizione
            FROM TransazioniCondivise tc
            JOIN ContiCondivisi cc ON tc.id_conto_condiviso = cc.id_conto_condiviso
            WHERE cc.id_famiglia = %s
        """, (id_famiglia,))
        transazioni = cur.fetchall()
        
        migrated_tc = 0
        skipped_tc = 0
        
        for t in transazioni:
            old_desc = t['descrizione']
            
            if not isinstance(old_desc, str) or not old_desc.startswith('gAAAAA'):
                skipped_tc += 1
                continue
                
            try:
                # Prova Decrypt con Master Key Admin
                decrypted = crypto.decrypt_data(old_desc, admin_master_key, silent=True)
                
                if decrypted == "[ENCRYPTED]":
                    # Prova Family Key (già corretto?)
                    check = crypto.decrypt_data(old_desc, family_key, silent=True)
                    if check != "[ENCRYPTED]":
                        # Già ok
                        skipped_tc += 1
                        continue
                    else:
                        print(f"  Transazione {t['id_transazione_condivisa']}: impossibile decriptare")
                        skipped_tc += 1
                        continue
                
                # Re-encrypt con Family Key
                new_enc = crypto.encrypt_data(decrypted, family_key)
                cur.execute("UPDATE TransazioniCondivise SET descrizione = %s WHERE id_transazione_condivisa = %s", 
                           (new_enc, t['id_transazione_condivisa']))
                migrated_tc += 1
                
            except Exception as e:
                print(f"  Errore Transazione {t['id_transazione_condivisa']}: {e}")
                skipped_tc += 1
        
        print(f"Transazioni migrate: {migrated_tc}, Saltate: {skipped_tc}")

        # --- MIGRAZIONE Budget_Storico (Storico) ---
        print(f"\n--- Migrazione Budget_Storico (Storico) ---")
        # In Budget_Storico abbiamo: nome_sottocategoria, importo_limite, importo_speso
        cur.execute("SELECT id_storico, nome_sottocategoria, importo_limite, importo_speso FROM Budget_Storico WHERE id_famiglia = %s", (id_famiglia,))
        storico = cur.fetchall()
        
        migrated_bm = 0
        skipped_bm = 0
        
        cols_to_fix = ['nome_sottocategoria', 'importo_limite', 'importo_speso']
        
        for row in storico:
            updates = {}
            needs_update = False
            
            for col in cols_to_fix:
                val = row[col]
                if isinstance(val, str) and val.startswith('gAAAAA'):
                    dec = crypto.decrypt_data(val, admin_master_key, silent=True)
                    if dec != "[ENCRYPTED]":
                        # Verifica se è già family key (tentativo)
                        check_fk = crypto.decrypt_data(val, family_key, silent=True)
                        if check_fk == "[ENCRYPTED]":
                            # Era con master key, converti
                            updates[col] = crypto.encrypt_data(dec, family_key)
                            needs_update = True
            
            if needs_update:
                set_clauses = ", ".join([f"{k} = %s" for k in updates.keys()])
                values = list(updates.values())
                values.append(row['id_storico'])
                cur.execute(f"UPDATE Budget_Storico SET {set_clauses} WHERE id_storico = %s", values)
                migrated_bm += 1
            else:
                skipped_bm += 1
                
        print(f"Storico Budget migrati: {migrated_bm}, Saltati: {skipped_bm}")
        
        con.commit()
        print(f"\n=== Migrazione Totale Completata ===")

if __name__ == "__main__":
    migrate_family_data_encryption()
