import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_transazioni_utente,
    elimina_transazione,
    elimina_transazione_condivisa,
    ottieni_riepilogo_patrimonio_utente,
    ottieni_anni_mesi_storicizzati  # Per popolare il filtro
)
import datetime
from utils.async_task import AsyncTask
from utils.styles import AppStyles, AppColors, PageConstants
from utils.logger import setup_logger

logger = setup_logger("PersonaleTab")


class PersonaleTab(ft.Container):
    # Numero di transazioni da mostrare nella vista compatta
    MAX_TRANSAZIONI_COMPATTE = 4
    
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)

        self.controller = controller
        self.controller.page = controller.page
        
        # Stato: True = vista compatta (riepilogo + 4 transazioni), False = vista espansa (tutte le transazioni)
        self.vista_compatta = True
        
        # Cache delle transazioni per evitare query multiple
        self.transazioni_correnti = []

        self.txt_bentornato = AppStyles.subheader_text("")
        self.txt_patrimonio = AppStyles.header_text("")
        self.txt_liquidita = AppStyles.caption_text("")

        # Filtro per mese
        self.dd_mese_filtro = ft.Dropdown(
            options=[],
            width=150,
            label=self.controller.loc.get("month"),
        )
        self.dd_mese_filtro.on_change = self._filtro_mese_cambiato

        self.lista_transazioni = ft.Column(
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
            spacing=10
        )
        
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
        
        # Main content
        self.main_view = ft.Column(expand=True, visible=True)

        # Stack to switch between content and loading
        self.content = ft.Stack([
            self.main_view,
            self.loading_view
        ], expand=True)

    def _safe_update(self):
        """Esegue l'update della pagina gestendo errori di loop chiuso."""
        if not self.controller.page: return
        try:
            self.controller.page.update()
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.debug("Tentativo di update a loop chiuso ignorato.")
            else:
                logger.error(f"Errore update UI: {e}")
        except Exception as e:
            logger.debug(f"Update fallito: {e}")

    def update_view_data(self, is_initial_load=False):
        # Popola il filtro sempre per aggiornare i mesi disponibili (sync is fast enough usually, or could be async too)
        self._popola_filtro_mese()

        utente_id = self.controller.get_user_id()
        if not utente_id:
            return

        utente = self.controller.page.session.get("utente_loggato")
        if not utente:
            print("ERRORE in PersonaleTab: utente non trovato in sessione.")
            return

        # Show loading
        self.main_view.visible = False
        self.loading_view.visible = True
        if self.controller.page:
            self._safe_update()

        # Ottieni anno e mese dal dropdown, o usa il mese corrente come default
        anno, mese = self._get_anno_mese_selezionato()
        master_key_b64 = self.controller.page.session.get("master_key")

        # Async fetch
        task = AsyncTask(
            target=self._fetch_data,
            args=(utente_id, anno, mese, master_key_b64),
            callback=partial(self._on_data_loaded, utente),
            error_callback=self._on_error
        )
        task.start()

    def _fetch_data(self, utente_id, anno, mese, master_key_b64):
        # --- Aggiorna i totali ---
        riepilogo = ottieni_riepilogo_patrimonio_utente(utente_id, anno, mese, master_key_b64=master_key_b64)
        
        # Carica le transazioni
        transazioni = ottieni_transazioni_utente(utente_id, anno, mese, master_key_b64=master_key_b64)
        # Filtra le transazioni di saldo iniziale
        transazioni_filtrate = [
            t for t in transazioni 
            if not t.get('descrizione', '').upper().startswith("SALDO INIZIALE")
        ]
        
        return {'riepilogo': riepilogo, 'transazioni': transazioni_filtrate}

    def _on_data_loaded(self, utente, result):
        riepilogo = result['riepilogo']
        self.transazioni_correnti = result['transazioni']
        loc = self.controller.loc
        
        # Create UI based on view mode
        if self.vista_compatta:
            self._costruisci_vista_compatta(utente, riepilogo, loc)
        else:
            self._costruisci_vista_espansa(utente, loc)

        # Hide loading
        self.loading_view.visible = False
        self.main_view.visible = True
        if self.controller.page:
            self._safe_update()

    def _on_error(self, e):
        print(f"Errore PersonaleTab: {e}")
        self.loading_view.visible = False
        self.main_view.controls = [AppStyles.body_text(f"Errore caricamento: {e}", color=AppColors.ERROR)]
        self.main_view.visible = True
        if self.controller.page:
            self._safe_update()

    def _costruisci_vista_compatta(self, utente, riepilogo, loc):
        """Costruisce la vista compatta con riepilogo e solo 4 transazioni."""
        val_patrimonio = riepilogo.get('patrimonio_netto', 0)
        val_liquidita = riepilogo.get('liquidita', 0)
        val_investimenti = riepilogo.get('investimenti', 0)
        val_fondi_pensione = riepilogo.get('fondi_pensione', 0)
        val_risparmio = riepilogo.get('risparmio', 0)
        # Recupera nuove chiavi con fallback
        val_patrimonio_immobile = riepilogo.get('patrimonio_immobile_lordo', 0)
        val_prestiti = riepilogo.get('prestiti_totali', 0)
        
        # Costruisci righe dettaglio
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
        righe_dettaglio.append(riga_resp(self.controller.loc.get("liquidity"), self.controller.loc.format_currency(val_liquidita)))
        
        if val_investimenti > 0:
            righe_dettaglio.append(riga_resp(self.controller.loc.get("investments"), self.controller.loc.format_currency(val_investimenti)))
        
        if val_fondi_pensione > 0:
             righe_dettaglio.append(riga_resp(self.controller.loc.get("pension_funds"), self.controller.loc.format_currency(val_fondi_pensione)))

        if val_risparmio > 0:
            righe_dettaglio.append(riga_resp(self.controller.loc.get("savings"), self.controller.loc.format_currency(val_risparmio)))
        
        if val_patrimonio_immobile > 0:
            righe_dettaglio.append(riga_resp(self.controller.loc.get("real_estate_assets"), self.controller.loc.format_currency(val_patrimonio_immobile)))

        if val_prestiti > 0:
            righe_dettaglio.append(riga_resp(self.controller.loc.get("loans"), self.controller.loc.format_currency(-val_prestiti), color=AppColors.ERROR))
        

        
        # --- Web Logic: Collapsible Details ---
        is_web = False
        try:
            from controllers.web_app_controller import WebAppController
            if isinstance(self.controller, WebAppController):
                 is_web = True
        except ImportError:
            pass

        content_dettagli = ft.Column(righe_dettaglio, spacing=5)
        
        icona_espandi = None
        if is_web:
            # Default hidden on web
            content_dettagli.visible = False
            
            def toggle_dettagli(e):
                content_dettagli.visible = not content_dettagli.visible
                e.control.icon = ft.Icons.KEYBOARD_ARROW_UP if content_dettagli.visible else ft.Icons.KEYBOARD_ARROW_DOWN
                self._safe_update()

            icona_espandi = ft.IconButton(
                icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                on_click=toggle_dettagli,
                tooltip="Mostra/Nascondi Dettagli"
            )

        # Card riepilogo patrimonio responsive
        header_patrimonio = ft.Column([
            AppStyles.caption_text(self.controller.loc.get("net_worth")),
            ft.Row([
                AppStyles.big_currency_text(self.controller.loc.format_currency(val_patrimonio),
                    color=AppColors.SUCCESS if val_patrimonio >= 0 else AppColors.ERROR),
                icona_espandi if icona_espandi else ft.Container()
            ], alignment=ft.MainAxisAlignment.START)
        ])

        card_riepilogo = AppStyles.card_container(
            content=ft.ResponsiveRow([
                # Colonna Totale
                ft.Column([header_patrimonio], col={"xs": 12, "sm": 12, "md": 5}),
                
                # Colonna Dettagli
                ft.Column([content_dettagli], col={"xs": 12, "sm": 12, "md": 7})
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20
        )
        
        # Usa il nome utente come titolo
        nome_utente = utente.get('nome', 'Utente')
        self.txt_bentornato.value = nome_utente
        
        # Ricostruisce l'interfaccia
        self.dd_mese_filtro.label = loc.get("filter_by_month")
        
        container_mese = ft.Container(
            content=self.dd_mese_filtro,
            padding=ft.padding.only(left=10, right=10, top=10)
        )

        area_riepilogo = ft.Column([card_riepilogo, container_mese], spacing=0)

        # Toggle Header for Web
        icona_global_collapser = None
        if is_web:
            area_riepilogo.visible = False # Default hidden on web as requested
            
            def toggle_area_riepilogo(e):
                area_riepilogo.visible = not area_riepilogo.visible
                e.control.icon = ft.Icons.KEYBOARD_ARROW_UP if area_riepilogo.visible else ft.Icons.KEYBOARD_ARROW_DOWN
                self._safe_update()
            
            icona_global_collapser = ft.IconButton(
                icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                on_click=toggle_area_riepilogo,
                tooltip="Espandi/Riduci Riepilogo"
            )

        # Pulsante per vedere tutte le transazioni
        btn_tutte_transazioni = ft.TextButton(
            loc.get("all_transactions"),
            icon=ft.Icons.LIST,
            on_click=self._mostra_tutte_transazioni
        )
        
        # Header delle transazioni Responsive
        header_transazioni = ft.ResponsiveRow([
            ft.Column([AppStyles.subheader_text(loc.get("latest_transactions"))], col={"xs": 12, "sm": 8}),
            ft.Column([btn_tutte_transazioni], col={"xs": 12, "sm": 4}, horizontal_alignment=ft.CrossAxisAlignment.END)
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        header_row_content = [ft.Container(AppStyles.section_header(nome_utente), expand=True)]
        if icona_global_collapser:
            header_row_content.append(icona_global_collapser)

        self.main_view.controls = [
            ft.Row(header_row_content, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            area_riepilogo,
            AppStyles.page_divider(),
            ft.Container(
                content=header_transazioni,
                padding=ft.padding.only(left=10, right=10, bottom=10)
            ),
            self.lista_transazioni
        ]

        # Costruisci le card delle transazioni (solo le prime 4)
        self._popola_lista_transazioni(limite=self.MAX_TRANSAZIONI_COMPATTE)

    def _costruisci_vista_espansa(self, utente, loc):
        """Costruisce la vista espansa con tutte le transazioni a pagina intera."""
        nome_utente = utente.get('nome', 'Utente')
        
        # Pulsante per tornare alla vista compatta
        btn_torna_indietro = ft.TextButton(
            loc.get("back"),
            icon=ft.Icons.ARROW_BACK,
            on_click=self._mostra_vista_compatta
        )
        
        # Header con pulsante indietro e filtro mese
        header = ft.Row([
            btn_torna_indietro,
            AppStyles.subheader_text(loc.get("all_transactions")),
            ft.Container(content=self.dd_mese_filtro, width=200)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        self.main_view.controls = [
            header,
            AppStyles.page_divider(),
            self.lista_transazioni
        ]

        # Costruisci le card di tutte le transazioni
        self._popola_lista_transazioni(limite=None)

    def _popola_lista_transazioni(self, limite=None):
        """Popola la lista transazioni con un limite opzionale."""
        loc = self.controller.loc
        self.lista_transazioni.controls.clear()
        
        transazioni_da_mostrare = self.transazioni_correnti
        if limite:
            transazioni_da_mostrare = self.transazioni_correnti[:limite]
        
        for t in transazioni_da_mostrare:
            azioni = ft.Row([
                ft.IconButton(icon=ft.Icons.EDIT, tooltip=loc.get("edit"), data=t,
                              on_click=lambda e: self.controller.transaction_dialog.apri_dialog_modifica_transazione(
                                  e.control.data),
                              icon_color=AppColors.INFO, icon_size=20),
                ft.IconButton(icon=ft.Icons.DELETE, tooltip=loc.get("delete"), data=t,
                              on_click=lambda e: self.controller.open_confirm_delete_dialog(
                                  partial(self.elimina_cliccato, e)),
                              icon_color=AppColors.ERROR, icon_size=20)
            ], spacing=0)

            # Formatta l'importo
            importo = t.get('importo', 0)
            if isinstance(importo, str):
                try:
                    importo = float(importo.replace(',', '.'))
                except:
                    importo = 0
            
            card_content = ft.ResponsiveRow(
                [
                    # Col 1: Descrizione e Conto (tutto spazio su mobile, metà su tablet/pc)
                    ft.Column([
                        AppStyles.body_text(t['descrizione']),
                        AppStyles.caption_text(f"{t['data']} - {t['nome_conto']}"),
                    ], col={"xs": 12, "sm": 6}, spacing=2),
                    
                    # Col 2: Importo e Categoria 
                    ft.Column([
                        AppStyles.currency_text(
                            loc.format_currency(importo),
                            color=AppColors.SUCCESS if importo >= 0 else AppColors.ERROR
                        ),
                        AppStyles.caption_text(t.get('nome_sottocategoria') or loc.get("no_category"))
                    ], col={"xs": 8, "sm": 4}, alignment=ft.MainAxisAlignment.END, horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
                    
                    # Col 3: Azioni (piccolo spazio a destra su mobile)
                    ft.Column([azioni], col={"xs": 4, "sm": 2}, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.END)
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
            
            self.lista_transazioni.controls.append(
                AppStyles.card_container(card_content, padding=10)
            )

    def _mostra_tutte_transazioni(self, e):
        """Passa alla vista espansa con tutte le transazioni."""
        self.vista_compatta = False
        self.update_view_data()

    def _mostra_vista_compatta(self, e):
        """Torna alla vista compatta."""
        self.vista_compatta = True
        self.update_view_data()

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
        self.update_view_data()

    def elimina_cliccato(self, e):
        transazione_data = e.control.data
        id_transazione = transazione_data.get('id_transazione')
        id_transazione_condivisa = transazione_data.get('id_transazione_condivisa')

        success = False
        if id_transazione and id_transazione > 0:
            success = elimina_transazione(id_transazione)
        elif id_transazione_condivisa and id_transazione_condivisa > 0:
            success = elimina_transazione_condivisa(id_transazione_condivisa)

        messaggio = "eliminata" if success else "errore nell'eliminazione"

        if success:
            self.controller.show_snack_bar(f"Transazione {messaggio}.", success=True)
            self.controller.db_write_operation()  # Esegue update e sync
        else:
            self.controller.show_snack_bar(f"Errore: {messaggio}.", success=False)