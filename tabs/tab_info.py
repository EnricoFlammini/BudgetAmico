import flet as ft
from utils.styles import AppColors

class InfoTab(ft.Container):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.expand = True
        self.padding = 20
        self.content = self._build_view()

    def _build_view(self):
        from app_controller import VERSION
        
        return ft.Column([
            ft.Text("Info & Download", size=24, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
            ft.Divider(),
            
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=64, color=AppColors.PRIMARY),
                    ft.Text(f"Budget Amico v{VERSION}", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text("Il tuo assistente personale per la gestione delle finanze.", size=16),
                    ft.Container(height=10),

                    # Dettagli Utente e Famiglia
                    self._build_personal_info_section(),

                    ft.Divider(height=30),
                    
                    ft.Text("Risorse Utili", weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.TextButton("Manuale Utente", icon=ft.Icons.MENU_BOOK, url="https://github.com/EnricoFlammini/BudgetAmico/blob/main/docs/Manuale_Completo_Budget_Amico.md"),
                        ft.TextButton("Repository GitHub", icon=ft.Icons.CODE, url="https://github.com/EnricoFlammini/BudgetAmico"),
                        ft.TextButton("Segnala un Problema", icon=ft.Icons.BUG_REPORT, url="https://github.com/EnricoFlammini/BudgetAmico/issues"),
                        ft.TextButton("Supporto Email", icon=ft.Icons.EMAIL, url="mailto:budgetamico@gmail.com"),
                    ], wrap=True),
                    
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                alignment=ft.alignment.center,
                padding=20,
                bgcolor=ft.Colors.GREY_100,
                border_radius=10
            )
        ], scroll=ft.ScrollMode.AUTO, spacing=20)

    def _build_personal_info_section(self):
        utente = self.controller.page.session.get("utente_loggato") or {}
        id_famiglia = self.controller.page.session.get("id_famiglia")
        
        info_famiglia = None
        if id_famiglia:
            from db.gestione_db import get_family_summary
            master_key = self.controller.page.session.get("master_key")
            id_utente_str = utente.get('id')
            info_famiglia = get_family_summary(id_famiglia, master_key_b64=master_key, id_utente=id_utente_str)

        info_rows = []
        if info_famiglia:
            info_rows.append(ft.Row([ft.Text("Famiglia:", weight=ft.FontWeight.BOLD), ft.Text(info_famiglia.get('nome', '-'))], alignment=ft.MainAxisAlignment.CENTER))
            info_rows.append(ft.Row([ft.Text("Codice Famiglia:", weight=ft.FontWeight.BOLD), ft.Text(info_famiglia.get('codice', '-'), color=ft.Colors.BLUE_900)], alignment=ft.MainAxisAlignment.CENTER))
        
        info_rows.append(ft.Row([ft.Text("Nome Utente:", weight=ft.FontWeight.BOLD), ft.Text(f"{utente.get('nome', '-')} {utente.get('cognome', '')}")], alignment=ft.MainAxisAlignment.CENTER))
        info_rows.append(ft.Row([ft.Text("Username:", weight=ft.FontWeight.BOLD), ft.Text(utente.get('username', '-'))], alignment=ft.MainAxisAlignment.CENTER))
        info_rows.append(ft.Row([ft.Text("Codice Utente:", weight=ft.FontWeight.BOLD), ft.Text(utente.get('codice_utente', '-'), color=ft.Colors.BLUE_900)], alignment=ft.MainAxisAlignment.CENTER))

        return ft.Container(
            content=ft.Column(info_rows, spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=15,
            bgcolor=ft.Colors.BLUE_GREY_50,
            border_radius=10,
            width=400
        )

    def update_view_data(self, is_initial_load=False):
        # Ricostruisce la vista per aggiornare i dati se necessario
        self.content = self._build_view()
        if self.page:
            self.update()
