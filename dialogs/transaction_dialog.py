import flet as ft
import datetime
import traceback
from db.gestione_db import (
    aggiungi_transazione,
    modifica_transazione,
    ottieni_tutti_i_conti_utente,
    ottieni_categorie_e_sottocategorie,
    ottieni_conto_default_utente,
    aggiungi_transazione_condivisa,
    modifica_transazione_condivisa,
    elimina_transazione,
    elimina_transazione_condivisa
)


class TransactionDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc

        self.modal = True
        self.title = ft.Text(size=20, weight="bold")

        # Controlli del dialogo
        self.txt_data_selezionata = ft.Text(size=16)
        self.radio_tipo_transazione = ft.RadioGroup(content=ft.Row())
        self.txt_descrizione_dialog = ft.TextField()
        self.txt_importo_dialog = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dd_conto_dialog = ft.Dropdown()
        self.dd_sottocategoria_dialog = ft.Dropdown()
        
        self.content = ft.Column(
            [
                ft.Row([
                    ft.Text(),  # Etichetta "Data:"
                    self.txt_data_selezionata,
                    ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=self.apri_date_picker),
                ], alignment=ft.MainAxisAlignment.START),
                self.radio_tipo_transazione,
                self.txt_descrizione_dialog,
                self.txt_importo_dialog,
                self.dd_conto_dialog,
                self.dd_sottocategoria_dialog,
            ],
            tight=True, height=420, width=400,
        )

        self.actions = [
            ft.TextButton(on_click=self.chiudi_dialog),
            ft.TextButton(on_click=self._salva_nuova_transazione),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _update_texts(self):
        """Aggiorna tutti i testi fissi con le traduzioni correnti."""
        self.title.value = self.loc.get("new_transaction")
        self.content.controls[0].controls[0].value = self.loc.get("date") + ":"
        self.radio_tipo_transazione.content.controls = [
            ft.Radio(value="Spesa", label=self.loc.get("expense")),
            ft.Radio(value="Incasso", label=self.loc.get("income")),
        ]
        self.txt_descrizione_dialog.label = self.loc.get("description")
        self.txt_importo_dialog.label = self.loc.get("amount")
        self.txt_importo_dialog.prefix_text = self.loc.currencies[self.loc.currency]['symbol']
        self.dd_conto_dialog.label = self.loc.get("account")
        self.dd_sottocategoria_dialog.label = self.loc.get("subcategory")
        self.actions[0].text = self.loc.get("cancel")
        self.actions[1].text = self.loc.get("save")

    def apri_date_picker(self, e):
        self.controller.date_picker.on_change = self.on_date_picker_change
        self.controller.page.open(self.controller.date_picker)

    def on_date_picker_change(self, e):
        if self.controller.date_picker.value:
            self.txt_data_selezionata.value = self.controller.date_picker.value.strftime('%Y-%m-%d')
            if self.controller.page: self.controller.page.update()

    def chiudi_dialog(self, e=None):
        print(f"DEBUG: chiudi_dialog chiamato per {self}")
        try:
            self.open = False
            self.controller.page.session.set("transazione_in_modifica", None)
            if self.controller.page:
                self.controller.page.update()
            print("DEBUG: chiudi_dialog completato (solo open=False)")
        except Exception as ex:
            print(f"Errore chiusura dialog transazione: {ex}")
            traceback.print_exc()

    def _popola_dropdowns(self):
        utente_id = self.controller.get_user_id()
        famiglia_id = self.controller.get_family_id()
        master_key_b64 = self.controller.page.session.get("master_key")

        tutti_i_conti = ottieni_tutti_i_conti_utente(utente_id, master_key_b64=master_key_b64)
        conti_filtrati = [c for c in tutti_i_conti if c['tipo'] not in ['Investimento', 'Fondo Pensione']]

        opzioni_conto = []
        for c in conti_filtrati:
            suffix = self.loc.get("shared_suffix") if c['is_condiviso'] else self.loc.get("personal_suffix")
            prefix = "C" if c['is_condiviso'] else "P"
            opzioni_conto.append(ft.dropdown.Option(key=f"{prefix}{c['id_conto']}", text=f"{c['nome_conto']} {suffix}"))
        self.dd_conto_dialog.options = opzioni_conto

        self.dd_sottocategoria_dialog.options = [ft.dropdown.Option(key=None, text=self.loc.get("no_category"))]
        if famiglia_id:
            categorie = ottieni_categorie_e_sottocategorie(famiglia_id)
            for cat_id, cat_data in categorie.items():
                for sub_cat in cat_data['sottocategorie']:
                    self.dd_sottocategoria_dialog.options.append(
                        ft.dropdown.Option(key=sub_cat['id_sottocategoria'], text=f"{cat_data['nome_categoria']} - {sub_cat['nome_sottocategoria']}")
                    )

    def _reset_campi(self):
        self.txt_descrizione_dialog.error_text = None
        self.txt_importo_dialog.error_text = None
        self.dd_conto_dialog.error_text = None
        self.txt_data_selezionata.value = datetime.date.today().strftime('%Y-%m-%d')
        self.radio_tipo_transazione.value = "Spesa"
        self.txt_descrizione_dialog.value = ""
        self.txt_importo_dialog.value = ""
        self.dd_conto_dialog.value = None
        self.dd_sottocategoria_dialog.value = None

    def apri_dialog_nuova_transazione(self, e=None):
        try:
            self._update_texts()
            self.controller.page.session.set("transazione_in_modifica", None)
            self._popola_dropdowns()
            self._reset_campi()

            utente_id = self.controller.get_user_id()
            conto_default_info = ottieni_conto_default_utente(utente_id)
            if conto_default_info:
                self.dd_conto_dialog.value = f"{conto_default_info['tipo'][0].upper()}{conto_default_info['id']}"

            if self not in self.controller.page.overlay:
                self.controller.page.overlay.append(self)
            self.open = True
            if self.controller.page: self.controller.page.update()
        except Exception as ex:
            print(f"Errore apertura dialog nuova transazione: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore: {ex}", success=False)

    def apri_dialog_modifica_transazione(self, transazione_dati):
        try:
            self._update_texts()
            self.title.value = self.loc.get("edit") + " " + self.loc.get("new_transaction")
            self._popola_dropdowns()
            self._reset_campi()

            importo_assoluto = abs(transazione_dati['importo'])
            is_spesa = transazione_dati['importo'] < 0

            self.txt_data_selezionata.value = transazione_dati['data']
            self.radio_tipo_transazione.value = "Spesa" if is_spesa else "Incasso"
            self.txt_descrizione_dialog.value = transazione_dati['descrizione']
            self.txt_importo_dialog.value = f"{importo_assoluto:.2f}"

            prefix = "C" if transazione_dati.get('id_transazione_condivisa', 0) > 0 else "P"
            self.dd_conto_dialog.value = f"{prefix}{transazione_dati['id_conto']}"

            self.dd_sottocategoria_dialog.value = transazione_dati.get('id_sottocategoria')

            self.controller.page.session.set("transazione_in_modifica", transazione_dati)
            if self not in self.controller.page.overlay:
                self.controller.page.overlay.append(self)
            self.open = True
            if self.controller.page: self.controller.page.update()
        except Exception as ex:
            print(f"Errore apertura dialog modifica transazione: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore: {ex}", success=False)

    def _valida_e_raccogli_dati(self):
        try:
            is_valid = True
            self.txt_descrizione_dialog.error_text = None
            self.txt_importo_dialog.error_text = None
            self.dd_conto_dialog.error_text = None

            if not self.txt_descrizione_dialog.value:
                self.txt_descrizione_dialog.error_text = self.loc.get("description_required")
                is_valid = False
            if not self.dd_conto_dialog.value:
                self.dd_conto_dialog.error_text = self.loc.get("select_an_account")
                is_valid = False

            importo = 0.0
            try:
                importo = abs(float(self.txt_importo_dialog.value.replace(",", ".")))
                if importo == 0:
                    self.txt_importo_dialog.error_text = self.loc.get("amount_not_zero")
                    is_valid = False
            except (ValueError, TypeError):
                self.txt_importo_dialog.error_text = self.loc.get("invalid_amount")
                is_valid = False

            if not is_valid:
                if self.controller.page: self.controller.page.update()
                return

            data = self.txt_data_selezionata.value
            descrizione = self.txt_descrizione_dialog.value
            if self.radio_tipo_transazione.value == "Spesa":
                importo = -importo

            return {
                "data": data, "descrizione": descrizione, "importo": importo,
                "id_sottocategoria": self.dd_sottocategoria_dialog.value,
                "id_conto": int(self.dd_conto_dialog.value[1:]),
                "is_nuovo_conto_condiviso": self.dd_conto_dialog.value.startswith('C')
            }
        except Exception as ex:
            print(f"Errore validazione dati transazione: {ex}")
            traceback.print_exc()
            return None

    def _esegui_modifica(self, dati_nuovi, transazione_originale):
        # Get master_key from session for encryption
        master_key_b64 = self.controller.page.session.get("master_key")
        
        is_originale_condivisa = transazione_originale.get('id_transazione_condivisa', 0) > 0
        is_nuova_condivisa = dati_nuovi['is_nuovo_conto_condiviso']

        # Caso 1: Il tipo di conto non è cambiato (Personale -> Personale o Condiviso -> Condiviso)
        if is_originale_condivisa == is_nuova_condivisa:
            if is_originale_condivisa:
                id_trans = transazione_originale['id_transazione_condivisa']
                return modifica_transazione_condivisa(id_trans, dati_nuovi['data'], dati_nuovi['descrizione'], dati_nuovi['importo'], dati_nuovi['id_sottocategoria'], master_key_b64=master_key_b64)
            else:
                id_trans = transazione_originale['id_transazione']
                return modifica_transazione(id_trans, dati_nuovi['data'], dati_nuovi['descrizione'], dati_nuovi['importo'], dati_nuovi['id_sottocategoria'], dati_nuovi['id_conto'], master_key_b64=master_key_b64)
        
        # Caso 2: Il tipo di conto è cambiato (es. da Personale a Condiviso)
        # Trattiamo come un'operazione di "elimina e crea"
        else:
            # Elimina la vecchia transazione
            if is_originale_condivisa:
                elimina_transazione_condivisa(transazione_originale['id_transazione_condivisa'])
            else:
                elimina_transazione(transazione_originale['id_transazione'])
            
            # Crea la nuova transazione
            return self._esegui_aggiunta(dati_nuovi)

    def _esegui_aggiunta(self, dati):
        # Get master_key from session for encryption
        master_key_b64 = self.controller.page.session.get("master_key")
        
        if dati['is_nuovo_conto_condiviso']:
            id_utente_autore = self.controller.get_user_id()
            return aggiungi_transazione_condivisa(
                id_utente_autore=id_utente_autore, id_conto_condiviso=dati['id_conto'],
                data=dati['data'], descrizione=dati['descrizione'], importo=dati['importo'],
                id_sottocategoria=dati['id_sottocategoria'], master_key_b64=master_key_b64
            ) is not None
        else:
            return aggiungi_transazione(
                id_conto=dati['id_conto'], data=dati['data'], descrizione=dati['descrizione'],
                importo=dati['importo'], id_sottocategoria=dati['id_sottocategoria'], master_key_b64=master_key_b64
            ) is not None

    def _salva_nuova_transazione(self, e):
        dati_validati = self._valida_e_raccogli_dati()
        if not dati_validati:
            return

        transazione_in_modifica = self.controller.page.session.get("transazione_in_modifica")
        success = False
        messaggio = ""

        try:
            if transazione_in_modifica:
                success = self._esegui_modifica(dati_validati, transazione_in_modifica)
                messaggio = "modificata" if success else "errore nella modifica"
            else:
                success = self._esegui_aggiunta(dati_validati)
                messaggio = "aggiunta" if success else "errore nell'aggiunta"

            if success:
                self.controller.db_write_operation()
                self.open = False
                self.controller.show_snack_bar(f"Transazione {messaggio} con successo!", success=True)
            else:
                self.controller.show_snack_bar(f"❌ {messaggio.capitalize()}.", success=False)

        except Exception as ex:
            print(f"Errore salvataggio transazione: {ex}")
            traceback.print_exc()
            self.controller.show_error_dialog(f"Errore inaspettato durante il salvataggio: {ex}")

        if self.controller.page: self.controller.page.update()