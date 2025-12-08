"""
Script di migrazione per ri-criptare i dati del budget 
dalla master_key dell'admin alla family_key.

Questo script è necessario perché i dati salvati prima del fix
erano criptati con la master_key dell'admin invece della family_key.
"""
import getpass
import base64
from db.gestione_db import get_db_connection
from utils.crypto_manager import CryptoManager

def migrate_budget_encryption():
    print("=== Migrazione Budget: da Master Key a Family Key ===\n")
    
    id_famiglia = int(input("ID Famiglia: "))
    password_admin = getpass.getpass("Password Admin (utente che ha creato i budget): ")
    id_admin = int(input("ID Admin (utente che ha creato i budget): "))
    
    crypto = CryptoManager()
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # Get admin master key
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
        
        # Get admin's family key
        cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_admin, id_famiglia))
        fk_enc = cur.fetchone()
        if not fk_enc or not fk_enc['chiave_famiglia_criptata']:
            print(f"[ERRORE] Family key non trovata per admin {id_admin} nella famiglia {id_famiglia}")
            return
            
        fk_b64 = crypto.decrypt_data(fk_enc['chiave_famiglia_criptata'], admin_master_key)
        family_key = base64.b64decode(fk_b64)
        print(f"[OK] Family key recuperata")
        
        # Get all budget entries for this family
        cur.execute("""
            SELECT id_budget, id_sottocategoria, importo_limite 
            FROM Budget 
            WHERE id_famiglia = %s
        """, (id_famiglia,))
        budget_entries = cur.fetchall()
        
        print(f"\n[INFO] Trovati {len(budget_entries)} budget da migrare")
        
        migrated = 0
        skipped = 0
        
        for entry in budget_entries:
            old_value = entry['importo_limite']
            
            # Skip if not encrypted
            if not isinstance(old_value, str) or not old_value.startswith('gAAAAA'):
                print(f"  Budget {entry['id_budget']}: non criptato, salto")
                skipped += 1
                continue
            
            # Try to decrypt with admin master key
            try:
                decrypted_value = crypto.decrypt_data(old_value, admin_master_key)
                if decrypted_value == "[ENCRYPTED]":
                    # Try with family key (already migrated?)
                    decrypted_value = crypto.decrypt_data(old_value, family_key)
                    if decrypted_value != "[ENCRYPTED]":
                        print(f"  Budget {entry['id_budget']}: già criptato con family_key, salto")
                        skipped += 1
                        continue
                    else:
                        print(f"  Budget {entry['id_budget']}: impossibile decriptare, salto")
                        skipped += 1
                        continue
                
                # Re-encrypt with family key
                new_encrypted = crypto.encrypt_data(decrypted_value, family_key)
                
                cur.execute("""
                    UPDATE Budget SET importo_limite = %s WHERE id_budget = %s
                """, (new_encrypted, entry['id_budget']))
                
                print(f"  Budget {entry['id_budget']}: migrato ({decrypted_value})")
                migrated += 1
                
            except Exception as e:
                print(f"  Budget {entry['id_budget']}: errore - {e}")
                skipped += 1
        
        con.commit()
        print(f"\n=== Migrazione completata ===")
        print(f"Migrati: {migrated}")
        print(f"Saltati: {skipped}")

if __name__ == "__main__":
    migrate_budget_encryption()
