import os
import sys

# Aggiungi la directory superiore al percorso
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection, save_system_config, get_configurazione
from utils.logger import setup_logger

logger = setup_logger("Diagnostic_Config")

def run_diagnostic():
    print("--- DIAGNOSTICA CONFIGURAZIONI ---")
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # 1. Verifica Indici sulla tabella Configurazioni
        print("\n[1] Verifica Indici su 'Configurazioni'...")
        try:
            cur.execute("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'configurazioni';
            """)
            indexes = cur.fetchall()
            found_partial = False
            for idx in indexes:
                print(f"- {idx['indexname']}: {idx['indexdef']}")
                if "WHERE (id_famiglia IS NULL)" in idx['indexdef']:
                    found_partial = True
            
            if found_partial:
                print("[OK] Indice parziale per configurazioni globali TROVATO.")
            else:
                print("[NO] Indice parziale per configurazioni globali MANCANTE.")
        except Exception as e:
            print(f"[ERR] Errore durante il recupero degli indici: {e}")

        # 2. Verifica record attuale
        print("\n[2] Verifica record attuale...")
        val = get_configurazione("system_default_cloud_automation")
        print(f"Valore corrente nel DB: {val}")

        # 3. Test di salvataggio
        print("\n[3] Test salvataggio 'true'...")
        res = save_system_config("system_default_cloud_automation", "true")
        if res:
            print("[OK] save_system_config ha restituito TRUE")
            new_val = get_configurazione("system_default_cloud_automation")
            print(f"Nuovo valore letto: {new_val}")
            if new_val == "true":
                print("[OK] Persistenza CONFERMATA.")
            else:
                print("[NO] Persistenza FALLITA (il valore non è cambiato).")
        else:
            print("[NO] save_system_config ha restituito FALSE")

        # 4. Test SMTP (per confronto)
        print("\n[4] Test salvataggio 'smtp_server'...")
        res_smtp = save_system_config("smtp_server", "smtp.test.com")
        print(f"Salvataggio SMTP: {'[OK]' if res_smtp else '[NO]'}")

if __name__ == "__main__":
    run_diagnostic()
