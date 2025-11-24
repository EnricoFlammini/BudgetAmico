import flet as ft
from app_controller import AppController
from db.crea_database import setup_database, SCHEMA_VERSION
from db.gestione_db import ottieni_versione_db, DB_FILE
from db.migration_manager import migra_database
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
    page.window_width = 600
    page.window_height = 700
    page.window_max_width = 600

    # Imposta il tema
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed="blue")
    page.dark_theme = ft.Theme(color_scheme_seed="blue")

    # --- Logica di Creazione e Migrazione Database ---
    if not os.path.exists(DB_FILE):
        print(f"Database non trovato, lo creo in: {DB_FILE}")
        setup_database()
    else:
        print(f"Database esistente trovato in: {DB_FILE}")
        versione_corrente_db = ottieni_versione_db()
        print(f"Versione DB: {versione_corrente_db}, Versione Schema Atteso: {SCHEMA_VERSION}")
        if versione_corrente_db < SCHEMA_VERSION:
            print("Avvio migrazione database...")
            if not migra_database(DB_FILE, versione_corrente_db, SCHEMA_VERSION):
                # Se la migrazione fallisce, mostra un errore critico e ferma l'app
                page.add(ft.Text("Errore critico durante la migrazione del database. Controllare i log.", color=ft.colors.RED))
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