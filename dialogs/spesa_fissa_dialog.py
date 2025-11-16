import flet as ft
import traceback
from db.gestione_db import (
    ottieni_tutti_i_conti_famiglia,
    ottieni_categorie,
    aggiungi_spesa_fissa,
    modifica_spesa_fissa
)


class SpesaFissaDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.page = controller.page
        self.modal = True
        self.title = ft.Text("Gestisci Spesa Fissa")

        self.id_spesa_fissa_in_modifica = None

        self.txt_nome = ft.TextField(label="Nome Spesa (es. Abbonamento Netflix)")
        self.txt_importo = ft.TextField(label="Importo", prefix="€", keyboard_type=ft.KeyboardType.NUMBER)
        self.dd_conto_addebito = ft.Dropdown(label="Conto di Addebito")
        self.dd_categoria = ft.Dropdown(label="Categoria")
        self.dd_giorno_addebito = ft.Dropdown(
            label="Giorno del Mese per l'Addebito",
            options=[ft.dropdown.Option(str(i)) for i in range(1, 29)]  # Fino a 28 per sicurezza
        )
        self.sw_attiva = ft.Switch(label="Attiva", value=True)

        self.content = ft.Column(
            [
                self.txt_nome,
                self.txt_importo,
                self.dd_conto_addebito,
                self.dd_categoria,
                self.dd_giorno_addebito,
                self.sw_attiva
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

    def apri_dialog(self, spesa_fissa_data=None):
        self._reset_campi()
        self._popola_dropdowns()

        if spesa_fissa_data:
            self.title.value = "Modifica Spesa Fissa"
            self.id_spesa_fissa_in_modifica = spesa_fissa_data['id_spesa_fissa']
            self.txt_nome.value = spesa_fissa_data['nome']
            self.txt_importo.value = str(abs(spesa_fissa_data['importo']))

            conto_key = f"{'C' if spesa_fissa_data['id_conto_condiviso_addebito'] else 'P'}{spesa_fissa_data['id_conto_personale_addebito'] or spesa_fissa_data['id_conto_condiviso_addebito']}"
            self.dd_conto_addebito.value = conto_key

            self.dd_categoria.value = spesa_fissa_data['id_categoria']
            self.dd_giorno_addebito.value = str(spesa_fissa_data['giorno_addebito'])
            self.sw_attiva.value = bool(spesa_fissa_data['attiva'])
        else:
            self.title.value = "Aggiungi Spesa Fissa"
            self.id_spesa_fissa_in_modifica = None

        self.page.dialog = self
        self.open = True
        self.page.update()

    def _reset_campi(self):
        for field in [self.txt_nome, self.txt_importo, self.dd_conto_addebito, self.dd_categoria,
                      self.dd_giorno_addebito]:
            field.error_text = None
            if isinstance(field, ft.TextField):
                field.value = ""
            else:
                field.value = None
        self.sw_attiva.value = True

    def _popola_dropdowns(self):
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return

        # Popola conti
        conti_famiglia = ottieni_tutti_i_conti_famiglia(id_famiglia)
        conti_filtrati = [c for c in conti_famiglia if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        opzioni_conto = []
        for c in conti_filtrati:
            prefix = "C" if c['is_condiviso'] else "P"
            owner = f" ({c['proprietario']})" if not c['is_condiviso'] else ""
            opzioni_conto.append(ft.dropdown.Option(key=f"{prefix}{c['id_conto']}", text=f"{c['nome_conto']}{owner}"))
        self.dd_conto_addebito.options = opzioni_conto

        # Popola categorie
        categorie = ottieni_categorie(id_famiglia)
        self.dd_categoria.options = [ft.dropdown.Option(key=cat['id_categoria'], text=cat['nome_categoria']) for cat in
                                     categorie]

    def _chiudi_dialog(self, e):
        self.open = False
        self.page.update()

    def _salva_cliccato(self, e):
        try:
            if self._valida_campi():
                nome = self.txt_nome.value
                importo = abs(float(self.txt_importo.value.replace(",", ".")))
                conto_key = self.dd_conto_addebito.value
                id_categoria = self.dd_categoria.value
                giorno_addebito = int(self.dd_giorno_addebito.value)
                attiva = self.sw_attiva.value

                id_conto_personale = None
                id_conto_condiviso = None
                if conto_key.startswith('P'):
                    id_conto_personale = int(conto_key[1:])
                else:
                    id_conto_condiviso = int(conto_key[1:])

                success = False
                if self.id_spesa_fissa_in_modifica:
                    success = modifica_spesa_fissa(
                        self.id_spesa_fissa_in_modifica, nome, importo, id_conto_personale, id_conto_condiviso,
                        id_categoria, giorno_addebito, attiva
                    )
                else:
                    id_famiglia = self.controller.get_family_id()
                    success = aggiungi_spesa_fissa(
                        id_famiglia, nome, importo, id_conto_personale, id_conto_condiviso,
                        id_categoria, giorno_addebito, attiva
                    )

                if success:
                    self.controller.show_snack_bar("Spesa fissa salvata con successo!", success=True)
                    self.open = False
                    self.controller.db_write_operation()
                else:
                    self.controller.show_snack_bar("❌ Errore durante il salvataggio della spesa fissa.", success=False)

                self.page.update()

        except Exception as ex:
            print(f"Errore salvataggio spesa fissa: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore inaspettato: {ex}", success=False)
            self.page.update()

    def _valida_campi(self):
        is_valid = True
        for field in [self.txt_nome, self.txt_importo, self.dd_conto_addebito, self.dd_categoria,
                      self.dd_giorno_addebito]:
            field.error_text = None
            if not field.value:
                field.error_text = "Campo obbligatorio"
                is_valid = False

        try:
            if float(self.txt_importo.value.replace(",", ".")) <= 0:
                self.txt_importo.error_text = "L'importo deve essere positivo"
                is_valid = False
        except (ValueError, TypeError):
            if self.txt_importo.value:  # solo se c'è un valore
                self.txt_importo.error_text = "Importo non valido"
                is_valid = False

        self.page.update()
        return is_valid