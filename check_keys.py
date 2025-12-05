from db.gestione_db import get_db_connection

def check_keys():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente, id_famiglia, chiave_famiglia_criptata FROM Appartenenza_Famiglia")
            rows = cur.fetchall()
            print(f"Found {len(rows)} rows in Appartenenza_Famiglia:")
            for row in rows:
                has_key = bool(row['chiave_famiglia_criptata'])
                key_len = len(row['chiave_famiglia_criptata']) if has_key else 0
                print(f"User: {row['id_utente']}, Family: {row['id_famiglia']}, Has Key: {has_key}, Key Len: {key_len}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_keys()
