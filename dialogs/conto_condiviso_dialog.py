import flet as ft
import datetime
import traceback
from db.gestione_db import (
    crea_conto_condiviso,
    modifica_conto_condiviso,
    ottieni_utenti_famiglia,
    ottieni_dettagli_conto_condiviso,
    aggiungi_transazione_condivisa,
    ottieni_categorie
)


class ContoCondivisoDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc

        self.modal = True
        self.title = ft.Text()

        self.txt_nome_conto = ft.TextField(autofocus=True)
        self.dd_tipo_conto = ft.Dropdown()
        self.dd_tipo_condivisione = ft.Dropdown(on_change=self._on_tipo_condivisione_change)

        self.partecipanti_title = ft.Text(weight="bold")
        self.lv_partecipanti = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, height=150)
        self.container_partecipanti = ft.Container(
            content=ft.Column([
                self.partecipanti_title,
                self.lv_partecipanti
            ]),
            visible=False
        )

        self.txt_saldo_iniziale = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)

        self.content = ft.Column(
            [
                self.txt_nome_conto,
                self.dd_tipo_conto,
                self.dd_tipo_condivisione,
                self.container_partecipanti,
                self.txt_saldo_iniziale
            ],
            tight=True,
            spacing=10,
            height=500,
            width=600,
            scroll=ft.ScrollMode.ADAPTIVE
        )
        self.actions = [
            ft.TextButton(on_click=self._chiudi_dialog),
            ft.TextButton(on_click=self._salva_conto_condiviso)
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

        self.id_conto_condiviso_in_modifica = None

    def _update_texts(self):
        """Aggiorna tutti i testi fissi con le traduzioni correnti."""
        self.title.value = self.loc.get("manage_shared_account_dialog")
        self.txt_nome_conto.label = self.loc.get("shared_account_name")
        self.dd_tipo_conto.label = self.loc.get("account_type")
        self.dd_tipo_conto.options = [
            ft.dropdown.Option("Corrente"),
            ft.dropdown.Option("Risparmio"),
            ft.dropdown.Option("Contanti"),
            ft.dropdown.Option("Altro"),
        ]
        self.dd_tipo_condivisione.label = self.loc.get("sharing_type")
        self.dd_tipo_condivisione.options = [
            ft.dropdown.Option("famiglia", self.loc.get("sharing_type_family")),
            ft.dropdown.Option("utenti", self.loc.get("sharing_type_users"))
        ]
        self.partecipanti_title.value = self.loc.get("select_participants")
        self.txt_saldo_iniziale.label = self.loc.get("initial_balance_optional")
        self.txt_saldo_iniziale.prefix_text = self.loc.currencies[self.loc.currency]['symbol']
        self.actions[0].text = self.loc.get("cancel")
        self.actions[1].text = self.loc.get("save")

    def _on_tipo_condivisione_change(self, e):
        if self.dd_tipo_condivisione.value == 'utenti':
            self.container_partecipanti.visible = True
            self._popola_lista_utenti()
        else:
            self.container_partecipanti.visible = False
            self.lv_partecipanti.controls.clear()
        self.content.update()

    def _popola_lista_utenti(self, utenti_selezionati_ids=None):
        self.lv_partecipanti.controls.clear()
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            self.lv_partecipanti.controls.append(ft.Text("Nessuna famiglia associata per selezionare utenti."))
            return

        utenti_famiglia = ottieni_utenti_famiglia(famiglia_id)
        for user in utenti_famiglia:
            self.lv_partecipanti.controls.append(
                ft.Checkbox(
                    label=user['nome_visualizzato'],
                    value=user['id_utente'] in (utenti_selezionati_ids if utenti_selezionati_ids else []),
                    data=user['id_utente']
                )
            )
        self.content.update()

    def apri_dialog(self, conto_data=None):
        self._update_texts()
        self.txt_nome_conto.error_text = None
        self.txt_saldo_iniziale.error_text = None
        self.txt_nome_conto.value = ""
        self.dd_tipo_conto.value = "Corrente"
        self.dd_tipo_condivisione.value = "famiglia"
        self.container_partecipanti.visible = False
        self.lv_partecipanti.controls.clear()
        self.txt_saldo_iniziale.value = ""
        self.id_conto_condiviso_in_modifica = None

        if conto_data:
            self.title.value = self.loc.get("edit_shared_account")
            self.id_conto_condiviso_in_modifica = conto_data['id_conto']
            dettagli_conto = ottieni_dettagli_conto_condiviso(conto_data['id_conto'])
            if dettagli_conto:
                self.txt_nome_conto.value = dettagli_conto['nome_conto']
                self.dd_tipo_conto.value = dettagli_conto['tipo']
                self.dd_tipo_condivisione.value = dettagli_conto['tipo_condivisione']
                if dettagli_conto['tipo_condivisione'] == 'utenti':
                    self.container_partecipanti.visible = True
                    utenti_selezionati_ids = [p['id_utente'] for p in dettagli_conto.get('partecipanti', [])]
                    self._popola_lista_utenti(utenti_selezionati_ids)
        else:
            self.title.value = self.loc.get("create_shared_account")
            self.dd_tipo_condivisione.value = "famiglia"

        self.open = True
        self.controller.page.update()

    def _chiudi_dialog(self, e):
        self.open = False
        self.controller.page.update()

    def _salva_conto_condiviso(self, e):
        try:
            is_valid = True
            self.txt_nome_conto.error_text = None
            self.txt_saldo_iniziale.error_text = None

            nome_conto = self.txt_nome_conto.value
            tipo_conto = self.dd_tipo_conto.value
            tipo_condivisione = self.dd_tipo_condivisione.value

            if not nome_conto:
                self.txt_nome_conto.error_text = self.loc.get("fill_all_fields")
                is_valid = False

            lista_utenti_selezionati = []
            if tipo_condivisione == 'utenti':
                for checkbox in self.lv_partecipanti.controls:
                    if isinstance(checkbox, ft.Checkbox) and checkbox.value:
                        lista_utenti_selezionati.append(checkbox.data)
                if not lista_utenti_selezionati:
                    self.controller.show_snack_bar(self.loc.get("select_at_least_one_participant"), success=False)
                    is_valid = False

            saldo_iniziale = 0.0
            if self.txt_saldo_iniziale.value:
                try:
                    saldo_iniziale = float(self.txt_saldo_iniziale.value.replace(",", "."))
                except ValueError:
                    self.txt_saldo_iniziale.error_text = self.loc.get("invalid_amount")
                    is_valid = False

            if not is_valid:
                self.content.update()
                return

            famiglia_id = self.controller.get_family_id()
            success = False
            messaggio = ""
            id_conto_condiviso_salvato = None

            if self.id_conto_condiviso_in_modifica:
                success = modifica_conto_condiviso(
                    self.id_conto_condiviso_in_modifica,
                    nome_conto,
                    tipo_conto,
                    lista_utenti_selezionati if tipo_condivisione == 'utenti' else None
                )
                messaggio = "modificato" if success else "errore modifica"
                id_conto_condiviso_salvato = self.id_conto_condiviso_in_modifica
            else:
                id_conto_condiviso_salvato = crea_conto_condiviso(
                    famiglia_id,
                    nome_conto,
                    tipo_conto,
                    tipo_condivisione,
                    lista_utenti_selezionati if tipo_condivisione == 'utenti' else None
                )
                success = id_conto_condiviso_salvato is not None
                messaggio = "aggiunto" if success else "errore aggiunta"

            if success and saldo_iniziale != 0 and id_conto_condiviso_salvato:
                oggi = datetime.date.today().strftime('%Y-%m-%d')
                id_utente_autore = self.controller.get_user_id()
                if id_utente_autore:
                    aggiungi_transazione_condivisa(id_utente_autore, id_conto_condiviso_salvato, oggi, "Saldo Iniziale",
                                                   saldo_iniziale)
                else:
                    print("❌ Errore: Impossibile aggiungere saldo iniziale perché l'ID utente non è stato trovato.")
                    self.controller.show_snack_bar("Errore: ID utente non trovato.", success=False)

            if success:
                self.controller.show_snack_bar(f"Conto condiviso {messaggio} con successo!", success=True)
                self.open = False
                self.controller.update_all_views()
            else:
                self.controller.show_snack_bar(f"❌ Errore: {messaggio.capitalize()}.", success=False)

            self.controller.page.update()

        except Exception as ex:
            print(f"Errore salvataggio conto condiviso: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore inaspettato: {ex}", success=False)
            self.controller.page.update()