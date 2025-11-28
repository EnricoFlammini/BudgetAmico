import psycopg2
from db.supabase_manager import get_db_connection
import traceback

def list_tables():
    try:
        print("Connessione al DB...")
        with get_db_connection() as conn:
            print("Connesso. Esecuzione query...")
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = cur.fetchall()
            print(f"Trovate {len(tables)} tabelle.")
            for table in tables:
                print(f"- {table['table_name']}")
                
            # Prova query diretta su utenti
            try:
                print("\nTest query su 'utenti' (lowercase):")
                cur.execute("SELECT count(*) FROM utenti")
                print(f"Count utenti: {cur.fetchone()[0]}")
            except Exception as e:
                print(f"Errore query utenti lowercase: {e}")
                conn.rollback()
                
            try:
                print("\nTest query su 'Utenti' (TitleCase con quote):")
                cur.execute('SELECT count(*) FROM "Utenti"')
                print(f"Count Utenti: {cur.fetchone()[0]}")
            except Exception as e:
                print(f"Errore query Utenti quoted: {e}")
                
    except Exception as e:
        print(f"Errore generale: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    list_tables()
