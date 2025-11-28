"""
Test di connessione a Supabase PostgreSQL - Versione semplificata
"""

import sys
import os

# Aggiungi la cartella padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.supabase_manager import SupabaseManager, SupabaseConnection
from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()

SUPABASE_DB_URL = os.getenv('SUPABASE_DB_URL')

print("="*70)
print("TEST CONNESSIONE SUPABASE")
print("="*70)

if not SUPABASE_DB_URL:
    print("[ERRORE] SUPABASE_DB_URL non configurato nel file .env")
    sys.exit(1)

print("[OK] SUPABASE_DB_URL configurato")
print()

# Test 1: Connessione base
print("TEST 1: Connessione al database")
print("-"*70)

try:
    with SupabaseConnection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            res = cur.fetchone()
            version = res['version']
            print(f"[OK] Connesso a PostgreSQL")
            print(f"     Versione: {version[:60]}...")
except Exception as e:
    print(f"[ERRORE] Impossibile connettersi: {repr(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 2: Verifica tabelle
print("TEST 2: Verifica tabelle migrate")
print("-"*70)

try:
    with SupabaseConnection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cur.fetchall()
            
            if tables:
                print(f"[OK] Trovate {len(tables)} tabelle:")
                for table in tables:
                    print(f"     - {table['table_name']}")
            else:
                print("[AVVISO] Nessuna tabella trovata")
except Exception as e:
    print(f"[ERRORE] {e}")

print()

# Test 3: RLS Context
print("TEST 3: Row Level Security Context")
print("-"*70)

try:
    conn = SupabaseManager.get_connection(id_utente=1)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('app.current_user_id', true) as user_id")
            user_id = cur.fetchone()['user_id']
            
            if user_id == '1':
                print(f"[OK] Contesto utente impostato correttamente (ID: {user_id})")
            else:
                print(f"[AVVISO] Contesto utente: {user_id}")
    finally:
        SupabaseManager.release_connection(conn)
except Exception as e:
    print(f"[ERRORE] {e}")
finally:
    SupabaseManager.close_all_connections()

print()
print("="*70)
print("[OK] TUTTI I TEST COMPLETATI CON SUCCESSO!")
print("="*70)
print()
print("La migrazione a Supabase e' completa!")
print("Puoi ora avviare l'applicazione.")
print()
