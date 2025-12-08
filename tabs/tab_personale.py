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
from utils.styles import AppStyles, AppColors, PageConstants


class PersonaleTab(ft.Container):
    # Numero di transazioni da mostrare nella vista compatta
    MAX_TRANSAZIONI_COMPATTE = 4
    
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)

        self.controller = controller
        self.page = controller.page
        
        # Stato: True = vista compatta (riepilogo + 4 transazioni), False = vista espansa (tutte le transazioni)
        self.vista_compatta = True
        
        # Cache delle transazioni per evitare query multiple
        self.transazioni_correnti = []

        self.txt_bentornato = AppStyles.subheader_text("")
        self.txt_patrimonio = AppStyles.header_text("")
        self.txt_liquidita = AppStyles.caption_text("")

        # Filtro per mese
        self.dd_mese_filtro = ft.Dropdown(
            on_change=self._filtro_mese_cambiato,
            border_color=ft.Colors.OUTLINE,
            text_size=14,
            content_padding=10
        )

        self.lista_transazioni = ft.Column(
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
            spacing=10
        )

        self.content = ft.Column(expand=True)

    def update_view_data(self, is_initial_load=False):
        # Popola il filtro sempre per aggiornare i mesi disponibili
        self._popola_filtro_mese()

        utente_id = self.controller.get_user_id()
        if not utente_id:
            return

        utente = self.controller.page.session.get("utente_loggato")
        if not utente:
            print("ERRORE in PersonaleTab: utente non trovato in sessione.")
            return

        # Ottieni anno e mese dal dropdown, o usa il mese corrente come default
        anno, mese = self._get_anno_mese_selezionato()

        # --- Aggiorna i totali usando la funzione centralizzata ---
        master_key_b64 = self.controller.page.session.get("master_key")
        riepilogo = ottieni_riepilogo_patrimonio_utente(utente_id, anno, mese, master_key_b64=master_key_b64)
        
        # Estrai i valori
        val_patrimonio = riepilogo.get('patrimonio_netto', 0)
        val_liquidita = riepilogo.get('liquidita', 0)
        val_investimenti = riepilogo.get('investimenti', 0)
        val_fondi_pensione = riepilogo.get('fondi_pensione', 0)
        val_risparmio = riepilogo.get('risparmio', 0)
        
        loc = self.controller.loc
        
        # Carica le transazioni e cachele
        self.transazioni_correnti = ottieni_transazioni_utente(utente_id, anno, mese, master_key_b64=master_key_b64)
        # Filtra le transazioni di saldo iniziale
        self.transazioni_correnti = [
            t for t in self.transazioni_correnti 
            if not t.get('descrizione', '').upper().startswith("SALDO INIZIALE")
        ]

        if self.vista_compatta:
            self._costruisci_vista_compatta(utente, riepilogo, loc)
        else:
            self._costruisci_vista_espansa(utente, loc)

        if self.page:
            self.page.update()

    def _costruisci_vista_compatta(self, utente, riepilogo, loc):
        """Costruisce la vista compatta con riepilogo e solo 4 transazioni."""
        val_patrimonio = riepilogo.get('patrimonio_netto', 0)
        val_liquidita = riepilogo.get('liquidita', 0)
        val_investimenti = riepilogo.get('investimenti', 0)
        val_fondi_pensione = riepilogo.get('fondi_pensione', 0)
        val_risparmio = riepilogo.get('risparmio', 0)
        
        # Costruisci il riepilogo schematico
        righe_dettaglio = []
        
        # Liquidità (sempre visibile)
        righe_dettaglio.append(ft.Row([
            AppStyles.body_text(loc.get("liquidity")),
            AppStyles.currency_text(loc.format_currency(val_liquidita))
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        
        # Risparmio (se presente)
        if val_risparmio > 0:
            righe_dettaglio.append(ft.Row([
                AppStyles.body_text(loc.get("savings")),
                AppStyles.currency_text(loc.format_currency(val_risparmio))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        
        # Investimenti (se presenti)
        if val_investimenti > 0:
            righe_dettaglio.append(ft.Row([
                AppStyles.body_text(loc.get("investments")),
                AppStyles.currency_text(loc.format_currency(val_investimenti))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        
        # Fondi Pensione (se presenti)
        if val_fondi_pensione > 0:
            righe_dettaglio.append(ft.Row([
                AppStyles.body_text(loc.get("pension_funds")),
                AppStyles.currency_text(loc.format_currency(val_fondi_pensione))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        
        # Usa il nome utente come titolo
        nome_utente = utente.get('nome', 'Utente')
        self.txt_bentornato.value = nome_utente
        
        # Costruisci la card del riepilogo
        card_riepilogo = AppStyles.card_container(
            content=ft.Row([
                # Colonna sinistra: Patrimonio Netto grande
                ft.Column([
                    AppStyles.caption_text(loc.get("net_worth")),
                    AppStyles.big_currency_text(loc.format_currency(val_patrimonio),
                        color=AppColors.SUCCESS if val_patrimonio >= 0 else AppColors.ERROR)
                ], expand=1),
                # Colonna destra: dettagli in righe
                ft.Column(righe_dettaglio, spacing=8, expand=2, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=20
        )
        
        # Ricostruisce l'interfaccia
        self.dd_mese_filtro.label = loc.get("filter_by_month")
        
        # Pulsante per vedere tutte le transazioni
        btn_tutte_transazioni = ft.TextButton(
            loc.get("all_transactions"),
            icon=ft.Icons.LIST,
            on_click=self._mostra_tutte_transazioni
        )
        
        # Header delle transazioni con pulsante
        header_transazioni = ft.Row([
            AppStyles.subheader_text(loc.get("latest_transactions")),
            btn_tutte_transazioni
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        self.content.controls = [
            AppStyles.section_header(nome_utente),
            card_riepilogo,
            ft.Container(
                content=self.dd_mese_filtro,
                padding=ft.padding.only(left=10, right=10, top=10)
            ),
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
        
        self.content.controls = [
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
            
            card_content = ft.Row(
                [
                    ft.Column([
                        AppStyles.body_text(t['descrizione']),
                        AppStyles.caption_text(f"{t['data']} - {t['nome_conto']}"),
                    ], expand=True),
                    ft.Column([
                        AppStyles.currency_text(
                            loc.format_currency(importo),
                            color=AppColors.SUCCESS if importo >= 0 else AppColors.ERROR
                        ),
                        AppStyles.caption_text(t.get('nome_sottocategoria') or loc.get("no_category"))
                    ], horizontal_alignment=ft.CrossAxisAlignment.END),
                    azioni
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

    def build_controls(self):
        """Non più usato - i controlli sono costruiti in update_view_data."""
        return []

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
        self.page.update()

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