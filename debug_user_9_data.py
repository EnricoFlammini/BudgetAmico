
import os
from dotenv import load_dotenv
from db.gestione_db import get_db_connection

load_dotenv()

def check_user_9_data():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Accounts
            print(f"--- CONTI UTENTE 9 ---")
            cur.execute("SELECT id_conto, nome_conto, tipo FROM Conti WHERE id_utente = 9")
            conti = cur.fetchall()
            if not conti:
                print("L'utente 9 non ha conti personali.")
            for c in conti:
                print(f"  ID: {c['id_conto']}, Nome: {c['nome_conto']}, Tipo: {c['tipo']}")
                
                # 2. Transactions for this account
                cur.execute("SELECT COUNT(*) as count FROM Transazioni WHERE id_conto = %s", (c['id_conto'],))
                count = cur.fetchone()['count']
                print(f"    Transazioni: {count}")

            # 3. Family Key check for both users
            print(f"\n--- CHIAVI FAMIGLIA ---")
            cur.execute("SELECT id_utente, id_famiglia, chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_famiglia = 4")
            keys = cur.fetchall()
            for k in keys:
                print(f"  Utente: {k['id_utente']}, Famiglia: {k['id_famiglia']}, ChiavePresente: {k['chiave_famiglia_criptata'] is not None}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    check_user_9_data()
