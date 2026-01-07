import os
import sys
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.supabase_manager import SupabaseManager
from utils.crypto_manager import CryptoManager
from cryptography.fernet import Fernet
import base64

# Simple decryption helper
def decrypt(val, key):
    if not val: return None
    try:
        f = Fernet(key)
        # Handle 0 bytes special case if necessary, but standard Fernet handles it
        return f.decrypt(val.encode()).decode()
    except Exception as e:
        return f"[Error: {e}]"

from db.gestione_db import get_db_connection

def check_orphans():
    query = """
    SELECT s.id_salvadanaio, s.nome, s.importo_assegnato, s.id_conto, s.id_conto_condiviso
    FROM Salvadanai s
    WHERE s.id_obiettivo IS NULL
    """
    
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        
    print(f"Found {len(rows)} Unlinked (Orphan) Piggy Banks.")
    
    for r in rows:
        print(f"PB ID: {r['id_salvadanaio']}, Account: {r['id_conto'] or r['id_conto_condiviso']}, Name Len: {len(r['nome'])}, Amount Len: {len(r['importo_assegnato'])}")

if __name__ == "__main__":
    try:
        check_orphans()
    except Exception as e:
        print(f"Error: {e}")
