import flet as ft
import datetime
import traceback
from db.gestione_db import (
    aggiungi_conto,
    modifica_conto,
    compra_asset,
    aggiungi_transazione,
    admin_imposta_saldo_conto_corrente,
    imposta_conto_default_utente,
    ottieni_conto_default_utente,
    ottieni_conti_utente,  # Importa per popolare il dropdown
    ottieni_saldo_iniziale_conto,
    aggiorna_saldo_iniziale_conto,
    admin_imposta_saldo_conto_condiviso
)


class ContoDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc
        self.conto_id_in_modifica = None
        self.is_condiviso_in_modifica = False

        # Dialogo Rettifica Saldo (Admin)
        self.txt_nuovo_saldo = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dialog_rettifica_saldo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Rettifica Saldo Conto"),
            content=self.txt_nuovo_saldo,
            actions=[
                ft.TextButton("Annulla", on_click=self._chiudi_dialog_rettifica),
                ft.TextButton("Salva", on_click=self._salva_rettifica_saldo)
            ]
        )

        # Controlli del dialogo principale
        self.txt_conto_nome = ft.TextField()
        self.dd_conto_tipo = ft.Dropdown(on_change=self._cambia_tipo_conto_in_dialog)
        self.txt_conto_iban = ft.TextField()
        self.txt_conto_saldo_iniziale = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)

        self.container_saldo_iniziale = ft.Container(
            content=ft.Column([
                ft.Text(weight="bold"),
                self.txt_conto_saldo_iniziale
            ]),
            visible=True
        )

        self.lv_asset_iniziali = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, spacing=10, height=200)
        self.btn_aggiungi_riga_asset = ft.TextButton(icon=ft.Icons.ADD, on_click=self._aggiungi_riga_asset_iniziale)

        self.container_asset_iniziali = ft.Container(
            content=ft.Column([
                ft.Text(weight="bold"),
                ft.Text(size=12, color=ft.Colors.GREY_500),
                self.lv_asset_iniziali,
                self.btn_aggiungi_riga_asset
            ]),
            visible=False
        )

        self.chk_conto_default = ft.Checkbox(value=False)

        # Struttura del dialogo
        self.modal = True
        self.title = ft.Text()
        self.content = ft.Column(
            [
                self.txt_conto_nome,
                self.dd_conto_tipo,
                self.txt_conto_iban,
                ft.Divider(),
                self.container_saldo_iniziale,
                self.container_asset_iniziali,
                self.chk_conto_default
            ],
            tight=True,
            spacing=10,
            height=550,
            width=650,
            scroll=ft.ScrollMode.ADAPTIVE
        )
        self.actions = [
            ft.TextButton(on_click=self._chiudi_dialog_conto),
            ft.TextButton(on_click=self._salva_conto),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _update_texts(self):
        """Aggiorna tutti i testi fissi con le traduzioni correnti."""
        loc = self.loc
        self.title.value = loc.get("manage_account")
        self.txt_conto_nome.label = loc.get("account_name_placeholder")
        self.dd_conto_tipo.label = loc.get("account_type")
        self.dd_conto_tipo.options = [
            ft.dropdown.Option("Corrente"), ft.dropdown.Option("Risparmio"),
            ft.dropdown.Option("Investimento"), ft.dropdown.Option("Fondo Pensione"),
            ft.dropdown.Option("Contanti"), ft.dropdown.Option("Altro"),
        ]
        self.txt_conto_iban.label = loc.get("iban_optional")
        self.container_saldo_iniziale.content.controls[0].value = loc.get("set_initial_balance")
        self.txt_conto_saldo_iniziale.label = loc.get("initial_balance_optional")
        self.txt_conto_saldo_iniziale.prefix_text = loc.currencies[loc.currency]['symbol']

        self.container_asset_iniziali.content.controls[0].value = loc.get("initial_assets")
        self.container_asset_iniziali.content.controls[1].value = loc.get("initial_assets_desc")
        self.btn_aggiungi_riga_asset.text = loc.get("add_initial_asset")

        self.chk_conto_default.label = loc.get("set_as_default_account")

        self.actions[0].text = loc.get("cancel")
        self.actions[1].text = loc.get("save")

    def _aggiungi_riga_asset_iniziale(self, e=None):
        loc = self.loc
        # Layout migliorato su due righe per dare più spazio ai campi
        riga_asset = ft.Column(
            [
                ft.Row([
                    ft.TextField(label=loc.get("ticker"), width=100, data="ticker"),
                    ft.TextField(label=loc.get("asset_name"), expand=True, data="nome"),
                    ft.IconButton(
                        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                        icon_color=ft.Colors.RED_400,
                        tooltip=loc.get("remove_asset"),
                        on_click=lambda ev: self._rimuovi_riga_asset_iniziale(ev.control.data)
                    )
                ]),
                ft.Row([
                    ft.TextField(label=loc.get("quantity"), width=100, keyboard_type=ft.KeyboardType.NUMBER,
                                 data="quantita"),
                    ft.TextField(label=loc.get("current_unit_price"), prefix=loc.currencies[loc.currency]['symbol'],
                                 width=140, keyboard_type=ft.KeyboardType.NUMBER, data="prezzo_attuale"),
                    ft.TextField(label=loc.get("avg_purchase_price"), prefix=loc.currencies[loc.currency]['symbol'],
                                 width=140, keyboard_type=ft.KeyboardType.NUMBER, data="costo_medio",
                                 tooltip=loc.get("avg_purchase_price_tooltip")),
                    ft.TextField(label=loc.get("past_gain_loss"), prefix=loc.currencies[loc.currency]['symbol'],
                                 width=140, keyboard_type=ft.KeyboardType.NUMBER, data="gain_loss",
                                 tooltip=loc.get("past_gain_loss_tooltip")),
                ], spacing=5)
            ], spacing=5
        )
        # Assegna il controllo Column al pulsante di rimozione per una facile identificazione
        riga_asset.controls[0].controls[2].data = riga_asset

        self.lv_asset_iniziali.controls.append(riga_asset)
        self.lv_asset_iniziali.controls.append(riga_asset)
        if self.open and self.content.page:
            self.content.update()

    def _rimuovi_riga_asset_iniziale(self, riga_control):
        self.lv_asset_iniziali.controls.remove(riga_control)
        self.lv_asset_iniziali.controls.remove(riga_control)
        if self.open and self.content.page:
            self.content.update()

    def _cambia_tipo_conto_in_dialog(self, e):
        tipo = self.dd_conto_tipo.value
        self.chk_conto_default.visible = (tipo not in ['Investimento', 'Fondo Pensione'])
        if tipo == 'Investimento':
            self.txt_conto_iban.visible = True
            self.container_saldo_iniziale.visible = False
            self.container_asset_iniziali.visible = True
        elif tipo == 'Contanti':
            self.txt_conto_iban.visible = False
            self.container_saldo_iniziale.visible = True
            self.container_asset_iniziali.visible = False
        else:
            self.txt_conto_iban.visible = True
            self.container_saldo_iniziale.visible = True
            self.container_asset_iniziali.visible = False
        if self.open:
            self.content.update()

    def _chiudi_dialog_conto(self, e):
        self.open = False
        self.page.update()

    def apri_dialog_conto(self, e, conto_data=None, escludi_investimento=False):
        self._update_texts()
        
        if escludi_investimento:
            self.dd_conto_tipo.options = [opt for opt in self.dd_conto_tipo.options if opt.key != "Investimento"]

        # Reset errori
        self.txt_conto_nome.error_text = None
        self.txt_conto_iban.error_text = None
        self.txt_conto_saldo_iniziale.error_text = None
        self.lv_asset_iniziali.controls.clear()

        id_utente = self.controller.get_user_id()
        conto_default = ottieni_conto_default_utente(id_utente)
        conto_default_id = conto_default['id'] if conto_default and conto_default['tipo'] == 'personale' else None

        if conto_data:
            # --- MODALITÀ MODIFICA ---
            self.title.value = self.loc.get("edit_account")
            self.conto_id_in_modifica = conto_data['id_conto']
            self.txt_conto_nome.value = conto_data['nome_conto']
            self.dd_conto_tipo.value = conto_data['tipo']
            self.dd_conto_tipo.disabled = False  # Ora si può cambiare il tipo
            self.txt_conto_iban.value = conto_data['iban']

            # Gestione visibilità in base al tipo
            # Saldo iniziale NON modificabile in edit mode (solo tramite rettifica admin)
            self.container_saldo_iniziale.visible = False
            self.container_asset_iniziali.visible = (conto_data['tipo'] == 'Investimento')
            
            self.chk_conto_default.visible = (conto_data['tipo'] not in ['Investimento', 'Fondo Pensione'])
            self.txt_conto_iban.visible = (conto_data['tipo'] != 'Contanti')
            self.chk_conto_default.value = (conto_data['id_conto'] == conto_default_id)
        else:
            # --- MODALITÀ CREAZIONE ---
            self.title.value = self.loc.get("add_account")
            self.conto_id_in_modifica = None
            self.txt_conto_nome.value = ""
            self.dd_conto_tipo.value = "Corrente"
            self.dd_conto_tipo.disabled = False
            self.txt_conto_iban.value = ""
            self.txt_conto_iban.visible = True
            self.txt_conto_saldo_iniziale.value = ""
            self.container_saldo_iniziale.visible = True
            self.container_asset_iniziali.visible = False
            self.chk_conto_default.visible = True
            self.chk_conto_default.value = False
            self._aggiungi_riga_asset_iniziale()  # Aggiungi una riga vuota per gli asset

        # self.controller.page.dialog = self # Deprecated/Conflict with overlay
        if self not in self.controller.page.overlay:
            self.controller.page.overlay.append(self)
        self.open = True
        self.controller.page.update()

    def _salva_conto(self, e):
        try:
            # Get master_key from session for encryption
            master_key_b64 = self.controller.page.session.get("master_key")
            print(f"[DEBUG] Salva Conto. Master Key in sessione: {bool(master_key_b64)}")
            if master_key_b64:
                print(f"[DEBUG] Master Key type: {type(master_key_b64)}")
                print(f"[DEBUG] Master Key len: {len(master_key_b64)}")
                print(f"[DEBUG] Master Key content (partial): {master_key_b64[:10]}")
            
            is_valid = True
            self.txt_conto_nome.error_text = None
            self.txt_conto_iban.error_text = None
            self.txt_conto_saldo_iniziale.error_text = None

            nome = self.txt_conto_nome.value
            tipo = self.dd_conto_tipo.value
            iban = self.txt_conto_iban.value if self.txt_conto_iban.visible else None

            if not nome:
                self.txt_conto_nome.error_text = self.loc.get("fill_all_fields")
                is_valid = False

            saldo_iniziale = 0.0
            lista_asset_iniziali = []

            # La validazione del saldo iniziale e degli asset avviene sempre (creazione e modifica)
            # Ma per modifica, solo se il tipo lo richiede
            if True: # Rimosso check if not self.conto_id_in_modifica
                if tipo == 'Investimento':
                    for riga_asset_widget in self.lv_asset_iniziali.controls:
                        # Estrai i campi di testo dalla riga
                        fields_list = [c for c in
                                       riga_asset_widget.controls[0].controls + riga_asset_widget.controls[1].controls
                                       if isinstance(c, ft.TextField)]
                        fields = {ctrl.data: ctrl for ctrl in fields_list}

                        ticker = fields['ticker'].value.strip().upper()
                        if not ticker: continue  # Salta righe vuote

                        try:
                            quantita = float(fields['quantita'].value.replace(",", "."))
                            prezzo_attuale = float(fields['prezzo_attuale'].value.replace(",", "."))
                            costo_medio_str = fields['costo_medio'].value.replace(",", ".")
                            gain_loss_str = fields['gain_loss'].value.replace(",", ".")

                            costo_medio = 0.0
                            if costo_medio_str:
                                costo_medio = float(costo_medio_str)
                            elif gain_loss_str and quantita > 0:
                                gain_loss = float(gain_loss_str)
                                costo_medio = prezzo_attuale - (gain_loss / quantita)

                            asset = {
                                'ticker': ticker,
                                'nome': fields['nome'].value.strip(),
                                'quantita': quantita,
                                'costo_medio': costo_medio,
                                'prezzo_attuale': prezzo_attuale
                            }
                            if not asset['nome'] or asset['quantita'] <= 0 or asset['costo_medio'] <= 0 or asset[
                                'prezzo_attuale'] <= 0:
                                raise ValueError("Campi asset non validi")

                            lista_asset_iniziali.append(asset)

                        except (ValueError, TypeError):
                            is_valid = False
                            for field in fields.values():
                                if not field.value:
                                    field.error_text = "!"
                            self.controller.show_snack_bar("Errore: controlla i dati degli asset.", success=False)
                            break
                else:  # Per tutti gli altri tipi di conto
                    saldo_str = self.txt_conto_saldo_iniziale.value.replace(",", ".")
                    if saldo_str:
                        try:
                            saldo_iniziale = float(saldo_str)
                        except ValueError:
                            self.txt_conto_saldo_iniziale.error_text = self.loc.get("invalid_amount")
                            is_valid = False

            if not is_valid:
                self.content.update()
                return

            utente_id = self.controller.get_user_id()
            success = False
            messaggio = ""
            new_conto_id = None

            if self.conto_id_in_modifica:
                # Passa il saldo_iniziale come valore_manuale solo se il tipo è 'Fondo Pensione'
                valore_manuale_modifica = saldo_iniziale if tipo == 'Fondo Pensione' else None
                
                success, msg = modifica_conto(self.conto_id_in_modifica, utente_id, nome, tipo, iban, valore_manuale=valore_manuale_modifica)
                messaggio = "modificato" if success else "errore modifica"
                new_conto_id = self.conto_id_in_modifica
                
                if success and tipo != 'Fondo Pensione' and tipo != 'Investimento':
                    # In modifica NON aggiorniamo più il saldo iniziale da qui.
                    pass

            else:
                # Passa il saldo_iniziale come valore_manuale solo se il tipo è 'Fondo Pensione'
                valore_manuale_iniziale = saldo_iniziale if tipo == 'Fondo Pensione' else 0.0
                res = aggiungi_conto(utente_id, nome, tipo, iban, valore_manuale=valore_manuale_iniziale, master_key_b64=master_key_b64)
                if isinstance(res, tuple):
                    new_conto_id, msg = res
                else:
                    new_conto_id = res
                
                if new_conto_id:
                    success = True
                    messaggio = "aggiunto"
                    # Crea la transazione di saldo iniziale solo per i conti che non sono Fondi Pensione
                    if saldo_iniziale != 0 and tipo != 'Fondo Pensione':
                        aggiungi_transazione(new_conto_id, datetime.date.today().strftime('%Y-%m-%d'),
                                             "Saldo Iniziale", saldo_iniziale, master_key_b64=master_key_b64)
                    for asset in lista_asset_iniziali:
                        compra_asset(
                            id_conto_investimento=new_conto_id,
                            ticker=asset['ticker'], nome_asset=asset['nome'], quantita=asset['quantita'],
                            costo_unitario_nuovo=asset['costo_medio'],
                            tipo_mov='INIZIALE',
                            prezzo_attuale_override=asset['prezzo_attuale']
                        )
                else:
                    success = False
                    messaggio = "errore aggiunta"

            if success:
                # Gestisci il conto di default
                if self.chk_conto_default.value and new_conto_id:
                    imposta_conto_default_utente(utente_id, id_conto_personale=new_conto_id)
                else:
                    # Se l'utente deseleziona il conto che era di default, lo rimuove
                    conto_default = ottieni_conto_default_utente(utente_id)
                    if conto_default and conto_default.get('id') == new_conto_id:
                        imposta_conto_default_utente(utente_id, None)

                self.controller.show_snack_bar(f"Conto {messaggio} con successo!", success=True)
                self.open = False
                self.controller.page.update()
                if self in self.controller.page.overlay:
                    self.controller.page.overlay.remove(self)
                self.controller.update_all_views()  # Aggiorna tutte le viste e sincronizza
            else:
                if not self.conto_id_in_modifica and not new_conto_id:
                    self.txt_conto_iban.error_text = self.loc.get("iban_in_use_or_invalid")
                    self.content.update()
                else:
                    self.controller.show_snack_bar(f"Errore durante l'operazione sul conto.", success=False)
                return

        except Exception as ex:
            print(f"Errore salvataggio conto: {ex}")
            traceback.print_exc()
            self.controller.show_error_dialog(f"Errore inaspettato: {ex}")
        finally:
            if self.page: self.page.update()

    # --- Logica per Rettifica Saldo (Admin) ---

    def apri_dialog_rettifica_saldo(self, conto_data, is_condiviso=False):
        self.conto_id_in_modifica = conto_data['id_conto']
        self.is_condiviso_in_modifica = is_condiviso
        self.dialog_rettifica_saldo.title.value = f"Rettifica: {conto_data['nome_conto']}"
        self.txt_nuovo_saldo.label = "Nuovo Saldo Reale"
        self.txt_nuovo_saldo.value = f"{conto_data['saldo_calcolato']:.2f}"
        self.txt_nuovo_saldo.error_text = None

        if self.dialog_rettifica_saldo not in self.controller.page.overlay:
            self.controller.page.overlay.append(self.dialog_rettifica_saldo)
        self.dialog_rettifica_saldo.open = True
        self.controller.page.update()

    def _chiudi_dialog_rettifica(self, e):
        self.dialog_rettifica_saldo.open = False
        self.controller.page.update()
        if self.dialog_rettifica_saldo in self.controller.page.overlay:
            self.controller.page.overlay.remove(self.dialog_rettifica_saldo)
        self.controller.page.update()

    def _salva_rettifica_saldo(self, e):
        try:
            nuovo_saldo = float(self.txt_nuovo_saldo.value.replace(",", "."))
            id_conto = self.conto_id_in_modifica

            if self.is_condiviso_in_modifica:
                success = admin_imposta_saldo_conto_condiviso(id_conto, nuovo_saldo)
            else:
                success = admin_imposta_saldo_conto_corrente(id_conto, nuovo_saldo)

            if success:
                self.controller.show_snack_bar("Saldo rettificato con successo!", success=True)
                self.controller.db_write_operation()
                self._chiudi_dialog_rettifica(e)
            else:
                self.controller.show_snack_bar("Errore durante la rettifica del saldo.", success=False)
        except (ValueError, TypeError):
            self.txt_nuovo_saldo.error_text = "Inserire un importo numerico valido."
            self.dialog_rettifica_saldo.update()