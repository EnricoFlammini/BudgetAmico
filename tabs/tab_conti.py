import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_dettagli_conti_utente,
    elimina_conto,
    ottieni_riepilogo_patrimonio_utente
)
import datetime
from utils.async_task import AsyncTask
from utils.styles import AppStyles, AppColors, PageConstants


class ContiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.page = controller.page

        # Controlli UI
        self.lv_conti_personali = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE, spacing=10)
        
        # Loading view (inline spinner)
        self.loading_view = ft.Container(
            content=ft.Column([
                ft.ProgressRing(color=AppColors.PRIMARY),
                ft.Text(self.controller.loc.get("loading"), color=AppColors.TEXT_SECONDARY)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True,
            visible=False
        )

        # Main content
        self.main_view = ft.Column(expand=True, spacing=10)

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
                loc.get("my_personal_accounts"),
                ft.IconButton(
                    icon=ft.Icons.ADD_CARD,
                    tooltip=loc.get("add_personal_account"),
                    on_click=lambda e: self.controller.conto_dialog.apri_dialog_conto(e, escludi_investimento=True),
                    icon_color=theme.primary
                )
            ),
            AppStyles.page_divider(),
            ft.Container(content=self.lv_conti_personali, expand=True),
        ]

        utente_id = self.controller.get_user_id()
        if not utente_id: return

        # Show loading
        self.main_view.visible = False
        self.loading_view.visible = True
        if self.page:
            self.page.update()

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
        # Filtra i conti di investimento - questi vengono gestiti nel tab Investimenti
        return [c for c in conti if c['tipo'] != 'Investimento']

    def _on_data_loaded(self, theme, conti_personali):
        loc = self.controller.loc
        self.lv_conti_personali.controls.clear()
        
        if not conti_personali:
            self.lv_conti_personali.controls.append(ft.Text(loc.get("no_personal_accounts")))
        else:
            for conto in conti_personali:
                self.lv_conti_personali.controls.append(self._crea_widget_conto_personale(conto, theme))

        # Hide loading
        self.loading_view.visible = False
        self.main_view.visible = True
        if self.page:
            self.page.update()

    def _on_error(self, e):
        print(f"Errore ContiTab: {e}")
        self.loading_view.visible = False
        self.main_view.controls = [AppStyles.body_text(f"Errore caricamento: {e}", color=AppColors.ERROR)]
        self.main_view.visible = True
        if self.page:
            self.page.update()

    def build_controls(self, theme):
        # Deprecated
        return []

    def _crea_widget_conto_personale(self, conto: dict, theme) -> ft.Container:
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

        content = ft.Row([
            ft.Column([
                AppStyles.subheader_text(conto['nome_conto']),
                AppStyles.caption_text(f"{conto['tipo']}" + (f" - IBAN: {conto['iban']}" if conto['iban'] else ""))
            ], expand=True),
            ft.Column([
                AppStyles.caption_text(label_saldo),
                AppStyles.currency_text(self.controller.loc.format_currency(conto['saldo_calcolato']), color=colore_saldo)
            ], horizontal_alignment=ft.CrossAxisAlignment.END),
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
                          on_click=lambda e: self.controller.conto_dialog.apri_dialog_conto(e, e.control.data, escludi_investimento=True),
                          icon_color=AppColors.INFO),
            ft.IconButton(icon=ft.Icons.DELETE, tooltip=self.controller.loc.get("delete_account"),
                          icon_color=AppColors.ERROR, data=conto['id_conto'],
                          on_click=lambda e: self.controller.open_confirm_delete_dialog(
                              partial(self.elimina_conto_personale_cliccato, e))),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        return AppStyles.card_container(content, padding=15)

    def elimina_conto_personale_cliccato(self, e):
        id_conto = e.control.data
        utente_id = self.controller.get_user_id()
        risultato = elimina_conto(id_conto, utente_id)

        if risultato is True:
            self.controller.show_snack_bar("Conto personale e dati collegati eliminati.", success=True)
            self.controller.db_write_operation()
        elif risultato == "SALDO_NON_ZERO":
            self.controller.show_snack_bar("❌ Errore: Il saldo/valore del conto non è 0.", success=False)
        elif risultato == "CONTO_NON_VUOTO":
            self.controller.show_snack_bar("❌ Errore: Non puoi eliminare un conto con transazioni o asset.", success=False)
        elif isinstance(risultato, tuple) and not risultato[0]:
            # Nuovo: gestisce l'errore restituito dal DB e mostra il popup
            self.controller.show_error_dialog(risultato[1])
        else:
            self.controller.show_error_dialog("Si è verificato un errore sconosciuto durante l'eliminazione del conto.")