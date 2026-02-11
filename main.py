import os
import sys

# Determina il percorso base (diverso per EXE vs script)
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# Carica le variabili d'ambiente dal file .env PRIMA di importare altri moduli
try:
    from dotenv import load_dotenv
    env_path = os.path.join(base_path, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[INFO] File .env caricato da: {env_path}")
    else:
        print(f"[WARNING] File .env non trovato in: {env_path}")
except ImportError:
    pass

import flet as ft
from controllers.web_app_controller import WebAppController
from db.supabase_manager import SupabaseManager
from db.gestione_db import ottieni_versione_db

def main(page: ft.Page):
    # Impostazioni iniziali della pagina Web
    page.title = "Budget Amico Web"
    # Mobile-first settings
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed="blue", font_family="Roboto")
    
    # Enable scrolling generally
    page.scroll = ft.ScrollMode.ADAPTIVE

    # --- Logica di Connessione Database (PostgreSQL/Supabase) ---
    print("Verifica connessione al database...")
    if not SupabaseManager.test_connection():
        page.add(ft.Text("Errore critico: Impossibile connettersi al database.", color=ft.Colors.RED))
        return

    try:
        versione_corrente_db = int(ottieni_versione_db())
        print(f"Versione DB: {versione_corrente_db}")
        
        # Esegui migrazione se necessario
        from db.crea_database import SCHEMA_VERSION
        if versione_corrente_db < SCHEMA_VERSION:
            print(f"Migrazione necessaria: v{versione_corrente_db} -> v{SCHEMA_VERSION}")
            from db.migration_manager import migra_database
            from db.supabase_manager import get_db_connection
            with get_db_connection() as con:
                migra_database(con, versione_corrente_db, SCHEMA_VERSION)
            print("Migrazione completata.")
    except Exception as e:
        print(f"Errore verifica/migrazione DB: {e}")
        page.add(ft.Text(f"Errore verifica versione DB: {e}", color=ft.Colors.RED))
        return
    # --- Fine Logica ---

    # Crea l'istanza del controller WEB
    app = WebAppController(page)

    # Imposta la funzione di routing del controller
    page.on_route_change = app.route_change

    # Avvia l'app andando alla route iniziale
    page.go(page.route)


import threading

def run_startup_sequence():
    """
    Esegue migrazione database e avvio Background Service in un thread separato
    per evitare di bloccare l'health check di Koyeb.
    """
    print("[STARTUP] Avvio sequenza di inizializzazione asincrona...")
    
    # 1. Verifica e Migrazione Database
    if SupabaseManager.test_connection():
        try:
            from db.crea_database import SCHEMA_VERSION
            from db.supabase_manager import get_db_connection
            from db.migration_manager import migra_database
            
            versione_corrente_db = int(ottieni_versione_db())
            print(f"[STARTUP] Versione DB attuale: {versione_corrente_db}, Schema richiesto: {SCHEMA_VERSION}")
            
            if versione_corrente_db < SCHEMA_VERSION:
                print(f"[STARTUP] Migrazione necessaria: v{versione_corrente_db} -> v{SCHEMA_VERSION}")
                with get_db_connection() as con:
                    migra_database(con, versione_corrente_db, SCHEMA_VERSION)
                print("[STARTUP] Migrazione completata con successo.")
            else:
                print("[STARTUP] Database già aggiornato.")
        except Exception as e:
            print(f"[ERRORE STARTUP] Migrazione database fallita: {e}")
    else:
        print("[ERRORE STARTUP] Connessione database fallita!")

    # 2. Inizializza DBLogHandler
    try:
        from utils.db_log_handler import attach_db_handler_to_all_loggers
        attach_db_handler_to_all_loggers()
        print("[STARTUP] DBLogHandler inizializzato.")
    except Exception as e:
        print(f"[WARNING STARTUP] Impossibile inizializzare DBLogHandler: {e}")

    # 3. Avvio Background Service
    try:
        from services.background_service import BackgroundService
        bg_service = BackgroundService()
        bg_service.start()
        print("[STARTUP] Background Service avviato.")
    except Exception as e:
        print(f"[ERRORE STARTUP] Impossibile avviare Background Service: {e}")
    
    print("[STARTUP] Sequenza completata.")


def main(page: ft.Page):
    # Impostazioni iniziali della pagina Web
    page.title = "Budget Amico Web"
    # Mobile-first settings
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed="blue", font_family="Roboto")
    
    # Enable scrolling generally
    page.scroll = ft.ScrollMode.ADAPTIVE

    # Crea l'istanza del controller WEB
    app = WebAppController(page)

    # Imposta la funzione di routing del controller
    page.on_route_change = app.route_change

    # Avvia l'app andando alla route iniziale
    page.go(page.route)


# Avvio dell'applicazione in modalità WEB
if __name__ == "__main__":
    # Avvia la sequenza di startup in background per non bloccare ft.app
    threading.Thread(target=run_startup_sequence, daemon=True).start()

    port = int(os.environ.get("PORT", 8556))
    print(f"Avvio server web... Apri il browser su: http://localhost:{port}")
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0", assets_dir="assets", upload_dir="temp_uploads")
