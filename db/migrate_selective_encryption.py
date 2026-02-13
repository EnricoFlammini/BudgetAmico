import os
import sys
import base64
import json
import decimal
from typing import List, Dict, Any, Optional

# Aggiungi la root al path per gli import
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.supabase_manager import get_db_connection
from db.crypto_helpers import get_server_family_key, _decrypt_if_key
from utils.crypto_manager import CryptoManager
from utils.logger import setup_logger

logger = setup_logger("MigrationPhase3")

def load_env_file(env_path):
    """Carica manualmente le variabili d'ambiente da un file .env"""
    if not os.path.exists(env_path):
        return False
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
        return True
    except Exception as e:
        print(f"[ERRORE] Caricamento .env fallito: {e}")
        return False

# Mappatura Tabelle e Campi da decriptare
MIGRATION_CONFIG = [
    {
        "table": "Categorie",
        "id_col": "id_categoria",
        "fields": ["nome_categoria"],
        "type": "text"
    },
    {
        "table": "Sottocategorie",
        "id_col": "id_sottocategoria",
        "fields": ["nome_sottocategoria"],
        "type": "text",
        "join_family": "JOIN Categorie C ON Sottocategorie.id_categoria = C.id_categoria",
        "family_id_col": "C.id_famiglia"
    },
    {
        "table": "Obiettivi_Risparmio",
        "id_col": "id",
        "fields": ["importo_obiettivo"],
        "type": "numeric"
    },
    {
        "table": "Salvadanai",
        "id_col": "id_salvadanaio",
        "fields": ["importo_assegnato"],
        "type": "numeric"
    },
    {
        "table": "Conti",
        "id_col": "id_conto",
        "fields": ["valore_manuale", "rettifica_saldo"],
        "type": "real_skip", # Già REAL nel DB
        "join_family": "JOIN Appartenenza_Famiglia AF ON Conti.id_utente = AF.id_utente",
        "family_id_col": "AF.id_famiglia"
    },
    {
        "table": "Asset",
        "id_col": "id_asset",
        "fields": ["ticker", "nome_asset"],
        "type": "text",
        "join_family": "JOIN Conti C ON Asset.id_conto = C.id_conto JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente",
        "family_id_col": "AF.id_famiglia"
    },
    {
        "table": "Storico_Asset",
        "id_col": "id_storico_asset",
        "fields": ["ticker"],
        "type": "text",
        "join_family": "JOIN Conti C ON Storico_Asset.id_conto = C.id_conto JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente",
        "family_id_col": "AF.id_famiglia"
    }
]

def migrate(con=None):
    # 0. Load Env
    if not os.getenv("SERVER_SECRET_KEY"):
        load_env_file(".env")
    
    crypto = CryptoManager()
    
    # Se la connessione è passata, usala. Altrimenti creane una nuova.
    close_conn = False
    if con is None:
        con = get_db_connection()
        close_conn = True

    try:
        cur = con.cursor()
        
        # 1. Recupera tutte le famiglie e le relative chiavi
        print("[*] Recupero chiavi famiglia...")
        cur.execute("SELECT id_famiglia, nome_famiglia FROM Famiglie")
        famiglie = cur.fetchall()
        
        family_keys = {} # id_famiglia -> key_bytes
        for fam in famiglie:
            fid = fam['id_famiglia']
            key_b64 = get_server_family_key(fid)
            if key_b64:
                family_keys[fid] = base64.b64decode(key_b64)
                print(f" [OK] Chiave trovata per famiglia: {fam['nome_famiglia']} (ID: {fid})")
            else:
                print(f" [!] Chiave NON trovata per famiglia: {fam['nome_famiglia']} (ID: {fid}) - Cloud Automation disabilitato?")

        # 2. Elaborazione tabelle
        for config in MIGRATION_CONFIG:
            table = config["table"]
            print(f"\n[*] Elaborazione tabella: {table}")
            
            # Recupera i record
            fam_col = config.get("family_id_col", "id_famiglia")
            if "join_family" in config:
                query = f"SELECT {table}.*, {fam_col} as family_id FROM {table} {config['join_family']}"
            else:
                query = f"SELECT *, id_famiglia as family_id FROM {table}"
            
            try:
                cur.execute(query)
                rows = cur.fetchall()
                print(f" [i] Trovati {len(rows)} record.")
            except Exception as e:
                print(f" [ERRORE] Impossibile leggere {table}: {e}")
                con.rollback() # Reset transaction
                continue

            updated_count = 0
            for row in rows:
                fid = row.get('family_id')
                key = family_keys.get(fid)
                
                if not key:
                    continue
                
                updates = {}
                for field in config["fields"]:
                    val_enc = row.get(field)
                    if not val_enc or not isinstance(val_enc, str) or not val_enc.startswith("gAAAAA"):
                        continue
                    
                    val_dec = _decrypt_if_key(val_enc, key, crypto, silent=True)
                    if val_dec != "[ENCRYPTED]":
                        updates[field] = val_dec
                
                if updates:
                    set_clause = ", ".join([f"{f} = %s" for f in updates.keys()])
                    params = list(updates.values()) + [row[config["id_col"]]]
                    cur.execute(f"UPDATE {table} SET {set_clause} WHERE {config['id_col']} = %s", params)
                    updated_count += 1
            
            print(f" [OK] Aggiornati {updated_count} record in {table}.")
            con.commit()

        # 3. Conversione tipi di colonna (Tentativo)
        print("\n[*] Conversione tipi di colonna...")
        for config in MIGRATION_CONFIG:
            if config["type"] == "numeric":
                table = config["table"]
                for field in config["fields"]:
                    print(f" [i] Conversione {table}.{field} in NUMERIC...", end=" ", flush=True)
                    try:
                        # Assicuriamoci che non ci siano NULL se non ammessi (Salvadanai.importo_assegnato)
                        cur.execute(f"UPDATE {table} SET {field} = '0' WHERE {field} IS NULL")
                        
                        # Conversione sicura (cast a TEXT per regex se fosse già numeric)
                        cur.execute(f"""
                            ALTER TABLE {table} 
                            ALTER COLUMN {field} TYPE NUMERIC 
                            USING CASE 
                                WHEN {field}::TEXT ~ '^-?[0-9.]+$' THEN {field}::numeric 
                                ELSE 0 
                            END
                        """)
                        con.commit()
                        print("Fatto.")
                    except Exception as e:
                        print(f"FALLITO: {e}")
                        con.rollback()

        print("\n[FINISH] Migrazione completata.")
    
    finally:
        if close_conn and con:
            con.close()


if __name__ == "__main__":
    migrate()
