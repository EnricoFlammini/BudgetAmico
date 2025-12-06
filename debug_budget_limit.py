import datetime
from db.gestione_db import (
    get_db_connection, ottieni_riepilogo_budget_mensile,
    ottieni_categorie_e_sottocategorie, _get_crypto_and_key, _decrypt_if_key
)

def debug_limit():
    print("--- Debug Budget Limit ---")
    
    # 1. Get User and Family
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT id_utente, username FROM Utenti LIMIT 1")
        user = cur.fetchone()
        
    if not user:
        print("No user found.")
        return

    id_utente = user['id_utente']
    # master_key is not in DB, it's in session. We can't easily get it here without mocking session.
    # For debugging, we might need to skip decryption or hardcode if we knew it.
    # But wait, the user said "dati vengono criptati".
    # Let's try to proceed without it for now, or check if we can get it from another way.
    # Actually, if we can't decrypt, we can't verify the value.
    # But we can see the raw value. If it's encrypted, it will look like garbage.
    master_key_b64 = None 
    print(f"User: {user['username']}, Master Key present: False (Session only)")
    
    # Get Family
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s", (id_utente,))
        fam = cur.fetchone()
        
    if not fam:
        print("No family found.")
        return
    id_famiglia = fam['id_famiglia']
    print(f"Family ID: {id_famiglia}")

    # 2. Find "ALIMENTI" subcategory
    print("\nSearching for 'ALIMENTI'...")
    target_sub_id = None
    
    cats = ottieni_categorie_e_sottocategorie(id_famiglia)
    for c_id, c_data in cats.items():
        for sub in c_data['sottocategorie']:
            if "ALIMENTI" in sub['nome_sottocategoria'].upper():
                target_sub_id = sub['id_sottocategoria']
                print(f"Found ALIMENTI: ID {target_sub_id}, Parent Cat: {c_data['nome_categoria']}")
                print(f"Admin View Limit (from ottieni_categorie_e_sottocategorie): {sub.get('importo_limite')}")
                break
        if target_sub_id: break
    
    if not target_sub_id:
        print("ALIMENTI subcategory not found.")
        return

    # 3. Check Budget Page View (ottieni_riepilogo_budget_mensile)
    anno = 2025
    mese = 11
    print(f"\nChecking Budget View for {anno}-{mese}...")
    
    riepilogo = ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese, master_key_b64)
    
    found_in_budget = False
    for c_id, c_data in riepilogo.items():
        for sub in c_data['sottocategorie']:
            if sub['id_sottocategoria'] == target_sub_id:
                print(f"Budget View Limit: {sub['importo_limite']}")
                print(f"Budget View Spent: {sub['spesa_totale']}")
                print(f"Budget View Remaining: {sub['rimanente']}")
                found_in_budget = True
                break
        if found_in_budget: break
        
    if not found_in_budget:
        print("Subcategory not found in budget summary.")

    # 4. Direct DB Inspection
    print("\nDirect DB Inspection:")
    with get_db_connection() as con:
        cur = con.cursor()
        
        # Check Budget Table
        cur.execute("""
            SELECT importo_limite 
            FROM Budget 
            WHERE id_sottocategoria = %s AND id_famiglia = %s AND periodo = 'Mensile'
        """, (target_sub_id, id_famiglia))
        row_budget = cur.fetchone()
        raw_budget = row_budget['importo_limite'] if row_budget else "None"
        print(f"Raw Budget Table Value: {raw_budget}")
        
        # Check Budget_Storico Table
        cur.execute("""
            SELECT importo_limite 
            FROM Budget_Storico 
            WHERE id_sottocategoria = %s AND id_famiglia = %s AND anno = %s AND mese = %s
        """, (target_sub_id, id_famiglia, anno, mese))
        row_storico = cur.fetchone()
        raw_storico = row_storico['importo_limite'] if row_storico else "None"
        print(f"Raw Budget_Storico Table Value: {raw_storico}")

        # Decrypt if possible
        crypto, key = _get_crypto_and_key(master_key_b64)
        if row_budget:
            decrypted = _decrypt_if_key(row_budget['importo_limite'], key, crypto)
            print(f"Decrypted Budget Table Value: {decrypted}")
            
        if row_storico:
            decrypted_storico = _decrypt_if_key(row_storico['importo_limite'], key, crypto)
            print(f"Decrypted Budget_Storico Value: {decrypted_storico}")

if __name__ == "__main__":
    debug_limit()
