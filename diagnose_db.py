import sqlite3
import os

DB_FILE = "budget_amico.db"

def check_db():
    if not os.path.exists(DB_FILE):
        print(f"❌ Database file {DB_FILE} not found.")
        return

    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            
            # Check Schema Version
            cur.execute("PRAGMA user_version")
            version = cur.fetchone()[0]
            print(f"Database Version: {version}")
            
            # Check Budget_Storico count
            try:
                cur.execute("SELECT COUNT(*) FROM Budget_Storico")
                count = cur.fetchone()[0]
                print(f"Rows in Budget_Storico: {count}")
                
                if count > 0:
                    print("\nSample rows from Budget_Storico:")
                    cur.execute("SELECT * FROM Budget_Storico LIMIT 5")
                    for row in cur.fetchall():
                        print(row)
            except sqlite3.OperationalError as e:
                print(f"❌ Error querying Budget_Storico: {e}")

            # Check Budget count
            cur.execute("SELECT COUNT(*) FROM Budget")
            count_budget = cur.fetchone()[0]
            print(f"\nRows in Budget (Current): {count_budget}")

            # Check Families
            cur.execute("SELECT id_famiglia, nome_famiglia FROM Famiglie")
            families = cur.fetchall()
            print(f"\nFamilies: {families}")

    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    check_db()
