import flet as ft
from db.gestione_db import ottieni_riepilogo_budget_mensile, ottieni_categorie, imposta_budget
import datetime


class BudgetTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page

        self.lv_budget = ft.Column(
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
            spacing=10
        )
        self.content = ft.Column(expand=True, spacing=10)

    def update_view_data(self, is_initial_load=False):
        self.content.controls = self.build_controls()

        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        # Per ora usiamo sempre il mese corrente
        oggi = datetime.date.today()
        riepilogo = ottieni_riepilogo_budget_mensile(id_famiglia, oggi.year, oggi.month)
        self.lv_budget.controls.clear()

        if not riepilogo:
            self.lv_budget.controls.append(ft.Text(self.controller.loc.get("no_budget_set")))
        else:
            for item in riepilogo:
                self.lv_budget.controls.append(self._crea_widget_budget(item))

        if self.page:
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        loc = self.controller.loc
        return [
            # --- RIGA MODIFICATA ---
            # Ora mostra solo il titolo, il pulsante è stato rimosso
            ft.Text(loc.get("budget_management"), size=24, weight=ft.FontWeight.BOLD),
            # -----------------------
            ft.Text(loc.get("budget_description")),
            ft.Divider(),
            self.lv_budget
        ]

    def _crea_widget_budget(self, item_budget):
        loc = self.controller.loc
        spesa_abs = abs(item_budget['spesa_totale'])
        limite = item_budget['importo_limite']
        rimanente = limite - spesa_abs
        percentuale_spesa = (spesa_abs / limite) if limite > 0 else 0

        # --- CORREZIONI QUI ---
        colore_progress = ft.Colors.GREEN_500
        if percentuale_spesa > 0.9:
            colore_progress = ft.Colors.RED_500
        elif percentuale_spesa > 0.7:
            colore_progress = ft.Colors.ORANGE_500

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(item_budget['nome_categoria'], weight=ft.FontWeight.BOLD, size=16),
                    ft.Text(
                        f"{loc.get('remaining')}: {loc.format_currency(rimanente)}",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=colore_progress
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(
                    f"{loc.get('spent')} {loc.format_currency(spesa_abs)} {loc.get('of')} {loc.format_currency(limite)}"),
                ft.ProgressBar(value=percentuale_spesa, color=colore_progress, bgcolor=ft.Colors.GREY_800) # <-- CORREZIONE QUI
            ]),
            padding=10,
            border=ft.border.all(1, ft.Colors.GREY_800), # <-- CORREZIONE QUI
            border_radius=5
        )

    # --- METODO _apri_dialog_imposta_budget RIMOSSO ---