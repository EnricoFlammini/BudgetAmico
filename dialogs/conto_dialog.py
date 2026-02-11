import flet as ft
import datetime
import traceback
import json
from utils.styles import AppStyles
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
    admin_imposta_saldo_conto_condiviso,
    # Shared Account Imports
    crea_conto_condiviso,
    modifica_conto_condiviso,
    ottieni_utenti_famiglia,
    ottieni_dettagli_conto_condiviso,
    # PB Imports
    ottieni_salvadanai_conto,
    admin_rettifica_salvadanaio,
    elimina_salvadanaio,
    ottieni_prima_famiglia_utente,
    get_configurazione,
    ottieni_tutti_i_conti_famiglia,
    ottieni_ids_conti_tecnici_carte
)


class ContoDialog(ft.AlertDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # self.controller.page = controller.page # Removed for Flet 0.80 compatibility
        self.loc = controller.loc
        self.conto_id_in_modifica = None
        self.is_condiviso_in_modifica = False
        self.is_shared_mode = False # Toggle state

        # Dialogo Rettifica Saldo (Admin)
        self.txt_nuovo_saldo = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER, label="Nuovo Saldo Reale")
        self.container_pb_rettifica = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO, height=200) # Container for PBs
        
        self.dialog_rettifica_saldo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Rettifica Saldo Conto"),
            content=ft.Container(
                content=ft.Column([
                    AppStyles.subheader_text("Saldo Conto"),
                    self.txt_nuovo_saldo,
                    ft.Divider(),
                    AppStyles.subheader_text("Salvadanai Associati"),
                    self.container_pb_rettifica
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                width=350,
            ),
            actions=[
                ft.TextButton("Annulla", on_click=self._chiudi_dialog_rettifica),
                ft.TextButton("Salva e Rettifica", on_click=self._salva_rettifica_saldo)
            ]
        )



        # Controlli del dialogo principale
        self.dd_scope_conto = ft.Dropdown(
            options=[
                ft.dropdown.Option("personale", "Conto Personale"),
                ft.dropdown.Option("condiviso", "Conto Condiviso"),
            ],
            value="personale",
            on_change=self._cambia_scope_conto
        )
        
        self.txt_conto_nome = ft.TextField()
        self.dd_conto_tipo = ft.Dropdown()
        self.dd_conto_tipo.on_change = self._cambia_tipo_conto_in_dialog
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

        # Shared Account Specific Fields
        self.dd_tipo_condivisione = ft.Dropdown(
            options=[
                ft.dropdown.Option("famiglia", "Condividi con Famiglia"),
                ft.dropdown.Option("utenti", "Seleziona Utenti")
            ],
            value="famiglia",
            on_change=self._on_tipo_condivisione_change,
            visible=False
        )
        self.partecipanti_title = ft.Text("Seleziona Partecipanti", weight="bold", visible=False)
        self.lv_partecipanti = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, height=150, visible=False)
        # E-Wallet Specific Fields
        self.dd_ewallet_sottotipo = ft.Dropdown(
            options=[
                ft.dropdown.Option("satispay", "Satispay"),
                ft.dropdown.Option("paypal", "PayPal"),
                ft.dropdown.Option("altro", "Altro")
            ],
            label="Sottotipo Portafoglio",
            on_change=self._on_ewallet_sottotipo_change,
            visible=False
        )
        
        # Satispay Fields
        self.txt_satispay_budget = ft.TextField(label="Budget Settimanale", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
        self.dd_satispay_conto_collegato = ft.Dropdown(label="Conto di Addebito/Accredito", visible=False, width=350)
        
        # PayPal Fields
        self.lv_paypal_fonti = ft.Column(visible=False, spacing=5)
        self.dd_paypal_fonte_preferita = ft.Dropdown(label="Fonte Preferita", visible=False, width=350)
        
        self.container_ewallet_settings = ft.Column([
            self.dd_ewallet_sottotipo,
            self.txt_satispay_budget,
            self.dd_satispay_conto_collegato,
            ft.Text("Seleziona Fonti Collegate (PayPal):", weight="bold", size=12, visible=False),
            self.lv_paypal_fonti,
            self.dd_paypal_fonte_preferita
        ], visible=False, spacing=10)

        # Personalizzazione: Icona e Colore
        self.selected_icon_value = None
        self.selected_color_value = None
        
        self.icon_preview = ft.Container(content=ft.Icon(ft.Icons.ACCOUNT_BALANCE, size=30))
        self.btn_icon_selector = ft.IconButton(
            icon=ft.Icons.AUTO_AWESOME_OUTLINED,
            tooltip="Seleziona Icona",
            on_click=self._apri_selettore_icona
        )
        
        self.color_preview = ft.Container(width=30, height=30, border_radius=15, bgcolor=ft.Colors.BLUE_GREY_700)
        self.btn_color_selector = ft.IconButton(
            icon=ft.Icons.COLOR_LENS_OUTLINED,
            tooltip="Seleziona Colore",
            on_click=self._apri_selettore_colore
        )
        
        self.container_personalizzazione = ft.Container(
            content=ft.Row([
                ft.Row([ft.Text("Icona:", size=12, weight="bold"), self.icon_preview, self.btn_icon_selector], spacing=5),
                ft.Row([ft.Text("Colore:", size=12, weight="bold"), self.color_preview, self.btn_color_selector], spacing=5),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=5,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8
        )

        self.container_partecipanti = ft.Container(
            content=ft.Column([
                self.partecipanti_title,
                self.lv_partecipanti
            ]),
            visible=False
        )

        # Struttura del dialogo
        self.modal = True
        self.title = ft.Text()
        self.content = ft.Column(
            [
                self.dd_scope_conto,
                self.txt_conto_nome,
                self.dd_conto_tipo,
                self.dd_tipo_condivisione,
                self.container_partecipanti,
                self.txt_conto_iban,
                ft.Divider(),
                self.container_personalizzazione,
                self.container_ewallet_settings,
                self.container_saldo_iniziale,
                self.container_asset_iniziali,
                self.chk_conto_default
            ],
            tight=True,
            spacing=10,
            width=350,
            scroll=ft.ScrollMode.AUTO
        )
        self.actions = [
            ft.TextButton(on_click=self._chiudi_dialog_conto),
            ft.TextButton(on_click=self._salva_conto),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

        # Mappatura tipi matrice -> tipi DB (usata per filtraggio FOP)
        self.tipo_map = {
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

    def _update_texts(self):
        """Aggiorna tutti i testi fissi con le traduzioni correnti."""
        loc = self.loc
        self.title.value = loc.get("manage_account")
        self.txt_conto_nome.label = loc.get("account_name_placeholder")
        self.dd_conto_tipo.label = loc.get("account_type")
        self.dd_scope_conto.label = "Tipo di Conto (Personale/Condiviso)" # TODO: Add to loc
        self.dd_scope_conto.options[0].text = loc.get("personal_account") if loc.get("personal_account") else "Conto Personale"
        self.dd_scope_conto.options[1].text = loc.get("shared_account") if loc.get("shared_account") else "Conto Condiviso"
        
        self.dd_conto_tipo.options = [
            ft.dropdown.Option("Conto Corrente"), ft.dropdown.Option("Risparmio"),
            ft.dropdown.Option("Fondo Pensione"), ft.dropdown.Option("Contanti"),
            ft.dropdown.Option("Portafoglio Elettronico"),
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
        
        # Shared fields texts
        self.dd_tipo_condivisione.label = loc.get("sharing_type")
        self.dd_tipo_condivisione.options[0].text = loc.get("sharing_type_family")
        self.dd_tipo_condivisione.options[1].text = loc.get("sharing_type_users")
        self.partecipanti_title.value = loc.get("select_participants")

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
        if self.open and self.content.page:
            self.content.update()

    def _rimuovi_riga_asset_iniziale(self, riga_control):
        self.lv_asset_iniziali.controls.remove(riga_control)
        if self.open and self.content.page:
            self.content.update()

    def _cambia_tipo_conto_in_dialog(self, e):
        tipo = self.dd_conto_tipo.value
        is_shared = self.dd_scope_conto.value == 'condiviso'
        
        # E-Wallet logic
        is_ewallet = tipo == 'Portafoglio Elettronico'
        self.container_ewallet_settings.visible = is_ewallet
        if is_ewallet:
             self.dd_ewallet_sottotipo.visible = True
             self._on_ewallet_sottotipo_change(None)
        
        self.chk_conto_default.visible = (tipo not in ['Investimento', 'Fondo Pensione', 'Portafoglio Elettronico']) and not is_shared
        
        if is_shared:
             # Shared account logic for visibility
             self.txt_conto_iban.visible = True # Or False if we want to simplify shared accounts
             self.container_saldo_iniziale.visible = True # Use simple initial balance for shared
             self.container_asset_iniziali.visible = False # No assets for shared yet
             
             # Adjust type options if needed? For now keep same types.
             
        elif tipo == 'Investimento':
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

    def _cambia_scope_conto(self, e):
        self.is_shared_mode = self.dd_scope_conto.value == 'condiviso'
        is_shared = self.is_shared_mode
        
        # Visibilità campi condivisi
        self.dd_tipo_condivisione.visible = is_shared
        self.container_partecipanti.visible = is_shared and self.dd_tipo_condivisione.value == 'utenti'
        
        # Visibilità campi personali
        # Asset solo se personale. Default solo se personale.
        self._cambia_tipo_conto_in_dialog(None) # Ricalcola visibilità basata su tipo e scope
        
        if is_shared:
             # Refresh user list if needed
             if self.dd_tipo_condivisione.value == 'utenti':
                 self._popola_lista_utenti()
        
        if self.open:
            self.content.update()

    def _on_ewallet_sottotipo_change(self, e):
        sottotipo = self.dd_ewallet_sottotipo.value
        
        # Satispay visibility
        is_satispay = sottotipo == 'satispay'
        self.txt_satispay_budget.visible = is_satispay
        self.dd_satispay_conto_collegato.visible = is_satispay
        
        # PayPal visibility
        is_paypal = sottotipo == 'paypal'
        self.container_ewallet_settings.controls[3].visible = is_paypal # Text title
        self.lv_paypal_fonti.visible = is_paypal
        self.dd_paypal_fonte_preferita.visible = is_paypal
        
        if is_satispay:
            self._popola_conti_collegati()
        elif is_paypal:
            self._popola_fonti_paypal()
            
        if self.open:
            self.content.update()

    def _popola_conti_collegati(self):
        id_utente = self.controller.get_user_id()
        id_famiglia = self.controller.get_family_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        
        # Recupera tutti i conti della famiglia per permettere selezione estesa come in Transazioni
        conti = ottieni_tutti_i_conti_famiglia(id_famiglia, id_utente, master_key_b64=master_key_b64)
        ids_conti_tecnici = ottieni_ids_conti_tecnici_carte(id_utente)
        
        # FOP Matrix filtering
        raw_matrix = get_configurazione("global_fop_matrix")
        matrix = {}
        if raw_matrix:
            try: matrix = json.loads(raw_matrix)
            except: pass
            
        op_satispay = "Satispay (Collegamento)"
        
        allowed_options = []
        for c in conti:
            # Filtro conti tecnici e nascosti
            if c.get('nascosto') or c['tipo'] == 'Portafoglio Elettronico':
                continue
            if c['id_conto'] in ids_conti_tecnici or "Saldo" in (c.get('nome_conto') or ""):
                continue
            
            # Check FOP
            t_db = str(c.get('tipo') or "").strip().lower()
            cat_fop = None
            for cat, db_list in self.tipo_map.items():
                if any(t_db == x.strip().lower() for x in db_list):
                    cat_fop = cat
                    break
            
            if not cat_fop: continue
            
            # Ambito
            if c['is_condiviso']: scope = "Condiviso"
            elif str(c['id_utente_owner']) == str(id_utente): scope = "Personale"
            else: scope = "Altri Familiari"
            
            # Check FOP with fallback if operation is not in matrix
            if matrix:
                op_perm = matrix.get(op_satispay)
                if op_perm:
                    if not op_perm.get(cat_fop, {}).get(scope, False):
                        continue
                else:
                    # Fallback default: Conto Corrente (Personale/Condiviso)
                    default = False
                    if cat_fop == "Conto Corrente" and scope != "Altri Familiari": default = True
                    if not default: continue

            suffix = ""
            if scope == "Condiviso": suffix = " (Condiviso)"
            elif scope == "Altri Familiari": suffix = f" ({c.get('nome_owner', 'Altro')})"

            # Icona e tipo per chiarezza
            icon = "🏦"
            if cat_fop == "Carte": icon = "💳"
            elif cat_fop == "Contanti": icon = "💵"
            elif cat_fop == "Salvadanaio": icon = "🐷"
            
            display_text = f"{icon} {c['nome_conto']} [{cat_fop}]{suffix}"
            allowed_options.append(ft.dropdown.Option(str(c['id_conto']), display_text))

        self.dd_satispay_conto_collegato.options = allowed_options

    def _popola_fonti_paypal(self):
        id_utente = self.controller.get_user_id()
        id_famiglia = self.controller.get_family_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        
        # Recupera tutti i conti della famiglia per permettere selezione estesa come in Transazioni
        conti = ottieni_tutti_i_conti_famiglia(id_famiglia, id_utente, master_key_b64=master_key_b64)
        ids_conti_tecnici = ottieni_ids_conti_tecnici_carte(id_utente)
        
        # FOP Matrix filtering
        raw_matrix = get_configurazione("global_fop_matrix")
        matrix = {}
        if raw_matrix:
            try: matrix = json.loads(raw_matrix)
            except: pass
            
        op_paypal = "PayPal (Fonti)"
        
        self.lv_paypal_fonti.controls.clear()
        self.dd_paypal_fonte_preferita.options.clear()
        
        for c in conti:
            # Filtro conti tecnici e nascosti
            if c.get('nascosto') or c['tipo'] == 'Portafoglio Elettronico':
                continue
            if c['id_conto'] in ids_conti_tecnici or "Saldo" in (c.get('nome_conto') or ""):
                continue
                
            # Check FOP
            t_db = str(c.get('tipo') or "").strip().lower()
            cat_fop = None
            for cat, db_list in self.tipo_map.items():
                if any(t_db == x.strip().lower() for x in db_list):
                    cat_fop = cat
                    break
            
            if not cat_fop: continue

            # Ambito
            if c['is_condiviso']: scope = "Condiviso"
            elif str(c['id_utente_owner']) == str(id_utente): scope = "Personale"
            else: scope = "Altri Familiari"
            
            # Check FOP with fallback if operation is not in matrix
            if matrix:
                op_perm = matrix.get(op_paypal)
                if op_perm:
                    if not op_perm.get(cat_fop, {}).get(scope, False):
                        continue
                else:
                    # Fallback default: Conto Corrente & Carte (Personale/Condiviso)
                    default = False
                    if cat_fop in ["Conto Corrente", "Carte"] and scope != "Altri Familiari": default = True
                    if not default: continue

            suffix = ""
            if scope == "Condiviso": suffix = " (Condiviso)"
            elif scope == "Altri Familiari": suffix = f" ({c.get('nome_owner', 'Altro')})"

            # Icona e tipo per chiarezza
            icon = "🏦"
            if cat_fop == "Carte": icon = "💳"
            elif cat_fop == "Contanti": icon = "💵"
            elif cat_fop == "Salvadanaio": icon = "🐷"

            display_lbl = f"{icon} {c['nome_conto']} [{cat_fop}]{suffix}"
            chk = ft.Checkbox(label=display_lbl, data=c['id_conto'], on_change=self._on_paypal_fonti_change)
            self.lv_paypal_fonti.controls.append(chk)

    def _on_paypal_fonti_change(self, e):
        # Update preferred source dropdown based on selected checkboxes
        selected_options = []
        for ctrl in self.lv_paypal_fonti.controls:
            if isinstance(ctrl, ft.Checkbox) and ctrl.value:
                selected_options.append(ft.dropdown.Option(str(ctrl.data), ctrl.label))
        
        self.dd_paypal_fonte_preferita.options = selected_options
        if not any(opt.key == self.dd_paypal_fonte_preferita.value for opt in selected_options):
            self.dd_paypal_fonte_preferita.value = None
        self.dd_paypal_fonte_preferita.update()

    def _on_tipo_condivisione_change(self, e):
        if self.dd_tipo_condivisione.value == 'utenti':
            self.container_partecipanti.visible = True
            self._popola_lista_utenti()
        else:
            self.container_partecipanti.visible = False
            
        self.content.update()

    def _popola_lista_utenti(self, utenti_selezionati_ids=None):
        self.lv_partecipanti.controls.clear()
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            self.lv_partecipanti.controls.append(ft.Text("Nessuna famiglia associata."))
            return

        utenti_famiglia = ottieni_utenti_famiglia(famiglia_id)
        current_user_id = self.controller.get_user_id()
        
        for user in utenti_famiglia:
            # Include everyone, even current user
            # if str(user['id_utente']) == str(current_user_id):
            #      continue
                 
            self.lv_partecipanti.controls.append(
                ft.Checkbox(
                    label=user['nome_visualizzato'],
                    value=user['id_utente'] in (utenti_selezionati_ids if utenti_selezionati_ids else []),
                    data=user['id_utente']
                )
            )
        self.lv_partecipanti.visible = True


    def _chiudi_dialog_conto(self, e):
        self.controller.show_loading("Attendere...")
        try:
            self.open = False
            self.controller.page.update()
        finally:
            self.controller.hide_loading()

    def apri_dialog_conto(self, e, conto_data=None, escludi_investimento=False, is_shared_edit=False, shared_default=False):
        self._update_texts()
        
        if escludi_investimento:
            self.dd_conto_tipo.options = [opt for opt in self.dd_conto_tipo.options if opt.key != "Investimento" and opt.text != "Investimento"]

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
            
            # Determine if it's shared based on passed flag or data
            is_shared = is_shared_edit or conto_data.get('condiviso', False)
            self.dd_scope_conto.value = "condiviso" if is_shared else "personale"
            self.dd_scope_conto.disabled = True # Cannot change scope in edit mode
            self.is_shared_mode = is_shared
            if is_shared:
                self.is_condiviso_in_modifica = True # Used for admin saldo fix, but let's reuse
                # Fetch details if not full
                master_key_b64 = self.controller.page.session.get("master_key")
                dettagli = ottieni_dettagli_conto_condiviso(self.conto_id_in_modifica, master_key_b64=master_key_b64, id_utente=id_utente)
                if dettagli:
                    conto_data = dettagli # Override with full details including participants
            
            self.txt_conto_nome.value = conto_data['nome_conto']
            
            # Retrocompatibilità per tipi rimossi
            tipo_corrente = conto_data['tipo']
            if tipo_corrente not in [opt.key for opt in self.dd_conto_tipo.options if opt.key]:
                # Se è un tipo rimosso, aggiungilo temporaneamente alle opzioni
                self.dd_conto_tipo.options.append(ft.dropdown.Option(tipo_corrente))
            
            self.dd_conto_tipo.value = tipo_corrente
            self.dd_conto_tipo.disabled = False
            self.txt_conto_iban.value = conto_data.get('iban', "")

            # Gestione visibilità in base al tipo
            # Load E-Wallet settings if present
            if tipo_corrente == 'Portafoglio Elettronico':
                try:
                    config = json.loads(conto_data.get('config_speciale') or '{}')
                    sottotipo = config.get('sottotipo')
                    self.dd_ewallet_sottotipo.value = sottotipo
                    if sottotipo == 'satispay':
                        self.txt_satispay_budget.value = config.get('budget_settimanale', '')
                        self.dd_satispay_conto_collegato.value = config.get('id_conto_collegato')
                    elif sottotipo == 'paypal':
                        fonti_ids = config.get('fonti_collegate', [])
                        self._popola_fonti_paypal()
                        for ctrl in self.lv_paypal_fonti.controls:
                            if isinstance(ctrl, ft.Checkbox) and ctrl.data in fonti_ids:
                                ctrl.value = True
                        self._on_paypal_fonti_change(None)
                        self.dd_paypal_fonte_preferita.value = config.get('fonte_preferita')
                except Exception as ex:
                    print(f"[ERRORE] Caricamento config ewallet: {ex}")
            
            # Saldo iniziale NON modificabile in edit mode (solo tramite rettifica admin)
            self.container_saldo_iniziale.visible = False
            self.container_asset_iniziali.visible = (conto_data['tipo'] == 'Investimento' and not is_shared)
            
            self.chk_conto_default.visible = (conto_data['tipo'] not in ['Investimento', 'Fondo Pensione']) and not is_shared
            self.txt_conto_iban.visible = (conto_data['tipo'] != 'Contanti')
            if not is_shared:
                self.chk_conto_default.value = (conto_data.get('id_conto') == conto_default_id)
            else:
                self.chk_conto_default.value = False
            
            if is_shared:
                 self.dd_tipo_condivisione.value = conto_data.get('tipo_condivisione', 'famiglia')
                 self.dd_tipo_condivisione.visible = True
                 if self.dd_tipo_condivisione.value == 'utenti':
                     self.container_partecipanti.visible = True
                     partecipanti_ids = [p['id_utente'] for p in conto_data.get('partecipanti', [])]
                     self._popola_lista_utenti(partecipanti_ids)
                 else:
                     self.container_partecipanti.visible = False
            else:
                 self.dd_tipo_condivisione.visible = False
                 self.container_partecipanti.visible = False
                 
        else:
            # --- MODALITÀ CREAZIONE ---
            self.title.value = self.loc.get("add_account")
            self.conto_id_in_modifica = None
            self.dd_scope_conto.value = "condiviso" if shared_default else "personale"
            self.dd_scope_conto.disabled = False
            self.is_shared_mode = shared_default
            
            self.txt_conto_nome.value = ""
            self.dd_conto_tipo.value = "Corrente"
            self.dd_conto_tipo.disabled = False
            self.txt_conto_iban.value = ""
            self.txt_conto_iban.visible = True
            self.txt_conto_saldo_iniziale.value = ""
            self.container_saldo_iniziale.visible = True
            self.container_asset_iniziali.visible = False
            
            self.chk_conto_default.visible = not shared_default
            self.chk_conto_default.value = False
            self._aggiungi_riga_asset_iniziale()
            
            # Shared defaults
            self.dd_tipo_condivisione.value = "famiglia"
            self.dd_tipo_condivisione.visible = shared_default
            self.container_partecipanti.visible = False
            if shared_default:
                self._popola_lista_utenti() # Prepare just in case switch to users

        # Trigger visibility update based on initial/edit state
        self._cambia_tipo_conto_in_dialog(None)
        self._cambia_scope_conto(None) # Ensure consistency

        # self.controller.page.dialog = self # Deprecated/Conflict with overlay
        if self not in self.controller.page.overlay:
            self.controller.page.overlay.append(self)
            

        
        # Carica icona e colore se presenti
        self.selected_icon_value = conto_data.get('icona') if conto_data else None
        self.selected_color_value = conto_data.get('colore') if conto_data else None
        self._aggiorna_preview_personalizzazione()

        self.open = True
        self.controller.page.update()

    def _salva_conto(self, e):
        # Protezione anti doppio-click
        if hasattr(self, '_saving_in_progress') and self._saving_in_progress:
            print("[DEBUG] Salvataggio già in corso, ignoro doppio click")
            return
        self._saving_in_progress = True
        
        self.controller.show_loading("Attendere...")
        try:
            # Get master_key from session for encryption
            master_key_b64 = self.controller.page.session.get("master_key")
            
            is_valid = True
            self.txt_conto_nome.error_text = None
            self.txt_conto_iban.error_text = None
            self.txt_conto_saldo_iniziale.error_text = None

            nome = self.txt_conto_nome.value
            tipo = self.dd_conto_tipo.value
            iban = self.txt_conto_iban.value if self.txt_conto_iban.visible else None
            is_shared = self.dd_scope_conto.value == 'condiviso'
            is_ewallet = tipo == 'Portafoglio Elettronico'
            
            config_spec_json = None
            if is_ewallet:
                sottotipo = self.dd_ewallet_sottotipo.value
                config_dict = {'sottotipo': sottotipo}
                if sottotipo == 'satispay':
                    config_dict['budget_settimanale'] = self.txt_satispay_budget.value
                    config_dict['id_conto_collegato'] = self.dd_satispay_conto_collegato.value
                elif sottotipo == 'paypal':
                    fonti_ids = []
                    for ctrl in self.lv_paypal_fonti.controls:
                        if isinstance(ctrl, ft.Checkbox) and ctrl.value:
                            fonti_ids.append(ctrl.data)
                    config_dict['fonti_collegate'] = fonti_ids
                    config_dict['fonte_preferita'] = self.dd_paypal_fonte_preferita.value
                
                config_spec_json = json.dumps(config_dict)

            if not nome:
                self.txt_conto_nome.error_text = self.loc.get("fill_all_fields")
                is_valid = False

            # Validate Shared Specifics
            lista_utenti_selezionati = []
            if is_shared and self.dd_tipo_condivisione.value == 'utenti':
                for checkbox in self.lv_partecipanti.controls:
                    if isinstance(checkbox, ft.Checkbox) and checkbox.value:
                        lista_utenti_selezionati.append(checkbox.data)
                if not lista_utenti_selezionati:
                    self.controller.show_snack_bar(self.loc.get("select_at_least_one_participant"), success=False)
                    is_valid = False

            saldo_iniziale = 0.0
            lista_asset_iniziali = []

            # La validazione del saldo iniziale e degli asset avviene sempre (creazione e modifica)
            # Ma per modifica, solo se il tipo lo richiede
            if True: # Rimosso check if not self.conto_id_in_modifica
                if tipo == 'Investimento' and not is_shared:
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
                self.controller.hide_loading()
                return

            utente_id = self.controller.get_user_id()
            id_famiglia = self.controller.get_family_id()  # Get family ID for family_key encryption
            success = False
            messaggio = ""
            new_conto_id = None

            # --- SALVATAGGIO ---
            print(f"[DEBUG] Saving Account {self.conto_id_in_modifica}. Icon: {self.selected_icon_value}, Color: {self.selected_color_value}")
            if is_shared:
                # -- SHARED ACCOUNT LOGIC --
                if self.conto_id_in_modifica:
                    # Modify Shared
                    success = modifica_conto_condiviso(
                        self.conto_id_in_modifica,
                        nome,
                        tipo,
                        tipo_condivisione=self.dd_tipo_condivisione.value,
                        lista_utenti=lista_utenti_selezionati if self.dd_tipo_condivisione.value == 'utenti' else None,
                        id_utente=utente_id,
                        master_key_b64=master_key_b64,
                        config_speciale=config_spec_json,
                        icona=self.selected_icon_value,
                        colore=self.selected_color_value
                    )
                    messaggio = "modificato" if success else "errore modifica"
                    new_conto_id = self.conto_id_in_modifica
                else:
                    # Create Shared
                    new_conto_id = crea_conto_condiviso(
                        id_famiglia,
                        nome,
                        tipo,
                        self.dd_tipo_condivisione.value,
                        lista_utenti_selezionati if self.dd_tipo_condivisione.value == 'utenti' else None,
                        id_utente=utente_id,
                        master_key_b64=master_key_b64,
                        config_speciale=config_spec_json,
                        icona=self.selected_icon_value,
                        colore=self.selected_color_value
                    )
                    success = new_conto_id is not None
                    messaggio = "aggiunto" if success else "errore aggiunta"
                    
                    # Saldo iniziale per condivisi
                    if success and saldo_iniziale != 0:
                         # Use existing transaction logic or specific for shared?
                         # crea_conto_condiviso_dialog used aggiungi_transazione_condivisa
                         from db.gestione_db import aggiungi_transazione_condivisa
                         oggi = datetime.date.today().strftime('%Y-%m-%d')
                         aggiungi_transazione_condivisa(utente_id, new_conto_id, oggi, "Saldo Iniziale", saldo_iniziale)
            else:
                # -- PERSONAL ACCOUNT LOGIC --
                if self.conto_id_in_modifica:
                    # Passa il saldo_iniziale come valore_manuale solo se il tipo è 'Fondo Pensione'
                    valore_manuale_modifica = saldo_iniziale if tipo == 'Fondo Pensione' else None
                    
                    success, msg = modifica_conto(self.conto_id_in_modifica, utente_id, nome, tipo, iban, valore_manuale=valore_manuale_modifica, master_key_b64=master_key_b64, id_famiglia=id_famiglia, config_speciale=config_spec_json, icona=self.selected_icon_value, colore=self.selected_color_value)
                    messaggio = "modificato" if success else "errore modifica"
                    new_conto_id = self.conto_id_in_modifica
                    
                    if success and tipo != 'Fondo Pensione' and tipo != 'Investimento':
                        # In modifica NON aggiorniamo più il saldo iniziale da qui.
                        pass

                else:
                    # Passa il saldo_iniziale come valore_manuale solo se il tipo è 'Fondo Pensione'
                    valore_manuale_iniziale = saldo_iniziale if tipo == 'Fondo Pensione' else 0.0
                    res = aggiungi_conto(utente_id, nome, tipo, iban, valore_manuale=valore_manuale_iniziale, master_key_b64=master_key_b64, id_famiglia=id_famiglia, config_speciale=config_spec_json, icona=self.selected_icon_value, colore=self.selected_color_value)
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
                                prezzo_attuale_override=asset['prezzo_attuale'],
                                id_utente=utente_id
                            )
                    else:
                        success = False
                        messaggio = "errore aggiunta"
            # --- END SAVE LOGIC ---

            if success:
                # Gestisci il conto di default (solo personale per ora)
                if self.chk_conto_default.value and new_conto_id and not is_shared:
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
            self._saving_in_progress = False  # Reset flag anti doppio-click
            self.controller.hide_loading()
            if self.controller.page: self.controller.page.update()

    def _aggiorna_preview_personalizzazione(self):
        # Preview Icona
        self.icon_preview.content = AppStyles.get_logo_control(
            tipo=self.dd_conto_tipo.value or "Conto",
            config_speciale=None,
            size=30,
            icona=self.selected_icon_value,
            colore=self.selected_color_value
        )
        # Preview Colore
        self.color_preview.bgcolor = self.selected_color_value if self.selected_color_value else ft.Colors.BLUE_GREY_700
        
        # Forza aggiornamento preview
        self.icon_preview.update()
        self.color_preview.update()
        self.container_personalizzazione.update()

    def _apri_selettore_icona(self, e):
        """Apre un selettore di icone categorizzato (Standard, Conti, Carte, Comuni)."""
        items = []

        # 1. Icone Standard Flet
        icone_standard = [
            ("Default", None),
            ("Banca", "ACCOUNT_BALANCE"), ("Carta", "CREDIT_CARD"),
            ("Contanti", "MONEY"), ("Risparmio", "SAVINGS"),
            ("Investimenti", "TRENDING_UP"), ("Pensione", "WAVES"),
            ("Shopping", "SHOPPING_CART"), ("Auto", "DIRECTIONS_CAR"),
            ("Casa", "HOME"), ("Viaggi", "FLIGHT"), ("Salute", "LOCAL_HOSPITAL"),
        ]
        
        items.append(AppStyles.subheader_text("Icone Standard"))
        standard_grid = ft.GridView(runs_count=4, max_extent=80, spacing=5, run_spacing=5, height=120)
        for nome, val in icone_standard:
            standard_grid.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(getattr(ft.Icons, val) if val else ft.Icons.ACCOUNT_BALANCE, size=24),
                        ft.Text(nome, size=10, text_align=ft.TextAlign.CENTER, no_wrap=True)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    padding=5,
                    border_radius=5,
                    on_click=lambda ev, v=val: self._seleziona_icona_flet(v),
                    ink=True
                )
            )
        items.append(standard_grid)
        items.append(ft.Divider())

        # 2. Icone Categorizzate dal Filesystem
        icone_cat = AppStyles.ottieni_icone_categorizzate()
        
        # Mappa nomi categorie per visualizzazione
        cat_labels = {
            "conti": "Loghi Banche / Conti",
            "carte": "Loghi Carte di Credito",
            "comuni": "Icone Comuni",
            "custom": "Altre Icone"
        }

        for cat_name, files in icone_cat.items():
            items.append(AppStyles.subheader_text(cat_labels.get(cat_name, cat_name.capitalize())))
            grid = ft.GridView(runs_count=3, max_extent=100, spacing=10, run_spacing=10, height=150)
            
            for f in files:
                # Label pulita senza estensione
                label = os.path.splitext(f)[0]
                grid.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Image(src=f"/icons/{cat_name}/{f}", width=32, height=32, fit=ft.ImageFit.CONTAIN),
                            ft.Text(label, size=9, text_align=ft.TextAlign.CENTER, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=5,
                        border_radius=5,
                        on_click=lambda ev, v=f"{cat_name}/{f}": self._seleziona_icona(v),
                        ink=True
                    )
                )
            items.append(grid)
            items.append(ft.Divider())

        self._picker_dlg = ft.AlertDialog(
            title=ft.Text("Seleziona Icona"),
            content=ft.Container(
                content=ft.Column(items, scroll=ft.ScrollMode.AUTO, height=500),
                width=400
            )
        )
        self.controller.page.open(self._picker_dlg)

    def _seleziona_icona_flet(self, icon_name):
        # Per le icone flet passiamo solo il nome (es. "ACCOUNT_BALANCE")
        self.selected_icon_value = icon_name
        self._aggiorna_preview_personalizzazione()
        self.controller.page.close(self._picker_dlg)

    def _seleziona_icona(self, icon_path):
        # Per le icone asset passiamo il percorso relativo (es. "conti/mio.png")
        self.selected_icon_value = icon_path
        self._aggiorna_preview_personalizzazione()
        self.controller.page.close(self._picker_dlg)



    def _apri_selettore_colore(self, e):
        from utils.color_utils import MATERIAL_COLORS
        
        grid = ft.GridView(expand=True, runs_count=6, max_extent=50, spacing=5, run_spacing=5)
        for color in MATERIAL_COLORS:
            grid.controls.append(
                ft.Container(
                    bgcolor=color,
                    width=40,
                    height=40,
                    border_radius=20,
                    on_click=lambda ev, c=color: self._seleziona_colore(c)
                )
            )
            
        self._picker_dlg = ft.AlertDialog(
            title=ft.Text("Seleziona Colore"),
            content=ft.Container(content=grid, width=300, height=300)
        )
        self.controller.page.open(self._picker_dlg)

    def _seleziona_colore(self, color):
        self.selected_color_value = color
        self._aggiorna_preview_personalizzazione()
        self.controller.page.close(self._picker_dlg)

    # --- Logica per Rettifica Saldo (Admin) ---

    def apri_dialog_rettifica_saldo(self, conto_data, is_condiviso=False):
        self.conto_id_in_modifica = conto_data['id_conto']
        self.is_condiviso_in_modifica = is_condiviso
        self.dialog_rettifica_saldo.title.value = f"Rettifica: {conto_data['nome_conto']}"
        self.txt_nuovo_saldo.label = "Nuovo Saldo Reale (Liquidità)" # Clarify what this is
        self.txt_nuovo_saldo.value = f"{conto_data['saldo_calcolato']:.2f}"
        self.txt_nuovo_saldo.error_text = None
        
        # Populate PBs
        self.container_pb_rettifica.controls.clear()
        
        # Determine Family/Master keys
        id_utente = self.controller.get_user_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        
        # Use ID Family from conto_data if available (Shared Account), otherwise fallback
        id_famiglia = conto_data.get('id_famiglia')
        if not id_famiglia:
             id_famiglia = ottieni_prima_famiglia_utente(id_utente)
        
        # Determine is_condiviso from data if not passed explicitly
        is_condiviso_effective = is_condiviso or conto_data.get('condiviso', False) or conto_data.get('tipo', '') == 'Condiviso'
        
        # Fetch PBs
        salvadanai = ottieni_salvadanai_conto(
            conto_data['id_conto'], 
            id_famiglia, 
            master_key_b64, 
            id_utente, 
            is_condiviso=is_condiviso_effective
        )
        
        if not salvadanai:
            self.container_pb_rettifica.controls.append(ft.Text("Nessun salvadanaio.", color="grey", size=12))
        else:
             for s in salvadanai:
                 # Row: Icon | Name | Amount Field | Delete Icon
                 tf_amount = ft.TextField(
                     value=str(s['importo']), 
                     keyboard_type=ft.KeyboardType.NUMBER, 
                     width=100, 
                     text_size=12,
                     data=s # Store PB data in textfield
                 )
                 
                 # Delete state tracking: use a boolean flag in data or a visual Indicator? 
                 # Let's simple use a distinct button that asks confirmation or toggles 'deleted' state visually.
                 # Simple approach: "Mark for delete" button turns red.
                 btn_delete = ft.IconButton(
                     icon=ft.Icons.DELETE_OUTLINE, 
                     icon_color="red", 
                     tooltip="Elimina Salvadanaio",
                     data={'s': s, 'deleted': False}, # Store state
                     on_click=self._toggle_delete_pb
                 )
                 
                 row = ft.Row([
                     ft.Icon(ft.Icons.SAVINGS, size=16, color=ft.Colors.PINK_400),
                     ft.Text(s['nome'], expand=True, size=12, weight="bold"),
                     tf_amount,
                     btn_delete
                 ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                 
                 # Link row to button for visual updates
                 btn_delete.data['row'] = row 
                 btn_delete.data['tf'] = tf_amount
                 
                 self.container_pb_rettifica.controls.append(row)

        if self.dialog_rettifica_saldo not in self.controller.page.overlay:
            self.controller.page.overlay.append(self.dialog_rettifica_saldo)
        self.dialog_rettifica_saldo.open = True
        self.controller.page.update()

    def _chiudi_dialog_rettifica(self, e):
        self.controller.show_loading("Attendere...")
        try:
            self.dialog_rettifica_saldo.open = False
            self.controller.page.update()
        finally:
            self.controller.hide_loading()

    def _toggle_delete_pb(self, e):
        # Toggle 'deleted' state
        current_state = e.control.data.get('deleted', False)
        new_state = not current_state
        e.control.data['deleted'] = new_state
        
        if new_state:
            e.control.icon = ft.Icons.RESTORE_FROM_TRASH
            e.control.icon_color = "green"
            e.control.tooltip = "Annulla eliminazione"
            e.control.data['row'].opacity = 0.5
            e.control.data['tf'].disabled = True
        else:
            e.control.icon = ft.Icons.DELETE_OUTLINE
            e.control.icon_color = "red"
            e.control.tooltip = "Elimina Salvadanaio"
            e.control.data['row'].opacity = 1.0
            e.control.data['tf'].disabled = False
            
        self.dialog_rettifica_saldo.update()

    def _salva_rettifica_saldo(self, e):
        try:
            nuovo_saldo = float(self.txt_nuovo_saldo.value.replace(",", "."))
            id_conto = self.conto_id_in_modifica

            # Chiudi il dialog PRIMA di mostrare lo spinner
            self.dialog_rettifica_saldo.open = False
            self.controller.page.update()
            
            self.controller.show_loading("Attendere...")
            
            if self.is_condiviso_in_modifica:
                success = admin_imposta_saldo_conto_condiviso(id_conto, nuovo_saldo)
            else:
                success = admin_imposta_saldo_conto_corrente(id_conto, nuovo_saldo)
            
            # --- Piggy Bank Rectification ---
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            id_famiglia = ottieni_prima_famiglia_utente(id_utente)
            
            pb_changes_count = 0
            
            for row in self.container_pb_rettifica.controls:
                 if isinstance(row, ft.Row) and len(row.controls) >= 4:
                     tf_amount = row.controls[2]
                     btn_delete = row.controls[3]
                     pb_data = tf_amount.data
                     
                     # Check Delete
                     if btn_delete.data.get('deleted', False):
                         elimina_salvadanaio(pb_data['id'], id_famiglia, master_key_b64=master_key_b64, id_utente=id_utente)
                         pb_changes_count += 1
                         continue
                     
                     # Check Amount Change
                     try:
                         new_amt = float(tf_amount.value.replace(",", "."))
                         if new_amt != pb_data['importo']:
                             admin_rettifica_salvadanaio(
                                 pb_data['id'], 
                                 new_amt, 
                                 master_key_b64, 
                                 id_utente, 
                                 is_shared=self.is_condiviso_in_modifica
                             )
                             pb_changes_count += 1
                     except: pass
            
            # -------------------------------

            if success:
                self.controller.show_snack_bar("Saldo rettificato con successo!", success=True)
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("Errore durante la rettifica del saldo.", success=False)
            
            self.controller.hide_loading()
        except (ValueError, TypeError):
            self.txt_nuovo_saldo.error_text = "Inserire un importo numerico valido."
            self.dialog_rettifica_saldo.update()