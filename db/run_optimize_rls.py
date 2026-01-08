
import os
import sys

# Ensure project root is in path to import db modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir)) # Adjust as needed based on folder structure
sys.path.append(project_root)

# Try to import get_db_connection
try:
    from Sviluppo.db.supabase_manager import get_db_connection
except ImportError:
    # Fallback if running from Sviluppo/db directly
    sys.path.append(os.path.join(current_dir, '..'))
    from db.supabase_manager import get_db_connection

def run_optimization():
    sql_file_path = os.path.join(current_dir, 'optimize_rls.sql')
    
    print(f"Reading SQL file: {sql_file_path}")
    try:
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    print("Connecting to database...")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                print("Executing SQL script...")
                # Execute the entire script as one block. 
                # psycopg2 usually handles multiple statements in one execute call.
                cur.execute(sql_script)
                conn.commit()
                print("✅ Optimization script executed successfully!")
    except Exception as e:
        print(f"❌ Database execution error: {e}")
        print("Detail: If the error mentions specific syntax, the script might need to be run in the Supabase SQL Editor directly.")

if __name__ == "__main__":
    run_optimization()
