import flet as ft
import datetime
import traceback
from db.gestione_db import (
    ottieni_tutti_i_conti_famiglia,
    ottieni_tutti_i_conti_utente,
    esegui_giroconto,
    ottieni_salvadanai_conto,
    esegui_giroconto_salvadanaio
)


class GirocontoDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # self.controller.page = controller.page # Removed for Flet 0.80 compatibility
        self.loc = controller.loc

        self.modal = True
        self.title = ft.Text()

        self.dd_conto_sorgente = ft.Dropdown(expand=True)
        self.dd_conto_destinazione = ft.Dropdown(expand=True)
        self.txt_importo = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.txt_descrizione = ft.TextField(expand=True)
        self.txt_data_selezionata = ft.Text(size=16)

        self.content = ft.Column(
            [
                self.dd_conto_sorgente,
                self.dd_conto_destinazione,
                self.txt_importo,
                self.txt_descrizione,
                ft.Row([
                    ft.Text(),  # Etichetta "Data:"
                    self.txt_data_selezionata,
                    ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=self.apri_date_picker),
                ], alignment=ft.MainAxisAlignment.START),
            ],
            tight=True,
            spacing=10,
            height=400,
            width=500,
        )

        self.actions = [
            ft.TextButton(on_click=self.chiudi_dialog),
            ft.TextButton(on_click=self._salva_giroconto),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _update_texts(self):
        """Aggiorna tutti i testi fissi con le traduzioni correnti."""
        self.title.value = self.loc.get("new_transfer_dialog")
        self.dd_conto_sorgente.label = self.loc.get("from_account")
        self.dd_conto_destinazione.label = self.loc.get("to_account")
        self.txt_importo.label = self.loc.get("amount")
        self.txt_importo.prefix_text = self.loc.currencies[self.loc.currency]['symbol']
        self.txt_descrizione.label = self.loc.get("transfer_description_placeholder")
        self.content.controls[4].controls[0].value = self.loc.get("date") + ":"
        self.actions[0].text = self.loc.get("cancel")
        self.actions[1].text = self.loc.get("execute_transfer")

    def apri_date_picker(self, e):
        self.controller.date_picker.on_change = self.on_date_picker_change
        self.controller.page.open(self.controller.date_picker)

    def on_date_picker_change(self, e):
        if self.controller.date_picker.value:
            self.txt_data_selezionata.value = self.controller.date_picker.value.strftime('%Y-%m-%d')
            if self.controller.page: self.controller.page.update()

    def chiudi_dialog(self, e):
        try:
            self.open = False
            self.controller.page.update()
        except Exception as ex:
            print(f"Errore chiusura dialog: {ex}")
            traceback.print_exc()

    def apri_dialog(self):
        self._update_texts()
        self._reset_campi()
        self._popola_dropdowns()
        if self not in self.controller.page.overlay:
            self.controller.page.overlay.append(self)
        self.open = True
        self.controller.page.update()

    def _reset_campi(self):
        self.dd_conto_sorgente.error_text = None
        self.dd_conto_destinazione.error_text = None
        self.txt_importo.error_text = None
        self.dd_conto_sorgente.value = None
        self.dd_conto_destinazione.value = None
        self.txt_importo.value = ""
        self.txt_descrizione.value = ""
        self.txt_data_selezionata.value = datetime.date.today().strftime('%Y-%m-%d')

    def _popola_dropdowns(self):
        id_utente = self.controller.get_user_id()
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia or not id_utente:
            return

        master_key_b64 = self.controller.page.session.get("master_key")

        # Popola conti SORGENTE (solo i miei conti personali e condivisi)
        # Include Salvadanai per ogni conto
        conti_utente = ottieni_tutti_i_conti_utente(id_utente, master_key_b64=master_key_b64)
        conti_sorgente_filtrati = [c for c in conti_utente if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        opzioni_sorgente = []
        
        for c in conti_sorgente_filtrati:
            prefix = "C" if c['is_condiviso'] else "P"
            suffix = " (Condiviso)" if c['is_condiviso'] else ""
            opzioni_sorgente.append(ft.dropdown.Option(key=f"{prefix}{c['id_conto']}", text=f"{c['nome_conto']}{suffix}"))
            
            # Add Salvadanai for this account
            salvadanai = ottieni_salvadanai_conto(c['id_conto'], id_famiglia, master_key_b64, id_utente, is_condiviso=c['is_condiviso'])
            for s in salvadanai:
                 # Key format: S<id_sb>_<parent_key>
                 parent_key = f"{prefix}{c['id_conto']}"
                 opzioni_sorgente.append(ft.dropdown.Option(
                     key=f"S{s['id']}_{parent_key}", 
                     text=f"  ↳ 🐷 {s['nome']} ({self.controller.loc.format_currency(s['importo'])})"
                 ))
                 
        self.dd_conto_sorgente.options = opzioni_sorgente

        # Popola conti DESTINAZIONE (tutti i conti della famiglia, più salvadanai)
        conti_famiglia = ottieni_tutti_i_conti_famiglia(id_famiglia, master_key_b64=master_key_b64, id_utente=id_utente)
        conti_destinazione_filtrati = [c for c in conti_famiglia if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        opzioni_destinazione = []
        for c in conti_destinazione_filtrati:
            prefix = "C" if c['is_condiviso'] else "P"
            # Show owner name for personal accounts, "Condiviso" for shared accounts
            if c['is_condiviso']:
                suffix = " (Condiviso)"
            else:
                proprietario = c.get('proprietario', '')
                suffix = f" ({proprietario})" if proprietario and proprietario != "Sconosciuto" else ""
            
            opzioni_destinazione.append(ft.dropdown.Option(key=f"{prefix}{c['id_conto']}", text=f"{c['nome_conto']}{suffix}"))
            
            # Add Salvadanai for this account
            salvadanai = ottieni_salvadanai_conto(c['id_conto'], id_famiglia, master_key_b64, id_utente, is_condiviso=c['is_condiviso'])
            for s in salvadanai:
                 parent_key = f"{prefix}{c['id_conto']}"
                 opzioni_destinazione.append(ft.dropdown.Option(
                     key=f"S{s['id']}_{parent_key}", 
                     text=f"  ↳ 🐷 {s['nome']} ({self.controller.loc.format_currency(s['importo'])})"
                 ))

        self.dd_conto_destinazione.options = opzioni_destinazione

    def _salva_giroconto(self, e):
        self.controller.show_loading("Attendere...")
        try:
            is_valid = True
            # Reset errori
            self.dd_conto_sorgente.error_text = None
            self.dd_conto_destinazione.error_text = None
            self.txt_importo.error_text = None

            sorgente_key = self.dd_conto_sorgente.value
            destinazione_key = self.dd_conto_destinazione.value

            if not sorgente_key:
                self.dd_conto_sorgente.error_text = self.loc.get("select_source_account")
                is_valid = False
            if not destinazione_key:
                self.dd_conto_destinazione.error_text = self.loc.get("select_destination_account")
                is_valid = False
            if sorgente_key and destinazione_key and sorgente_key == destinazione_key:
                self.dd_conto_destinazione.error_text = self.loc.get("accounts_must_be_different")
                is_valid = False

            importo = 0.0
            try:
                importo = abs(float(self.txt_importo.value.replace(",", ".")))
                if importo <= 0:
                    self.txt_importo.error_text = self.loc.get("amount_not_zero")
                    is_valid = False
            except (ValueError, TypeError):
                self.txt_importo.error_text = self.loc.get("invalid_amount")
                is_valid = False

            if not is_valid:
                self.controller.page.update()
                self.controller.hide_loading()
                return

            # Check if using Salvadanai
            is_source_sb = sorgente_key.startswith("S")
            is_dest_sb = destinazione_key.startswith("S")
            
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            id_famiglia = self.controller.get_family_id()

            if is_source_sb and is_dest_sb:
                self.controller.show_error_dialog("Trasferimento diretto tra salvadanai non ancora supportato.\nPassare prima dal conto principale.")
                self.controller.page.update()
                self.controller.hide_loading()
                return
            
            if is_source_sb:
                # PB -> Account
                # Key format: S<id_sb>_<parent_key>
                sb_part, parent_key_check = sorgente_key.split('_')
                id_salvadanaio = int(sb_part[1:])
                
                # Validation: Can only transfer to OWN parent account
                if destinazione_key != parent_key_check:
                    self.controller.show_error_dialog("Puoi trasferire dai salvadanai SOLO verso il loro conto di origine.")
                    self.controller.page.update()
                    self.controller.hide_loading()
                    return
                
                id_conto = int(destinazione_key[1:])
                is_shared_parent = destinazione_key.startswith("C")
                
                success = esegui_giroconto_salvadanaio(
                    id_conto=id_conto,
                    id_salvadanaio=id_salvadanaio,
                    direzione='da_salvadanaio',
                    importo=importo,
                    data=self.txt_data_selezionata.value,
                    descrizione=self.txt_descrizione.value,
                    master_key_b64=master_key_b64,
                    id_utente=id_utente,
                    id_famiglia=id_famiglia,
                    parent_is_shared=is_shared_parent
                )

            elif is_dest_sb:
                # Account -> PB
                sb_part, parent_key_check = destinazione_key.split('_')
                id_salvadanaio = int(sb_part[1:])
                
                # Validation: Can only transfer FROM own parent account
                if sorgente_key != parent_key_check:
                    self.controller.show_error_dialog("Puoi trasferire nei salvadanai SOLO dal loro conto di origine.")
                    self.controller.page.update()
                    self.controller.hide_loading()
                    return
                
                id_conto = int(sorgente_key[1:])
                is_shared_parent = sorgente_key.startswith("C")
                
                success = esegui_giroconto_salvadanaio(
                    id_conto=id_conto,
                    id_salvadanaio=id_salvadanaio,
                    direzione='verso_salvadanaio',
                    importo=importo,
                    data=self.txt_data_selezionata.value,
                    descrizione=self.txt_descrizione.value,
                    master_key_b64=master_key_b64,
                    id_utente=id_utente,
                    id_famiglia=id_famiglia,
                    parent_is_shared=is_shared_parent
                )
            
            else:
                # Standard Account -> Account
                id_conto_sorgente = int(sorgente_key[1:])
                tipo_sorgente = "personale" if sorgente_key.startswith("P") else "condiviso"
                id_conto_destinazione = int(destinazione_key[1:])
                tipo_destinazione = "personale" if destinazione_key.startswith("P") else "condiviso"
                
                success = esegui_giroconto(
                    id_conto_sorgente, id_conto_destinazione,
                    importo, self.txt_data_selezionata.value,
                    self.txt_descrizione.value,
                    master_key_b64=master_key_b64,
                    tipo_origine=tipo_sorgente,
                    tipo_destinazione=tipo_destinazione,
                    id_utente_autore=id_utente,
                    id_famiglia=id_famiglia
                )

            if success:
                self.controller.show_snack_bar("Giroconto eseguito con successo!", success=True)
                self.chiudi_dialog(None)
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("Errore durante l'esecuzione del giroconto", success=False)

        except Exception as ex:
            print(f"Errore salvataggio giroconto: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore inaspettato: {ex}", success=False)
        finally:
            self.controller.hide_loading()