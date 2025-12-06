import flet as ft
from app_controller import AppController
from db.gestione_db import ottieni_versione_db
from db.supabase_manager import SupabaseManager
import os

# Carica le variabili d'ambiente dal file .env (opzionale)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv non disponibile (es. in eseguibile), ignora
    pass

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
        page.add(ft.Text("Errore critico: Impossibile connettersi al database.", color=ft.colors.RED))
        return

    try:
        versione_corrente_db = int(ottieni_versione_db())
        print(f"Versione DB: {versione_corrente_db}")
    except Exception as e:
        print(f"Errore verifica versione DB: {e}")
        page.add(ft.Text(f"Errore verifica versione DB: {e}", color=ft.colors.RED))
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