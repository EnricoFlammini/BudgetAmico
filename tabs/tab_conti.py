import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_dettagli_conti_utente,
    elimina_conto,
    ottieni_riepilogo_patrimonio_utente
)
import datetime
from utils.styles import AppStyles, AppColors


class ContiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page

        # Controlli UI
        self.txt_patrimonio_netto = AppStyles.header_text("")
        self.txt_liquidita = AppStyles.body_text("")
        self.txt_investimenti = AppStyles.body_text("")
        
        self.lv_conti_personali = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE, spacing=10)
        self.content = ft.Column(expand=True, spacing=10)

    def update_view_data(self, is_initial_load=False):
        # Get master_key from session for encryption
        master_key_b64 = self.controller.page.session.get("master_key")
        
        # Soluzione robusta per ottenere il tema
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()

        self.content.controls = self.build_controls(theme)

        self.txt_patrimonio_netto.color = theme.primary

        utente_id = self.controller.get_user_id()
        if not utente_id: return

        oggi = datetime.date.today()
        riepilogo = ottieni_riepilogo_patrimonio_utente(utente_id, oggi.year, oggi.month)
        
        val_patrimonio = riepilogo.get('patrimonio_netto', 0)
        self.txt_patrimonio_netto.value = self.controller.loc.format_currency(val_patrimonio)
        self.txt_patrimonio_netto.color = AppColors.SUCCESS if val_patrimonio >= 0 else AppColors.ERROR
        
        self.txt_liquidita.value = self.controller.loc.format_currency(riepilogo.get('liquidita', 0))
        self.txt_investimenti.value = self.controller.loc.format_currency(riepilogo.get('investimenti', 0))
        self.txt_investimenti.visible = riepilogo.get('investimenti', 0) > 0

        self.lv_conti_personali.controls.clear()
        conti_personali = ottieni_dettagli_conti_utente(utente_id, master_key_b64=master_key_b64)
        # Filtra i conti di investimento - questi vengono gestiti nel tab Investimenti
        conti_personali = [c for c in conti_personali if c['tipo'] != 'Investimento']
        if not conti_personali:
            self.lv_conti_personali.controls.append(ft.Text(self.controller.loc.get("no_personal_accounts")))
        else:
            for conto in conti_personali:
                self.lv_conti_personali.controls.append(self._crea_widget_conto_personale(conto, theme))

        if self.page:
            self.page.update()

    def build_controls(self, theme):
        return [
            AppStyles.card_container(
                content=ft.Row([
                    ft.Column([
                        AppStyles.caption_text(self.controller.loc.get("net_worth")),
                        self.txt_patrimonio_netto
                    ]),
                    ft.Column([
                        AppStyles.caption_text(self.controller.loc.get("liquidity")),
                        self.txt_liquidita,
                        ft.Text(self.controller.loc.get("investments"), size=12, color=AppColors.TEXT_SECONDARY,
                                visible=self.txt_investimenti.visible),
                        self.txt_investimenti
                    ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.END)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=15
            ),
            ft.Row([
                AppStyles.subheader_text(self.controller.loc.get("my_personal_accounts")),
                ft.IconButton(
                    icon=ft.Icons.ADD_CARD,
                    tooltip=self.controller.loc.get("add_personal_account"),
                    on_click=lambda e: self.controller.conto_dialog.apri_dialog_conto(e, escludi_investimento=True),
                    icon_color=theme.primary
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(color=ft.Colors.OUTLINE_VARIANT),
            ft.Container(content=self.lv_conti_personali, expand=True),
        ]

    def _crea_widget_conto_personale(self, conto: dict, theme) -> ft.Container:
        is_investimento = conto['tipo'] == 'Investimento'
        is_fondo_pensione = conto['tipo'] == 'Fondo Pensione'

        is_admin = self.controller.get_user_role() == 'admin'
        is_corrente = conto['tipo'] in ['Corrente', 'Risparmio', 'Contanti']

        label_saldo = self.controller.loc.get(
            "value") if is_investimento or is_fondo_pensione else self.controller.loc.get("current_balance")
        
        # Usa AppColors per coerenza
        colore_saldo = theme.secondary if is_investimento or is_fondo_pensione else (
            AppColors.SUCCESS if conto['saldo_calcolato'] >= 0 else AppColors.ERROR)

        content = ft.Row([
            ft.Column([
                AppStyles.subheader_text(conto['nome_conto']),
                AppStyles.caption_text(f"{conto['tipo']}" + (f" - IBAN: {conto['iban']}" if conto['iban'] else ""))
            ], expand=True),
            ft.Column([
                AppStyles.caption_text(label_saldo),
                ft.Text(self.controller.loc.format_currency(conto['saldo_calcolato']), size=16,
                        weight=ft.FontWeight.BOLD, color=colore_saldo)
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