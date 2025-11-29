from db.gestione_db import get_db_connection, _get_crypto_and_key, _decrypt_if_key
import os

# Mock session or get key manually? 
# I'll try to fetch the user and their key first.
# Assuming single user or I can find the user by username/email if needed.
# But I don't have the user's password to decrypt the master key if it's encrypted.
# Wait, I can't decrypt the master key without the user's password!
# But the app is running, so the master key is in the session.
# I am an agent, I don't have access to the running app's memory directly.
# However, I can check if the data is encrypted or plain text.

# If the user just registered/logged in, the key is in memory.
# But I am running a separate script.
# I cannot decrypt the data without the master key.

# BUT, I can check if the ticker is "WVCE.DE" in PLAIN TEXT.
# If it was encrypted, it would look like random bytes/string.
# If I see "WVCE.DE" in the DB, it means it's NOT encrypted.
# If I see garbage, it's encrypted.

# If it's encrypted, I can't know what it is without the key.
# But I can check the `Asset` table.

def inspect_assets():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_asset, ticker, nome_asset, id_conto FROM Asset")
            assets = cur.fetchall()
            
            print(f"Found {len(assets)} assets.")
            for asset in assets:
                print(f"ID: {asset['id_asset']}, Ticker: {asset['ticker']}, Name: {asset['nome_asset']}, Conto: {asset['id_conto']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_assets()
