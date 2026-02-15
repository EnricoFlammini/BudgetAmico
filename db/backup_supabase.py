
import os
import sys
import datetime
import json
import decimal

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

try:
    from db.supabase_manager import get_db_connection
except ImportError:
    print("Error: Could not import get_db_connection from db.supabase_manager")
    sys.exit(1)

BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

def json_serializer(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    return str(obj)

def backup_supabase():
    print("Starting Supabase Backup...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(BACKUP_DIR, f"supabase_backup_{timestamp}.json")
    
    full_backup = {}
    
    try:
        conn_ctx = get_db_connection()
        with conn_ctx as conn:
            cur = conn.cursor()
            
            # Get list of tables (public schema)
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_type = 'BASE TABLE'
            """)
            tables = [row['table_name'] for row in cur.fetchall()]
            
            print(f"Found {len(tables)} tables: {', '.join(tables)}")
            
            for table in tables:
                print(f"  Backing up {table}...")
                cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                full_backup[table] = rows
                print(f"    - {len(rows)} records")
            
        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(full_backup, f, default=json_serializer, indent=4)
            
        print(f"\nBackup completed successfully!")
        print(f"File saved to: {filename}")
        return filename

    except Exception as e:
        print(f"\n❌ Backup Failed: {e}")
        return None

if __name__ == "__main__":
    backup_supabase()
