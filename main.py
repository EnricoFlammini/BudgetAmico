import flet as ft
from app_controller import AppController
from db.crea_database import setup_database
import os

def main(page: ft.Page):
    # Impostazioni iniziali della pagina
    page.title = "Budget Familiare"
    page.window_width = 600
    page.window_height = 700
    page.window_max_width = 600  # Forza la larghezza massima

    # Assicurati che il database esista prima di avviare l'app
    # Costruisce un percorso robusto che funziona indipendentemente da dove viene eseguito lo script.
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'budget_familiare.db')
    if not os.path.exists(db_path):
        print(f"Database non trovato, lo creo in: {db_path}")
        setup_database()

    # Crea l'istanza del controller principale
    # Il controller ora gestisce tutto
    app = AppController(page)

    # Imposta la funzione di routing del controller
    page.on_route_change = app.route_change

    # Avvia l'app andando alla route iniziale
    page.go(page.route)


# Avvio dell'applicazione
if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)