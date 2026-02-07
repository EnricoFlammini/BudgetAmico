
import os
from dotenv import load_dotenv
from db.gestione_db import get_db_connection

load_dotenv()

def list_all_families_and_members():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            print("--- TUTTE LE FAMIGLIE ---")
            cur.execute("SELECT id_famiglia, nome_famiglia FROM Famiglie")
            fams = cur.fetchall()
            for f in fams:
                print(f"ID Famiglia: {f['id_famiglia']}, Nome (Enc): {f['nome_famiglia'][:30]}...")
            
            print("\n--- TUTTI GLI UTENTI E LE LORO FAMIGLIE ---")
            cur.execute("""
                SELECT U.id_utente, AF.id_famiglia, AF.ruolo
                FROM Utenti U
                LEFT JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                ORDER BY U.id_utente
            """)
            users = cur.fetchall()
            for u in users:
                print(f"Utente ID: {u['id_utente']}, Famiglia ID: {u['id_famiglia']}, Ruolo: {u['ruolo']}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    list_all_families_and_members()
