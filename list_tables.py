import psycopg2
from db.supabase_manager import get_db_connection

def list_tables():
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = cur.fetchall()
            print("Tabelle trovate:")
            for table in tables:
                print(f"- {table[0]}")
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    list_tables()
