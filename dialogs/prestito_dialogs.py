import flet as ft
import traceback
import datetime
from db.gestione_db import (
    aggiungi_prestito,
    modifica_prestito,
    ottieni_tutti_i_conti_utente,
    ottieni_categorie_e_sottocategorie,
    effettua_pagamento_rata
)


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
        self.txt_data_inizio = ft.TextField(
            read_only=True,
            suffix=ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH,
                on_click=self._apri_date_picker_inizio
            )
        )
        self.txt_numero_rate = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_rate_residue = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_importo_finanziato = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_importo_interessi = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_importo_rata = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dd_giorno_scadenza = ft.Dropdown(options=[ft.dropdown.Option(str(i)) for i in range(1, 29)])
        self.dd_conto_default = ft.Dropdown()
        self.dd_sottocategoria_default = ft.Dropdown()
        self.cb_addebito_automatico = ft.Checkbox()

        self.dialog_prestito = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column(
                [
                    self.txt_nome, self.dd_tipo, self.txt_descrizione, self.txt_data_inizio,
                    self.txt_numero_rate, self.txt_rate_residue, self.txt_importo_finanziato, self.txt_importo_interessi,
                    self.txt_importo_rata, self.dd_giorno_scadenza, self.dd_conto_default,
                    self.dd_sottocategoria_default, self.cb_addebito_automatico
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
        self.txt_data_pagamento = ft.TextField(read_only=True, on_focus=self._apri_date_picker_pagamento)
        self.dd_conto_pagamento = ft.Dropdown()
        self.dd_sottocategoria_pagamento = ft.Dropdown()

        self.dialog_paga_rata = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([
                self.txt_importo_pagamento, self.txt_data_pagamento,
                self.dd_conto_pagamento, self.dd_sottocategoria_pagamento
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
            ft.dropdown.Option("Finanziamento"), ft.dropdown.Option("Mutuo")
        ]
        self.txt_descrizione.label = loc.get("description")
        self.txt_data_inizio.label = loc.get("start_date")
        self.txt_numero_rate.label = loc.get("total_installments")
        self.txt_rate_residue.label = loc.get("remaining_installments_label")
        self.txt_importo_finanziato.label = loc.get("financed_amount")
        self.txt_importo_finanziato.prefix_text = loc.currencies[loc.currency]['symbol']
        self.txt_importo_interessi.label = loc.get("interest_amount")
        self.txt_importo_interessi.prefix_text = loc.currencies[loc.currency]['symbol']
        self.txt_importo_rata.label = loc.get("monthly_installment")
        self.txt_importo_rata.prefix_text = loc.currencies[loc.currency]['symbol']
        self.dd_giorno_scadenza.label = loc.get("installment_due_day")
        self.dd_conto_default.label = loc.get("default_payment_account")
        self.dd_sottocategoria_default.label = loc.get("default_payment_subcategory")
        self.cb_addebito_automatico.label = loc.get("automatic_debit")

        # Dialogo Paga Rata
        self.dialog_paga_rata.title.value = loc.get("pay_installment_dialog_title")
        self.dialog_paga_rata.actions[0].text = loc.get("cancel")
        self.dialog_paga_rata.actions[1].text = loc.get("execute_payment")
        self.txt_importo_pagamento.label = loc.get("payment_amount")
        self.txt_importo_pagamento.prefix_text = loc.currencies[loc.currency]['symbol']
        self.txt_data_pagamento.label = loc.get("payment_date")
        self.dd_conto_pagamento.label = loc.get("payment_account")
        self.dd_sottocategoria_pagamento.label = loc.get("payment_category")

    def apri_dialog_prestito(self, prestito_data=None, tipo_default=None):
        self._update_texts()
        self._popola_dropdowns_prestito()
        self._reset_fields_prestito()

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
            # Imposta il valore del dropdown in base al tipo di conto
            if prestito_data.get('id_conto_pagamento_default'):
                self.dd_conto_default.value = f"p_{prestito_data['id_conto_pagamento_default']}"
            elif prestito_data.get('id_conto_condiviso_pagamento_default'):
                self.dd_conto_default.value = f"s_{prestito_data['id_conto_condiviso_pagamento_default']}"
            else:
                self.dd_conto_default.value = None
            
            self.dd_sottocategoria_default.value = prestito_data.get('id_sottocategoria_pagamento_default')
            self.cb_addebito_automatico.value = bool(prestito_data.get('addebito_automatico', False))

            # Calcola e imposta le rate residue visualizzate
            if prestito_data['importo_rata'] > 0:
                rate_residue_calc = int(prestito_data['importo_residuo'] / prestito_data['importo_rata'])
                self.txt_rate_residue.value = str(rate_residue_calc)
            else:
                self.txt_rate_residue.value = ""
        else:
            self.dialog_prestito.title.value = self.loc.get("add_loan")
            self.prestito_in_modifica = None
            if tipo_default:
                self.dd_tipo.value = tipo_default

        if self.dialog_prestito not in self.controller.page.overlay:
            self.controller.page.overlay.append(self.dialog_prestito)
        self.dialog_prestito.open = True
        self.controller.page.update()

    def _reset_fields_prestito(self):
        self.txt_nome.value = ""
        self.dd_tipo.value = "Finanziamento"
        self.txt_descrizione.value = ""
        self.txt_data_inizio.value = datetime.date.today().strftime('%Y-%m-%d')
        self.txt_numero_rate.value = ""
        self.txt_rate_residue.value = ""
        self.txt_importo_finanziato.value = ""
        self.txt_importo_interessi.value = ""
        self.txt_importo_rata.value = ""
        self.dd_giorno_scadenza.value = "1"
        self.dd_conto_default.value = None
        self.dd_sottocategoria_default.value = None
        self.cb_addebito_automatico.value = False
        # Reset errori
        for field in [self.txt_nome, self.txt_numero_rate, self.txt_rate_residue, self.txt_importo_finanziato, self.txt_importo_rata]:
            field.error_text = None

    def _popola_dropdowns_prestito(self):
        id_famiglia = self.controller.get_family_id()
        id_utente = self.controller.get_user_id()
        master_key_b64 = self.controller.page.session.get("master_key")

        # Popola dropdown con conti personali E condivisi
        from db.gestione_db import ottieni_conti_condivisi_utente, ottieni_dettagli_conti_utente
        
        conti_personali = ottieni_dettagli_conti_utente(id_utente, master_key_b64=master_key_b64)
        conti_personali_filtrati = [c for c in conti_personali if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        
        conti_condivisi = ottieni_conti_condivisi_utente(id_utente, master_key_b64=master_key_b64)
        conti_condivisi_filtrati = [c for c in conti_condivisi if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        
        opzioni_conti = []
        for c in conti_personali_filtrati:
            opzioni_conti.append(ft.dropdown.Option(key=f"p_{c['id_conto']}", text=c['nome_conto']))
        for c in conti_condivisi_filtrati:
            opzioni_conti.append(ft.dropdown.Option(key=f"s_{c['id_conto']}", text=f"{c['nome_conto']} (Condiviso)"))
        
        self.dd_conto_default.options = opzioni_conti

        categorie_con_sottocategorie = ottieni_categorie_e_sottocategorie(id_famiglia)
        opzioni = []
        for cat_data in categorie_con_sottocategorie:
            if cat_data['sottocategorie']:
                opzioni.append(ft.dropdown.Option(key=f"cat_{cat_data['id_categoria']}", text=cat_data['nome_categoria'], disabled=True))
                for sub in cat_data['sottocategorie']:
                    opzioni.append(
                        ft.dropdown.Option(key=sub['id_sottocategoria'], text=f"  - {sub['nome_sottocategoria']}"))
        self.dd_sottocategoria_default.options = opzioni

    def _chiudi_dialog_prestito(self, e):
        self.controller.show_loading("Attendere...")
        try:
            self.dialog_prestito.open = False
            self.controller.page.update()
        except Exception as ex:
            print(f"Errore chiusura dialog prestito: {ex}")
            traceback.print_exc()
        finally:
            self.controller.hide_loading()

    def _salva_prestito_cliccato(self, e):
        self.controller.show_loading("Attendere...")
        try:
            if not self._valida_campi_prestito():
                self.controller.hide_loading()
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
            # Estrai il tipo di conto e l'ID dal valore del dropdown
            id_conto_default = None
            id_conto_condiviso_default = None
            if self.dd_conto_default.value:
                if self.dd_conto_default.value.startswith('p_'):
                    id_conto_default = int(self.dd_conto_default.value[2:])
                elif self.dd_conto_default.value.startswith('s_'):
                    id_conto_condiviso_default = int(self.dd_conto_default.value[2:])
            
            id_sottocategoria_default = self.dd_sottocategoria_default.value
            addebito_automatico = self.cb_addebito_automatico.value

            # Calcolo importo residuo
            importo_residuo = None
            if self.txt_rate_residue.value:
                rate_residue = int(self.txt_rate_residue.value)
                importo_residuo = rate_residue * importo_rata
            
            success = False
            if self.prestito_in_modifica:
                # Se importo_residuo non è stato ricalcolato (campo vuoto), usa quello esistente
                if importo_residuo is None:
                    importo_residuo = self.prestito_in_modifica['importo_residuo']
                
                master_key_b64 = self.controller.page.session.get("master_key")
                id_utente = self.controller.get_user_id()
                
                success = modifica_prestito(
                    id_prestito=self.prestito_in_modifica['id_prestito'],
                    nome=nome, tipo=tipo, descrizione=descrizione, data_inizio=data_inizio,
                    numero_mesi_totali=numero_rate, importo_finanziato=importo_finanziato,
                    importo_interessi=importo_interessi, importo_rata=importo_rata,
                    giorno_scadenza_rata=giorno_scadenza, id_conto_default=id_conto_default,
                    id_conto_condiviso_default=id_conto_condiviso_default,
                    id_sottocategoria_default=id_sottocategoria_default,
                    importo_residuo=importo_residuo, addebito_automatico=addebito_automatico,
                    master_key_b64=master_key_b64, id_utente=id_utente
                )
            else:
                # Se nuovo prestito e rate residue non specificate, residuo = finanziato + interessi
                if importo_residuo is None:
                    importo_residuo = importo_finanziato + importo_interessi

                master_key_b64 = self.controller.page.session.get("master_key")
                id_utente = self.controller.get_user_id()

                success = aggiungi_prestito(
                    id_famiglia=id_famiglia, nome=nome, tipo=tipo, descrizione=descrizione,
                    data_inizio=data_inizio, numero_mesi_totali=numero_rate,
                    importo_finanziato=importo_finanziato, importo_interessi=importo_interessi,
                    importo_rata=importo_rata, giorno_scadenza_rata=giorno_scadenza,
                    id_conto_default=id_conto_default, id_conto_condiviso_default=id_conto_condiviso_default,
                    id_sottocategoria_default=id_sottocategoria_default,
                    importo_residuo=importo_residuo, addebito_automatico=addebito_automatico,
                    master_key_b64=master_key_b64, id_utente=id_utente
                )

            if success:
                self.controller.show_snack_bar("Prestito salvato con successo!", success=True)
                self.dialog_prestito.open = False
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("Errore durante il salvataggio del prestito.", success=False)

        except Exception as ex:
            print(f"Errore salvataggio prestito: {ex}")
            traceback.print_exc()
            self.controller.show_error_dialog(f"Errore inaspettato: {ex}")
        finally:
            self.controller.hide_loading()

        self.controller.page.update()

    def _valida_campi_prestito(self):
        is_valid = True
        for field in [self.txt_nome, self.txt_numero_rate, self.txt_importo_finanziato, self.txt_importo_rata]:
            field.error_text = None
            if not field.value:
                field.error_text = self.loc.get("required_field")
                is_valid = False

        # Validazione numerica
        for field in [self.txt_numero_rate, self.txt_importo_finanziato, self.txt_importo_rata]:
            try:
                if float(field.value.replace(",", ".")) <= 0:
                    field.error_text = "Deve essere > 0"
                    is_valid = False
            except (ValueError, TypeError):
                if field.value:
                    field.error_text = self.loc.get("invalid_amount")
                    is_valid = False
        
        # Validazione opzionale per rate residue
        if self.txt_rate_residue.value:
            try:
                if int(self.txt_rate_residue.value) < 0:
                     self.txt_rate_residue.error_text = "Non può essere negativo"
                     is_valid = False
            except ValueError:
                self.txt_rate_residue.error_text = self.loc.get("invalid_amount")
                is_valid = False

        self.controller.page.update()
        return is_valid

    def apri_dialog_paga_rata(self, prestito_data):
        self._update_texts()
        self.prestito_per_pagamento = prestito_data
        self.dialog_paga_rata.title.value = f"{self.loc.get('pay_installment')}: {prestito_data['nome']}"

        self.txt_importo_pagamento.value = str(prestito_data['importo_rata'])
        self.txt_data_pagamento.value = datetime.date.today().strftime('%Y-%m-%d')

        # Popola dropdown
        id_utente = self.controller.get_user_id()
        id_famiglia = self.controller.get_family_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        conti = ottieni_tutti_i_conti_utente(id_utente, master_key_b64=master_key_b64)
        conti_filtrati = [c for c in conti if
                          c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        opzioni_conti = []
        for c in conti_filtrati:
            is_condiviso = c.get('is_condiviso') or c.get('condiviso')
            suffix = " (Condiviso)" if is_condiviso else ""
            opzioni_conti.append(ft.dropdown.Option(key=c['id_conto'], text=f"{c['nome_conto']}{suffix}"))
        self.dd_conto_pagamento.options = opzioni_conti

        categorie_con_sottocategorie = ottieni_categorie_e_sottocategorie(id_famiglia)
        opzioni = []
        for cat_data in categorie_con_sottocategorie:
            if cat_data['sottocategorie']:
                opzioni.append(ft.dropdown.Option(key=f"cat_{cat_data['id_categoria']}", text=cat_data['nome_categoria'], disabled=True))
                for sub in cat_data['sottocategorie']:
                    opzioni.append(
                        ft.dropdown.Option(key=sub['id_sottocategoria'], text=f"  - {sub['nome_sottocategoria']}"))
        self.dd_sottocategoria_pagamento.options = opzioni

        self.dd_conto_pagamento.value = prestito_data.get('id_conto_pagamento_default')
        self.dd_sottocategoria_pagamento.value = prestito_data.get('id_sottocategoria_pagamento_default')

        if self.dialog_paga_rata not in self.controller.page.overlay:
            self.controller.page.overlay.append(self.dialog_paga_rata)
        self.dialog_paga_rata.open = True
        self.controller.page.update()

    def _chiudi_dialog_paga_rata(self, e):
        self.controller.show_loading("Attendere...")
        try:
            self.dialog_paga_rata.open = False
            self.controller.page.update()
        except Exception as ex:
            print(f"Errore chiusura dialog paga rata: {ex}")
            traceback.print_exc()
        finally:
            self.controller.hide_loading()

    def _esegui_pagamento_cliccato(self, e):
        self.controller.show_loading("Attendere...")
        try:
            importo = float(self.txt_importo_pagamento.value.replace(",", "."))
            data = self.txt_data_pagamento.value
            id_conto = self.dd_conto_pagamento.value
            id_sottocategoria = self.dd_sottocategoria_pagamento.value

            if not all([importo > 0, data, id_conto, id_sottocategoria]):
                self.controller.show_snack_bar(self.loc.get("fill_all_fields"), success=False)
                return

            success = effettua_pagamento_rata(
                id_prestito=self.prestito_per_pagamento['id_prestito'],
                id_conto_pagamento=id_conto,
                importo_pagato=importo,
                data_pagamento=data,
                id_sottocategoria=id_sottocategoria,
                nome_prestito=self.prestito_per_pagamento['nome']
            )

            if success:
                self.controller.show_snack_bar("Pagamento rata registrato con successo!", success=True)
                self.dialog_paga_rata.open = False
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("Errore durante la registrazione del pagamento.", success=False)

        except Exception as ex:
            print(f"Errore pagamento rata: {ex}")
            traceback.print_exc()
            self.controller.show_error_dialog(f"Errore inaspettato: {ex}")
        finally:
            self.controller.hide_loading()

        self.controller.page.update()

    def _apri_date_picker_inizio(self, e):
        self.controller.date_picker.on_change = lambda ev: self._on_date_picker_change(ev, self.txt_data_inizio)
        self.controller.date_picker.open = True
        self.controller.page.update()

    def _apri_date_picker_pagamento(self, e):
        self.controller.date_picker.on_change = lambda ev: self._on_date_picker_change(ev, self.txt_data_pagamento)
        self.controller.date_picker.open = True
        self.controller.page.update()

    def _on_date_picker_change(self, e, target_field):
        if self.controller.date_picker.value:
            target_field.value = self.controller.date_picker.value.strftime('%Y-%m-%d')
            self.controller.page.update()