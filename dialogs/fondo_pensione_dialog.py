import flet as ft
from db.gestione_db import (
    aggiorna_valore_fondo_pensione,
    esegui_operazione_fondo_pensione,
    ottieni_conti_utente
)
import datetime


class FondoPensioneDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.loc = controller.loc
        self.modal = True
        self.title = ft.Text()
        self.content = ft.Column(spacing=20)
        self.actions = [
            ft.TextButton(on_click=self.chiudi_dialog)
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

        # Controlli del dialogo
        self.conto_selezionato = None
        self.txt_valore_attuale = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.btn_aggiorna_valore = ft.ElevatedButton(on_click=self.aggiorna_valore_cliccato)

        self.txt_importo_operazione = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dd_conto_collegato = ft.Dropdown()
        self.btn_versa_da_conto = ft.ElevatedButton(on_click=self.versa_da_conto_cliccato)
        self.btn_versa_esterno = ft.ElevatedButton(on_click=self.versa_esterno_cliccato)
        self.btn_preleva = ft.ElevatedButton(on_click=self.preleva_cliccato)

    def _update_texts(self):
        """Aggiorna tutti i testi fissi con le traduzioni correnti."""
        loc = self.loc
        self.title.value = loc.get("manage_pension_fund_dialog")
        self.actions[0].text = loc.get("close")

        self.txt_valore_attuale.label = loc.get("current_total_value")
        self.txt_valore_attuale.prefix_text = loc.currencies[loc.currency]['symbol']
        self.btn_aggiorna_valore.text = loc.get("update_value")

        self.txt_importo_operazione.label = loc.get("operation_amount")
        self.txt_importo_operazione.prefix_text = loc.currencies[loc.currency]['symbol']
        self.dd_conto_collegato.label = loc.get("linked_account")

        self.btn_versa_da_conto.text = loc.get("deposit_from_account")
        self.btn_versa_esterno.text = loc.get("deposit_from_external")
        self.btn_versa_esterno.tooltip = loc.get("deposit_from_external_tooltip")
        self.btn_preleva.text = loc.get("withdraw_to_account")

    def apri_dialog(self, conto_data):
        self._update_texts()
        self.conto_selezionato = conto_data
        self.title.value = self.loc.get("manage_pension_fund_for", conto_data['nome_conto'])
        self.txt_valore_attuale.value = f"{conto_data.get('saldo_calcolato', 0.0):.2f}"
        self.txt_importo_operazione.value = ""
        self.txt_importo_operazione.error_text = None

        # Popola dropdown con conti validi
        conti_utente = ottieni_conti_utente(self.controller.get_user_id())
        self.dd_conto_collegato.options = [
            ft.dropdown.Option(c['id_conto'], c['nome_conto'])
            for c in conti_utente if c['tipo'] not in ['Fondo Pensione', 'Investimento']
        ]
        self.dd_conto_collegato.value = None

        self.content.controls = [
            ft.Text(self.loc.get("update_total_value")),
            ft.Row([self.txt_valore_attuale, self.btn_aggiorna_valore], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            ft.Text(self.loc.get("perform_operation")),
            self.txt_importo_operazione,
            self.dd_conto_collegato,
            ft.Row([self.btn_versa_da_conto, self.btn_versa_esterno, self.btn_preleva],
                   alignment=ft.MainAxisAlignment.SPACE_AROUND)
        ]
        self.open = True
        self.controller.page.update()

    def chiudi_dialog(self, e=None):
        self.open = False
        self.controller.page.update()

    def aggiorna_valore_cliccato(self, e):
        try:
            nuovo_valore = float(self.txt_valore_attuale.value.replace(",", "."))
            success = aggiorna_valore_fondo_pensione(self.conto_selezionato['id_conto'], nuovo_valore)
            if success:
                self.controller.show_snack_bar(self.loc.get("pension_fund_value_updated"), success=True)
                self.controller.update_all_views()
                self.chiudi_dialog()
            else:
                self.controller.show_snack_bar(self.loc.get("error_updating_value"), success=False)
        except (ValueError, TypeError):
            self.txt_valore_attuale.error_text = self.loc.get("invalid_amount")
            self.controller.page.update()

    def _esegui_operazione(self, tipo_operazione):
        try:
            importo = float(self.txt_importo_operazione.value.replace(",", "."))
            if importo <= 0:
                raise ValueError("Importo deve essere positivo")

            id_conto_collegato = None
            if tipo_operazione != 'VERSAMENTO_ESTERNO':
                id_conto_collegato = self.dd_conto_collegato.value
                if not id_conto_collegato:
                    self.dd_conto_collegato.error_text = self.loc.get("select_an_account")
                    self.controller.page.update()
                    return

            data_operazione = datetime.date.today().strftime('%Y-%m-%d')

            success = esegui_operazione_fondo_pensione(
                id_fondo_pensione=self.conto_selezionato['id_conto'],
                tipo_operazione=tipo_operazione,
                importo=importo,
                data=data_operazione,
                id_conto_collegato=id_conto_collegato
            )

            if success:
                self.controller.show_snack_bar(self.loc.get("pension_fund_op_success"), success=True)
                self.controller.update_all_views()
                self.chiudi_dialog()
            else:
                self.controller.show_snack_bar(self.loc.get("pension_fund_op_error"), success=False)

        except (ValueError, TypeError):
            self.txt_importo_operazione.error_text = self.loc.get("invalid_amount")
            self.controller.page.update()

    def versa_da_conto_cliccato(self, e):
        self._esegui_operazione('VERSAMENTO')

    def versa_esterno_cliccato(self, e):
        self._esegui_operazione('VERSAMENTO_ESTERNO')

    def preleva_cliccato(self, e):
        self._esegui_operazione('PRELIEVO')