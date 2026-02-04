import pg8000.dbapi
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

def get_conn(url):
    result = urlparse(url)
    conn = pg8000.dbapi.connect(
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port or 5432,
        database=result.path[1:],
        ssl_context=True
    )
    return conn

def get_db_schema(name, url):
    print(f"Recupero schema per {name}...")
    try:
        conn = get_conn(url)
        cur = conn.cursor()
        
        # 1. Versione DB
        cur.execute("SELECT valore FROM InfoDB WHERE chiave = 'versione'")
        res = cur.fetchone()
        version = res[0] if res else "0"
        
        # 2. Schema completo (tabelle e colonne)
        schema = {}
        cur.execute("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        for row in cur.fetchall():
            table = row[0]
            col = row[1]
            dtype = row[2]
            if table not in schema:
                schema[table] = []
            schema[table].append(f"{col} ({dtype})")
            
        conn.close()
        return {
            'version': version,
            'schema': schema
        }
    except Exception as e:
        print(f"Errore su {name}: {e}")
        return None

def main():
    load_dotenv()
    test_url = os.getenv('SUPABASE_DB_URL')
    prod_url = "postgresql://postgres.zvuesichckiryhkbztgr:hwjcjhdkvmflnlfmhlfbdbg@aws-1-eu-west-3.pooler.supabase.com:5432/postgres"
    
    test_data = get_db_schema("TEST", test_url)
    prod_data = get_db_schema("PRODUZIONE", prod_url)
    
    if test_data and prod_data:
        print("\n=== CONFRONTO SCHEMI ===")
        print(f"Versione DB: Test={test_data['version']}, Produzione={prod_data['version']}")
        
        test_tables = set(test_data['schema'].keys())
        prod_tables = set(prod_data['schema'].keys())
        
        # Tabelle mancanti
        mancanti_in_prod = test_tables - prod_tables
        mancanti_in_test = prod_tables - test_tables
        
        if mancanti_in_prod: print(f"[!] Tabelle in Test ma NON in Prod: {mancanti_in_prod}")
        if mancanti_in_test: print(f"[!] Tabelle in Prod ma NON in Test: {mancanti_in_test}")
        
        # Confronto colonne per tabelle comuni
        comuni = test_tables & prod_tables
        differenze_colonne = False
        
        for table in sorted(comuni):
            t_cols = test_data['schema'][table]
            p_cols = prod_data['schema'][table]
            
            if t_cols != p_cols:
                differenze_colonne = True
                print(f"\n[DIFF] Differenza nella tabella '{table}':")
                
                solo_test = set(t_cols) - set(p_cols)
                solo_prod = set(p_cols) - set(t_cols)
                
                if solo_test: print(f"  - Solo in Test: {solo_test}")
                if solo_prod: print(f"  - Solo in Prod: {solo_prod}")
        
        if not differenze_colonne and not mancanti_in_prod and not mancanti_in_test:
            print("[OK] Gli schemi sono strutturalmente identici.")
        else:
            print("\n[!] ATTENZIONE: Sono state rilevate differenze strutturali.")

if __name__ == "__main__":
    main()
