import os
import json
import datetime
import sys
from urllib.parse import urlparse

# Aggiungi la cartella Sviluppo al path per importare i moduli del progetto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from db.supabase_manager import get_db_connection
    from utils.logger import setup_logger
except ImportError:
    print("[ERRORE] Impossibile caricare i moduli del progetto. Assicurati di eseguire lo script dalla cartella Sviluppo/db.")
    sys.exit(1)

logger = setup_logger("BackupService")

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

def backup_database(destination_path):
    """
    Esegue un backup integrale di tutte le tabelle nel database Supabase.
    Salva il risultato in un file JSON nella cartella specificata.
    """
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_budgetamico_full_{now}.json"
    full_path = os.path.join(destination_path, filename)
    
    print(f"[*] Inizio backup database...")
    print(f"[*] Destinazione: {full_path}")
    
    backup_data = {
        "metadata": {
            "timestamp": datetime.datetime.now().isoformat(),
            "source": "BudgetAmico Full Backup Script"
        },
        "tables": {}
    }
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Recupera l'elenco di tutte le tabelle nel database
            print("[*] Recupero elenco tabelle...")
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            tables = [row['table_name'] for row in cur.fetchall()]
            
            print(f"[+] Trovate {len(tables)} tabelle: {', '.join(tables)}")
            
            # 2. Esporta i dati per ogni tabella
            for table in tables:
                print(f"[*] Esportazione tabella: {table}...", end=" ", flush=True)
                cur.execute(f'SELECT * FROM "{table}";')
                rows = cur.fetchall()
                
                # Convertiamo eventuali oggetti datetime o Decimal in stringhe per JSON
                serializable_rows = []
                for row in rows:
                    processed_row = {}
                    for key, value in row.items():
                        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
                            processed_row[key] = value.isoformat()
                        elif hasattr(value, '__str__') and 'Decimal' in str(type(value)):
                            processed_row[key] = float(value)
                        elif isinstance(value, bytes):
                            processed_row[key] = value.hex() # O base64 se preferito
                        else:
                            processed_row[key] = value
                    serializable_rows.append(processed_row)
                
                backup_data["tables"][table] = serializable_rows
                print(f"fatto ({len(rows)} righe)")
        
        # 3. Scrittura su file
        print(f"[*] Scrittura file di backup...")
        os.makedirs(destination_path, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=4, ensure_ascii=False)
            
        print(f"\n[OK] Backup completato con successo!")
        print(f"[OK] File salvato in: {full_path}")
        return full_path
        
    except Exception as e:
        print(f"\n[ERRORE!] Errore durante il backup: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # La cartella di destinazione richiesta dall'utente
    DEST_DIR = r"G:\Il mio Drive\PROGETTI\BudgetAmico\File"
    
    # 1. Carica variabili d'ambiente se mancano
    if not os.getenv('SUPABASE_DB_URL') and not os.getenv('DATABASE_URL'):
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if load_env_file(env_file):
             print(f"[INFO] Variabili d'ambiente caricate da {env_file}")
        else:
            print("[AVVISO] Impossibile trovare o caricare il file .env")
        
    backup_path = backup_database(DEST_DIR)
    if backup_path:
        sys.exit(0)
    else:
        sys.exit(1)
