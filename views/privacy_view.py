import flet as ft
from utils.logger import setup_logger

logger = setup_logger("PrivacyView")

class PrivacyView:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc

    def build_view(self) -> ft.View:
        logger.info("Richiamata build_view() per /privacy")
        
        return ft.View(
            "/privacy",
            [
                ft.AppBar(
                    title=ft.Text("Informativa Privacy"),
                    center_title=True,
                    bgcolor=ft.Colors.SURFACE_VARIANT,
                ),
                ft.Column([
                    ft.Text("Informativa sulla Privacy", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Text(
                        "La tua privacy è fondamentale. I tuoi dati sensibili sono criptati end-to-end con la tua Master Key personale.",
                        size=16
                    ),
                    ft.Text("1. Dati Raccolti", weight=ft.FontWeight.BOLD),
                    ft.Text("Raccogliamo solo email e nomi necessari per identificare il tuo account e permettere la condivisione in famiglia."),
                    ft.Text("2. Crittografia", weight=ft.FontWeight.BOLD),
                    ft.Text("Tutti i dati finanziari vengono criptati sul tuo dispositivo. Nessuno, nemmeno gli amministratori, può leggerli."),
                    ft.Text("3. I Tuoi Diritti", weight=ft.FontWeight.BOLD),
                    ft.Text("Puoi rettificare o eliminare i tuoi dati in ogni momento dalle impostazioni del profilo."),
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        "Torna Indietro",
                        icon=ft.Icons.ARROW_BACK,
                        on_click=lambda _: self.page.go("/")
                    ),
                ], spacing=15, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
            ],
            padding=20
        )
