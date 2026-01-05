import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db.supabase_manager as db
from db.gestione_db import get_db_connection

def check_raw_values():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_asset, ticker, quantita, prezzo_attuale_manuale, costo_iniziale_unitario FROM Asset LIMIT 5")
            rows = cur.fetchall()
            print("--- ASSETS DEBUG ---")
            for row in rows:
                print(f"ID: {row['id_asset']}, Ticker: {row['ticker']}, Qty: {row['quantita']} ({type(row['quantita'])}), Price: {row['prezzo_attuale_manuale']} ({type(row['prezzo_attuale_manuale'])})")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_raw_values()
