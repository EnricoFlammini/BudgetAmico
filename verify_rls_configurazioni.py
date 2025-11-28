from db.supabase_manager import get_db_connection, SupabaseManager
from db.gestione_db import get_configurazione, set_configurazione

def verify_rls():
    print("--- Verifica RLS su Configurazioni ---")
    
    # 1. Test Global Read (Senza contesto utente)
    print("\n1. Test Global Read (No Context)...")
    try:
        # Reset context just in case
        SupabaseManager._current_user_id = None
        
        val = get_configurazione('smtp_server') # id_famiglia=None default
        print(f"Global Config Value: {val}")
        
        if val:
            print("[OK] Global config read successfully without context.")
        else:
            print("[WARN] Global config not found or read failed.")
            
    except Exception as e:
        print(f"[ERRORE] Test Global Read fallito: {e}")

    # 2. Test Family Write/Read (Con contesto)
    print("\n2. Test Family Access...")
    # Trova un utente admin
    admin_user = None
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT U.id_utente, AF.id_famiglia 
            FROM Utenti U 
            JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente 
            WHERE AF.ruolo = 'admin' 
            LIMIT 1
        """)
        admin_user = cur.fetchone()
    
    if admin_user:
        id_utente = admin_user['id_utente']
        id_famiglia = admin_user['id_famiglia']
        print(f"Trovato Admin: ID {id_utente}, Famiglia {id_famiglia}")
        
        # Imposta contesto GLOBALE
        print(f"Imposto contesto globale utente {id_utente}...")
        SupabaseManager._current_user_id = id_utente
        
        # Test Scrittura Famiglia
        test_key = 'test_family_config'
        test_val = 'family_value_123'
        print(f"Tentativo scrittura config famiglia: {test_key} = {test_val}")
        
        success = set_configurazione(test_key, test_val, id_famiglia=id_famiglia)
        if success:
            print("[OK] Scrittura config famiglia riuscita.")
        else:
            print("[ERRORE] Scrittura config famiglia fallita.")
            
        # Test Lettura Famiglia
        print("Tentativo lettura config famiglia...")
        read_val = get_configurazione(test_key, id_famiglia=id_famiglia)
        print(f"Valore letto: {read_val}")
        
        if read_val == test_val:
            print("[OK] Lettura config famiglia riuscita e valore corretto.")
        else:
            print(f"[ERRORE] Valore letto errato: atteso {test_val}, ottenuto {read_val}")
            
        # Test Lettura Senza Contesto (Dovrebbe fallire o non trovare nulla se RLS funziona)
        print("\n3. Test RLS Isolation (Reset Context)...")
        SupabaseManager._current_user_id = None
        
        # Nota: Se RLS blocca, la query potrebbe ritornare vuoto o errore.
        # Con id_famiglia specificato nella query, RLS controlla se l'utente ha accesso a quella famiglia.
        # Senza utente, get_current_user_family_id() ritorna NULL (o fallisce).
        # La policy "Family members can view..." usa id_famiglia = get_current_user_family_id().
        # Se get_... ritorna NULL, id_famiglia = NULL è falso (a meno che id_famiglia nella riga sia NULL, ma qui è settato).
        # Quindi non dovrebbe ritornare nulla.
        
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                # Simula ruolo 'authenticated' per testare RLS (dato che postgres è superuser)
                print("DEBUG: Switching to role 'authenticated' for RLS test...")
                cur.execute("SET ROLE authenticated")
                
                cur.execute("SELECT current_user, current_setting('app.current_user_id', true)")
                res = cur.fetchone()
                print(f"DEBUG: DB User: {res['current_user']}, App User ID: {res['current_setting']}")
                
                try:
                    cur.execute("SELECT get_current_user_family_id()")
                    fam_id = cur.fetchone()['get_current_user_family_id']
                    print(f"DEBUG: get_current_user_family_id() returned: {fam_id}")
                except Exception as e:
                    print(f"DEBUG: get_current_user_family_id() failed: {e}")
                    con.rollback() # Reset transaction if failed
                
                # Check what rows are visible
                cur.execute("SELECT * FROM Configurazioni")
                rows = cur.fetchall()
                print(f"DEBUG: Visible rows in Configurazioni: {len(rows)}")
                for r in rows:
                    print(f" - {r}")

                read_val_no_ctx = get_configurazione(test_key, id_famiglia=id_famiglia)
                print(f"Valore letto senza contesto: {read_val_no_ctx}")
                
                # Reset role
                cur.execute("RESET ROLE")
            
            if read_val_no_ctx is None:
                print("[OK] RLS ha impedito la lettura senza contesto.")
            else:
                print("[ERRORE] RLS NON ha bloccato la lettura! (O la policy è troppo permissiva)")
        except Exception as e:
            print(f"Eccezione attesa (forse): {e}")

    else:
        print("Nessun utente admin trovato per il test.")

if __name__ == "__main__":
    verify_rls()
