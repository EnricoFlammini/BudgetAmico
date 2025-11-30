import os
import sys
from dotenv import load_dotenv
import psycopg2

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

SUPABASE_DB_URL = os.getenv('SUPABASE_DB_URL')

def migrate_budget_tables():
    if not SUPABASE_DB_URL:
        print("Error: SUPABASE_DB_URL not found.")
        return

    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
        
        print("Migrating Budget table...")
        # Alter importo_limite to TEXT
        cur.execute("ALTER TABLE Budget ALTER COLUMN importo_limite TYPE TEXT USING importo_limite::text;")
        
        print("Migrating Budget_Storico table...")
        # Alter importo_limite and importo_speso to TEXT
        cur.execute("ALTER TABLE Budget_Storico ALTER COLUMN importo_limite TYPE TEXT USING importo_limite::text;")
        cur.execute("ALTER TABLE Budget_Storico ALTER COLUMN importo_speso TYPE TEXT USING importo_speso::text;")
        
        conn.commit()
        print("Migration completed successfully.")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_budget_tables()
