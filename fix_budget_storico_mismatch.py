import datetime
from db.gestione_db import get_db_connection, ottieni_prima_famiglia_utente

def fix_budget_storico():
    print("--- Fix Budget Storico Mismatch ---")
    
    # 1. Get User and Family
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT id_utente, username FROM Utenti LIMIT 1")
        user = cur.fetchone()
        
    if not user:
        print("No user found.")
        return

    id_utente = user['id_utente']
    print(f"User: {user['username']}")

    id_famiglia = ottieni_prima_famiglia_utente(id_utente)
    if not id_famiglia:
        print("No family found.")
        return
    print(f"Family ID: {id_famiglia}")

    # 2. Delete Budget_Storico for current month
    anno = 2025
    mese = 11
    print(f"\nDeleting Budget_Storico for {anno}-{mese}...")
    
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("""
            DELETE FROM Budget_Storico 
            WHERE id_famiglia = %s AND anno = %s AND mese = %s
        """, (id_famiglia, anno, mese))
        deleted_count = cur.rowcount
        print(f"Deleted {deleted_count} rows.")
        
    print("\nFix completed. Budget page should now fall back to Budget table.")

if __name__ == "__main__":
    fix_budget_storico()
