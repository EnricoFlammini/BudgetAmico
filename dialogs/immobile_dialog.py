import flet as ft
import traceback
from db.gestione_db import aggiungi_immobile, modifica_immobile, ottieni_prestiti_famiglia


class ImmobileDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.loc = controller.loc
        self.modal = True
        self.title = ft.Text()

        self.id_immobile_in_modifica = None

        self.txt_nome = ft.TextField()
        self.txt_via = ft.TextField()
        self.txt_citta = ft.TextField()
        self.txt_valore_acquisto = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_valore_attuale = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.chk_nuda_proprieta = ft.Checkbox()
        self.dd_prestito_collegato = ft.Dropdown(on_change=self._on_prestito_change)

        self.content = ft.Column(
            [
                self.txt_nome,
                self.txt_via,
                self.txt_citta,
                self.txt_valore_acquisto,
                self.txt_valore_attuale,
                self.chk_nuda_proprieta,
                self.dd_prestito_collegato,
            ],
            tight=True,
            spacing=10,
            height=500,
            width=500,
            scroll=ft.ScrollMode.ADAPTIVE
        )
        self.actions = [
            ft.TextButton(on_click=self.chiudi_dialog),
            ft.TextButton(on_click=self.salva_immobile),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _update_texts(self):
        """Aggiorna tutti i testi fissi con le traduzioni correnti."""
        loc = self.loc
        self.title.value = loc.get("manage_property_dialog")
        self.txt_nome.label = loc.get("property_name")
        self.txt_via.label = loc.get("address")
        self.txt_citta.label = loc.get("city")
        self.txt_valore_acquisto.label = loc.get("purchase_value")
        self.txt_valore_acquisto.prefix_text = loc.currencies[loc.currency]['symbol']
        self.txt_valore_attuale.label = loc.get("current_value")
        self.txt_valore_attuale.prefix_text = loc.currencies[loc.currency]['symbol']
        self.chk_nuda_proprieta.label = loc.get("bare_ownership")
        self.dd_prestito_collegato.label = loc.get("linked_mortgage")
        self.actions[0].text = loc.get("cancel")
        self.actions[1].text = loc.get("save")

    def apri_dialog_immobile(self, immobile_data=None):
        self._update_texts()
        self._reset_fields()
        self._popola_dropdown_prestiti()

        if immobile_data:
            self.title.value = self.loc.get("edit_property")
            self.id_immobile_in_modifica = immobile_data['id_immobile']
            self.txt_nome.value = immobile_data['nome']
            self.txt_via.value = immobile_data.get('via', '')
            self.txt_citta.value = immobile_data.get('citta', '')
            self.txt_valore_acquisto.value = str(immobile_data['valore_acquisto'])
            self.txt_valore_attuale.value = str(immobile_data['valore_attuale'])
            self.chk_nuda_proprieta.value = bool(immobile_data['nuda_proprieta'])
            self.dd_prestito_collegato.value = immobile_data.get('id_prestito_collegato')
        else:
            self.title.value = self.loc.get("add_property")
            self.id_immobile_in_modifica = None

        self.controller.page.dialog = self
        self.open = True
        self.controller.page.update()

    def _reset_fields(self):
        for field in [self.txt_nome, self.txt_via, self.txt_citta, self.txt_valore_acquisto, self.txt_valore_attuale]:
            field.value = ""
            field.error_text = None
        self.chk_nuda_proprieta.value = False
        self.dd_prestito_collegato.value = None

    def _popola_dropdown_prestiti(self):
        id_famiglia = self.controller.get_family_id()
        prestiti = ottieni_prestiti_famiglia(id_famiglia)
        self.dd_prestito_collegato.options = [
            ft.dropdown.Option(key=None, text="Nessuno"),
            ft.dropdown.Option(key="__new__", text=self.loc.get("create_new_mortgage"))
        ]
        self.dd_prestito_collegato.options.extend(
            [ft.dropdown.Option(key=p['id_prestito'], text=p['nome']) for p in prestiti if p['tipo'] == 'Mutuo']
        )

    def _on_prestito_change(self, e):
        if self.dd_prestito_collegato.value == "__new__":
            # Chiudi questo dialogo e apri quello per creare un prestito
            self.open = False
            self.controller.page.update()
            self.controller.prestito_dialogs.apri_dialog_prestito(tipo_default='Mutuo')


    def chiudi_dialog(self, e):
        self.open = False
        self.controller.page.update()

    def salva_immobile(self, e):
        if not self.txt_nome.value or not self.txt_valore_attuale.value:
            self.txt_nome.error_text = self.loc.get("fill_all_fields") if not self.txt_nome.value else None
            self.txt_valore_attuale.error_text = self.loc.get(
                "fill_all_fields") if not self.txt_valore_attuale.value else None
            self.content.update()
            return

        try:
            valore_acquisto = float(self.txt_valore_acquisto.value.replace(",", ".")) if self.txt_valore_acquisto.value else 0.0
            valore_attuale = float(self.txt_valore_attuale.value.replace(",", "."))

            success = False
            if self.id_immobile_in_modifica:
                success = modifica_immobile(
                    self.id_immobile_in_modifica, self.txt_nome.value, self.txt_via.value, self.txt_citta.value,
                    valore_acquisto, valore_attuale, self.chk_nuda_proprieta.value, self.dd_prestito_collegato.value
                )
            else:
                id_famiglia = self.controller.get_family_id()
                success = aggiungi_immobile(
                    id_famiglia, self.txt_nome.value, self.txt_via.value, self.txt_citta.value,
                    valore_acquisto, valore_attuale, self.chk_nuda_proprieta.value, self.dd_prestito_collegato.value
                )

            if success:
                self.controller.show_snack_bar("Immobile salvato con successo!", success=True)
                self.open = False
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("Errore durante il salvataggio dell'immobile.", success=False)

        except ValueError:
            self.txt_valore_acquisto.error_text = self.loc.get("invalid_amount")
            self.txt_valore_attuale.error_text = self.loc.get("invalid_amount")
            self.content.update()
        except Exception as ex:
            print(f"Errore salvataggio immobile: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore inaspettato: {ex}", success=False)