import flet as ft
import traceback
import json
from db.gestione_db import (
    ottieni_tutti_i_conti_utente,
    ottieni_categorie_e_sottocategorie,
    aggiungi_spesa_fissa,
    modifica_spesa_fissa,
    ottieni_carte_utente,
    ottieni_ids_conti_tecnici_carte,
    get_configurazione,
    ottieni_tutti_i_conti_famiglia
)


class SpesaFissaDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # self.controller.page = controller.page # Removed for Flet 0.80 compatibility
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

        # NUOVI CONTROLLI GIROCONTO
        self.radio_tipo = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="spesa", label="Spesa"),
                ft.Radio(value="giroconto", label="Giroconto (Trasferimento)"),
            ]),
            value="spesa",
            on_change=self._on_tipo_change
        )
        
        self.dd_conto_beneficiario = ft.Dropdown(label="Conto Destinazione (Accredito)")

        self.container_beneficiario = ft.Container(
            content=self.dd_conto_beneficiario,
            visible=False # Default hidden
        )

        self.content = ft.Column(
            [
                self.radio_tipo, # Moved to top
                self.txt_nome,
                self.txt_importo,
                self.dd_conto_addebito,
                self.container_beneficiario, # New
                self.dd_sottocategoria,
                self.dd_giorno_addebito,
                self.sw_attiva,
                self.cb_addebito_automatico
            ],
            tight=True,
            spacing=10,
            width=350,
            scroll=ft.ScrollMode.AUTO
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

    def _on_tipo_change(self, e):
        is_giro = (self.radio_tipo.value == "giroconto")
        self.container_beneficiario.visible = is_giro
        self._popola_dropdowns() # Re-populate to apply specific filters
        if self.content.page:
            self.content.update()

    def apri_dialog(self, spesa_fissa_data=None):
        self._update_texts()
        self._reset_campi()
        self._popola_dropdowns()

        if spesa_fissa_data:
            self.title.value = "Modifica Spesa Fissa"
            self.id_spesa_fissa_in_modifica = spesa_fissa_data['id_spesa_fissa']
            self.txt_nome.value = spesa_fissa_data['nome']
            self.txt_importo.value = str(abs(spesa_fissa_data['importo']))
            
            # Set Type
            is_giro = spesa_fissa_data.get('is_giroconto', False)
            self.radio_tipo.value = "giroconto" if is_giro else "spesa"
            self.container_beneficiario.visible = is_giro
            
            # Set Beneficiary Account
            if is_giro:
                 c_ben_pers = spesa_fissa_data.get('id_conto_personale_beneficiario')
                 c_ben_cond = spesa_fissa_data.get('id_conto_condiviso_beneficiario')
                 if c_ben_pers:
                     self.dd_conto_beneficiario.value = f"P{c_ben_pers}"
                 elif c_ben_cond:
                     self.dd_conto_beneficiario.value = f"C{c_ben_cond}"

            if spesa_fissa_data.get('id_carta'):
                 # Reconstruct key for card
                 # Need to find the card in options to get the correct suffix/account if we want to be precise,
                 # OR we just need to reconstruct the key logic used in popola_dropdowns
                 # But we don't have the backing account info here easily unless we fetch it or iterate options.
                 # Let's try to match by ID from options
                 for opt in self.dd_conto_addebito.options:
                     if str(opt.key).startswith(f"CARD_{spesa_fissa_data['id_carta']}_"):
                         self.dd_conto_addebito.value = opt.key
                         break
            else:
                conto_key = f"{'C' if spesa_fissa_data['id_conto_condiviso_addebito'] else 'P'}{spesa_fissa_data['id_conto_personale_addebito'] or spesa_fissa_data['id_conto_condiviso_addebito']}"
                self.dd_conto_addebito.value = conto_key

            self.dd_sottocategoria.value = spesa_fissa_data.get('id_sottocategoria')
            self.dd_giorno_addebito.value = str(spesa_fissa_data['giorno_addebito'])
            self.sw_attiva.value = bool(spesa_fissa_data['attiva'])
            self.cb_addebito_automatico.value = bool(spesa_fissa_data['addebito_automatico'])
        else:
            self.title.value = self.loc.get("add_fixed_expense")
            self.id_spesa_fissa_in_modifica = None
            self.radio_tipo.value = "spesa"
            self.container_beneficiario.visible = False
            self.dd_conto_beneficiario.value = None

        if self not in self.controller.page.overlay:
            self.controller.page.overlay.append(self)
        self.open = True
        self.controller.page.update()

    def _chiudi_dialog(self, e):
        """Chiude il dialog (pulsante Annulla)."""
        self.controller.show_loading("Attendere...")
        try:
            self.open = False
            self.controller.page.update()
        except Exception as ex:
            print(f"Errore chiusura dialog spesa fissa: {ex}")
            traceback.print_exc()
        finally:
            self.controller.hide_loading()

    def _chiudi_dopo_salvataggio(self):
        """Chiude il dialog dopo un salvataggio riuscito."""
        self.open = False
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
        self.dd_conto_beneficiario.error_text = None
        self.dd_sottocategoria.error_text = None
        self.radio_tipo.value = "spesa"
        self.container_beneficiario.visible = False
        self.dd_conto_beneficiario.value = None

    def _popola_dropdowns(self):
        master_key = self.controller.page.session.get("master_key")
        user_id = self.controller.get_user_id()
        famiglia_id = self.controller.get_family_id()
        
        # 0. Recupera Matrice FOP Globale per Spesa Fissa
        raw_matrix = get_configurazione("global_fop_matrix")
        matrix_all = {}
        if raw_matrix:
            try: matrix_all = json.loads(raw_matrix)
            except: pass
        
        is_giro = (self.radio_tipo.value == "giroconto")
        matrix_addebito = matrix_all.get("Spesa Fissa", {}) if not is_giro else matrix_all.get("Giroconto (Mittente)", {})
        matrix_beneficiario = matrix_all.get("Giroconto (Ricevente)", {})

        # Default fallback se matrici vuote
        if not matrix_addebito:
            matrix_addebito = {"Conto Corrente": {"Personale": True, "Condiviso": True, "Altri Familiari": False}, "Carte": {"Personale": True, "Condiviso": True, "Altri Familiari": False}}
        if not matrix_beneficiario:
            matrix_beneficiario = {"Conto Corrente": {"Personale": True, "Condiviso": True, "Altri Familiari": True}, "Salvadanaio": {"Personale": True, "Condiviso": True, "Altri Familiari": True}}

        # 1. Recupera tutti i conti della famiglia
        conti_famiglia = ottieni_tutti_i_conti_famiglia(famiglia_id, user_id, master_key_b64=master_key)
        ids_conti_tecnici = ottieni_ids_conti_tecnici_carte(user_id)

        # Mappatura tipi
        tipo_map = {
            "Conto Corrente": ["Conto Corrente", "Conto", "Corrente"],
            "Carte": ["Carta", "Carta di Credito", "Prepagata"],
            "Risparmio": ["Risparmio", "Conto Deposito"],
            "Investimenti": ["Investimenti", "Investimento", "Crypto", "Azioni", "Obbligazioni", "ETF", "Fondo"],
            "Contanti": ["Contanti"],
            "Fondo Pensione": ["Fondo Pensione"],
            "Salvadanaio": ["Salvadanaio"],
            "Satispay": ["Satispay"],
            "PayPal": ["PayPal"]
        }

        def is_allowed(account_data, scope, matrix):
            t_db = str(account_data.get('tipo') or "").strip().lower()
            cat_fop = None
            
            # Special handling for e-wallets
            if t_db == "portafoglio elettronico":
                try:
                    config = json.loads(account_data.get('config_speciale') or '{}')
                    sottotipo = config.get('sottotipo', '').strip().lower()
                    if sottotipo == 'satispay': cat_fop = "Satispay"
                    elif sottotipo == 'paypal': cat_fop = "PayPal"
                except: pass
            
            if not cat_fop:
                for cat, db_list in tipo_map.items():
                    if any(t_db == x.strip().lower() for x in db_list):
                        cat_fop = cat
                        break
            
            if not cat_fop: return False
            
            # Check FOP with fallback
            scope_perms = matrix.get(cat_fop)
            if scope_perms is not None:
                return scope_perms.get(scope, False)
            return True if scope != "Altri Familiari" else False

        options_conti_addebito = []
        options_conti_beneficiario = []

        for c in conti_famiglia:
            if c['id_conto'] in ids_conti_tecnici or "Saldo" in (c.get('nome_conto') or ""):
                continue
            
            # Ambito
            if c['is_condiviso']: scope = "Condiviso"
            elif str(c['id_utente_owner']) == str(user_id): scope = "Personale"
            else: scope = "Altri Familiari"

            prefix = "C" if c['is_condiviso'] else "P"
            suffix = ""
            if scope == "Condiviso": suffix = " (Condiviso)"
            elif scope == "Altri Familiari": suffix = f" ({c.get('nome_owner', 'Altro')})"
            
            icon = "🏦"
            if c['tipo'] in tipo_map["Carte"]: icon = "💳"
            elif c['tipo'] == "Salvadanaio": icon = "🐷"
            elif c['tipo'] == "Portafoglio Elettronico": icon = "📱"
            
            key = c['id_conto'] if c['tipo'] in tipo_map["Carte"] else f"{prefix}{c['id_conto']}"
            opt = ft.dropdown.Option(key=key, text=f"{icon} {c['nome_conto']}{suffix}")

            # Filtro Addebito
            if is_allowed(c, scope, matrix_addebito):
                options_conti_addebito.append(opt)
            
            # Filtro Beneficiario (solo se Giroconto)
            if is_allowed(c, scope, matrix_beneficiario):
                options_conti_beneficiario.append(opt)

        self.dd_conto_addebito.options = options_conti_addebito
        self.dd_conto_beneficiario.options = options_conti_beneficiario

        # 4. Categories Dropdown
        self.dd_sottocategoria.options = []
        if famiglia_id:
            categorie = ottieni_categorie_e_sottocategorie(famiglia_id)
            for cat_data in categorie:
                for sub_cat in cat_data['sottocategorie']:
                    self.dd_sottocategoria.options.append(
                        ft.dropdown.Option(key=sub_cat['id_sottocategoria'], text=f"{cat_data['nome_categoria']} - {sub_cat['nome_sottocategoria']}")
                    )


    def _salva_cliccato(self, e):
        self.controller.show_loading("Attendere...")
        if not self._valida_campi():
            if self.content.page:
                self.content.update()
            self.controller.hide_loading()
            return

        try:
            nome = self.txt_nome.value
            importo = float(self.txt_importo.value.replace(",", "."))
            
            # Parsa conto
            # Parsa conto
            conto_key = self.dd_conto_addebito.value
            id_conto_personale = None
            id_conto_condiviso = None
            id_carta = None

            if conto_key.startswith("CARD_"):
                parts = conto_key.split("_")
                id_carta = int(parts[1])
                # We also need the backing account for consistency, although DB layer might override if we pass id_carta
                # But SpeseFisse table needs id_conto_X_addebito populated too for FK constraints usually?
                # Actually, SpeseFisse schema allows NULLs if we changed it... 
                # Wait, my migration just added id_carta. It didn't remove NOT NULL from id_conto if it was there.
                # Let's check schema creation... SpeseFisse id_conto_personale_addebito is REFERENCES ... ON DELETE SET NULL.
                # But is it NOT NULL? 
                # Create script says: id_conto_personale_addebito INTEGER REFERENCES ... (doesn't say NOT NULL)
                # So it's nullable.
                # However, logic in gestion_db uses it.
                # Let's extract it from key anyway.
                id_conto = int(parts[2])
                is_condiviso = (parts[3] == 'S')
                if is_condiviso:
                    id_conto_condiviso = id_conto
                else:
                    id_conto_personale = id_conto

            else:
                is_condiviso = conto_key.startswith("C")
                id_conto = int(conto_key[1:])
                id_conto_personale = None if is_condiviso else id_conto
                id_conto_condiviso = id_conto if is_condiviso else None

            # Parsa conto beneficiario
            is_giroconto = (self.radio_tipo.value == "giroconto")
            id_conto_personale_beneficiario = None
            id_conto_condiviso_beneficiario = None
            
            if is_giroconto:
                ben_key = self.dd_conto_beneficiario.value
                if ben_key:
                    is_cond_ben = ben_key.startswith("C")
                    id_conto_ben = int(ben_key[1:])
                    id_conto_personale_beneficiario = None if is_cond_ben else id_conto_ben
                    id_conto_condiviso_beneficiario = id_conto_ben if is_cond_ben else None
            
            if is_giroconto and not (id_conto_personale_beneficiario or id_conto_condiviso_beneficiario):
                 self.dd_conto_beneficiario.error_text = "Seleziona un conto di destinazione"
                 if self.content.page:
                     self.content.update()
                 self.controller.hide_loading()
                 return

            id_sottocategoria = int(self.dd_sottocategoria.value)
            giorno = int(self.dd_giorno_addebito.value)
            attiva = self.sw_attiva.value
            auto = self.cb_addebito_automatico.value

            master_key_b64 = self.controller.page.session.get("master_key")
            current_user_id = self.controller.get_user_id()

            success = False
            if self.id_spesa_fissa_in_modifica:
                success = modifica_spesa_fissa(
                    id_spesa_fissa=self.id_spesa_fissa_in_modifica,
                    nome=nome,
                    importo=importo,
                    id_conto_personale=id_conto_personale,
                    id_conto_condiviso=id_conto_condiviso,
                    id_sottocategoria=id_sottocategoria,
                    giorno_addebito=giorno,
                    attiva=attiva,
                    addebito_automatico=auto,
                    master_key_b64=master_key_b64,
                    id_utente=current_user_id,
                    id_carta=id_carta,
                    is_giroconto=is_giroconto,
                    id_conto_personale_beneficiario=id_conto_personale_beneficiario,
                    id_conto_condiviso_beneficiario=id_conto_condiviso_beneficiario
                )
            else:
                success = aggiungi_spesa_fissa(
                    id_famiglia=self.controller.get_family_id(),
                    nome=nome,
                    importo=importo,
                    id_conto_personale=id_conto_personale,
                    id_conto_condiviso=id_conto_condiviso,
                    id_sottocategoria=id_sottocategoria,
                    giorno_addebito=giorno,
                    attiva=attiva,
                    addebito_automatico=auto,
                    master_key_b64=master_key_b64,
                    id_utente=current_user_id,
                    id_carta=id_carta,
                    is_giroconto=is_giroconto,
                    id_conto_personale_beneficiario=id_conto_personale_beneficiario,
                    id_conto_condiviso_beneficiario=id_conto_condiviso_beneficiario
                )

            if success:
                self.controller.show_snack_bar("Spesa fissa salvata!", success=True)
                self._chiudi_dopo_salvataggio()
                self.controller.update_all_views()
            else:
                self.controller.show_snack_bar("Errore nel salvataggio.", success=False)

        except Exception as ex:
            print(f"Errore salvataggio spesa fissa: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore: {ex}", success=False)
        finally:
            self.controller.hide_loading()

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