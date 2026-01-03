from db.gestione_db import get_db_connection
import sys

def check_account_user(account_id):
    print(f"Checking Account {account_id}...", flush=True)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Check Account
            cursor.execute("SELECT * FROM Conti WHERE id_conto = %s", (account_id,))
            account_row = cursor.fetchone()
            if not account_row:
                print(f"Account {account_id} NOT FOUND.", flush=True)
                return
                
            print(f"Account found: {dict(account_row)}", flush=True)
            user_id = account_row['id_utente']
            print(f"Account Owner ID: {user_id}", flush=True)
            
            # 2. Check User
            cursor.execute("SELECT * FROM Utenti WHERE id_utente = %s", (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                print(f"User {user_id} NOT FOUND in Utenti table!", flush=True)
            else:
                user_data = dict(user_row)
                # Hide sensitive
                if 'password_hash' in user_data: del user_data['password_hash']
                print(f"User found: {user_data}", flush=True)

            # 3. Check Join Query manually
            query = """
            SELECT 
                C.id_conto, 
                C.nome_conto, 
                U.username 
            FROM Conti C
            LEFT JOIN Utenti U ON C.id_utente = U.id_utente
            WHERE C.id_conto = %s
            """
            cursor.execute(query, (account_id,))
            join_row = cursor.fetchone()
            print(f"Join Result: {dict(join_row) if join_row else 'None'}", flush=True)

    except Exception as e:
        print(f"Error: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_account_user(6)
    print("-" * 20)
    check_account_user(17)
