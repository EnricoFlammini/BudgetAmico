
import os
from dotenv import load_dotenv
from db.gestione_db import get_db_connection

load_dotenv()

def find_user_and_family():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            print("--- RICERCA UTENTE 7 ---")
            cur.execute("SELECT * FROM Utenti WHERE id_utente = 7")
            u = cur.fetchone()
            if u:
                print(f"Utente 7 trovato: ID {u['id_utente']}, Username (Enc): {u['username_enc']}")
                
                print("\n--- FAMIGLIE DI UTENTE 7 ---")
                cur.execute("""
                    SELECT AF.id_famiglia, F.nome_famiglia, AF.ruolo
                    FROM Appartenenza_Famiglia AF
                    JOIN Famiglie F ON AF.id_famiglia = F.id_famiglia
                    WHERE AF.id_utente = 7
                """)
                fams = cur.fetchall()
                for f in fams:
                    print(f"  Famiglia ID: {f['id_famiglia']}, Nome: {f['nome_famiglia']}, Ruolo: {f['ruolo']}")
                    
                    print(f"\n    --- MEMBRI DELLA FAMIGLIA {f['id_famiglia']} ---")
                    cur.execute("""
                        SELECT id_utente, ruolo FROM Appartenenza_Famiglia WHERE id_famiglia = %s
                    """, (f['id_famiglia'],))
                    members = cur.fetchall()
                    for m in members:
                        print(f"      ID Utente: {m['id_utente']}, Ruolo: {m['ruolo']}")
            else:
                print("Utente 7 non trovato nel database connesso.")

            print("\n--- TUTTI GLI UTENTI ---")
            cur.execute("SELECT id_utente FROM Utenti")
            all_u = cur.fetchall()
            print(f"ID Utenti presenti: {[u['id_utente'] for u in all_u]}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    find_user_and_family()
