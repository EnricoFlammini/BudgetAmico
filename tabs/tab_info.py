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
                    ft.Container(height=20),
                    
                    ft.Text("Versione Desktop", weight=ft.FontWeight.BOLD),
                    ft.Text("Scarica l'ultima versione completa per Windows dal nostro repository ufficiale.", size=14),
                    ft.ElevatedButton(
                        "Scarica e Installa",
                        icon=ft.Icons.DOWNLOAD,
                        url="https://github.com/EnricoFlammini/BudgetAmico/releases/latest",
                        style=ft.ButtonStyle(
                            color=ft.Colors.WHITE,
                            bgcolor=ft.Colors.GREEN_600,
                            padding=15
                        )
                    ),
                    
                    ft.Divider(height=30),
                    
                    ft.Text("Risorse Utili", weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.TextButton("Repository GitHub", icon=ft.Icons.CODE, url="https://github.com/EnricoFlammini/BudgetAmico"),
                        ft.TextButton("Segnala un Problema", icon=ft.Icons.BUG_REPORT, url="https://github.com/EnricoFlammini/BudgetAmico/issues"),
                    ], wrap=True),
                    
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                alignment=ft.alignment.center,
                padding=20,
                bgcolor=ft.Colors.SURFACE_VARIANT,
                border_radius=10
            )
        ], scroll=ft.ScrollMode.AUTO, spacing=20)

    def update_view_data(self, is_initial_load=False):
        pass
