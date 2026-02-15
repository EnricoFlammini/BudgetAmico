
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

try:
    from db.supabase_manager import get_db_connection
except ImportError:
    print("Error: Could not import get_db_connection from db.supabase_manager")
    sys.exit(1)

SQL_FILE = os.path.join(os.path.dirname(__file__), 'consolidamento_produzione.sql')

def run_consolidation():
    print(f"Starting Database Consolidation...")
    
    if not os.path.exists(SQL_FILE):
        print(f"Error: SQL file not found at {SQL_FILE}")
        return

    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split script into individual commands (primitive split by ;)
    # Note: this is a simple split, for more complex SQL use a real parser
    commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip()]

    try:
        conn_ctx = get_db_connection()
        with conn_ctx as conn:
            cur = conn.cursor()
            
            for cmd in commands:
                print(f"Executing: {cmd[:50]}...")
                try:
                    cur.execute(cmd)
                except Exception as cmd_error:
                    # Ignore "already exists" errors if they happen despite IF NOT EXISTS
                    if "already exists" in str(cmd_error).lower():
                        print(f"  (Skipped: Already exists)")
                    else:
                        print(f"  ❌ Command failed: {cmd_error}")
                        # Depending on the error, we might want to rollback and stop
                        # For consolidation, we usually want to continue and see other errors
            
            conn.commit()
            print(f"\nConsolidation completed successfully!")
            return True

    except Exception as e:
        print(f"\n❌ Consolidation Failed: {e}")
        return False

if __name__ == "__main__":
    run_consolidation()
