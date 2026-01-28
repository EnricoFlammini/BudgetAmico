import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_spese_fisse_famiglia,
    elimina_spesa_fissa,
    modifica_stato_spesa_fissa,
    aggiungi_transazione,
    aggiungi_transazione_condivisa,
    ottieni_tutti_i_conti_utente
)
from utils.async_task import AsyncTask
from utils.styles import AppStyles, AppColors, PageConstants
from datetime import datetime


class SpeseFisseTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page
        
        # Dati locali per gestire il resize senza ricaricare dal DB
        self.spese_fisse_local_data = []

        # Controlli UI
        # Container per il contenuto (Tabella o Lista Card)
        self.content_container = ft.Container(expand=True)
        
        self.no_data_view = ft.Container(
            content=AppStyles.body_text(self.controller.loc.get("no_fixed_expenses")),
            alignment=ft.Alignment(0, 0),
            expand=True,
            visible=False
        )

        # Loading view
        self.loading_view = ft.Container(
            content=ft.Column([
                ft.ProgressRing(color=AppColors.PRIMARY),
                AppStyles.body_text("Caricamento spese fisse...", color=AppColors.TEXT_SECONDARY)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment(0, 0),
            expand=True,
            visible=False
        )

        # Stack per alternare tra contenuto dati, loading e messaggio "nessun dato"
        self.data_stack = ft.Stack(
            controls=[
                self.content_container,
                self.no_data_view,
                self.loading_view
            ],
            expand=True
        )
        
        self.content = ft.Column(expand=True, spacing=10)

    def did_mount(self):
        # Sottoscrizione all'evento di resize della pagina
        if self.page:
            self.page.on_resized = self._on_page_resize

    def _on_page_resize(self, e):
        # Ridisegna la vista corrente usando i dati locali quando la pagina viene ridimensionata
        if self.spese_fisse_local_data:
             self._render_responsive_view()
             if self.page:
                 self.page.update()

    def update_view_data(self, is_initial_load=False):
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        self.content.controls = self.build_controls(theme)

        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return

        # Mostra loading
        self.content_container.visible = False
        self.no_data_view.visible = False
        self.loading_view.visible = True
        if self.controller.page:
            self.controller.page.update()

        master_key_b64 = self.controller.page.session.get("master_key")
        current_user_id = self.controller.get_user_id()
        
        # Async Task
        task = AsyncTask(
            target=self._fetch_data,
            args=(id_famiglia, master_key_b64, current_user_id),
            callback=self._on_data_loaded,
            error_callback=self._on_error
        )
        task.start()

    def _fetch_data(self, id_famiglia, master_key_b64, current_user_id):
        return ottieni_spese_fisse_famiglia(id_famiglia, master_key_b64, current_user_id)

    def _on_data_loaded(self, spese_fisse):
        self.loading_view.visible = False
        self.spese_fisse_local_data = [] # Reset

        if not spese_fisse:
            self.content_container.visible = False
            self.no_data_view.visible = True
        else:
            # Ottieni la lista di conti accessibili all'utente corrente
            master_key_b64 = self.controller.page.session.get("master_key")
            current_user_id = self.controller.get_user_id()
            conti_utente = ottieni_tutti_i_conti_utente(current_user_id, master_key_b64=master_key_b64)
            
            # Crea set di ID conti accessibili (separati per personale e condiviso)
            id_conti_personali_accessibili = set(
                c['id_conto'] for c in conti_utente if not c.get('is_condiviso')
            )
            id_conti_condivisi_accessibili = set(
                c['id_conto'] for c in conti_utente if c.get('is_condiviso')
            )
            
            # Arricchisci i dati con info permessi per usarli nel rendering
            self.spese_fisse_local_data = []
            for spesa in spese_fisse:
                ha_accesso = False
                if spesa.get('id_conto_personale_addebito'):
                    ha_accesso = spesa['id_conto_personale_addebito'] in id_conti_personali_accessibili
                elif spesa.get('id_conto_condiviso_addebito'):
                    ha_accesso = spesa['id_conto_condiviso_addebito'] in id_conti_condivisi_accessibili
                
                spesa['ha_accesso'] = ha_accesso
                self.spese_fisse_local_data.append(spesa)
            
            self.content_container.visible = True
            self.no_data_view.visible = False
            
            self._render_responsive_view()

        if self.page:
            self.page.update()

    def _render_responsive_view(self):
        """Sceglie quale vista renderizzare in base alla larghezza della pagina."""
        if not self.page: return
        
        # Su web usa sempre la vista mobile cards
        is_web = False
        try:
            from controllers.web_app_controller import WebAppController
            if isinstance(self.controller, WebAppController):
                is_web = True
        except ImportError:
            pass
        
        is_mobile = is_web  # Su web sempre mobile
        if not is_mobile:
            is_mobile = self.page.width < 600  # Fallback per desktop
        
        if is_mobile:
            self.content_container.content = self._build_mobile_view(self.spese_fisse_local_data)
        else:
            self.content_container.content = self._build_desktop_view(self.spese_fisse_local_data)

    def _build_desktop_view(self, spese_fisse):
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        loc = self.controller.loc
        
        dt_spese_fisse = ft.DataTable(
            columns=[
                ft.DataColumn(AppStyles.data_text(loc.get("name"))),
                ft.DataColumn(AppStyles.data_text(loc.get("amount")), numeric=True),
                ft.DataColumn(AppStyles.data_text(loc.get("account"))),
                ft.DataColumn(AppStyles.data_text(loc.get("debit_day"))),
                ft.DataColumn(AppStyles.data_text(loc.get("active"))),
                ft.DataColumn(AppStyles.data_text(loc.get("actions"))),
            ],
            heading_row_color=AppColors.SURFACE_VARIANT,
            data_row_color={"hovered": ft.Colors.with_opacity(0.1, theme.primary)},
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            heading_row_height=40,
            data_row_max_height=60,
            border_radius=10,
            expand=True
        )

        for spesa in spese_fisse:
            ha_accesso = spesa.get('ha_accesso', False)
            
            dt_spese_fisse.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(AppStyles.data_text(spesa['nome'])),
                    ft.DataCell(AppStyles.body_text(self.controller.loc.format_currency(spesa['importo']))),
                    ft.DataCell(AppStyles.body_text(spesa['nome_conto'])),
                    ft.DataCell(AppStyles.body_text(str(spesa['giorno_addebito']))),
                    ft.DataCell(ft.Switch(
                        value=bool(spesa['attiva']), 
                        data=spesa['id_spesa_fissa'], 
                        on_change=self._cambia_stato_attiva,
                        disabled=not ha_accesso
                    )),
                    ft.DataCell(ft.Row([
                        # Icona addebito automatico
                        ft.Icon(
                            name=ft.Icons.AUTO_MODE if spesa.get('addebito_automatico') else ft.Icons.BLOCK,
                            color=AppColors.SUCCESS if spesa.get('addebito_automatico') else ft.Colors.GREY_400,
                            size=20,
                            tooltip="Addebito automatico attivo" if spesa.get('addebito_automatico') else "Addebito automatico disattivato"
                        ),
                        ft.IconButton(
                            icon=ft.Icons.PAYMENT, 
                            tooltip="Paga" if ha_accesso else "Non hai accesso a questo conto", 
                            data=spesa,
                            icon_color=AppColors.SUCCESS if ha_accesso else ft.Colors.GREY_400,
                            disabled=not ha_accesso,
                            on_click=self._paga_spesa_fissa
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT, 
                            tooltip=self.controller.loc.get("edit") if ha_accesso else "Non hai accesso a questo conto", 
                            data=spesa,
                            icon_color=AppColors.PRIMARY if ha_accesso else ft.Colors.GREY_400,
                            disabled=not ha_accesso,
                            on_click=lambda e: self.controller.spesa_fissa_dialog.apri_dialog(e.control.data)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE, 
                            tooltip=self.controller.loc.get("delete") if ha_accesso else "Non hai accesso a questo conto", 
                            icon_color=AppColors.ERROR if ha_accesso else ft.Colors.GREY_400,
                            disabled=not ha_accesso,
                            data=spesa['id_spesa_fissa'],
                            on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.elimina_cliccato, e))
                        ),
                    ])),
                ])
            )
        
        return ft.Column([dt_spese_fisse], scroll=ft.ScrollMode.ADAPTIVE, expand=True)

    def _build_mobile_view(self, spese_fisse):
        """Costruisce una lista di schede per la visualizzazione mobile."""
        cards = []
        for spesa in spese_fisse:
            ha_accesso = spesa.get('ha_accesso', False)
            
            # Contenuto della card
            card_content = ft.Column([
                # Header Card: Nome e Importo
                ft.Row([
                    ft.Column([
                        AppStyles.subheader_text(spesa['nome']),
                        AppStyles.small_text(spesa['nome_conto'])
                    ], expand=True),
                    ft.Column([
                         AppStyles.data_text(self.controller.loc.format_currency(spesa['importo']), 
                                            color=AppColors.PRIMARY, size=16),
                         AppStyles.small_text(f"Giorno: {spesa['giorno_addebito']}")
                    ], alignment=ft.MainAxisAlignment.END, horizontal_alignment=ft.CrossAxisAlignment.END)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Divider(height=10, color=ft.Colors.OUTLINE_VARIANT),
                
                # Azioni e controlli
                ft.Row([
                    # Switch Attivo
                    ft.Row([
                        ft.Switch(
                            value=bool(spesa['attiva']), 
                            data=spesa['id_spesa_fissa'], 
                            on_change=self._cambia_stato_attiva,
                            disabled=not ha_accesso,
                            scale=0.8
                        ),
                         AppStyles.small_text("Attiva")
                    ]),
                    
                    ft.Row([
                        # Icona addebito automatico (solo visualizzazione)
                        ft.Container(
                            content=ft.Icon(ft.Icons.AUTO_MODE, color=AppColors.SUCCESS, size=20),
                            tooltip="Addebito automatico attivo",
                            padding=5,
                            visible=bool(spesa.get('addebito_automatico'))
                        ),

                        ft.IconButton(
                            icon=ft.Icons.PAYMENT, 
                            tooltip="Paga", 
                            data=spesa,
                            icon_color=AppColors.SUCCESS if ha_accesso else ft.Colors.GREY_400,
                            disabled=not ha_accesso,
                            on_click=self._paga_spesa_fissa,
                            icon_size=20
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT, 
                            tooltip="Modifica", 
                            data=spesa,
                            icon_color=AppColors.PRIMARY if ha_accesso else ft.Colors.GREY_400,
                            disabled=not ha_accesso,
                            on_click=lambda e: self.controller.spesa_fissa_dialog.apri_dialog(e.control.data),
                             icon_size=20
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE, 
                            tooltip="Elimina", 
                            icon_color=AppColors.ERROR if ha_accesso else ft.Colors.GREY_400,
                            disabled=not ha_accesso,
                            data=spesa['id_spesa_fissa'],
                            on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.elimina_cliccato, e)),
                             icon_size=20
                        ),
                    ], spacing=0)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], spacing=5)
            
            cards.append(AppStyles.card_container(content=card_content))

        return ft.ListView(controls=cards, spacing=10, padding=10, expand=True)

    def _on_error(self, e):
        print(f"Errore caricamento spese fisse: {e}")
        self.loading_view.visible = False
        self.no_data_view.content = AppStyles.body_text(f"Errore: {e}", color=AppColors.ERROR)
        self.no_data_view.visible = True
        if self.page:
            self.page.update()

    def build_controls(self, theme):
        loc = self.controller.loc
        return [
            ft.Row([
                AppStyles.title_text(loc.get("fixed_expenses_management")),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            AppStyles.page_divider(),
            self.data_stack
        ]

    def elimina_cliccato(self, e):
        id_spesa = e.control.data
        if elimina_spesa_fissa(id_spesa):
            self.controller.show_snack_bar("Spesa fissa eliminata.", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("❌ Errore durante l'eliminazione.", success=False)

    def _cambia_stato_attiva(self, e):
        id_spesa = e.control.data
        nuovo_stato = e.control.value
        if modifica_stato_spesa_fissa(id_spesa, nuovo_stato):
            self.controller.show_snack_bar("Stato aggiornato.", success=True)
        else:
            self.controller.show_snack_bar("❌ Errore durante l'aggiornamento dello stato.", success=False)
            e.control.value = not nuovo_stato
            if self.page:
                self.page.update()

    def _paga_spesa_fissa(self, e):
        """Crea una transazione per pagare la spesa fissa."""
        spesa = e.control.data
        try:
            # Prepara i dati per la transazione
            data_oggi = datetime.now().strftime("%Y-%m-%d")
            # Usa lo stesso suffisso del sistema automatico per evitare duplicati
            suffisso_id = f"[SF-{spesa['id_spesa_fissa']}]"
            descrizione = f"Spesa Fissa: {spesa['nome']} {suffisso_id}"
            importo = -abs(spesa['importo'])  # Negativo perché è un'uscita
            id_sottocategoria = spesa.get('id_sottocategoria')
            
            # Determina se è un conto personale o condiviso
            success = False
            if spesa['id_conto_personale_addebito']:
                # Transazione su conto personale
                master_key_b64 = self.controller.page.session.get("master_key")
                success = aggiungi_transazione(
                    id_conto=spesa['id_conto_personale_addebito'],
                    data=data_oggi,
                    descrizione=descrizione,
                    importo=importo,
                    id_sottocategoria=id_sottocategoria,
                    master_key_b64=master_key_b64
                )
            elif spesa['id_conto_condiviso_addebito']:
                # Transazione su conto condiviso
                id_utente = self.controller.get_user_id()
                master_key_b64 = self.controller.page.session.get("master_key")
                success = aggiungi_transazione_condivisa(
                    id_utente_autore=id_utente,
                    id_conto_condiviso=spesa['id_conto_condiviso_addebito'],
                    data=data_oggi,
                    descrizione=descrizione,
                    importo=importo,
                    id_sottocategoria=id_sottocategoria,
                    master_key_b64=master_key_b64
                )
            
            if success:
                self.controller.show_snack_bar(f"✅ Pagamento registrato: {spesa['nome']}", success=True)
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("❌ Errore durante la registrazione del pagamento.", success=False)
                
        except Exception as ex:
            print(f"Errore pagamento spesa fissa: {ex}")
            self.controller.show_snack_bar(f"❌ Errore: {ex}", success=False)