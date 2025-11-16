import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_dettagli_conti_utente,
    elimina_conto,
    ottieni_riepilogo_patrimonio_utente  # Importa la funzione per i totali
)
import datetime


class ContiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page

        # Controlli per i totali
        self.txt_patrimonio_netto = ft.Text(size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_300)
        self.txt_liquidita = ft.Text(size=16)
        self.txt_investimenti = ft.Text(size=16)

        self.lv_conti_personali = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE,
            spacing=10
        )
        
        # Il contenuto ora è un Column vuoto, verrà popolato da build_controls
        self.content = ft.Column(expand=True, spacing=10)

    def update_view_data(self, is_initial_load=False):
        # Ricostruisce l'interfaccia con le traduzioni corrette ogni volta
        self.content.controls = self.build_controls()

        utente_id = self.controller.get_user_id()
        if not utente_id:
            return

        print(f"DEBUG (ContiTab.update_view_data): utente_id = {utente_id}")

        # --- Aggiorna i totali del patrimonio utente ---
        oggi = datetime.date.today()
        # Calcola il patrimonio sempre per il mese corrente in questa vista
        riepilogo_patrimonio = ottieni_riepilogo_patrimonio_utente(utente_id, oggi.year, oggi.month)
        self.txt_patrimonio_netto.value = self.controller.loc.format_currency(riepilogo_patrimonio.get('patrimonio_netto', 0))
        self.txt_liquidita.value = self.controller.loc.format_currency(riepilogo_patrimonio.get('liquidita', 0))
        self.txt_investimenti.value = self.controller.loc.format_currency(riepilogo_patrimonio.get('investimenti', 0))
        # Rendi visibile la label investimenti solo se c'è un valore > 0
        self.txt_investimenti.visible = riepilogo_patrimonio.get('investimenti', 0) > 0

        print(f"DEBUG (ContiTab.update_view_data): Riepilogo patrimonio: {riepilogo_patrimonio}")
        if self.page:
            self.page.update()  # Update the page to show the totals immediately

        print("Aggiornamento Scheda Conti...")
        self.lv_conti_personali.controls.clear()
        # --- Conti Personali ---
        conti_personali = ottieni_dettagli_conti_utente(utente_id)
        if not conti_personali:
            self.lv_conti_personali.controls.append(ft.Text(self.controller.loc.get("no_personal_accounts")))
        else:
            for conto in conti_personali:
                widget_conto = self._crea_widget_conto_personale(conto)
                self.lv_conti_personali.controls.append(widget_conto)

        if self.page:
            self.page.update()
            
    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        return [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column([
                            ft.Text(self.controller.loc.get("net_worth"), size=12, color=ft.Colors.GREY_500),
                            self.txt_patrimonio_netto
                        ]),
                        ft.Column([
                            ft.Text(self.controller.loc.get("liquidity"), size=12, color=ft.Colors.GREY_500),
                            self.txt_liquidita,
                            ft.Text(self.controller.loc.get("investments"), size=12, color=ft.Colors.GREY_500,
                                    visible=False),
                            # Nascosto per ora
                            self.txt_investimenti
                        ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.END)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ), padding=10, border=ft.border.all(1, ft.Colors.GREY_800), border_radius=5),
            ft.Row(
                [
                    ft.Text(self.controller.loc.get("my_personal_accounts"), size=24, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.Icons.ADD_CARD,
                        tooltip=self.controller.loc.get("add_personal_account"),
                        on_click=lambda e: self.controller.conto_dialog.apri_dialog_conto(e)
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            ft.Divider(),
            self.lv_conti_personali,
        ]

    def _crea_widget_conto_personale(self, conto: dict) -> ft.Container:
        """Crea e restituisce il widget Container per un singolo conto personale."""
        is_investimento = conto['tipo'] == 'Investimento'
        is_fondo_pensione = conto['tipo'] == 'Fondo Pensione'

        # Determina etichetta e colore del saldo
        label_saldo = self.controller.loc.get("value")
        colore_saldo = ft.Colors.CYAN_400
        if not is_investimento and not is_fondo_pensione:
            label_saldo = self.controller.loc.get("current_balance")
            colore_saldo = ft.Colors.GREEN_500 if conto['saldo_calcolato'] >= 0 else ft.Colors.RED_500

        saldo_testo = ft.Text(
            self.controller.loc.format_currency(conto['saldo_calcolato']),
            size=16, weight=ft.FontWeight.BOLD, color=colore_saldo
        )

        # Crea i pulsanti di azione
        btn_modifica = ft.IconButton(icon=ft.Icons.EDIT, tooltip=self.controller.loc.get("edit_account"), data=conto,
                                     on_click=lambda e: self.controller.conto_dialog.apri_dialog_conto(e,
                                                                                                       e.control.data))
        btn_elimina = ft.IconButton(
            icon=ft.Icons.DELETE, tooltip=self.controller.loc.get("delete_account"), icon_color=ft.Colors.RED_400, data=conto['id_conto'],
            on_click=lambda e: self.controller.open_confirm_delete_dialog(
                partial(self.elimina_conto_personale_cliccato, e))
        )
        btn_portafoglio = ft.IconButton(icon=ft.Icons.INSIGHTS, tooltip=self.controller.loc.get("manage_portfolio"),
                                        icon_color=ft.Colors.BLUE_300, data=conto,
                                        on_click=lambda e: self.controller.portafoglio_dialogs.apri_dialog_portafoglio(
                                            e, e.control.data), visible=is_investimento)
        btn_fondo_pensione = ft.IconButton(icon=ft.Icons.MANAGE_ACCOUNTS, tooltip=self.controller.loc.get("manage_pension_fund"),
                                           icon_color=ft.Colors.CYAN_400, data=conto,
                                           on_click=lambda e: self.controller.fondo_pensione_dialog.apri_dialog(
                                               e.control.data), visible=is_fondo_pensione)

        # Assembla il widget
        return ft.Container(
            content=ft.Row(
                [
                    # Colonna con nome e tipo conto
                    ft.Column(
                        [
                            ft.Text(conto['nome_conto'], weight=ft.FontWeight.BOLD, size=18),
                            ft.Text(f"{conto['tipo']}" + (f" - IBAN: {conto['iban']}" if conto['iban'] else ""),
                                    size=12,
                                    color=ft.Colors.GREY_500)
                        ],
                        expand=True
                    ),
                    # Colonna con il saldo
                    ft.Column(
                        [
                            ft.Text(label_saldo, size=10, color=ft.Colors.GREY_500),
                            saldo_testo
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.END
                    ),
                    # Pulsanti di azione
                    btn_portafoglio,
                    btn_fondo_pensione,
                    btn_modifica,
                    btn_elimina,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=10,
            border_radius=5,
            border=ft.border.all(1, ft.Colors.GREY_800)
        )

    def elimina_conto_personale_cliccato(self, e):
        id_conto = e.control.data
        utente_id = self.controller.get_user_id()

        risultato = elimina_conto(id_conto, utente_id)

        if risultato == True:
            self.controller.show_snack_bar("Conto personale e dati collegati eliminati.", success=True)
            self.controller.db_write_operation()  # Esegue update e sync
        elif risultato == "SALDO_NON_ZERO":
            self.controller.show_snack_bar("❌ Errore: Il saldo/valore del conto non è 0.", success=False)
        else:
            self.controller.show_snack_bar("❌ Errore sconosciuto durante l'eliminazione.", success=False)