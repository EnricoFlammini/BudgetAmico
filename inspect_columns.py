
from db.supabase_manager import get_db_connection
from db.backup_db import load_env_file
import json

load_env_file('.env')
with get_db_connection() as con:
    cur = con.cursor()
    tables = ['Categorie', 'Sottocategorie', 'Obiettivi_Risparmio', 'Salvadanai', 'Conti', 'Asset']
    results = {}
    for table in tables:
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table.lower()}'")
        results[table] = cur.fetchall()
    print(json.dumps(results, indent=2))
