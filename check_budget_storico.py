import sqlite3
import os
import sys

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.gestione_db import DB_FILE

def check_storico():
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        return

    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM Budget_Storico")
            count = cur.fetchone()[0]
            print(f"Total rows in Budget_Storico: {count}")

            if count > 0:
                cur.execute("SELECT * FROM Budget_Storico LIMIT 5")
                rows = cur.fetchall()
                print("\nSample rows:")
                for row in rows:
                    print(row)
            else:
                print("\nBudget_Storico is empty.")
                
            # Check Budget table
            cur.execute("SELECT COUNT(*) FROM Budget")
            budget_count = cur.fetchone()[0]
            print(f"\nTotal rows in Budget (current limits): {budget_count}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_storico()
