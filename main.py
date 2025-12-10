import os
import sys

# Determina il percorso base (diverso per EXE vs script)
if getattr(sys, 'frozen', False):
    # Eseguibile PyInstaller
    base_path = sys._MEIPASS
else:
    # Script Python normale
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
    print("[INFO] python-dotenv non disponibile, uso variabili d'ambiente di sistema")
    pass

import flet as ft
from app_controller import AppController
from db.gestione_db import ottieni_versione_db
from db.supabase_manager import SupabaseManager

def main(page: ft.Page):
    # Impostazioni iniziali della pagina
    page.title = "Budget Amico"
    
    # Impostazioni finestra (nuova sintassi Flet 0.21+)
    page.window.width = 1500
    page.window.height = 1000
    page.window.min_width = 700
    page.window.min_height = 600

    # Imposta il tema
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed="blue")
    page.dark_theme = ft.Theme(color_scheme_seed="blue")

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

    # Crea l'istanza del controller principale
    app = AppController(page)

    # Imposta la funzione di routing del controller
    page.on_route_change = app.route_change

    # Avvia l'app andando alla route iniziale
    page.go(page.route)


# Avvio dell'applicazione
if __name__ == "__main__":
    ft.app(target=main)