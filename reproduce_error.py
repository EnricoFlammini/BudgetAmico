import psycopg2
from psycopg2 import extras
import os
from dotenv import load_dotenv

# Mocking the behavior to verify the exception string
try:
    # Simulate RealDictCursor behavior
    row = {'count': 5}
    print(f"Row: {row}")
    val = row[0] # This should raise KeyError: 0
except Exception as e:
    print(f"Caught exception: {type(e).__name__}: {e}")
    print(f"String representation: '{e}'")

# Also checking if I can connect and see what the actual key is for COUNT(*)
load_dotenv()
db_url = os.getenv('SUPABASE_DB_URL')
if db_url:
    try:
        conn = psycopg2.connect(db_url, cursor_factory=extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Utenti")
        res = cur.fetchone()
        print(f"Real Query Result: {res}")
        print(f"Keys: {list(res.keys())}")
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")
else:
    print("No DB URL found")
