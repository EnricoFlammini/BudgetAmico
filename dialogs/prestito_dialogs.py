import flet as ft
import traceback
from db.gestione_db import (
    aggiungi_prestito,
    modifica_prestito,
    ottieni_tutti_i_conti_utente,
    ottieni_categorie,
    effettua_pagamento_rata
)
import datetime


class PrestitoDialogs:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc
        self.prestito_in_modifica = None
        self.prestito_per_pagamento = None

        # --- Dialogo Aggiungi/Modifica Prestito ---
        self.txt_nome = ft.TextField()
        self.dd_tipo = ft.Dropdown()
        self.txt_descrizione = ft.TextField(multiline=True, min_lines=2)
        self.txt_data_inizio = ft.TextField(read_only=True)
        self.txt_numero_rate = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_importo_finanziato = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_importo_interessi = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_importo_rata = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dd_giorno_scadenza = ft.Dropdown(options=[ft.dropdown.Option(str(i)) for i in range(1, 32)])
        self.dd_conto_default = ft.Dropdown()
        self.dd_categoria_default = ft.Dropdown()

        self.dialog_prestito = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column(
                [
                    self.txt_nome, self.dd_tipo, self.txt_descrizione, self.txt_data_inizio,
                    self.txt_numero_rate, self.txt_importo_finanziato, self.txt_importo_interessi,
                    self.txt_importo_rata, self.dd_giorno_scadenza, self.dd_conto_default,
                    self.dd_categoria_default
                ],
                tight=True, spacing=10, height=600, width=500, scroll=ft.ScrollMode.ADAPTIVE
            ),
            actions=[
                ft.TextButton(on_click=self._chiudi_dialog_prestito),
                ft.TextButton(on_click=self._salva_prestito_cliccato)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        # --- Dialogo Paga Rata ---
        self.txt_importo_pagamento = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_data_pagamento = ft.TextField(read_only=True)
        self.dd_conto_pagamento = ft.Dropdown()
        self.dd_categoria_pagamento = ft.Dropdown()

        self.dialog_paga_rata = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([
                self.txt_importo_pagamento, self.txt_data_pagamento,
                self.dd_conto_pagamento, self.dd_categoria_pagamento
            ], tight=True, spacing=10),
            actions=[
                ft.TextButton(on_click=self._chiudi_dialog_paga_rata),
                ft.TextButton(on_click=self._esegui_pagamento_cliccato)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

    def _update_texts(self):
        """Aggiorna i testi di tutti i dialoghi."""
        loc = self.loc
        # Dialogo Prestito
        self.dialog_prestito.actions[0].text = loc.get("cancel")
        self.dialog_prestito.actions[1].text = loc.get("save")
        self.txt_nome.label = loc.get("loan_name")
        self.dd_tipo.label = loc.get("loan_type")
        self.dd_tipo.options = [
            ft.dropdown.Option("Prestito"), ft.dropdown.Option("Finanziamento"), ft.dropdown.Option("Mutuo")
        ]
        self.txt_descrizione.label = loc.get("description")
        self.txt_data_inizio.label = loc.get("start_date")
        self.txt_numero_rate.label = loc.get("total_installments")
        self.txt_importo_finanziato.label = loc.get("financed_amount")
        self.txt_importo_finanziato.prefix_text = loc.currencies[loc.currency]['symbol']
        self.txt_importo_interessi.label = loc.get("interest_amount")
        self.txt_importo_interessi.prefix_text = loc.currencies[loc.currency]['symbol']
        self.txt_importo_rata.label = loc.get("monthly_installment")
        self.txt_importo_rata.prefix_text = loc.currencies[loc.currency]['symbol']
        self.dd_giorno_scadenza.label = loc.get("installment_due_day")
        self.dd_conto_default.label = loc.get("default_payment_account")
        self.dd_categoria_default.label = loc.get("default_payment_category")

        # Dialogo Paga Rata
        self.dialog_paga_rata.title.value = loc.get("pay_installment_dialog_title")
        self.dialog_paga_rata.actions[0].text = loc.get("cancel")
        self.dialog_paga_rata.actions[1].text = loc.get("execute_payment")
        self.txt_importo_pagamento.label = loc.get("payment_amount")
        self.txt_importo_pagamento.prefix_text = loc.currencies[loc.currency]['symbol']
        self.txt_data_pagamento.label = loc.get("payment_date")
        self.dd_conto_pagamento.label = loc.get("payment_account")
        self.dd_categoria_pagamento.label = loc.get("payment_category")

    def apri_dialog_prestito(self, prestito_data=None, tipo_default=None):
        self._update_texts()
        self._reset_fields_prestito()
        self._popola_dropdowns_prestito()

        if prestito_data:
            self.dialog_prestito.title.value = self.loc.get("edit_loan")
            self.prestito_in_modifica = prestito_data
            # Popola i campi con i dati esistenti
            self.txt_nome.value = prestito_data['nome']
            self.dd_tipo.value = prestito_data['tipo']
            self.txt_descrizione.value = prestito_data.get('descrizione', '')
            self.txt_data_inizio.value = prestito_data['data_inizio']
            self.txt_numero_rate.value = str(prestito_data['numero_mesi_totali'])
            self.txt_importo_finanziato.value = str(prestito_data['importo_finanziato'])
            self.txt_importo_interessi.value = str(prestito_data['importo_interessi'])
            self.txt_importo_rata.value = str(prestito_data['importo_rata'])
            self.dd_giorno_scadenza.value = str(prestito_data['giorno_scadenza_rata'])
            self.dd_conto_default.value = prestito_data.get('id_conto_pagamento_default')
            self.dd_categoria_default.value = prestito_data.get('id_categoria_pagamento_default')
        else:
            self.dialog_prestito.title.value = self.loc.get("add_loan")
            self.prestito_in_modifica = None
            if tipo_default:
                self.dd_tipo.value = tipo_default

        self.page.dialog = self.dialog_prestito
        self.dialog_prestito.open = True
        self.page.update()

    def _reset_fields_prestito(self):
        self.txt_nome.value = ""
        self.dd_tipo.value = "Prestito"
        self.txt_descrizione.value = ""
        self.txt_data_inizio.value = datetime.date.today().strftime('%Y-%m-%d')
        self.txt_numero_rate.value = ""
        self.txt_importo_finanziato.value = ""
        self.txt_importo_interessi.value = ""
        self.txt_importo_rata.value = ""
        self.dd_giorno_scadenza.value = "1"
        self.dd_conto_default.value = None
        self.dd_categoria_default.value = None
        # Reset errori
        for field in [self.txt_nome, self.txt_numero_rate, self.txt_importo_finanziato, self.txt_importo_rata]:
            field.error_text = None

    def _popola_dropdowns_prestito(self):
        id_famiglia = self.controller.get_family_id()
        id_utente = self.controller.get_user_id()

        conti = ottieni_tutti_i_conti_utente(id_utente)
        conti_filtrati = [c for c in conti if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        self.dd_conto_default.options = [ft.dropdown.Option(key=c['id_conto'], text=c['nome_conto']) for c in
                                         conti_filtrati]

        categorie = ottieni_categorie(id_famiglia)
        self.dd_categoria_default.options = [ft.dropdown.Option(key=c['id_categoria'], text=c['nome_categoria']) for c
                                             in categorie]

    def _chiudi_dialog_prestito(self, e):
        self.dialog_prestito.open = False
        self.page.update()

    def _salva_prestito_cliccato(self, e):
        try:
            # Validazione
            is_valid = True
            for field in [self.txt_nome, self.txt_numero_rate, self.txt_importo_finanziato, self.txt_importo_rata]:
                if not field.value:
                    field.error_text = self.loc.get("required_field")
                    is_valid = False

            if not is_valid:
                self.page.update()
                return

            # Raccolta dati
            id_famiglia = self.controller.get_family_id()
            nome = self.txt_nome.value
            tipo = self.dd_tipo.value
            descrizione = self.txt_descrizione.value
            data_inizio = self.txt_data_inizio.value
            numero_rate = int(self.txt_numero_rate.value)
            importo_finanziato = float(self.txt_importo_finanziato.value.replace(",", "."))
            importo_interessi = float(
                self.txt_importo_interessi.value.replace(",", ".")) if self.txt_importo_interessi.value else 0.0
            importo_rata = float(self.txt_importo_rata.value.replace(",", "."))
            giorno_scadenza = int(self.dd_giorno_scadenza.value)
            id_conto = self.dd_conto_default.value
            id_categoria = self.dd_categoria_default.value

            success = False
            if self.prestito_in_modifica:
                success = modifica_prestito(
                    id_prestito=self.prestito_in_modifica['id_prestito'],
                    nome=nome, tipo=tipo, descrizione=descrizione, data_inizio=data_inizio,
                    numero_mesi_totali=numero_rate, importo_finanziato=importo_finanziato,
                    importo_interessi=importo_interessi, importo_rata=importo_rata,
                    giorno_scadenza_rata=giorno_scadenza, id_conto_default=id_conto,
                    id_categoria_default=id_categoria, importo_residuo=self.prestito_in_modifica['importo_residuo']
                )
            else:
                success = aggiungi_prestito(
                    id_famiglia=id_famiglia, nome=nome, tipo=tipo, descrizione=descrizione,
                    data_inizio=data_inizio, numero_mesi_totali=numero_rate,
                    importo_finanziato=importo_finanziato, importo_interessi=importo_interessi,
                    importo_rata=importo_rata, giorno_scadenza_rata=giorno_scadenza,
                    id_conto_default=id_conto, id_categoria_default=id_categoria, importo_residuo=importo_finanziato
                )

            if success:
                self.controller.show_snack_bar("Prestito salvato con successo!", success=True)
                self.dialog_prestito.open = False
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("Errore durante il salvataggio del prestito.", success=False)

        except ValueError:
            self.controller.show_snack_bar(self.loc.get("invalid_amount"), success=False)
        except Exception as ex:
            print(f"Errore salvataggio prestito: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore inaspettato: {ex}", success=False)

        self.page.update()

    def apri_dialog_paga_rata(self, prestito_data):
        self._update_texts()
        self.prestito_per_pagamento = prestito_data
        self.dialog_paga_rata.title.value = f"{self.loc.get('pay_installment')}: {prestito_data['nome']}"

        self.txt_importo_pagamento.value = str(prestito_data['importo_rata'])
        self.txt_data_pagamento.value = datetime.date.today().strftime('%Y-%m-%d')

        # Popola dropdown
        id_utente = self.controller.get_user_id()
        id_famiglia = self.controller.get_family_id()
        conti = ottieni_tutti_i_conti_utente(id_utente)
        conti_filtrati = [c for c in conti if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        self.dd_conto_pagamento.options = [ft.dropdown.Option(key=c['id_conto'], text=c['nome_conto']) for c in
                                           conti_filtrati]

        categorie = ottieni_categorie(id_famiglia)
        self.dd_categoria_pagamento.options = [ft.dropdown.Option(key=c['id_categoria'], text=c['nome_categoria']) for c
                                               in categorie]

        self.dd_conto_pagamento.value = prestito_data.get('id_conto_pagamento_default')
        self.dd_categoria_pagamento.value = prestito_data.get('id_categoria_pagamento_default')

        self.page.dialog = self.dialog_paga_rata
        self.dialog_paga_rata.open = True
        self.page.update()

    def _chiudi_dialog_paga_rata(self, e):
        self.dialog_paga_rata.open = False
        self.page.update()

    def _esegui_pagamento_cliccato(self, e):
        # Logica di pagamento... (già implementata)
        pass