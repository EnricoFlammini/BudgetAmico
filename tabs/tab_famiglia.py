import flet as ft
from db.gestione_db import (
    ottieni_riepilogo_patrimonio_famiglia_aggregato,
    ottieni_dettagli_famiglia,
    ottieni_dati_analisi_mensile,
    ottieni_anni_mesi_storicizzati
)
import datetime
from utils.styles import AppStyles, AppColors, PageConstants


class FamigliaTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page

        # Loading Indicator
        self.loading_view = ft.Container(
            content=ft.Column([
                ft.ProgressRing(color=AppColors.PRIMARY),
                ft.Text(self.controller.loc.get("loading"), color=AppColors.TEXT_SECONDARY)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment(0, 0),
            expand=True,
            visible=False
        )

        # Controlli UI e Main Content
        self.txt_patrimonio_totale_famiglia = AppStyles.title_text("")
        self.txt_liquidita_totale_famiglia = AppStyles.body_text("")
        self.txt_investimenti_totali_famiglia = AppStyles.body_text("")
        
        self.dd_mese_filtro = ft.Dropdown(
            border_color=ft.Colors.OUTLINE,
            text_size=14,
            content_padding=10
        )
        self.dd_mese_filtro.on_change = self._filtro_mese_cambiato
        
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
            alignment=ft.Alignment(0, 0),
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
        if self.controller.page: self.controller.page.update()
        
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
            anno, mese = self._get_anno_mese_selezionato()
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            dati_mensili = ottieni_dati_analisi_mensile(famiglia_id, anno, mese, master_key_b64, id_utente)
            result['dati_mensili'] = dati_mensili
            result['anno'] = anno
            result['mese'] = mese
            return result

        if ruolo in ['admin', 'livello1']:
            anno, mese = self._get_anno_mese_selezionato()
            master_key_b64 = self.controller.page.session.get("master_key")
            transazioni = ottieni_dettagli_famiglia(
                famiglia_id, anno, mese, 
                master_key_b64=master_key_b64, 
                id_utente=self.controller.get_user_id()
            )
            riepilogo = ottieni_riepilogo_patrimonio_famiglia_aggregato(
                famiglia_id, anno, mese, master_key_b64=master_key_b64
            )
            result['transazioni'] = transazioni
            result['riepilogo'] = riepilogo
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
        if self.controller.page: self.controller.page.update()

    def _on_error(self, e):
        print(f"Errore FamigliaTab: {e}")
        self.loading_view.visible = False
        self.main_content.controls = [AppStyles.body_text(f"Errore caricamento: {e}", color=AppColors.ERROR)]
        self.main_content.visible = True
        if self.controller.page: self.controller.page.update()

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
            loc = self.controller.loc
            dati = data.get('dati_mensili') or {}
            
            entrate = dati.get('entrate', 0)
            spese_totali = dati.get('spese_totali', 0)
            risparmio = dati.get('risparmio', 0)
            
            # Titolo con mese/anno
            anno = data.get('anno', datetime.date.today().year)
            mese = data.get('mese', datetime.date.today().month)
            titolo_mese = datetime.date(anno, mese, 1).strftime("%B %Y").capitalize()
            
            self.main_content.controls = [
                AppStyles.title_text(f"Riepilogo Famiglia - {titolo_mese}"),
                ft.Container(content=self.dd_mese_filtro, padding=ft.padding.only(top=5, bottom=10)),
                AppStyles.page_divider(),
                AppStyles.card_container(
                    content=ft.Column([
                        ft.Row([
                            AppStyles.subheader_text("Entrate Mensili"),
                            AppStyles.currency_text(loc.format_currency(entrate), color=AppColors.SUCCESS)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                        ft.Row([
                            AppStyles.subheader_text("Spese Totali"),
                            AppStyles.currency_text(loc.format_currency(spese_totali), color=AppColors.ERROR)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                        ft.Row([
                            AppStyles.subheader_text("Risparmio"),
                            AppStyles.currency_text(loc.format_currency(risparmio), 
                                color=AppColors.SUCCESS if risparmio >= 0 else AppColors.ERROR)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=10),
                    padding=20
                )
            ]
            return

        if ruolo in ['admin', 'livello1']:
            loc = self.controller.loc
            riepilogo = data.get('riepilogo', {})
            
            val_patrimonio = riepilogo.get('patrimonio_netto', 0)
            val_liquidita = riepilogo.get('liquidita', 0)
            val_investimenti = riepilogo.get('investimenti', 0)
            val_fondi_pensione = riepilogo.get('fondi_pensione', 0)
            val_risparmio = riepilogo.get('risparmio', 0)
            val_patrimonio_immobile = riepilogo.get('patrimonio_immobile_lordo', 0)
            val_prestiti = riepilogo.get('prestiti_totali', 0)
            
            # Custom styles for responsive text
            text_style_label = ft.TextStyle(size=14, color=AppColors.TEXT_SECONDARY)
            text_style_val = ft.TextStyle(size=14, weight=ft.FontWeight.BOLD)

            # Helper to create responsive detail row
            def riga_resp(label, val_formatted, color=None):
                return ft.ResponsiveRow([
                    ft.Column([ft.Text(label, style=text_style_label)], col={"xs": 6, "sm": 6}),
                    ft.Column([ft.Text(val_formatted, style=text_style_val, color=color, text_align=ft.TextAlign.RIGHT)], 
                              col={"xs": 6, "sm": 6}, alignment=ft.MainAxisAlignment.END, horizontal_alignment=ft.CrossAxisAlignment.END)
                ])

            # Costruisci righe dettaglio responsive
            righe_dettaglio = []
            righe_dettaglio.append(riga_resp(loc.get("liquidity"), loc.format_currency(val_liquidita)))
            
            if val_investimenti > 0:
                righe_dettaglio.append(riga_resp(loc.get("investments"), loc.format_currency(val_investimenti)))
            
            if val_fondi_pensione > 0:
                righe_dettaglio.append(riga_resp(loc.get("pension_funds"), loc.format_currency(val_fondi_pensione)))

            if val_risparmio > 0:
                righe_dettaglio.append(riga_resp(loc.get("savings"), loc.format_currency(val_risparmio)))
            
            if val_patrimonio_immobile > 0:
                righe_dettaglio.append(riga_resp(loc.get("real_estate_assets"), loc.format_currency(val_patrimonio_immobile)))

            if val_prestiti > 0:
                righe_dettaglio.append(riga_resp(loc.get("loans"), loc.format_currency(-val_prestiti), color=AppColors.ERROR))
            
            # Card riepilogo patrimonio famiglia responsive - FORCE STACKING ON MOBILE/TABLET
            card_riepilogo = AppStyles.card_container(
                content=ft.ResponsiveRow([
                    # Colonna Totale: Full width on xs AND sm. Only side-by-side on md+
                    ft.Column([
                        AppStyles.caption_text(loc.get("family_net_worth")),
                        AppStyles.big_currency_text(loc.format_currency(val_patrimonio),
                            color=AppColors.SUCCESS if val_patrimonio >= 0 else AppColors.ERROR)
                    ], col={"xs": 12, "sm": 12, "md": 5}),
                    
                    # Colonna Dettagli: Full width on xs AND sm.
                    ft.Column(righe_dettaglio, spacing=5, col={"xs": 12, "sm": 12, "md": 7})
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20
            )
            
            # Aggiorna i controlli del main_content con riepilogo patrimonio
            self.main_content.controls = [
                AppStyles.title_text(loc.get("family_transactions")),
                card_riepilogo,
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
                    # Determina il testo dell'importo
                    if t.get('importo_nascosto'):
                        importo_text = self.controller.loc.get("amount_reserved")
                        importo_color = AppColors.TEXT_SECONDARY
                    else:
                        importo_text = self.controller.loc.format_currency(t.get('importo', 0))
                        importo_color = AppColors.SUCCESS if t.get('importo', 0) >= 0 else AppColors.ERROR
                    
                    self.dt_transazioni_famiglia.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(t.get('utente_nome') or self.controller.loc.get("shared"))),
                            ft.DataCell(ft.Text(t.get('data') or "N/A")),
                            ft.DataCell(ft.Text(t.get('descrizione') or "N/A", tooltip=t.get('descrizione'))),
                            ft.DataCell(ft.Text(t.get('nome_sottocategoria') or "N/A")),
                            ft.DataCell(ft.Text(t.get('conto_nome') or "N/A")),
                            ft.DataCell(ft.Text(importo_text,
                                                color=importo_color,
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