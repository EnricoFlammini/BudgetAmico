
import os
from dotenv import load_dotenv
from db.gestione_db import get_db_connection

load_dotenv()

def check_prod_family_2():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            print("--- STATO FAMIGLIA 2 ---")
            cur.execute("SELECT * FROM Famiglie WHERE id_famiglia = 2")
            fam = cur.fetchone()
            if fam:
                print(f"Famiglia ID: 2, Nome (Enc?): {fam['nome_famiglia']}")
                print(f"Server Automation Enabled: {fam['server_encrypted_key'] is not None}")
            else:
                print("Famiglia 2 non trovata.")

            print("\n--- MEMBRI FAMIGLIA 2 ---")
            cur.execute("""
                SELECT AF.id_utente, AF.ruolo, AF.chiave_famiglia_criptata IS NOT NULL as has_key,
                       U.username_enc, U.sospeso
                FROM Appartenenza_Famiglia AF
                JOIN Utenti U ON AF.id_utente = U.id_utente
                WHERE AF.id_famiglia = 2
            """)
            members = cur.fetchall()
            for m in members:
                print(f"Utente ID: {m['id_utente']}, Ruolo: {m['ruolo']}, Ha Chiave: {m['has_key']}, Sospeso: {m['sospeso']}")

            print("\n--- CONTI E TRANSAZIONI UTENTE 11 ---")
            cur.execute("SELECT id_conto, nome_conto, tipo FROM Conti WHERE id_utente = 11")
            conti_11 = cur.fetchall()
            if not conti_11:
                print("L'utente 11 non ha conti.")
            for c in conti_11:
                cur.execute("SELECT COUNT(*) as count FROM Transazioni WHERE id_conto = %s", (c['id_conto'],))
                t_count = cur.fetchone()['count']
                print(f"  Conto ID: {c['id_conto']}, Nome (Enc?): {c['nome_conto']}, Tipo: {c['tipo']}, Transazioni: {t_count}")
                
                if t_count > 0:
                    cur.execute("SELECT descrizione FROM Transazioni WHERE id_conto = %s LIMIT 1", (c['id_conto'],))
                    sample = cur.fetchone()['descrizione']
                    is_enc = isinstance(sample, str) and sample.startswith("gAAAAA")
                    print(f"    Esempio descr: {sample[:20]}... Criptato: {is_enc}")

            print("\n--- BUDGET FAMIGLIA 2 ---")
            cur.execute("SELECT COUNT(*) as count FROM Budget WHERE id_famiglia = 2")
            b_count = cur.fetchone()['count']
            print(f"Righe Budget: {b_count}")
            if b_count > 0:
                cur.execute("SELECT importo_limite FROM Budget WHERE id_famiglia = 2 LIMIT 1")
                sample_b = cur.fetchone()['importo_limite']
                is_enc_b = isinstance(sample_b, str) and sample_b.startswith("gAAAAA")
                print(f"  Esempio budget limit: {sample_b[:20]}... Criptato: {is_enc_b}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    check_prod_family_2()
