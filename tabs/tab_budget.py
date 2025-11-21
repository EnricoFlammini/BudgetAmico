import flet as ft
from db.gestione_db import ottieni_riepilogo_budget_mensile
import datetime
from utils.styles import AppStyles, AppColors


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
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        self.content.controls = self.build_controls()

        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        oggi = datetime.date.today()
        riepilogo = ottieni_riepilogo_budget_mensile(id_famiglia, oggi.year, oggi.month)
        self.lv_budget.controls.clear()

        if not riepilogo:
            self.lv_budget.controls.append(ft.Text(self.controller.loc.get("no_budget_set")))
        else:
            # Correzione: Itera sui valori del dizionario, non sulle chiavi
            for cat_data in riepilogo.values():
                self.lv_budget.controls.append(self._crea_widget_categoria(cat_data, theme))

        if self.page:
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        loc = self.controller.loc
        return [
            AppStyles.header_text(loc.get("budget_management")),
            AppStyles.body_text(loc.get("budget_description")),
            ft.Divider(color=ft.Colors.OUTLINE_VARIANT),
            self.lv_budget
        ]

    def _crea_widget_categoria(self, cat_data, theme):
        loc = self.controller.loc
        
        # Calcoli per la categoria aggregata
        limite_cat = cat_data['importo_limite_totale']
        spesa_cat = cat_data['spesa_totale_categoria']
        rimanente_cat = cat_data['rimanente_totale']
        percentuale_cat = (spesa_cat / limite_cat) if limite_cat > 0 else 0
        
        colore_cat = theme.primary
        if percentuale_cat > 0.9:
            colore_cat = AppColors.ERROR
        elif percentuale_cat > 0.7:
            colore_cat = AppColors.WARNING

        # Creazione dei widget per le sottocategorie
        sottocategorie_widgets = []
        for sub_data in cat_data['sottocategorie']:
            sottocategorie_widgets.append(self._crea_widget_sottocategoria(sub_data, theme))

        content = ft.Column([
            ft.Row([
                AppStyles.subheader_text(cat_data['nome_categoria']),
                ft.Text(
                    f"{loc.get('remaining')}: {loc.format_currency(rimanente_cat)}",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=colore_cat
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            AppStyles.caption_text(
                f"{loc.get('spent')} {loc.format_currency(spesa_cat)} {loc.get('of')} {loc.format_currency(limite_cat)}"),
            ft.ProgressBar(value=percentuale_cat, color=colore_cat, bgcolor=AppColors.SURFACE_VARIANT),
            ft.Divider(height=10, color=ft.Colors.OUTLINE_VARIANT),
            ft.Column(sottocategorie_widgets, spacing=8)
        ])
        
        return AppStyles.card_container(content, padding=15)

    def _crea_widget_sottocategoria(self, sub_data, theme):
        loc = self.controller.loc
        limite = sub_data['importo_limite']
        spesa = sub_data['spesa_totale']
        rimanente = sub_data['rimanente']
        percentuale = (spesa / limite) if limite > 0 else 0

        colore_progress = theme.primary
        if percentuale > 0.9:
            colore_progress = AppColors.ERROR
        elif percentuale > 0.7:
            colore_progress = AppColors.WARNING

        return ft.Column([
            ft.Row([
                AppStyles.body_text(sub_data['nome_sottocategoria']),
                ft.Text(f"{loc.format_currency(rimanente)}", color=colore_progress, size=14)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ProgressBar(value=percentuale, color=colore_progress, bgcolor=AppColors.SURFACE_VARIANT, height=5)
        ])