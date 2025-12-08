
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from db import gestione_db
    print("[OK] Importazione di gestione_db riuscita con successo.")
    
    version = gestione_db.ottieni_versione_db()
    print(f"[OK] Versione DB: {version}")
    
except ImportError as e:
    print(f"[ERRORE] Errore di importazione: {e}")
except Exception as e:
    print(f"[ERRORE] Errore generico: {e}")
