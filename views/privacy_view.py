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
            route="/privacy",
            appbar=ft.AppBar(
                title=ft.Text("Informativa Privacy", weight=ft.FontWeight.BOLD),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_VARIANT,
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: self.page.go("/"))
            ),
            controls=[
                ft.Column([
                    ft.Text("Informativa sulla Privacy", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Text(
                        "La tua privacy è fondamentale per noi di BudgetAmico. Questa informativa spiega come "
                        "raccogliamo, utilizziamo e proteggiamo i tuoi dati personali.",
                        size=14
                    ),
                    ft.Text("1. Raccolta dei Dati", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Raccogliamo solo i dati necessari per il funzionamento dell'applicazione: "
                        "e-mail (per l'account e le notifiche), nome e cognome (per la visualizzazione in famiglia). "
                        "Tutti i dati sensibili, come descrizioni di transazioni e nomi dei conti, sono "
                        "criptati end-to-end con la tua chiave master personale.",
                        size=14
                    ),
                    ft.Text("2. Utilizzo della Crittografia", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "BudgetAmico utilizza la crittografia lato client. Questo significa che i tuoi dati "
                        "vengono criptati sul tuo dispositivo prima di essere inviati al nostro database. "
                        "Noi non abbiamo accesso alla tua master key e non possiamo leggere i tuoi dati finanziari.",
                        size=14
                    ),
                    ft.Text("3. I Tuoi Diritti", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Hai il diritto di accedere ai tuoi dati, rettificarli o chiederne la cancellazione "
                        "in qualsiasi momento tramite le impostazioni del profilo o contattando l'amministratore.",
                        size=14
                    ),
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        "Torna Indietro",
                        icon=ft.Icons.ARROW_BACK,
                        on_click=lambda _: self.page.go("/")
                    ),
                ], spacing=15, scroll=ft.ScrollMode.ADAPTIVE)
            ],
            padding=20,
            scroll=ft.ScrollMode.ADAPTIVE
        )
