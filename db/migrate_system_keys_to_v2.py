import os
import sys

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
from db.crypto_helpers import decrypt_system_data, encrypt_system_data

def migrate_famiglie_keys():
    print("[*] Inizio migrazione server_encrypted_key in Famiglie...")
    migrati = 0
    falliti = 0
    gia_migrati = 0
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia, server_encrypted_key FROM Famiglie WHERE server_encrypted_key IS NOT NULL AND server_encrypted_key != ''")
            rows = cur.fetchall()
            
            print(f"[*] Trovate {len(rows)} chiavi da processare.")
            
            for row in rows:
                fid = row['id_famiglia']
                enc_key = row['server_encrypted_key']
                
                # Se è già v2, salta
                if enc_key.startswith("v2:"):
                    gia_migrati += 1
                    continue
                
                # Decrypt (fallback legacy as defined in crypto_helpers)
                dec = decrypt_system_data(enc_key)
                if dec:
                    # Re-encrypt (uses v2 as default)
                    new_enc = encrypt_system_data(dec)
                    
                    cur.execute("UPDATE Famiglie SET server_encrypted_key = %s WHERE id_famiglia = %s", (new_enc, fid))
                    migrati += 1
                    print(f"[OK] Famiglia {fid} migrata a V2.")
                else:
                    print(f"[ERRORE] Impossibile decriptare chiave per famiglia {fid}.")
                    falliti += 1
            
            con.commit()
            print(f"\n[FINE] Migrazione completata.")
            print(f" - Migrati a V2: {migrati}")
            print(f" - Già V2: {gia_migrati}")
            print(f" - Falliti: {falliti}")
    except Exception as e:
        print(f"[FATALE] Errore migrazione: {e}")

if __name__ == "__main__":
    # Load .env manually if needed
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
                        
    if not os.getenv("SERVER_SECRET_KEY"):
        print("[ERRORE] SERVER_SECRET_KEY non trovata in .env. Impossibile procedere.")
        sys.exit(1)
        
    migrate_famiglie_keys()
