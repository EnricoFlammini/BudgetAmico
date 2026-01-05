import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_dettagli_conti_utente,
    elimina_conto,
    ottieni_riepilogo_patrimonio_utente,
    ottieni_conti_condivisi_famiglia,
    elimina_conto_condiviso,
    ottieni_prima_famiglia_utente, # Add helper to get family id
    ottieni_salvadanai_conto,
    crea_salvadanaio
)
import datetime
from utils.async_task import AsyncTask
from utils.styles import AppStyles, AppColors, PageConstants


class ContiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page

        # --- Dialog Crea Salvadanaio ---
        self.dialog_crea_salvadanaio = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nuovo Salvadanaio"),
            actions=[
                ft.TextButton("Annulla", on_click=self._chiudi_dialog_salvadanaio),
                ft.TextButton("Crea", on_click=self._salva_nuovo_salvadanaio)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.tf_nome_salvadanaio = ft.TextField(label="Nome Salvadanaio", width=300)
        self.tf_nome_salvadanaio = ft.TextField(label="Nome Salvadanaio", width=300)
        self.current_conto_id_for_sb = None

        # Controlli UI
        # Unica lista scrollabile per tutti i conti
        self.lv_conti = ft.Column(spacing=10) 
        
        # Loading view (inline spinner)
        self.loading_view = ft.Container(
            content=ft.Column([
                ft.ProgressRing(color=AppColors.PRIMARY),
                AppStyles.body_text(self.controller.loc.get("loading"), color=AppColors.TEXT_SECONDARY)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment(0, 0),
            expand=True,
            visible=False
        )

        # Main content - Scrollable Column
        self.main_view = ft.Column(
            expand=True, 
            spacing=10, 
            scroll=ft.ScrollMode.HIDDEN # Use hidden scroll to avoid double scrollbars if parent handles it, but here we want scrolling.
        )
        # Actually, let's set scroll on main_view so the whole page scrolls.
        self.main_view.scroll = ft.ScrollMode.ADAPTIVE

        # Stack to switch between content and loading
        self.content = ft.Stack([
            self.main_view,
            self.loading_view
        ], expand=True)


    def update_view_data(self, is_initial_load=False):
        # Get master_key from session for encryption
        master_key_b64 = self.controller.page.session.get("master_key")
        
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        loc = self.controller.loc

        # Setup main view structure
        self.main_view.controls = [
            ft.Row([
                AppStyles.title_text("Conti"),
                ft.IconButton(
                    icon=ft.Icons.ADD_CARD,
                    tooltip=loc.get("add_account"),
                    on_click=lambda e: self.controller.conto_dialog.apri_dialog_conto(e, escludi_investimento=True),
                    icon_color=theme.primary
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            AppStyles.page_divider(),
            self.lv_conti,
            ft.Container(height=50) # Spacer at bottom
        ]
        self.main_view.alignment = ft.MainAxisAlignment.START

        utente_id = self.controller.get_user_id()
        if not utente_id: return

        # Show loading
        self.main_view.visible = False
        self.loading_view.visible = True
        if self.controller.page:
            self.controller.page.update()

        # Async fetch
        task = AsyncTask(
            target=self._fetch_data,
            args=(utente_id, master_key_b64),
            callback=partial(self._on_data_loaded, theme),
            error_callback=self._on_error
        )
        task.start()

    def _fetch_data(self, utente_id, master_key_b64):
        conti = ottieni_dettagli_conti_utente(utente_id, master_key_b64=master_key_b64)
        personali = [c for c in conti if c['tipo'] not in ['Investimento', 'Carta di Credito']]
        
        id_famiglia = ottieni_prima_famiglia_utente(utente_id)
        
        if id_famiglia:
            for c in personali:
                c['salvadanai'] = ottieni_salvadanai_conto(c['id_conto'], id_famiglia, master_key_b64, utente_id, is_condiviso=False)
        
        # Fetch Shared Accounts
        condivisi = []
        if id_famiglia:
            condivisi = ottieni_conti_condivisi_famiglia(id_famiglia, utente_id, master_key_b64=master_key_b64)
            # Fetch Salvadanai for shared accounts too? Assuming logic applies same way.
            for c in condivisi:
                 c['salvadanai'] = ottieni_salvadanai_conto(c['id_conto'], id_famiglia, master_key_b64, utente_id, is_condiviso=True)
            
        return personali, condivisi

    def _on_data_loaded(self, theme, result):
        conti_personali, conti_condivisi = result
        loc = self.controller.loc
        self.lv_conti.controls.clear()
        
        has_accounts = False

        # Personal Accounts
        if conti_personali:
            # self.lv_conti.controls.append(ft.Text("Personali", weight="bold")) # Optional label? User said remove page "Shared", implies unified list.
            for conto in conti_personali:
                self.lv_conti.controls.append(self._crea_widget_conto(conto, theme, is_shared=False))
            has_accounts = True

        # Shared Accounts
        if conti_condivisi:
            # self.lv_conti.controls.append(ft.Divider())
            # self.lv_conti.controls.append(ft.Text("Condivisi", weight="bold"))
            for conto in conti_condivisi:
                self.lv_conti.controls.append(self._crea_widget_conto(conto, theme, is_shared=True))
            has_accounts = True

        if not has_accounts:
             self.lv_conti.controls.append(AppStyles.body_text(loc.get("no_accounts_yet")))

        # Hide loading
        self.loading_view.visible = False
        self.main_view.visible = True
        if self.controller.page:
            self.controller.page.update()

    def _on_error(self, e):
        print(f"Errore ContiTab: {e}")
        self.loading_view.visible = False
        self.main_view.controls = [AppStyles.body_text(f"Errore caricamento: {e}", color=AppColors.ERROR)]
        self.main_view.visible = True
        if self.controller.page:
            self.controller.page.update()

    def build_controls(self, theme):
        # Deprecated
        return []

    def _crea_widget_conto(self, conto: dict, theme, is_shared: bool = False) -> ft.Container:
        is_investimento = conto['tipo'] == 'Investimento'
        is_fondo_pensione = conto['tipo'] == 'Fondo Pensione'

        is_admin = self.controller.get_user_role() == 'admin'
        is_corrente = conto['tipo'] in ['Corrente', 'Risparmio', 'Contanti']

        label_saldo = self.controller.loc.get(
            "value") if is_investimento or is_fondo_pensione else self.controller.loc.get("current_balance")
        
        # I fondi pensione usano verde/rosso come i conti correnti
        # Solo gli investimenti usano il colore secondario
        if is_investimento:
            colore_saldo = theme.secondary
        else:
            colore_saldo = AppColors.SUCCESS if conto['saldo_calcolato'] >= 0 else AppColors.ERROR

        content = ft.ResponsiveRow([
            # Col 1: Nome Conto e IBAN
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.GROUP if is_shared else ft.Icons.PERSON, size=16, color=theme.outline),
                    AppStyles.subheader_text(conto['nome_conto']),
                ], spacing=5, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                AppStyles.caption_text(f"{conto['tipo']}" + 
                                       (f" - IBAN: {conto['iban']}" if not is_shared and conto.get('iban') else "") + 
                                       (" - Conto Condiviso" if is_shared else ""))
            ], col={"xs": 12, "sm": 6}, spacing=2),
            
            # Col 2: Saldo & Breakdown
            ft.Column([
                # Main Balance (Liquidity + Savings PBs + Liquidity PBs ?? No. "Saldo Attuale" usually means Available.)
                # User wants "Totale", "Liquidità", "Risparmio"
                
                # Calculate breakdown
                self._build_saldo_breakdown(conto, theme, is_investimento)
                
            ], col={"xs": 6, "sm": 3}, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.END if not is_investimento else ft.CrossAxisAlignment.START),
            
            # Col 3: Azioni
            ft.Column([
                ft.Row([
                    ft.IconButton(icon=ft.Icons.SAVINGS, tooltip="Crea Salvadanaio", 
                                  icon_color=ft.Colors.PINK_400, data=(conto['id_conto'], is_shared),
                                  on_click=self._apri_dialog_salvadanaio,
                                  visible=not is_investimento), # No PB for investments for now
                    ft.IconButton(icon=ft.Icons.INSIGHTS, tooltip=self.controller.loc.get("manage_portfolio"),
                                  icon_color=theme.primary, data=conto,
                                  on_click=lambda e: self.controller.portafoglio_dialogs.apri_dialog_portafoglio(e,
                                                                                                                  e.control.data),
                                  visible=is_investimento),
                    ft.IconButton(icon=ft.Icons.MANAGE_ACCOUNTS, tooltip=self.controller.loc.get("manage_pension_fund"),
                                  icon_color=theme.secondary, data=conto,
                                  on_click=lambda e: self.controller.fondo_pensione_dialog.apri_dialog(e.control.data),
                                  visible=is_fondo_pensione),
                    ft.IconButton(icon=ft.Icons.EDIT_NOTE, tooltip="Rettifica Saldo (Admin)", data=conto,
                                  on_click=lambda e: self.controller.conto_dialog.apri_dialog_rettifica_saldo(
                                      e.control.data), visible=is_admin and is_corrente),
                    ft.IconButton(icon=ft.Icons.EDIT, tooltip=self.controller.loc.get("edit_account"), data=conto,
                                  on_click=lambda e: self.controller.conto_dialog.apri_dialog_conto(e, e.control.data, escludi_investimento=True, is_shared_edit=is_shared),
                                  icon_color=AppColors.INFO),
                    ft.IconButton(icon=ft.Icons.DELETE, tooltip=self.controller.loc.get("delete_account"),
                                  icon_color=AppColors.ERROR, data=(conto['id_conto'], is_shared),
                                  on_click=lambda e: self.controller.open_confirm_delete_dialog(
                                      partial(self.elimina_conto_cliccato, e))),
                ], alignment=ft.MainAxisAlignment.END, spacing=0)
            ], col={"xs": 6, "sm": 3}, alignment=ft.MainAxisAlignment.CENTER)
            
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # Add Piggy Banks Chips if present
        salvadanai_controls = []
        if 'salvadanai' in conto and conto['salvadanai']:
            for s in conto['salvadanai']:
                salvadanai_controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.SAVINGS, size=12, color=ft.Colors.PINK_400),
                            ft.Text(f"{s['nome']}: {self.controller.loc.format_currency(s['importo'])}", size=10, weight=ft.FontWeight.BOLD)
                        ], spacing=2),
                        bgcolor=ft.Colors.PINK_50,
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        border_radius=10,
                        border=ft.border.all(1, ft.Colors.PINK_200)
                    )
                )

        final_content = content
        if salvadanai_controls:
            final_content = ft.Column([
                content,
                ft.Row(salvadanai_controls, wrap=True, spacing=5)
            ], spacing=5)

        return AppStyles.card_container(final_content, padding=15)

    def _build_saldo_breakdown(self, conto, theme, is_investimento):
        saldo_db = conto['saldo_calcolato']
        
        if is_investimento:
             return ft.Column([
                AppStyles.caption_text(self.controller.loc.get("value")),
                AppStyles.currency_text(self.controller.loc.format_currency(saldo_db), color=theme.secondary)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.START)
            
        # For standard accounts:
        # Calculate Liquidity vs Savings PBs
        pb_liquidita = 0.0
        pb_risparmio = 0.0
        
        if 'salvadanai' in conto:
            for s in conto['salvadanai']:
                if s.get('incide_su_liquidita', False):
                    pb_liquidita += s['importo']
                else:
                    pb_risparmio += s['importo']
        
        # Logic:
        # Saldo DB = Available (Soldi veri sul conto) - (Transazioni verso PBs)??
        # WAIT. esegui_giroconto_salvadanaio creates a transaction.
        # So 'saldo_db' ALREADY excludes money moved to PBs? YES.
        # Example: 1000 initial. Move 200 to PB. Transaction -200. Saldo DB = 800. PB = 200.
        #
        # User wants:
        # Totale: 1000 (800 + 200) -- The physical money
        # Liquidità: ? If PB is liquidity -> 800 + 200 = 1000? Or just 800? 
        #   "Incide su liquidità" means it counts as available.
        #   So Liquidità = Saldo DB (Free) + PB (Liq).
        # Risparmio: PB (Savings).
        
        totale_fisico = saldo_db + pb_liquidita + pb_risparmio
        liquidita_totale = saldo_db + pb_liquidita
        risparmio_totale = pb_risparmio
        
        colore_saldo = AppColors.SUCCESS if liquidita_totale >= 0 else AppColors.ERROR
        
        return ft.Column([
            # Totale
             ft.Row([
                ft.Text("Totale:", size=10, color="grey"),
                ft.Text(self.controller.loc.format_currency(totale_fisico), size=10, weight="bold")
            ], spacing=5, alignment=ft.MainAxisAlignment.END),
            
            # Liquidità (Main View)
            AppStyles.currency_text(self.controller.loc.format_currency(liquidita_totale), color=colore_saldo, size=16),
            AppStyles.caption_text("Liquidità Disponibile"),
            
            # Risparmio (small if present)
            ft.Row([
                ft.Icon(ft.Icons.SAVINGS, size=12, color=ft.Colors.PINK_400),
                ft.Text(f"Risparmio: {self.controller.loc.format_currency(risparmio_totale)}", size=11, color=ft.Colors.PINK_400)
            ], spacing=2, alignment=ft.MainAxisAlignment.END, visible=risparmio_totale > 0)
            
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.END)

    def _apri_dialog_salvadanaio(self, e):
        # Data is tuple (id_conto, is_shared)
        if isinstance(e.control.data, tuple):
             self.current_conto_id_for_sb = e.control.data
        else:
             # Legacy/Fallback
             self.current_conto_id_for_sb = (e.control.data, False)

        self.tf_nome_salvadanaio.value = ""
        self.tf_nome_salvadanaio.value = ""
        
        self.dialog_crea_salvadanaio.content = ft.Container(
            content=ft.Column([
                ft.Text("Nuovo salvadanaio per questo conto.", size=14),
                ft.Container(height=10),
                self.tf_nome_salvadanaio,
                ft.Container(height=10),
                ft.Text("Il salvadanaio verrà creato vuoto.\nUsa la funzione 'Giroconto' per versare fondi.", size=11, color="grey", italic=True)
            ], tight=True),
            width=350,
            padding=10
        )
        
        self.controller.page.open(self.dialog_crea_salvadanaio)

    def _chiudi_dialog_salvadanaio(self, e):
        self.controller.page.close(self.dialog_crea_salvadanaio)

    def _salva_nuovo_salvadanaio(self, e):
        nome = self.tf_nome_salvadanaio.value
            
        if not nome: return
        
        id_famiglia = self.controller.get_family_id()
        id_utente = self.controller.get_user_id()
        master_key = self.controller.page.session.get("master_key")
        
        id_conto, is_shared = self.current_conto_id_for_sb
        
        self.controller.show_loading("Creazione salvadanaio...")
        
        # Force creation with 0 amount first to avoid ghost money
        success = crea_salvadanaio(
            id_famiglia, nome, 0.0, # Start with 0 
            id_conto=id_conto if not is_shared else None, 
            id_conto_condiviso=id_conto if is_shared else None,  
            master_key_b64=master_key, 
            id_utente=id_utente,
            incide_su_liquidita=False # Default to Savings (False)
        )
        # REMOVED: Automatic Transfer Logic. PBs are created empty.
        
        self.controller.hide_loading()
        
        self._chiudi_dialog_salvadanaio(None)
        if success:
            self.controller.show_snack_bar("Salvadanaio creato!", success=True)
            self.update_view_data()
        else:
             self.controller.show_snack_bar("Errore creazione salvadanaio.", success=False)

    def elimina_conto_cliccato(self, e):
        # Data is tuple (id, is_shared)
        id_conto, is_shared = e.control.data
        utente_id = self.controller.get_user_id()
        
        if is_shared:
             # Logic for shared account deletion (requires implementing/importing elimina_conto_condiviso)
             risultato = elimina_conto_condiviso(id_conto)
             if risultato is True:
                self.controller.show_snack_bar("Conto condiviso eliminato.", success=True)
                self.controller.db_write_operation()
             else:
                 self.controller.show_error_dialog("Errore durante l'eliminazione del conto condiviso.")
        else:
            risultato = elimina_conto(id_conto, utente_id)

            if risultato is True:
                self.controller.show_snack_bar("Conto personale e dati collegati eliminati.", success=True)
                self.controller.db_write_operation()
            elif risultato == "NASCOSTO":
                # Il conto è stato nascosto (ha transazioni ma saldo = 0)
                self.controller.show_snack_bar("✅ Conto nascosto. Le transazioni storiche sono state mantenute.", success=True)
                self.controller.db_write_operation()
            elif risultato == "SALDO_NON_ZERO":
                self.controller.show_snack_bar("❌ Errore: Il saldo/valore del conto non è 0.", success=False)
            elif isinstance(risultato, tuple) and not risultato[0]:
                # Nuovo: gestisce l'errore restituito dal DB e mostra il popup
                self.controller.show_error_dialog(risultato[1])
            else:
                self.controller.show_error_dialog("Si è verificato un errore sconosciuto durante l'eliminazione del conto.")