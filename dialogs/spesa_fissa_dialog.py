import flet as ft
import traceback
from db.gestione_db import (
    ottieni_tutti_i_conti_famiglia,
    ottieni_categorie_e_sottocategorie,
    aggiungi_spesa_fissa,
    modifica_spesa_fissa
)


class SpesaFissaDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc
        self.modal = True
        self.title = ft.Text("Gestisci Spesa Fissa")

        self.id_spesa_fissa_in_modifica = None

        self.txt_nome = ft.TextField()
        self.txt_importo = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dd_conto_addebito = ft.Dropdown()
        self.dd_sottocategoria = ft.Dropdown()
        self.dd_giorno_addebito = ft.Dropdown(
            options=[ft.dropdown.Option(str(i)) for i in range(1, 29)]  # Fino a 28 per sicurezza
        )
        self.sw_attiva = ft.Switch(value=True)
        self.cb_addebito_automatico = ft.Checkbox(value=False)

        self.content = ft.Column(
            [
                self.txt_nome,
                self.txt_importo,
                self.dd_conto_addebito,
                self.dd_sottocategoria,
                self.dd_giorno_addebito,
                self.sw_attiva,
                self.cb_addebito_automatico
            ],
            tight=True,
            spacing=10,
            height=450,
            width=500,
        )

        self.actions = [
            ft.TextButton("Annulla", on_click=self._chiudi_dialog),
            ft.TextButton("Salva", on_click=self._salva_cliccato),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _update_texts(self):
        """Aggiorna i testi fissi con le traduzioni."""
        loc = self.loc
        self.txt_nome.label = loc.get("name")
        self.txt_importo.label = loc.get("amount")
        self.txt_importo.prefix_text = loc.currencies[loc.currency]['symbol']
        self.dd_conto_addebito.label = loc.get("debit_account")
        self.dd_sottocategoria.label = loc.get("subcategory")
        self.dd_giorno_addebito.label = loc.get("debit_day_of_month")
        self.sw_attiva.label = loc.get("active")
        self.cb_addebito_automatico.label = loc.get("auto_debit")
        self.actions[0].text = loc.get("cancel")
        self.actions[1].text = loc.get("save")

    def apri_dialog(self, spesa_fissa_data=None):
        self._update_texts()
        self._reset_campi()
        self._popola_dropdowns()

        if spesa_fissa_data:
            self.title.value = "Modifica Spesa Fissa"
            self.id_spesa_fissa_in_modifica = spesa_fissa_data['id_spesa_fissa']
            self.txt_nome.value = spesa_fissa_data['nome']
            self.txt_importo.value = str(abs(spesa_fissa_data['importo']))
import flet as ft
import traceback
from db.gestione_db import (
    ottieni_tutti_i_conti_famiglia,
    ottieni_categorie_e_sottocategorie,
    aggiungi_spesa_fissa,
    modifica_spesa_fissa
)


class SpesaFissaDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc
        self.modal = True
        self.title = ft.Text("Gestisci Spesa Fissa")

        self.id_spesa_fissa_in_modifica = None

        self.txt_nome = ft.TextField()
        self.txt_importo = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dd_conto_addebito = ft.Dropdown()
        self.dd_sottocategoria = ft.Dropdown()
        self.dd_giorno_addebito = ft.Dropdown(
            options=[ft.dropdown.Option(str(i)) for i in range(1, 29)]  # Fino a 28 per sicurezza
        )
        self.sw_attiva = ft.Switch(value=True)
        self.cb_addebito_automatico = ft.Checkbox(value=False)

        self.content = ft.Column(
            [
                self.txt_nome,
                self.txt_importo,
                self.dd_conto_addebito,
                self.dd_sottocategoria,
                self.dd_giorno_addebito,
                self.sw_attiva,
                self.cb_addebito_automatico
            ],
            tight=True,
            spacing=10,
            height=450,
            width=500,
        )

        self.actions = [
            ft.TextButton("Annulla", on_click=self._chiudi_dialog),
            ft.TextButton("Salva", on_click=self._salva_cliccato),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _update_texts(self):
        """Aggiorna i testi fissi con le traduzioni."""
        loc = self.loc
        self.txt_nome.label = loc.get("name")
        self.txt_importo.label = loc.get("amount")
        self.txt_importo.prefix_text = loc.currencies[loc.currency]['symbol']
        self.dd_conto_addebito.label = loc.get("debit_account")
        self.dd_sottocategoria.label = loc.get("subcategory")
        self.dd_giorno_addebito.label = loc.get("debit_day_of_month")
        self.sw_attiva.label = loc.get("active")
        self.cb_addebito_automatico.label = loc.get("auto_debit")
        self.actions[0].text = loc.get("cancel")
        self.actions[1].text = loc.get("save")

    def apri_dialog(self, spesa_fissa_data=None):
        self._update_texts()
        self._reset_campi()
        self._popola_dropdowns()

        if spesa_fissa_data:
            self.title.value = "Modifica Spesa Fissa"
            self.id_spesa_fissa_in_modifica = spesa_fissa_data['id_spesa_fissa']
            self.txt_nome.value = spesa_fissa_data['nome']
            self.txt_importo.value = str(abs(spesa_fissa_data['importo']))

            conto_key = f"{'C' if spesa_fissa_data['id_conto_condiviso_addebito'] else 'P'}{spesa_fissa_data['id_conto_personale_addebito'] or spesa_fissa_data['id_conto_condiviso_addebito']}"
            self.dd_conto_addebito.value = conto_key

            self.dd_sottocategoria.value = spesa_fissa_data.get('id_sottocategoria')
            self.dd_giorno_addebito.value = str(spesa_fissa_data['giorno_addebito'])
            self.sw_attiva.value = bool(spesa_fissa_data['attiva'])
            self.cb_addebito_automatico.value = bool(spesa_fissa_data['addebito_automatico'])
        else:
            self.title.value = self.loc.get("add_fixed_expense")
            self.id_spesa_fissa_in_modifica = None

        if self not in self.controller.page.overlay:
            self.controller.page.overlay.append(self)
        self.open = True
        self.controller.page.update()

    def _chiudi_dialog(self, e):
        self.open = False
        self.controller.page.update()
        if self in self.controller.page.overlay:
            self.controller.page.overlay.remove(self)
        self.controller.page.update()

    def _reset_campi(self):
        self.txt_nome.value = ""
        self.txt_importo.value = ""
        self.dd_conto_addebito.value = None
        self.dd_sottocategoria.value = None
        self.dd_giorno_addebito.value = "1"
        self.sw_attiva.value = True
        self.cb_addebito_automatico.value = False
        self.txt_nome.error_text = None
        self.txt_importo.error_text = None
        self.dd_conto_addebito.error_text = None
        self.dd_sottocategoria.error_text = None

    def _popola_dropdowns(self):
        # Popola conti
        conti = ottieni_tutti_i_conti_famiglia(self.controller.get_family_id())
        options_conti = []
        for conto in conti:
            tipo_prefix = "C" if conto.get('condiviso') else "P"
            key = f"{tipo_prefix}{conto['id_conto']}"
            text = f"{conto['nome_conto']} ({'Condiviso' if conto.get('condiviso') else 'Personale'})"
            options_conti.append(ft.dropdown.Option(key, text))
        self.dd_conto_addebito.options = options_conti

        # Popola categorie
        cats_subcats = ottieni_categorie_e_sottocategorie(self.controller.get_family_id())
        options_subcats = []
        for cat in cats_subcats:
            for sub in cat['sottocategorie']:
                options_subcats.append(ft.dropdown.Option(sub['id_sottocategoria'], f"{cat['nome']} - {sub['nome']}"))
        self.dd_sottocategoria.options = options_subcats

    def _salva_cliccato(self, e):
        if not self._valida_campi():
            self.content.update()
            return

        try:
            nome = self.txt_nome.value
            importo = float(self.txt_importo.value.replace(",", "."))
            
            # Parsa conto
            conto_key = self.dd_conto_addebito.value
            is_condiviso = conto_key.startswith("C")
            id_conto = int(conto_key[1:])
            id_conto_personale = None if is_condiviso else id_conto
            id_conto_condiviso = id_conto if is_condiviso else None

            id_sottocategoria = int(self.dd_sottocategoria.value)
            giorno = int(self.dd_giorno_addebito.value)
            attiva = self.sw_attiva.value
            auto = self.cb_addebito_automatico.value

            success = False
            if self.id_spesa_fissa_in_modifica:
                success = modifica_spesa_fissa(
                    self.id_spesa_fissa_in_modifica, nome, importo, id_sottocategoria,
                    id_conto_personale, id_conto_condiviso, giorno, attiva, auto
                )
            else:
                success = aggiungi_spesa_fissa(
                    self.controller.get_family_id(), nome, importo, id_sottocategoria,
                    id_conto_personale, id_conto_condiviso, giorno, attiva, auto
                )

            if success:
                self.controller.show_snack_bar("Spesa fissa salvata!", success=True)
                self._chiudi_dialog(None)
                self.controller.update_all_views()
            else:
                self.controller.show_snack_bar("Errore nel salvataggio.", success=False)

        except Exception as ex:
            print(f"Errore salvataggio spesa fissa: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore: {ex}", success=False)

    def _valida_campi(self):
        is_valid = True
        for field in [self.txt_nome, self.txt_importo, self.dd_conto_addebito, self.dd_sottocategoria, self.dd_giorno_addebito]:
            if not field.value:
                field.error_text = self.loc.get("required_field")
                is_valid = False
            else:
                field.error_text = None
        
        if self.txt_importo.value:
            try:
                if float(self.txt_importo.value.replace(",", ".")) <= 0:
                    self.txt_importo.error_text = self.loc.get("amount_must_be_positive")
                    is_valid = False
            except ValueError:
                self.txt_importo.error_text = self.loc.get("invalid_amount")
                is_valid = False
                
        return is_valid