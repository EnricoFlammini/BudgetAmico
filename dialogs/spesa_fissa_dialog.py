import flet as ft
import traceback
from db.gestione_db import (
    ottieni_tutti_i_conti_utente,
    ottieni_categorie_e_sottocategorie,
    aggiungi_spesa_fissa,
    modifica_spesa_fissa,
    ottieni_carte_utente
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
            height=550, # Increased height
            width=500,
            scroll=ft.ScrollMode.ADAPTIVE
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
        # Popola conti - solo quelli accessibili all'utente corrente
        master_key = self.controller.page.session.get("master_key")
        user_id = self.controller.get_user_id()
        conti = ottieni_tutti_i_conti_utente(user_id, master_key_b64=master_key)
        
        # Filtra i tipi di conto che non fanno parte della liquidità (per addebito)
        tipi_esclusi_addebito = ['Investimento', 'Fondo Pensione', 'Risparmio']
        conti_filtrati_addebito = [c for c in conti if c.get('tipo') not in tipi_esclusi_addebito]

        # Per beneficiario (giroconto), includiamo anche Risparmio
        tipi_esclusi_beneficiario = ['Investimento', 'Fondo Pensione']
        conti_filtrati_beneficiario = [c for c in conti if c.get('tipo') not in tipi_esclusi_beneficiario]
        
        options_conti_addebito = []
        options_conti_beneficiario = []
        
        # 1. Carte (Prima per consistenza)
        carte = ottieni_carte_utente(user_id, master_key_b64=master_key)
        if carte:
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
                     
                if target_acc:
                    flag = 'S' if is_shared_card else 'P'
                    key = f"CARD_{c['id_carta']}_{target_acc}_{flag}"
                    options_conti_addebito.append(ft.dropdown.Option(key, f"💳 {c['nome_carta']}"))

            options_conti_addebito.append(ft.dropdown.Option(key="DIVIDER", text="-- Conti --", disabled=True))

        # Populate Debit Accounts
        for conto in conti_filtrati_addebito:
            is_condiviso = conto.get('is_condiviso') or conto.get('condiviso')
            tipo_prefix = "C" if is_condiviso else "P"
            key = f"{tipo_prefix}{conto['id_conto']}"
            suffix = " (Condiviso)" if is_condiviso else ""
            text = f"{conto['nome_conto']}{suffix}"
            options_conti_addebito.append(ft.dropdown.Option(key, text))
        self.dd_conto_addebito.options = options_conti_addebito
        
        # Populate Beneficiary Accounts (for Giroconto)
        for conto in conti_filtrati_beneficiario:
            is_condiviso = conto.get('is_condiviso') or conto.get('condiviso')
            tipo_prefix = "C" if is_condiviso else "P"
            key = f"{tipo_prefix}{conto['id_conto']}"
            suffix = " (Condiviso)" if is_condiviso else ""
            text = f"{conto['nome_conto']}{suffix}"
            # Add Savings icon if saving
            icon_str = "🐖 " if conto.get('tipo') == 'Risparmio' else ""
            options_conti_beneficiario.append(ft.dropdown.Option(key, f"{icon_str}{text}"))
        self.dd_conto_beneficiario.options = options_conti_beneficiario

        # Popola categorie
        cats_subcats = ottieni_categorie_e_sottocategorie(self.controller.get_family_id())
        options_subcats = []
        for cat in cats_subcats:
            for sub in cat['sottocategorie']:
                options_subcats.append(ft.dropdown.Option(sub['id_sottocategoria'], f"{cat['nome_categoria']} - {sub['nome_sottocategoria']}"))
        self.dd_sottocategoria.options = options_subcats


    def _salva_cliccato(self, e):
        self.controller.show_loading("Attendere...")
        if not self._valida_campi():
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