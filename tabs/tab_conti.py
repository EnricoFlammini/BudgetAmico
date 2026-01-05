import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_dettagli_conti_utente,
    elimina_conto,
    ottieni_riepilogo_patrimonio_utente,
    ottieni_conti_condivisi_famiglia,
    elimina_conto_condiviso,
    ottieni_prima_famiglia_utente # Add helper to get family id
)
import datetime
from utils.async_task import AsyncTask
from utils.styles import AppStyles, AppColors, PageConstants


class ContiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page

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
            AppStyles.section_header(
                loc.get("my_accounts"), # Use generic "Miei Conti" (need to ensure translation exists or use string)
                ft.IconButton(
                    icon=ft.Icons.ADD_CARD,
                    tooltip=loc.get("add_account"),
                    on_click=lambda e: self.controller.conto_dialog.apri_dialog_conto(e, escludi_investimento=True),
                    icon_color=theme.primary
                )
            ),
            AppStyles.page_divider(),
            self.lv_conti,
            ft.Container(height=50) # Spacer at bottom
        ]

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
        
        # Fetch Shared Accounts
        condivisi = []
        id_famiglia = ottieni_prima_famiglia_utente(utente_id)
        if id_famiglia:
            condivisi = ottieni_conti_condivisi_famiglia(id_famiglia, utente_id, master_key_b64=master_key_b64)
            
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
            
            # Col 2: Saldo
            ft.Column([
                AppStyles.caption_text(label_saldo),
                AppStyles.currency_text(self.controller.loc.format_currency(conto['saldo_calcolato']), color=colore_saldo)
            ], col={"xs": 6, "sm": 3}, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.END if not is_investimento else ft.CrossAxisAlignment.START),
            
            # Col 3: Azioni
            ft.Column([
                ft.Row([
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

        return AppStyles.card_container(content, padding=15)

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