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
    elimina_transazione_condivisa,
    ottieni_carte_utente
)
from utils.logger import setup_logger

logger = setup_logger("TransactionDialog")


class TransactionDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # self.controller.page = controller.page # Removed for Flet 0.80 compatibility
        self.loc = controller.loc

        self.modal = True
        self.title = ft.Text(size=20, weight="bold")

        # Controlli del dialogo
        self.txt_data_selezionata = ft.Text(size=16)
        self.radio_tipo_transazione = ft.RadioGroup(content=ft.Row())
        self.txt_descrizione_dialog = ft.TextField()
        self.txt_importo_dialog = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dd_conto_dialog = ft.Dropdown(expand=True)
        self.dd_sottocategoria_dialog = ft.Dropdown(expand=True)
        self.cb_importo_nascosto = ft.Checkbox(value=False)
        
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
                self.cb_importo_nascosto,
            ],
            tight=True, height=450, width=400,
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
        self.cb_importo_nascosto.label = self.loc.get("hide_amount_in_family")
        self.actions[0].text = self.loc.get("cancel")
        self.actions[1].text = self.loc.get("save")
        self.actions[0].disabled = False
        self.actions[1].disabled = False

    def apri_date_picker(self, e):
        self.controller.date_picker.on_change = self.on_date_picker_change
        self.controller.page.open(self.controller.date_picker)

    def on_date_picker_change(self, e):
        if self.controller.date_picker.value:
            self.txt_data_selezionata.value = self.controller.date_picker.value.strftime('%Y-%m-%d')
            if self.controller.page: self.controller.page.update()

    def chiudi_dialog(self, e=None):
        logger.debug("[DIALOG] Closing TransactionDialog")
        try:
            self.open = False
            self.controller.page.session.set("transazione_in_modifica", None)
            if self.controller.page:
                self.controller.page.update()
        except Exception as ex:
            logger.error(f"Errore chiusura dialog transazione: {ex}")
            traceback.print_exc()

    def _popola_dropdowns(self):
        utente_id = self.controller.get_user_id()
        famiglia_id = self.controller.get_family_id()
        master_key_b64 = self.controller.page.session.get("master_key")

        # 1. Cards (Caricate PRIMA dei conti)
        carte = ottieni_carte_utente(utente_id, master_key_b64)
        opzioni_conto = []
        
        if carte:
            # Aggiungi Carte all'inizio
            for c in carte:
                target_acc = c.get('id_conto_contabile')
                is_shared_card = False
                
                if not target_acc:
                     target_acc = c.get('id_conto_contabile_condiviso')
                     if target_acc: is_shared_card = True
                
                if not target_acc:
                    # Fallback
                    target_acc = c.get('id_conto_riferimento')
                    if not target_acc:
                        target_acc = c.get('id_conto_riferimento_condiviso')
                        if target_acc: is_shared_card = True
                
                logger.debug(f"[DEBUG_CARD] Card: {c.get('nome_carta')}, ID: {c.get('id_carta')}, "
                             f"Contabile: {c.get('id_conto_contabile')}, Rif: {c.get('id_conto_riferimento')}, "
                             f"TargetResolved: {target_acc}")

                if target_acc:
                    flag = 'S' if is_shared_card else 'P'
                    key = f"CARD_{c['id_carta']}_{target_acc}_{flag}"
                    opzioni_conto.append(ft.dropdown.Option(key=key, text=f"💳 {c['nome_carta']}"))
            
            # Aggiungi separatore DOPO le carte
            opzioni_conto.append(ft.dropdown.Option(key="DIVIDER", text="-- Conti --", disabled=True))

        # 2. Accounts (Caricati DOPO le carte)
        tutti_i_conti = ottieni_tutti_i_conti_utente(utente_id, master_key_b64=master_key_b64)
        conti_filtrati = [c for c in tutti_i_conti if c['tipo'] not in ['Fondo Pensione']]

        for c in conti_filtrati:
            suffix = " " + self.loc.get("shared_suffix") if c['is_condiviso'] else ""
            prefix = "C" if c['is_condiviso'] else "P"
            opzioni_conto.append(ft.dropdown.Option(key=f"{prefix}{c['id_conto']}", text=f"{c['nome_conto']}{suffix}"))

        self.dd_conto_dialog.options = opzioni_conto

        self.dd_sottocategoria_dialog.options = [
            ft.dropdown.Option(key=None, text=self.loc.get("no_category")),
            ft.dropdown.Option(key="INTERESSI", text="💰 Interessi")
        ]
        if famiglia_id:
            categorie = ottieni_categorie_e_sottocategorie(famiglia_id)
            for cat_data in categorie:
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
        self.cb_importo_nascosto.value = False

    def apri_dialog_nuova_transazione(self, e=None):
        logger.info("[DIALOG] Opening: New Transaction")
        try:
            self._update_texts()
            self.controller.page.session.set("transazione_in_modifica", None)
            self._popola_dropdowns()
            self._reset_campi()

            utente_id = self.controller.get_user_id()
            conto_default_info = ottieni_conto_default_utente(utente_id)
            if conto_default_info:
                if conto_default_info['tipo'] == 'carta':
                    # Find the option key for this card (CARD_{id_carta}_{acc}_{flag})
                    card_id = conto_default_info['id']
                    prefix = f"CARD_{card_id}_"
                    for opt in self.dd_conto_dialog.options:
                        if opt.key and str(opt.key).startswith(prefix):
                            self.dd_conto_dialog.value = opt.key
                            break
                elif conto_default_info['tipo'] == 'condiviso': 
                    self.dd_conto_dialog.value = f"C{conto_default_info['id']}"
                else:
                    self.dd_conto_dialog.value = f"P{conto_default_info['id']}"
                
            if self not in self.controller.page.overlay:
                self.controller.page.overlay.append(self)
            self.open = True
            if self.controller.page: self.controller.page.update()
        except Exception as ex:
            logger.error(f"Errore apertura dialog nuova transazione: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore: {ex}", success=False)

    def apri_dialog_modifica_transazione(self, transazione_dati):
        logger.info(f"[DIALOG] Opening: Edit Transaction (id={transazione_dati.get('id_transazione') or transazione_dati.get('id_transazione_condivisa')})")
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
            
            # Check if card transaction
            if transazione_dati.get('id_carta'):
                 is_shared = transazione_dati.get('id_transazione_condivisa', 0) > 0
                 flag = 'S' if is_shared else 'P'
                 self.dd_conto_dialog.value = f"CARD_{transazione_dati['id_carta']}_{transazione_dati['id_conto']}_{flag}"
            else:
                prefix = "C" if transazione_dati.get('id_transazione_condivisa', 0) > 0 else "P"
                self.dd_conto_dialog.value = f"{prefix}{transazione_dati['id_conto']}"

            self.dd_sottocategoria_dialog.value = transazione_dati.get('id_sottocategoria')
            self.cb_importo_nascosto.value = transazione_dati.get('importo_nascosto', False)

            self.controller.page.session.set("transazione_in_modifica", transazione_dati)
            if self not in self.controller.page.overlay:
                self.controller.page.overlay.append(self)
            self.open = True
            if self.controller.page: self.controller.page.update()
        except Exception as ex:
            logger.error(f"Errore apertura dialog modifica transazione: {ex}")
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
            
            # Gestione speciale per "Interessi"
            id_sottocategoria_raw = self.dd_sottocategoria_dialog.value
            is_interessi = (id_sottocategoria_raw == "INTERESSI")
            
            if is_interessi:
                # Gli interessi sono sempre entrate (importo positivo)
                importo = abs(importo)
                id_sottocategoria = None  # Non associare a nessuna categoria
                if not descrizione:
                    descrizione = "Interessi"
            else:
                if self.radio_tipo_transazione.value == "Spesa":
                    importo = -importo
                id_sottocategoria = id_sottocategoria_raw

            # Extract Account and Card Logic
            val = self.dd_conto_dialog.value
            id_conto = 0
            is_condiviso = False
            id_carta = None
            
            if val.startswith("CARD_"):
                parts = val.split("_")
                id_carta = int(parts[1])
                id_conto = int(parts[2])
                if len(parts) > 3:
                     is_condiviso = (parts[3] == 'S')
                else:
                     is_condiviso = False
            else:
                id_conto = int(val[1:])
                is_condiviso = val.startswith('C')

            return {
                "data": data, "descrizione": descrizione, "importo": importo,
                "id_sottocategoria": id_sottocategoria,
                "id_conto": id_conto,
                "is_nuovo_conto_condiviso": is_condiviso,
                "importo_nascosto": self.cb_importo_nascosto.value,
                "id_carta": id_carta
            }
        except Exception as ex:
            logger.error(f"Errore validazione dati transazione: {ex}")
            traceback.print_exc()
            return None

    def _esegui_modifica(self, dati_nuovi, transazione_originale):
        # Get master_key from session for encryption
        master_key_b64 = self.controller.page.session.get("master_key")
        
        is_originale_condivisa = transazione_originale.get('id_transazione_condivisa', 0) > 0
        is_nuova_condivisa = dati_nuovi['is_nuovo_conto_condiviso']

        # Caso 1: Il tipo di conto non è cambiato (Personale -> Personale o Condiviso -> Condiviso)
        # Caso 1: Il tipo di conto non è cambiato (Personale -> Personale o Condiviso -> Condiviso)
        if is_originale_condivisa == is_nuova_condivisa:
            if is_originale_condivisa:
                id_trans = transazione_originale['id_transazione_condivisa']
                id_utente = self.controller.get_user_id()
                return modifica_transazione_condivisa(id_trans, dati_nuovi['data'], dati_nuovi['descrizione'], dati_nuovi['importo'], dati_nuovi['id_sottocategoria'], master_key_b64=master_key_b64, id_utente=id_utente, importo_nascosto=dati_nuovi.get('importo_nascosto', False), id_carta=dati_nuovi.get('id_carta'))
            else:
                id_trans = transazione_originale['id_transazione']
                return modifica_transazione(
                    id_trans, dati_nuovi['data'], dati_nuovi['descrizione'], dati_nuovi['importo'], 
                    dati_nuovi['id_sottocategoria'], dati_nuovi['id_conto'], 
                    master_key_b64=master_key_b64, importo_nascosto=dati_nuovi.get('importo_nascosto', False),
                    id_carta=dati_nuovi.get('id_carta')
                )
        
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
                id_sottocategoria=dati['id_sottocategoria'], master_key_b64=master_key_b64,
                importo_nascosto=dati.get('importo_nascosto', False), id_carta=dati.get('id_carta')
            ) is not None
        else:
            return aggiungi_transazione(
                id_conto=dati['id_conto'], data=dati['data'], descrizione=dati['descrizione'],
                importo=dati['importo'], id_sottocategoria=dati['id_sottocategoria'], 
                master_key_b64=master_key_b64, importo_nascosto=dati.get('importo_nascosto', False),
                id_carta=dati.get('id_carta')
            ) is not None

    def _salva_nuova_transazione(self, e):
        # 1. Feedback locale: Disabilita pulsanti e cambia testo
        save_btn = self.actions[1]
        cancel_btn = self.actions[0]
        original_text = save_btn.text
        
        save_btn.text = "Salvataggio..."
        save_btn.disabled = True
        cancel_btn.disabled = True
        self.update()

        try:
            dati_validati = self._valida_e_raccogli_dati()
            if not dati_validati:
                # Ripristina pulsanti se validazione fallisce
                save_btn.text = original_text
                save_btn.disabled = False
                cancel_btn.disabled = False
                self.update()
                return

            transazione_in_modifica = self.controller.page.session.get("transazione_in_modifica")
            success = False
            messaggio = ""

            # Esegue l'operazione (sincrona per ora)
            if transazione_in_modifica:
                success = self._esegui_modifica(dati_validati, transazione_in_modifica)
                messaggio = "modificata" if success else "errore nella modifica"
            else:
                success = self._esegui_aggiunta(dati_validati)
                messaggio = "aggiunta" if success else "errore nell'aggiunta"

            if success:
                # 2. Chiudi il dialog PRIMA di aggiornare la dashboard
                self.open = False
                
                # Reset pulsanti
                save_btn.text = original_text
                save_btn.disabled = False
                cancel_btn.disabled = False

                self.controller.page.update()
                
                # 3. Ora avvia l'aggiornamento globale (che mostrerà lo spinner correttamente)
                self.controller.db_write_operation()
                logger.info(f"[DB] Transaction saved successfully: {messaggio}")
                self.controller.show_snack_bar(f"Transazione {messaggio} con successo!", success=True)
            else:
                logger.warning(f"[DB] Transaction save failed: {messaggio}")
                self.controller.show_snack_bar(f"❌ {messaggio.capitalize()}.", success=False)
                # Ripristina pulsanti in caso di errore logico
                save_btn.text = original_text
                save_btn.disabled = False
                cancel_btn.disabled = False
                self.update()

        except Exception as ex:
            logger.error(f"Errore salvataggio transazione: {ex}")
            traceback.print_exc()
            self.controller.show_error_dialog(f"Errore inaspettato durante il salvataggio: {ex}")
            # Ripristina pulsanti
            save_btn.text = original_text
            save_btn.disabled = False
            cancel_btn.disabled = False
            self.update()