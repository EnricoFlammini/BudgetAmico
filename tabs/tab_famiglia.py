import flet as ft
from db.gestione_db import (
    ottieni_riepilogo_patrimonio_famiglia_aggregato,
    ottieni_dettagli_famiglia,
    ottieni_totali_famiglia,
    ottieni_anni_mesi_storicizzati
)
import datetime
from utils.styles import AppStyles, AppColors, PageConstants


class FamigliaTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.page = controller.page

        # Loading Indicator
        self.loading_view = ft.Container(
            content=ft.Column([
                ft.ProgressRing(color=AppColors.PRIMARY),
                ft.Text(self.controller.loc.get("loading"), color=AppColors.TEXT_SECONDARY)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True,
            visible=False
        )

        # Controlli UI e Main Content
        self.txt_patrimonio_totale_famiglia = AppStyles.header_text("")
        self.txt_liquidita_totale_famiglia = AppStyles.body_text("")
        self.txt_investimenti_totali_famiglia = AppStyles.body_text("")
        
        self.dd_mese_filtro = ft.Dropdown(
            on_change=self._filtro_mese_cambiato,
            border_color=ft.Colors.OUTLINE,
            text_size=14,
            content_padding=10
        )
        
        self.dt_transazioni_famiglia = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("..."))],
            rows=[],
            expand=True,
            border_radius=10,
            heading_row_height=40,
            data_row_max_height=60
        )
        
        self.no_data_view = ft.Container(
            content=AppStyles.body_text(self.controller.loc.get("no_transactions_found_family")),
            alignment=ft.alignment.center,
            expand=True,
            visible=False
        )

        self.data_stack = ft.Stack(
            controls=[
                ft.Column([self.dt_transazioni_famiglia], scroll=ft.ScrollMode.ADAPTIVE, expand=True),
                self.no_data_view
            ],
            expand=True
        )
        
        self.main_content = ft.Column([], expand=True, spacing=10)
        
        # Stack principale
        self.content = ft.Stack([
            self.main_content,
            self.loading_view
        ], expand=True)

    def update_view_data(self, is_initial_load=False):
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        
        self.main_content.controls = self.build_controls(theme)
        
        self.txt_patrimonio_totale_famiglia.color = theme.primary
        self.dt_transazioni_famiglia.heading_row_color = AppColors.SURFACE_VARIANT
        self.dt_transazioni_famiglia.data_row_color = {"hovered": ft.Colors.with_opacity(0.1, theme.primary)}
        self.dt_transazioni_famiglia.border = ft.border.all(1, ft.Colors.OUTLINE_VARIANT)

        # Popola filtro mese Sync
        self._popola_filtro_mese()

        famiglia_id = self.controller.get_family_id()
        ruolo = self.controller.get_user_role()

        # Show Loading
        self.main_content.visible = False
        self.loading_view.visible = True
        if self.page: self.page.update()
        
        # Async Task
        from utils.async_task import AsyncTask
        task = AsyncTask(
            target=self._fetch_data,
            args=(famiglia_id, ruolo, theme),
            callback=self._on_data_loaded,
            error_callback=self._on_error
        )
        task.start()

    def _fetch_data(self, famiglia_id, ruolo, theme):
        result = {'famiglia_id': famiglia_id, 'ruolo': ruolo, 'theme': theme}
        
        if not famiglia_id:
            return result
            
        if ruolo == 'livello3':
            return result
            
        if ruolo == 'livello2':
            master_key_b64 = self.controller.page.session.get("master_key")
            totali = ottieni_totali_famiglia(famiglia_id, master_key_b64=master_key_b64)
            result['totali'] = totali
            return result

        if ruolo in ['admin', 'livello1']:
            anno, mese = self._get_anno_mese_selezionato()
            master_key_b64 = self.controller.page.session.get("master_key")
            transazioni = ottieni_dettagli_famiglia(
                famiglia_id, anno, mese, 
                master_key_b64=master_key_b64, 
                id_utente=self.controller.get_user_id()
            )
            result['transazioni'] = transazioni
            result['anno'] = anno
            result['mese'] = mese
            return result

        return result

    def _on_data_loaded(self, result):
        famiglia_id = result['famiglia_id']
        ruolo = result['ruolo']
        theme = result['theme']

        # Ricostruisci UI con i dati
        self._aggiorna_contenuto_per_ruolo(famiglia_id, ruolo, theme, result)

        # Hide Loading
        self.loading_view.visible = False
        self.main_content.visible = True
        if self.page: self.page.update()

    def _on_error(self, e):
        print(f"Errore FamigliaTab: {e}")
        self.loading_view.visible = False
        self.main_content.controls = [AppStyles.body_text(f"Errore caricamento: {e}", color=AppColors.ERROR)]
        self.main_content.visible = True
        if self.page: self.page.update()

    def _aggiorna_contenuto_per_ruolo(self, famiglia_id, ruolo, theme, data):
        if not famiglia_id:
            self.main_content.controls = [ft.Column(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=50, color=AppColors.TEXT_SECONDARY),
                    AppStyles.subheader_text(self.controller.loc.get("not_in_family"))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, expand=True
            )]
            return

        if ruolo == 'livello3':
            self.main_content.controls = [ft.Column(
                [
                    ft.Icon(ft.Icons.LOCK, size=50, color=AppColors.TEXT_SECONDARY),
                    AppStyles.subheader_text(self.controller.loc.get("no_family_access_permission"))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, expand=True
            )]
            return
            
        if ruolo == 'livello2':
            self.main_content.controls.clear()
            self.main_content.controls.extend([
                AppStyles.header_text(self.controller.loc.get("wealth_by_member")),
                ft.Divider(color=ft.Colors.OUTLINE_VARIANT)
            ])
            totali = data.get('totali', [])
            for m in totali:
                self.main_content.controls.append(
                    AppStyles.card_container(
                        content=ft.Row([
                            AppStyles.subheader_text(m['nome_visualizzato']),
                            AppStyles.currency_text(self.controller.loc.format_currency(m['saldo_totale']),
                                    color=AppColors.SUCCESS if m['saldo_totale'] >= 0 else AppColors.ERROR)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=15
                    )
                )
            return

        if ruolo in ['admin', 'livello1']:
            loc = self.controller.loc
            
            # Aggiorna i controlli del main_content senza riepilogo patrimonio
            self.main_content.controls = [
                AppStyles.section_header(loc.get("family_transactions")),
                ft.Container(content=self.dd_mese_filtro, padding=ft.padding.only(top=5, bottom=10)),
                AppStyles.page_divider(),
                self.data_stack
            ]

            transazioni = data.get('transazioni', [])
            self.dt_transazioni_famiglia.rows.clear()
            if not transazioni:
                self.dt_transazioni_famiglia.visible = False
                self.no_data_view.visible = True
            else:
                self.dt_transazioni_famiglia.visible = True
                self.no_data_view.visible = False
                for t in transazioni:
                    self.dt_transazioni_famiglia.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(t.get('utente_nome') or self.controller.loc.get("shared"))),
                            ft.DataCell(ft.Text(t.get('data') or "N/A")),
                            ft.DataCell(ft.Text(t.get('descrizione') or "N/A", tooltip=t.get('descrizione'))),
                            ft.DataCell(ft.Text(t.get('nome_sottocategoria') or "N/A")),
                            ft.DataCell(ft.Text(t.get('conto_nome') or "N/A")),
                            ft.DataCell(ft.Text(self.controller.loc.format_currency(t.get('importo', 0)),
                                                color=AppColors.SUCCESS if t.get('importo', 0) >= 0 else AppColors.ERROR,
                                                weight=ft.FontWeight.BOLD)),
                        ])
                    )

    def build_controls(self, theme):
        loc = self.controller.loc
        
        self.dd_mese_filtro.label = loc.get("filter_by_month")
        self.dt_transazioni_famiglia.columns = [
            ft.DataColumn(ft.Text(loc.get("user"), weight=ft.FontWeight.BOLD)), 
            ft.DataColumn(ft.Text(loc.get("date"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(loc.get("description"), weight=ft.FontWeight.BOLD)), 
            ft.DataColumn(ft.Text(loc.get("subcategory"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(loc.get("account"), weight=ft.FontWeight.BOLD)), 
            ft.DataColumn(ft.Text(loc.get("amount"), weight=ft.FontWeight.BOLD), numeric=True),
        ]

        return []  # Controlli costruiti dinamicamente in _aggiorna_contenuto_per_ruolo

    def _popola_filtro_mese(self):
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return

        # Salva la selezione corrente prima di aggiornare le opzioni
        selezione_corrente = self.dd_mese_filtro.value

        periodi = ottieni_anni_mesi_storicizzati(id_famiglia)
        oggi = datetime.date.today()
        periodo_corrente = {'anno': oggi.year, 'mese': oggi.month}
        if periodo_corrente not in periodi:
            periodi.insert(0, periodo_corrente)

        self.dd_mese_filtro.options = [
            ft.dropdown.Option(key=f"{p['anno']}-{p['mese']}", text=datetime.date(p['anno'], p['mese'], 1).strftime("%B %Y"))
            for p in periodi
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
        self.update_view_data()