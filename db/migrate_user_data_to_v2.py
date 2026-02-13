import os
import sys
import base64

# Add path to Sviluppo
sviluppo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(sviluppo_path)

# Load .env manually BEFORE importing project modules
env_file = os.path.join(sviluppo_path, ".env")
if os.path.exists(env_file):
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

from db.supabase_manager import get_db_connection
from db.crypto_helpers import decrypt_system_data, _decrypt_if_key, _encrypt_if_key
from utils.crypto_manager import CryptoManager

def migrate_family_data():
    print("[*] Inizio migrazione di massa dati Famiglie a AES-256-GCM (V2)...")
    cm = CryptoManager()
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Recupera tutte le famiglie con automazione abilitata
            cur.execute("SELECT id_famiglia, nome_famiglia, server_encrypted_key FROM Famiglie WHERE server_encrypted_key IS NOT NULL AND server_encrypted_key != ''")
            famiglie = cur.fetchall()
            
            print(f"[*] Trovate {len(famiglie)} famiglie con automazione abilitata.")
            
            for f in famiglie:
                fid = f['id_famiglia']
                # Decrypt family key using system key
                fk_b64 = decrypt_system_data(f['server_encrypted_key'])
                if not fk_b64:
                    print(f"[!] Errore: Impossibile decriptare Family Key per Famiglia {fid}. Salto.")
                    continue
                
                f_key = base64.b64decode(fk_b64)
                print(f"[*] Processando Famiglia {fid}...")

                # A. Migrazione Nome Famiglia
                if f['nome_famiglia'] and not f['nome_famiglia'].startswith("v2:"):
                    dec_nome = cm.decrypt_data(f['nome_famiglia'], f_key, silent=True)
                    if dec_nome != "[ENCRYPTED]":
                        new_enc = cm.encrypt_data(dec_nome, f_key)
                        cur.execute("UPDATE Famiglie SET nome_famiglia = %s WHERE id_famiglia = %s", (new_enc, fid))
                        print(f"   [OK] Nome Famiglia {fid} migrato.")

                # B. Migrazione Conti della Famiglia
                # Cerchiamo conti personali di utenti in questa famiglia E conti condivisi della famiglia
                cur.execute("""
                    SELECT id_conto, nome_conto, tipo, config_speciale 
                    FROM Conti 
                    WHERE id_utente IN (SELECT id_utente FROM Appartenenza_Famiglia WHERE id_famiglia = %s)
                """, (fid,))
                conti = cur.fetchall()
                for c in conti:
                    cid = c['id_conto']
                    # Migrazione nome_conto
                    if c['nome_conto'] and c['nome_conto'].startswith("gAAAAA"):
                        dec = cm.decrypt_data(c['nome_conto'], f_key, silent=True)
                        if dec != "[ENCRYPTED]":
                            cur.execute("UPDATE Conti SET nome_conto = %s WHERE id_conto = %s", (cm.encrypt_data(dec, f_key), cid))
                    # Migrazione tipo
                    if c['tipo'] and c['tipo'].startswith("gAAAAA"):
                        dec = cm.decrypt_data(c['tipo'], f_key, silent=True)
                        if dec != "[ENCRYPTED]":
                            cur.execute("UPDATE Conti SET tipo = %s WHERE id_conto = %s", (cm.encrypt_data(dec, f_key), cid))
                    # Migrazione config_speciale
                    if c['config_speciale'] and c['config_speciale'].startswith("gAAAAA"):
                        dec = cm.decrypt_data(c['config_speciale'], f_key, silent=True)
                        if dec != "[ENCRYPTED]":
                            cur.execute("UPDATE Conti SET config_speciale = %s WHERE id_conto = %s", (cm.encrypt_data(dec, f_key), cid))
                print(f"   [OK] {len(conti)} conti processati.")

                # C. Migrazione Salvadanai
                cur.execute("SELECT id_salvadanaio, nome FROM Salvadanai WHERE id_famiglia = %s", (fid,))
                pbs = cur.fetchall()
                for pb in pbs:
                    if pb['nome'] and pb['nome'].startswith("gAAAAA"):
                        dec = cm.decrypt_data(pb['nome'], f_key, silent=True)
                        if dec != "[ENCRYPTED]":
                            cur.execute("UPDATE Salvadanai SET nome = %s WHERE id_salvadanaio = %s", (cm.encrypt_data(dec, f_key), pb['id_salvadanaio']))
                print(f"   [OK] {len(pbs)} salvadanai processati.")

                # D. Migrazione Transazioni (Grande volume)
                # Solo transazioni collegate ai conti della famiglia
                cur.execute("""
                    UPDATE Transazioni SET descrizione = %s 
                    WHERE id_transazione = %s
                """, (None, None)) # Placeholder to prepare cursor
                
                cur.execute("""
                    SELECT id_transazione, descrizione 
                    FROM Transazioni 
                    WHERE id_conto IN (
                        SELECT id_conto FROM Conti 
                        WHERE id_utente IN (SELECT id_utente FROM Appartenenza_Famiglia WHERE id_famiglia = %s)
                    ) AND descrizione LIKE 'gAAAAA%'
                """, (fid,))
                txs = cur.fetchall()
                count_tx = 0
                for tx in txs:
                    dec = cm.decrypt_data(tx['descrizione'], f_key, silent=True)
                    if dec != "[ENCRYPTED]":
                        cur.execute("UPDATE Transazioni SET descrizione = %s WHERE id_transazione = %s", (cm.encrypt_data(dec, f_key), tx['id_transazione']))
                        count_tx += 1
                print(f"   [OK] {count_tx} transazioni migrate.")

            con.commit()
            print("\n[FINE] Migrazione di massa completata con successo!")
            
    except Exception as e:
        print(f"[FATALE] Errore durante la migrazione: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_family_data()
