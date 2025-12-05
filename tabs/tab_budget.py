import flet as ft
from db.gestione_db import ottieni_riepilogo_budget_mensile, ottieni_anni_mesi_storicizzati
import datetime
from utils.styles import AppStyles, AppColors


class BudgetTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page

        # Filtro per mese
        self.dd_mese_filtro = ft.Dropdown(
            on_change=self._filtro_mese_cambiato,
            border_color=ft.Colors.OUTLINE,
            text_size=14,
            content_padding=10
        )

        self.lv_budget = ft.ListView(
            expand=True,
            spacing=10,
            padding=10
        )
        self.content = ft.Column(expand=True, spacing=10)


    def update_view_data(self, is_initial_load=False):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        loc = self.controller.loc
        self.dd_mese_filtro.label = loc.get("filter_by_month")
        
        self._popola_filtro_mese()
        self._popola_budget()
        
        self.content.controls = [
            AppStyles.header_text(loc.get("budget_management")),
            AppStyles.body_text(loc.get("budget_description")),
            ft.Container(
                content=self.dd_mese_filtro,
                padding=ft.padding.only(top=10, bottom=10)
            ),
            ft.Divider(color=ft.Colors.OUTLINE_VARIANT),
            self.lv_budget
        ]
        # self.update() # Rimosso per evitare crash se il controllo non è montato

    def _popola_filtro_mese(self):
        """Popola il dropdown con i mesi disponibili."""
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        # Salva la selezione corrente prima di aggiornare le opzioni
        selezione_corrente = self.dd_mese_filtro.value

        periodi = ottieni_anni_mesi_storicizzati(id_famiglia)
        oggi = datetime.date.today()
        periodo_corrente = {'anno': oggi.year, 'mese': oggi.month}
        if periodo_corrente not in periodi:
            periodi.insert(0, periodo_corrente)

        self.dd_mese_filtro.options = [
            ft.dropdown.Option(
                key=f"{p['anno']}-{p['mese']}",
                text=datetime.date(p['anno'], p['mese'], 1).strftime("%B %Y")
            ) for p in periodi
        ]
        
        # Ripristina la selezione precedente se ancora valida, altrimenti usa il mese corrente
        if selezione_corrente and any(opt.key == selezione_corrente for opt in self.dd_mese_filtro.options):
            self.dd_mese_filtro.value = selezione_corrente
        else:
            self.dd_mese_filtro.value = f"{oggi.year}-{oggi.month}"

    def _get_anno_mese_selezionato(self):
        if self.dd_mese_filtro.value:
            return map(int, self.dd_mese_filtro.value.split('-'))
        oggi = datetime.date.today()
        return oggi.year, oggi.month

    def _filtro_mese_cambiato(self, e):
        self._popola_budget()
        self.page.update()

    def _popola_budget(self):
        self.lv_budget.controls.clear()
        
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        anno, mese = self._get_anno_mese_selezionato()
        
        # Passa id_utente per la decriptazione corretta
        id_utente = self.controller.get_user_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        
        budget_data = ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese, master_key_b64, id_utente)
        
        if not budget_data:
            self.lv_budget.controls.append(
                ft.Text(self.controller.loc.get("no_budget_data"), italic=True, color=AppColors.TEXT_SECONDARY)
            )
            return

        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        
        # Ordina per nome categoria
        sorted_cats = sorted(budget_data.items(), key=lambda x: x[1]['nome_categoria'].lower())
        
        for cat_id, cat_data in sorted_cats:
            self.lv_budget.controls.append(self._crea_widget_categoria(cat_data, theme))

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