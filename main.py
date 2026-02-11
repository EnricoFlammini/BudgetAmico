import os
import sys
import threading
import traceback
import flet as ft
from controllers.web_app_controller import WebAppController
from db.supabase_manager import SupabaseManager
from db.gestione_db import ottieni_versione_db

# Determina il percorso base (diverso per EXE vs script)
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# Su Koyeb questo è normale, le variabili sono settate nell'ambiente OS
print(f"[INFO] Ambiente OS pronto (base_path: {base_path})")

def run_startup_sequence():
    """
    Esegue migrazione database e avvio Background Service in un thread separato.
    """
    print("[STARTUP] Avvio sequenza di inizializzazione asincrona...")
    
    # Tentativi iniziali per stabilizzare la connessione
    db_connected = False
    for attempt in range(1, 4):
        print(f"[STARTUP] Test connessione database (tentativo {attempt}/3)...")
        if SupabaseManager.test_connection():
            print(f"[STARTUP] Connessione database OK (tentativo {attempt}).")
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
                    migra_database(con, versione_corrente_db, SCHEMA_VERSION)
                print("[STARTUP] Migrazione completata con successo.")
            else:
                print("[STARTUP] Database già aggiornato.")
        except Exception as e:
            print(f"[ERRORE STARTUP] Migrazione database fallita: {e}")
            traceback.print_exc()
    else:
        print("[ERRORE STARTUP] Connessione database fallita dopo 3 tentativi!")

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
    """Entry point per ogni singola sessione utente (Flet Page)."""
    # Impostazioni iniziali
    page.title = "Budget Amico Web"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed="blue", font_family="Roboto")
    page.scroll = ft.ScrollMode.ADAPTIVE
    
    # Debug: Mostriamo qualcosa subito per capire se il server risponde
    # Se l'utente vede questo testo, allora Flet sta funzionando e il problema è nel controller
    loading_text = ft.Text("Budget Amico - Inizializzazione sessione...", size=16, weight="bold")
    page.add(
        ft.Container(
            content=ft.Column([
                ft.ProgressRing(),
                loading_text,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True
        )
    )
    page.update()

    try:
        # Crea l'istanza del controller WEB dedicato
        print(f"[SESSION] Creazione WebAppController per sessione {page.session_id}...")
        app = WebAppController(page)

        # Imposta la funzione di routing del controller
        page.on_route_change = app.route_change

        # Rimuoviamo il caricamento e andiamo alla route
        page.controls.clear()
        page.go(page.route)
        print(f"[SESSION] Sessione {page.session_id} pronta sulla route: {page.route}")
        
    except Exception as e:
        print(f"[ERRORE SESSIONE] Errore critico durante l'inizializzazione: {e}")
        traceback.print_exc()
        page.controls.clear()
        page.add(ft.Text(f"Errore critico durante l'avvio: {e}\n\nControlla i log per i dettagli.", color=ft.Colors.RED))
        page.update()


if __name__ == "__main__":
    # Avvia la sequenza di startup (migrazioni e servizi) in background.
    threading.Thread(target=run_startup_sequence, daemon=True).start()

    # Porta di ascolto configurabile
    server_port = int(os.environ.get("PORT", 8000))
    print(f"Avvio server web sulla porta {server_port}...")
    
    # ft.app è bloccante e gestisce il server Flet
    ft.app(
        target=main, 
        view=ft.AppView.WEB_BROWSER, 
        port=server_port, 
        host="0.0.0.0", 
        assets_dir="assets", 
        upload_dir="temp_uploads"
    )
