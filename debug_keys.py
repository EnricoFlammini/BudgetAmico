from db.supabase_manager import get_db_connection
import sys
import os

# Add parent dir to path
sys.path.append(os.getcwd())

def check_family_keys():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT u.username, af.id_famiglia, length(af.chiave_famiglia_criptata) as key_len FROM Appartenenza_Famiglia af JOIN Utenti u ON af.id_utente = u.id_utente")
            rows = cur.fetchall()
            print(f"Found {len(rows)} family memberships:")
            for row in rows:
                print(f"User: {row['username']}, Family: {row['id_famiglia']}, Key Len: {row['key_len']}")
                
            cur.execute("SELECT id_asset, ticker, nome_asset FROM Asset LIMIT 5")
            assets = cur.fetchall()
            print("\nSample Assets:")
            for a in assets:
                print(f"Asset {a['id_asset']}: Ticker={a['ticker'][:15]}..., Name={a['nome_asset'][:15]}...")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_family_keys()
