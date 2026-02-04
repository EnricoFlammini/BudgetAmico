
import os
from dotenv import load_dotenv

load_dotenv()

import base64
from db.gestione_db import get_db_connection, decrypt_system_data
from utils.crypto_manager import CryptoManager

def audit_all_families_keys():
    crypto = CryptoManager()
    
    # Helper per decriptare il backup della master key (gestisce la doppia codifica)
    def decrypt_mk_backup(bk_enc):
        if not bk_enc: return None
        try:
            # 1. Prova decrittazione diretta
            res = decrypt_system_data(bk_enc)
            if res: return res
            
            # 2. Se fallisce, prova decodifica base64 extra (Double Encoding Fix)
            try:
                decoded = base64.urlsafe_b64decode(bk_enc)
                return decrypt_system_data(decoded.decode())
            except:
                pass
        except:
            pass
        return None

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            cur.execute("SELECT id_famiglia, nome_famiglia, server_encrypted_key FROM Famiglie ORDER BY id_famiglia")
            families = cur.fetchall()
            
            overall_inconsistencies = []
            
            for fam in families:
                id_fam = fam['id_famiglia']
                server_fk_b64 = decrypt_system_data(fam['server_encrypted_key'])
                fam_name = decrypt_system_data(fam['nome_famiglia']) or f"Famiglia_{id_fam}"
                
                print(f"\n>>> ANALISI {fam_name} (ID: {id_fam}) [Server Key: {'SI' if server_fk_b64 else 'NO'}]")
                
                cur.execute("""
                    SELECT AF.id_utente, AF.chiave_famiglia_criptata, U.encrypted_master_key_backup, U.username_enc
                    FROM Appartenenza_Famiglia AF
                    JOIN Utenti U ON AF.id_utente = U.id_utente
                    WHERE AF.id_famiglia = %s
                """, (id_fam,))
                members = cur.fetchall()
                
                if not members:
                    print("    (Nessun membro trovato)")
                    continue

                family_keys_found = {}
                
                for m in members:
                    uid = m['id_utente']
                    username = decrypt_system_data(m['username_enc']) or f"User_{uid}"
                    
                    mk_b64 = decrypt_mk_backup(m['encrypted_master_key_backup'])
                    if not mk_b64:
                        print(f"  [!] Utente {uid} ({username}): Impossibile recuperare Master Key (Backup Assente).")
                        continue
                        
                    if not m['chiave_famiglia_criptata']:
                        print(f"  [X] Utente {uid} ({username}): Chiave di famiglia MANCANTE.")
                        overall_inconsistencies.append((id_fam, uid, "Mancante"))
                        continue
                        
                    try:
                        mk_bytes = base64.urlsafe_b64decode(mk_b64)
                        user_fk_b64 = crypto.decrypt_data(m['chiave_famiglia_criptata'], mk_bytes)
                        family_keys_found[uid] = user_fk_b64
                        
                        if server_fk_b64:
                            if user_fk_b64 == server_fk_b64:
                                print(f"  [OK] Utente {uid} ({username}): Chiave COERENTE.")
                            else:
                                print(f"  [!!!] Utente {uid} ({username}): Chiave INCOERENTE con il server.")
                                overall_inconsistencies.append((id_fam, uid, "Incoerente (Server)"))
                        else:
                            print(f"  [?] Utente {uid} ({username}): Chiave presente ({user_fk_b64[:10]}...).")
                    except Exception as e:
                        print(f"  [ERR] Utente {uid} ({username}): Errore decrittazione con Master Key.")
                        overall_inconsistencies.append((id_fam, uid, "Errore Decriptazione"))

                if not server_fk_b64 and len(family_keys_found) > 1:
                    first_key = list(family_keys_found.values())[0]
                    all_match = all(k == first_key for k in family_keys_found.values())
                    if not all_match:
                        print(f"  [WARN] Incoerenza interna tra i membri!")
                        overall_inconsistencies.append((id_fam, "Global", "Incoerenza Interna"))

            if overall_inconsistencies:
                print(f"\n--- RIEPILOGO PROBLEMI TROVATI ({len(overall_inconsistencies)}) ---")
                for prob in overall_inconsistencies:
                    print(f"  Famiglia {prob[0]}, Utente {prob[1]}: {prob[2]}")
            else:
                print("\n--- TUTTO OK. Nessuna incoerenza rilevata nelle altre famiglie. ---")

    except Exception as e:
        print(f"Errore durante l'audit: {e}")

if __name__ == "__main__":
    audit_all_families_keys()
