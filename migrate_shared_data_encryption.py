import sys
import os
import getpass
import base64
from db.supabase_manager import SupabaseManager
from db.gestione_db import get_db_connection, verifica_login, _get_family_key_for_user, _decrypt_if_key, _encrypt_if_key
from utils.crypto_manager import CryptoManager

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_shared_data(username, password):
    print(f"\nMigrating data for user: {username}")
    
    # 1. Login to get Master Key
    user_data = verifica_login(username, password)
    if not user_data:
        print("Login failed.")
        return

    id_utente = user_data['id']
    master_key_b64 = user_data['master_key']
    
    if not master_key_b64:
        print("No master key found for user.")
        return

    crypto = CryptoManager()
    master_key = base64.b64decode(master_key_b64)
    
    print("Master Key retrieved successfully.")

    # 2. Get Family Keys
    family_keys = {}
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia, chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s", (id_utente,))
            rows = cur.fetchall()
            for row in rows:
                if row['chiave_famiglia_criptata']:
                    try:
                        fk_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_keys[row['id_famiglia']] = base64.b64decode(fk_b64)
                        print(f"Family Key retrieved for family ID: {row['id_famiglia']}")
                    except Exception as e:
                        print(f"Failed to decrypt family key for family {row['id_famiglia']}: {e}")
    except Exception as e:
        print(f"Error fetching family keys: {e}")
        return

    if not family_keys:
        print("No family keys found. Skipping.")
        return

    with get_db_connection() as con:
        cur = con.cursor()
        
        # 3. Migrate TransazioniCondivise (only those authored by this user)
        print("\nMigrating TransazioniCondivise...")
        cur.execute("""
            SELECT TC.id_transazione_condivisa, TC.descrizione, CC.id_famiglia
            FROM TransazioniCondivise TC
            JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
            WHERE TC.id_utente_autore = %s
        """, (id_utente,))
        
        transazioni = cur.fetchall()
        count_trans = 0
        for t in transazioni:
            id_trans = t['id_transazione_condivisa']
            desc_enc = t['descrizione']
            id_fam = t['id_famiglia']
            
            if id_fam not in family_keys:
                continue
                
            family_key = family_keys[id_fam]
            
            # Try to decrypt with Master Key (old way)
            try:
                decrypted = crypto.decrypt_data(desc_enc, master_key)
                # If successful, re-encrypt with Family Key
                new_enc = crypto.encrypt_data(decrypted, family_key)
                
                cur.execute("UPDATE TransazioniCondivise SET descrizione = %s WHERE id_transazione_condivisa = %s", (new_enc, id_trans))
                count_trans += 1
            except Exception:
                # Might be already encrypted with Family Key or unencrypted
                pass
        print(f"Migrated {count_trans} shared transactions.")

        # 4. Migrate Budget (try to decrypt with Master Key)
        print("\nMigrating Budget...")
        cur.execute("SELECT id_budget, id_famiglia, importo_limite FROM Budget")
        budgets = cur.fetchall()
        count_budget = 0
        for b in budgets:
            id_budget = b['id_budget']
            id_fam = b['id_famiglia']
            limit_enc = b['importo_limite']
            
            if id_fam not in family_keys:
                continue
            
            family_key = family_keys[id_fam]
            
            # Try to decrypt with Master Key
            try:
                decrypted = crypto.decrypt_data(limit_enc, master_key)
                # If successful, re-encrypt with Family Key
                new_enc = crypto.encrypt_data(decrypted, family_key)
                
                cur.execute("UPDATE Budget SET importo_limite = %s WHERE id_budget = %s", (new_enc, id_budget))
                count_budget += 1
            except Exception:
                pass
        print(f"Migrated {count_budget} budget entries.")

        # 5. Migrate Budget_Storico
        print("\nMigrating Budget_Storico...")
        cur.execute("SELECT id_famiglia, id_sottocategoria, anno, mese, importo_limite, importo_speso FROM Budget_Storico")
        budgets_storico = cur.fetchall()
        count_storico = 0
        for b in budgets_storico:
            id_fam = b['id_famiglia']
            id_sub = b['id_sottocategoria']
            anno = b['anno']
            mese = b['mese']
            limit_enc = b['importo_limite']
            speso_enc = b['importo_speso']
            
            if id_fam not in family_keys:
                continue
            
            family_key = family_keys[id_fam]
            
            updated = False
            new_limit = limit_enc
            new_speso = speso_enc
            
            # Try decrypt limit
            try:
                dec = crypto.decrypt_data(limit_enc, master_key)
                new_limit = crypto.encrypt_data(dec, family_key)
                updated = True
            except:
                pass
                
            # Try decrypt speso
            try:
                dec = crypto.decrypt_data(speso_enc, master_key)
                new_speso = crypto.encrypt_data(dec, family_key)
                updated = True
            except:
                pass
            
            if updated:
                cur.execute("""
                    UPDATE Budget_Storico 
                    SET importo_limite = %s, importo_speso = %s 
                    WHERE id_famiglia = %s AND id_sottocategoria = %s AND anno = %s AND mese = %s
                """, (new_limit, new_speso, id_fam, id_sub, anno, mese))
                count_storico += 1
                
        print(f"Migrated {count_storico} historical budget entries.")
        
        con.commit()
        print("\nMigration completed successfully.")

if __name__ == "__main__":
    if len(sys.argv) == 3:
        username = sys.argv[1]
        password = sys.argv[2]
    else:
        print("Migration Script for Shared Data Encryption")
        username = input("Username: ")
        password = getpass.getpass("Password: ")
    migrate_shared_data(username, password)
