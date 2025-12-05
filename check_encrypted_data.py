from db.gestione_db import get_db_connection

def is_likely_encrypted(text):
    if not text: return False
    # Fernet tokens are url-safe base64 strings, usually starting with gAAAA
    return text.startswith('gAAAA')

def check_data():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            print("Checking Prestiti...")
            cur.execute("SELECT nome, descrizione FROM Prestiti")
            for row in cur.fetchall():
                if is_likely_encrypted(row['nome']) or is_likely_encrypted(row['descrizione']):
                    print(f"Found encrypted Prestito: {row}")
            
            print("Checking Immobili...")
            cur.execute("SELECT nome, via, citta FROM Immobili")
            for row in cur.fetchall():
                if is_likely_encrypted(row['nome']) or is_likely_encrypted(row['via']):
                    print(f"Found encrypted Immobile: {row}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_data()
