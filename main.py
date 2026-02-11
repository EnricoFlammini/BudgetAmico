import os
import sys
import threading
import flet as ft
from controllers.web_app_controller import WebAppController
from db.supabase_manager import SupabaseManager
from db.gestione_db import ottieni_versione_db

# Determina il percorso base (diverso per EXE vs script)
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# Carica le variabili d'ambiente dal file .env (solo per sviluppo locale)
try:
    from dotenv import load_dotenv
    env_path = os.path.join(base_path, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[INFO] File .env caricato da: {env_path}")
    else:
        # Su Koyeb questo è normale, le variabili sono settate nell'ambiente OS
        print(f"[INFO] Ambiente OS pronto (nessun .env trovato in {env_path})")
except ImportError:
    pass

def run_startup_sequence():
    """
    Esegue migrazione database e avvio Background Service in un thread separato.
    """
    print("[STARTUP] Avvio sequenza di inizializzazione asincrona...")
    
    # Tentativi iniziali per stabilizzare la connessione (utili se il DB sta ripartendo o è sotto stress)
    db_connected = False
    for attempt in range(1, 4):
        print(f"[STARTUP] Test connessione database (tentativo {attempt}/3)...")
        if SupabaseManager.test_connection():
            db_connected = True
            break
        import time
        time.sleep(2)

    if db_connected:
        try:
            from db.crea_database import SCHEMA_VERSION
            from db.supabase_manager import get_db_connection
            from db.migration_manager import migra_database
            
            versione_corrente_db = int(ottieni_versione_db())
            print(f"[STARTUP] Versione DB attuale: {versione_corrente_db}, Schema richiesto: {SCHEMA_VERSION}")
            
            if versione_corrente_db < SCHEMA_VERSION:
                print(f"[STARTUP] Migrazione necessaria: v{versione_corrente_db} -> v{SCHEMA_VERSION}")
                with get_db_connection() as con:
                    # La migrazione ha ora un timeout illimitato grazie al fix precedente
                    migra_database(con, versione_corrente_db, SCHEMA_VERSION)
                print("[STARTUP] Migrazione completata con successo.")
            else:
                print("[STARTUP] Database già aggiornato.")
        except Exception as e:
            print(f"[ERRORE STARTUP] Migrazione database fallita: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("[ERRORE STARTUP] Connessione database fallita dopo 3 tentativi!")

    # 2. Inizializza DBLogHandler (carica i log sulla tabella Logs del DB)
    try:
        from utils.db_log_handler import attach_db_handler_to_all_loggers
        attach_db_handler_to_all_loggers()
        print("[STARTUP] DBLogHandler inizializzato.")
    except Exception as e:
        print(f"[WARNING STARTUP] Impossibile inizializzare DBLogHandler: {e}")

    # 3. Avvio Background Service (scadenze, spese fisse, etc.)
    try:
        from services.background_service import BackgroundService
        bg_service = BackgroundService()
        bg_service.start()
        print("[STARTUP] Background Service avviato.")
    except Exception as e:
        print(f"[ERRORE STARTUP] Impossibile avviare Background Service: {e}")
    
    print("[STARTUP] Sequenza completata.")


def main(page: ft.Page):
    """Entry point per ogni singola sessione utente (Flet Page)."""
    # Impostazioni iniziali della pagina
    page.title = "Budget Amico Web"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed="blue", font_family="Roboto")
    page.scroll = ft.ScrollMode.ADAPTIVE

    # Crea l'istanza del controller WEB dedicato
    # Inizializza viste e dialoghi. I dialoghi non blockeranno più se il DB è in migrazione
    # grazie alla cache e ai fallback implementati in gestione_db.py.
    app = WebAppController(page)

    # Imposta la funzione di routing del controller
    page.on_route_change = app.route_change

    # Avvia l'app andando alla route iniziale (solitamente / login)
    page.go(page.route)


if __name__ == "__main__":
    # Avvia la sequenza di startup (migrazioni e servizi) in background.
    # Daemon=True assicura che il thread si chiuda se il processo principale muore.
    threading.Thread(target=run_startup_sequence, daemon=True).start()

    # Porta di ascolto configurabile (Koyeb usa 8000 o assegna via env PORT)
    server_port = int(os.environ.get("PORT", 8000))
    print(f"Avvio server web sulla porta {server_port}...")
    
    # ft.app è bloccante e gestisce il server Flet (Gunicorn/Uvicorn sotto il cofano)
    ft.app(
        target=main, 
        view=ft.AppView.WEB_BROWSER, 
        port=server_port, 
        host="0.0.0.0", 
        assets_dir="assets", 
        upload_dir="temp_uploads"
    )
