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
    except Exception as e:
        print(f"Errore verifica versione DB: {e}")
        page.add(ft.Text(f"Errore verifica versione DB: {e}", color=ft.Colors.RED))
        return
    # --- Fine Logica ---

    # Crea l'istanza del controller WEB
    app = WebAppController(page)

    # Imposta la funzione di routing del controller
    page.on_route_change = app.route_change

    # Avvia l'app andando alla route iniziale
    page.go(page.route)


# Avvio dell'applicazione in modalità WEB
if __name__ == "__main__":
    # Avvio Background Service per automazione server
    try:
        from services.background_service import BackgroundService
        bg_service = BackgroundService()
        bg_service.start()
        print("[INFO] Background Service avviato.")
    except Exception as e:
        print(f"[ERRORE] Impossibile avviare Background Service: {e}")

    port = int(os.environ.get("PORT", 8556))
    print(f"Avvio server web... Apri il browser su: http://localhost:{port}")
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")
