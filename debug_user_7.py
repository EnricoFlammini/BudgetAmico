
import os
from dotenv import load_dotenv
from db.gestione_db import get_db_connection, _get_family_key_for_user
from utils.crypto_manager import CryptoManager

load_dotenv()

def check_user_family_status(id_utente):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT U.id_utente, U.username_enc, AF.id_famiglia, AF.ruolo, AF.chiave_famiglia_criptata
                FROM Utenti U
                LEFT JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                WHERE U.id_utente = %s
            """, (id_utente,))
            rows = cur.fetchall()
            if not rows:
                print(f"Utente {id_utente} non trovato.")
                return
            
            for row in rows:
                print(f"Utente ID: {row['id_utente']}")
                print(f"ID Famiglia: {row['id_famiglia']}")
                print(f"Ruolo: {row['ruolo']}")
                print(f"Chiave Famiglia Presente: {row['chiave_famiglia_criptata'] is not None}")
                if row['id_famiglia']:
                    # Check other members of the same family
                    cur.execute("""
                        SELECT id_utente, ruolo, chiave_famiglia_criptata IS NOT NULL as has_key
                        FROM Appartenenza_Famiglia
                        WHERE id_famiglia = %s
                    """, (row['id_famiglia'],))
                    members = cur.fetchall()
                    print("\nMembri della stessa famiglia:")
                    for m in members:
                        print(f"  - ID Utente: {m['id_utente']}, Ruolo: {m['ruolo']}, Ha Chiave: {m['has_key']}")
                        
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    check_user_family_status(7)
