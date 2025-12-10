
import os
import sys

# Add parent directory to path to find db module
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.supabase_manager import get_db_connection

def check_policies():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT tablename, policyname, cmd, qual, with_check FROM pg_policies")
            policies = cur.fetchall()
            if not policies:
                print("No policies found.")
            for p in policies:
                print(f"Table: {p['tablename']}, Policy: {p['policyname']}, Cmd: {p['cmd']}")
                print(f"  USING: {p['qual']}")
                print(f"  CHECK: {p['with_check']}")
                print("-" * 20)

    except Exception as e:
        print(f"Error checking policies: {e}")

if __name__ == "__main__":
    check_policies()
