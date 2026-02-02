import flet as ft
import traceback
import datetime
from db.gestione_db import (
    aggiungi_prestito,
    modifica_prestito,
    ottieni_tutti_i_conti_utente,
    ottieni_categorie_e_sottocategorie,
    effettua_pagamento_rata,
    ottieni_membri_famiglia,
    ottieni_quote_prestito,
    aggiungi_rata_piano_ammortamento,
    ottieni_piano_ammortamento,
    ottieni_ids_conti_tecnici_carte
)
from dialogs.piano_ammortamento_dialog import PianoAmmortamentoDialog


class PrestitoDialogs:
    def __init__(self, controller):
        self.controller = controller
        # self.page = controller.page # Removed for Flet 0.80 compatibility
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

        # Button per Piano Ammortamento (visibile sempre, ma con logica diversa in creazione)
        self.btn_piano_ammortamento = ft.ElevatedButton(
            "Gestisci Piano Ammortamento", 
            icon=ft.Icons.TABLE_CHART, 
            on_click=self._apri_piano_ammortamento_click,
            visible=False
        )
        
        self.temp_piano_ammortamento = [] # Lista temporanea per creazione nuovi prestiti

        # Dialogo Piano Ammortamento
        self.piano_ammortamento_dialog = PianoAmmortamentoDialog(controller)

        # Sezione Quote
        self.container_quote = ft.Column(spacing=5)
        self.quote_inputs = {} # Mappa id_utente -> TextField

        # Progress bar per operazioni lunghe
        self.progress_bar = ft.ProgressBar(width=400, color="blue", bgcolor="#eeeeee", visible=False)


        self.dialog_prestito = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column(
                [
                    self.progress_bar, # Spostata in alto per visibilità
                    self.txt_nome, self.dd_tipo, self.txt_descrizione,
                    self.btn_piano_ammortamento, # Spostato in alto come richiesto
                    self.txt_data_inizio,
                    self.txt_numero_rate, self.txt_rate_residue, self.txt_importo_finanziato, self.txt_importo_interessi,
                    self.txt_importo_rata, self.dd_giorno_scadenza, self.dd_conto_default,
                    self.dd_sottocategoria_default, self.cb_addebito_automatico,
                    ft.Divider(),
                    ft.Text("Ripartizione Quote di Competenza", weight=ft.FontWeight.BOLD),
                    self.container_quote
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
        self._update_quote_section()

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
            # Calcola e imposta le rate residue visualizzate
            if prestito_data.get('importo_rata') and float(prestito_data['importo_rata']) > 0:
                rate_residue_calc = int(float(prestito_data['importo_residuo']) / float(prestito_data['importo_rata']))
            else:
                rate_residue_calc = 0
            
            self.txt_rate_residue.value = str(rate_residue_calc)
            # Fine calcolo rate residue
            
            # Mostra bottone piano ammortamento
            self.btn_piano_ammortamento.visible = True

            # CHECK PIANO AMMORTAMENTO e Blocca campi se esiste
            try:
                piano = ottieni_piano_ammortamento(prestito_data['id_prestito'])
                has_piano = len(piano) > 0
                self._set_fields_locked(has_piano)
            except Exception as e:
                print(f"Errore check piano in apri_dialog: {e}")
                
        else:
            self.dialog_prestito.title.value = self.loc.get("add_loan")
            self.prestito_in_modifica = None
            if tipo_default:
                self.dd_tipo.value = tipo_default
            
            # Nascondi bottone in creazione -> ORA VISIBILE SEMPRE
            self.temp_piano_ammortamento = [] # Reset lista temporanea
            self.btn_piano_ammortamento.visible = True
            self._set_fields_locked(False) # Sblocca default in creazione

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

        from db.gestione_db import ottieni_conti_condivisi_utente, ottieni_dettagli_conti_utente
        
        conti_personali = ottieni_dettagli_conti_utente(id_utente, master_key_b64=master_key_b64)
        conti_condivisi = ottieni_conti_condivisi_utente(id_utente, master_key_b64=master_key_b64)
        
        # Identifica ID conti tecnici delle carte da escludere
        ids_conti_tecnici = ottieni_ids_conti_tecnici_carte(id_utente)
        
        # Filtra i conti: escludiamo i conti tecnici delle carte di credito (che hanno solitamente "Saldo" nel nome)
        # ma manteniamo i conti correnti che potrebbero essere marcati come tecnici per le carte di debito.
        conti_personali_filtrati = [
            c for c in conti_personali 
            if c['tipo'] not in ['Investimento', 'Fondo Pensione'] 
            and not (c['id_conto'] in ids_conti_tecnici and "Saldo" in (c.get('nome_conto') or ""))
        ]
        conti_condivisi_filtrati = [
            c for c in conti_condivisi 
            if c['tipo'] not in ['Investimento', 'Fondo Pensione'] 
            and not (c['id_conto'] in ids_conti_tecnici and "Saldo" in (c.get('nome_conto') or ""))
        ]
        
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

    def _update_quote_section(self):
        self.container_quote.controls.clear()
        self.quote_inputs = {}
        
        id_famiglia = self.controller.get_family_id()
        membri = ottieni_membri_famiglia(id_famiglia)
        
        # Recupera quote esistenti se in modifica
        quote_esistenti = {} # id_utente -> perc
        if self.prestito_in_modifica:
            quote_list = ottieni_quote_prestito(self.prestito_in_modifica['id_prestito'])
            for q in quote_list:
                quote_esistenti[q['id_utente']] = q['percentuale']
        else:
            # Default: 100% all'utente corrente
            curr_user = self.controller.get_user_id()
            quote_esistenti[curr_user] = 100.0
            
        for membro in membri:
            uid = membro['id_utente']
            perc_val = quote_esistenti.get(uid, 0.0)
            
            # Text Field per la percentuale
            txt_perc = ft.TextField(
                value=str(perc_val) if perc_val > 0 else "0",
                suffix_text="%",
                width=100,
                keyboard_type=ft.KeyboardType.NUMBER,
                text_align=ft.TextAlign.RIGHT,
                dense=True,
                height=40
            )
            self.quote_inputs[uid] = txt_perc
            
            row = ft.Row([
                ft.Text(membro['nome_visualizzato'], expand=True),
                txt_perc
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            
            self.container_quote.controls.append(row)

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
            # Blocca UI
            self.progress_bar.visible = True
            self.dialog_prestito.actions[0].disabled = True
            self.dialog_prestito.actions[1].disabled = True
            self.controller.page.update()
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
            
            # Parse Quote
            lista_quote = []
            totale_perc = 0.0
            for uid, txt_field in self.quote_inputs.items():
                try:
                    val = float(txt_field.value.replace(",", "."))
                    if val > 0:
                        lista_quote.append({'id_utente': uid, 'percentuale': val})
                        totale_perc += val
                except ValueError:
                    pass
            
            if totale_perc > 100.001:
                self.controller.show_snack_bar(f"Il totale delle quote ({totale_perc}%) supera il 100%!", success=False)
                self.controller.hide_loading()
                return

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
                    master_key_b64=master_key_b64, id_utente=id_utente, lista_quote=lista_quote
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
                    master_key_b64=master_key_b64, id_utente=id_utente, lista_quote=lista_quote
                )
                print(f"[DEBUG] Risultato aggiunta prestito: {success}")

            if success:
                # Se nuovo prestito (success è l'ID) e abbiamo un piano temporaneo, salviamolo ora
                if not self.prestito_in_modifica and self.temp_piano_ammortamento:
                    try:
                        id_new_prestito = success
                        count_rate = 0
                        for rata in self.temp_piano_ammortamento:
                            aggiungi_rata_piano_ammortamento(
                                id_new_prestito, 
                                rata['numero_rata'], 
                                rata['data_scadenza'], 
                                rata['importo_rata'], 
                                rata['quota_capitale'], 
                                rata['quota_interessi'], 
                                rata['spese_fisse'],
                                stato=rata.get('stato', 'da_pagare')
                            )
                            count_rate += 1
                        print(f"Salvate {count_rate} rate del piano ammortamento per prestito {id_new_prestito}")
                    except Exception as e_rata:
                        print(f"Errore salvataggio piano ammortamento differito: {e_rata}")

                self.controller.show_snack_bar("Prestito salvato con successo!", success=True)
                self.dialog_prestito.open = False
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("Errore durante il salvataggio del prestito (DB returned False).", success=False)

        except Exception as ex:
            print(f"Errore salvataggio prestito: {ex}")
            traceback.print_exc()
            self.controller.show_error_dialog(f"Errore inaspettato: {ex}")
        finally:
            self.controller.hide_loading()
            # Sblocca UI
            self.progress_bar.visible = False
            self.dialog_prestito.actions[0].disabled = False
            self.dialog_prestito.actions[1].disabled = False
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
        
        # Identifica ID conti tecnici delle carte da escludere
        ids_conti_tecnici = ottieni_ids_conti_tecnici_carte(id_utente)
        
        conti_filtrati = [
            c for c in conti 
            if c['tipo'] not in ['Investimento', 'Fondo Pensione'] 
            and not (c['id_conto'] in ids_conti_tecnici and "Saldo" in (c.get('nome_conto') or ""))
        ]
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
        self.controller.date_picker.first_date = datetime.datetime(1980, 1, 1)
        self.controller.date_picker.last_date = datetime.datetime(2050, 12, 31)
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

    def _apri_piano_ammortamento_click(self, e):
        # Nascondiamo temporaneamente il dialog principale per evitare conflitti di sovrapposizione
        self.dialog_prestito.open = False
        self.controller.page.update()

        if self.prestito_in_modifica:
            # Se siamo in modifica, usiamo una callback che riapre semplicemente il dialog
            self.piano_ammortamento_dialog.apri(
                id_prestito=self.prestito_in_modifica['id_prestito'],
                on_save=lambda: self._on_return_from_piano_modifica() 
            )
        else:
            # Modalità creazione: passa la lista temporanea e callback aggiornamento
            self.piano_ammortamento_dialog.apri(
                id_prestito=None, 
                temp_list=self.temp_piano_ammortamento,
                on_save=self._aggiorna_dati_da_piano
            )

    def _aggiorna_dati_da_piano(self):
        """Aggiorna i campi del prestito in base al piano di ammortamento temporaneo."""
    def _aggiorna_dati_da_piano(self):
        """Aggiorna i campi del prestito in base al piano di ammortamento temporaneo."""
        try:
            if self.temp_piano_ammortamento:
                num_rate = len(self.temp_piano_ammortamento)
                tot_capitale = sum(r['quota_capitale'] for r in self.temp_piano_ammortamento)
                tot_interessi = sum(r['quota_interessi'] for r in self.temp_piano_ammortamento)
                
                # Importo rata: prendiamo il primo per semplicità, l'utente può correggere
                importo_rata = self.temp_piano_ammortamento[0]['importo_rata'] if num_rate > 0 else 0.0

                # Data Inizio: prendiamo la data più vecchia nel piano
                date_list = [r['data_scadenza'] for r in self.temp_piano_ammortamento]
                if date_list:
                    min_data = min(date_list)
                    self.txt_data_inizio.value = min_data
                    # print(f"[DEBUG] Data inizio impostata da piano: {min_data}")
                
                # Calcolo rate residue (quelle NON pagate)
                # OCCHIO: 'stato' potrebbe mancare se manuale e non settato default? nel dialog init manuale mettiamo 'da_pagare'.
                num_residue = sum(1 for r in self.temp_piano_ammortamento if r.get('stato', 'da_pagare') == 'da_pagare')

                self.txt_numero_rate.value = str(num_rate)
                self.txt_rate_residue.value = str(num_residue)
                self.txt_importo_finanziato.value = f"{tot_capitale:.2f}"
                self.txt_importo_interessi.value = f"{tot_interessi:.2f}"
                self.txt_importo_rata.value = f"{importo_rata:.2f}"
                
                # Blocca campi
                self._set_fields_locked(True)
                
                self.controller.show_snack_bar("Dati importati dal piano. Clicca su SALVA per confermare.", success=True)
            else:
                self.controller.show_snack_bar("Nessun piano inserito.", success=False)
                # Sblocca campi se piano rimosso/vuoto
                self._set_fields_locked(False)
                
        except Exception as ex:
            print(f"Errore calcolo totali da piano: {ex}")
            self.controller.show_snack_bar(f"Errore importazione dati piano: {ex}", success=False)
        finally:
            # Forziamo il dialog open SEMPRE
            self.dialog_prestito.open = True
            self.controller.page.update()

    def _on_return_from_piano_modifica(self):
        # Al ritorno da modifica, ricarichiamo (e riblocchiamo se serve)
        # Controllo se esiste piano
        if self.prestito_in_modifica:
            from db.gestione_db import ottieni_piano_ammortamento
            piano = ottieni_piano_ammortamento(self.prestito_in_modifica['id_prestito'])
            has_piano = len(piano) > 0
            self._set_fields_locked(has_piano)
            
            # TODO: Ricalcolare i totali/residui visualizzati nel dialog padre in base al piano aggiornato?
            # Per ora l'utente vede quello che c'era, se vuole refresh deve chiudere e riaprire o facciamo refresh qui.
            # Facciamo refresh campi:
            if has_piano:
               # Ricalcolo rapido valori visualizzati per coerenza
                tot_cap = sum(r['quota_capitale'] for r in piano)
                tot_int = sum(r['quota_interessi'] for r in piano)
                importo_rata = piano[0]['importo_rata']
                
                self.txt_numero_rate.value = str(len(piano))
                # num_residue = sum(1 for r in piano if r['stato']=='da_pagare') # Calcolato da db spesso
                self.txt_importo_finanziato.value = f"{tot_cap:.2f}"
                self.txt_importo_interessi.value = f"{tot_int:.2f}"
                self.txt_importo_rata.value = f"{importo_rata:.2f}"
        
        self.dialog_prestito.open = True
        self.controller.page.update()

    def _set_fields_locked(self, locked):
        bg = ft.Colors.GREY_100 if locked else None
        
        self.txt_numero_rate.read_only = locked
        self.txt_numero_rate.bgcolor = bg
        
        self.txt_rate_residue.read_only = locked
        self.txt_rate_residue.bgcolor = bg
        
        self.txt_importo_finanziato.read_only = locked
        self.txt_importo_finanziato.bgcolor = bg
        
        self.txt_importo_interessi.read_only = locked
        self.txt_importo_interessi.bgcolor = bg
        
        self.txt_importo_rata.read_only = locked
        self.txt_importo_rata.bgcolor = bg
        
        # Data inizio
        # self.txt_data_inizio.read_only = True # Già readonly di base
        if self.txt_data_inizio.suffix:
            self.txt_data_inizio.suffix.disabled = locked
            self.txt_data_inizio.suffix.icon_color = ft.Colors.GREY if locked else None
            
        self.dialog_prestito.update()