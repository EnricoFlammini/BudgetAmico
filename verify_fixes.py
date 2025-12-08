import sys
import os
import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.gestione_db import (
    ottieni_riepilogo_patrimonio_utente,
    ottieni_riepilogo_patrimonio_famiglia_aggregato,
    ottieni_totali_famiglia,
    get_db_connection
)

def verify():
    print("Verifying fixes...")
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Get a user and family
            cur.execute("SELECT id_utente FROM Utenti LIMIT 1")
            res = cur.fetchone()
            if not res:
                print("No users found.")
                return
            id_utente = res['id_utente']
            
            cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s LIMIT 1", (id_utente,))
            res = cur.fetchone()
            if not res:
                print("No family found for user.")
                return
            id_famiglia = res['id_famiglia']
            
            print(f"Testing with User ID: {id_utente}, Family ID: {id_famiglia}")
            
            anno = datetime.date.today().year
            mese = datetime.date.today().month
            
            print("\n1. Testing ottieni_riepilogo_patrimonio_utente...")
            try:
                res = ottieni_riepilogo_patrimonio_utente(id_utente, anno, mese)
                print(f"Result: {res}")
            except Exception as e:
                print(f"FAILED: {e}")

            print("\n2. Testing ottieni_riepilogo_patrimonio_famiglia_aggregato...")
            try:
                res = ottieni_riepilogo_patrimonio_famiglia_aggregato(id_famiglia, anno, mese)
                print(f"Result: {res}")
            except Exception as e:
                print(f"FAILED: {e}")

            print("\n3. Testing ottieni_totali_famiglia...")
            try:
                res = ottieni_totali_famiglia(id_famiglia)
                print(f"Result: {res}")
            except Exception as e:
                print(f"FAILED: {e}")
                
    except Exception as e:
        print(f"Database connection failed: {e}")

if __name__ == "__main__":
    verify()
