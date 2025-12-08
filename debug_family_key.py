"""
Script di debug per verificare la family key di un utente.
"""
from db.gestione_db import get_db_connection

def check_user_family_key():
    id_utente = int(input("ID Utente da verificare: "))
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # Get user info
        cur.execute("SELECT id_utente, username, salt, encrypted_master_key FROM Utenti WHERE id_utente = %s", (id_utente,))
        user = cur.fetchone()
        if not user:
            print(f"Utente {id_utente} non trovato")
            return
        
        print(f"\n=== Utente: {user['username']} (ID: {user['id_utente']}) ===")
        print(f"Salt presente: {bool(user['salt'])}")
        print(f"Encrypted Master Key presente: {bool(user['encrypted_master_key'])}")
        
        # Get family membership
        cur.execute("""
            SELECT af.id_famiglia, af.ruolo, af.chiave_famiglia_criptata, f.nome_famiglia
            FROM Appartenenza_Famiglia af
            JOIN Famiglie f ON af.id_famiglia = f.id_famiglia
            WHERE af.id_utente = %s
        """, (id_utente,))
        memberships = cur.fetchall()
        
        if not memberships:
            print("Utente non appartiene a nessuna famiglia!")
            return
            
        for m in memberships:
            print(f"\n--- Famiglia: {m['nome_famiglia']} (ID: {m['id_famiglia']}) ---")
            print(f"Ruolo: {m['ruolo']}")
            fk = m['chiave_famiglia_criptata']
            if fk:
                print(f"Chiave famiglia criptata: {fk[:50]}...")
            else:
                print("⚠️ CHIAVE FAMIGLIA MANCANTE!")
        
        # Get admin's family key for comparison
        print("\n=== Confronto con Admin ===")
        cur.execute("""
            SELECT u.id_utente, u.username, af.chiave_famiglia_criptata
            FROM Appartenenza_Famiglia af
            JOIN Utenti u ON af.id_utente = u.id_utente
            WHERE af.id_famiglia = %s AND af.ruolo = 'admin'
        """, (memberships[0]['id_famiglia'],))
        admins = cur.fetchall()
        
        for admin in admins:
            print(f"Admin: {admin['username']} (ID: {admin['id_utente']})")
            afk = admin['chiave_famiglia_criptata']
            if afk:
                print(f"  Chiave famiglia criptata: {afk[:50]}...")
            else:
                print("  ⚠️ ADMIN SENZA CHIAVE!")

if __name__ == "__main__":
    check_user_family_key()
