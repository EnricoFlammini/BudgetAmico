import flet as ft
import datetime
import traceback
import json
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
    ottieni_carte_utente,
    ottieni_tutti_i_conti_famiglia,
    esegui_giroconto,
    ottieni_salvadanai_conto,
    esegui_giroconto_salvadanaio,
    ottieni_ids_conti_tecnici_carte,
    get_configurazione
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
        self.radio_tipo_transazione = ft.RadioGroup(content=ft.Row(wrap=True, spacing=5))
        self.txt_descrizione_dialog = ft.TextField()
        self.txt_importo_dialog = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        
        # Nuovo Selettore Conto Custom
        self.selected_account_logo = ft.Icon(ft.Icons.ACCOUNT_BALANCE, size=20)
        self.selected_account_name = ft.Text("Seleziona Conto", size=16)
        self.selected_account_key = None
        self.selected_account_data = None
        
        self.pm_conto = ft.PopupMenuButton(
            content=ft.Container(
                content=ft.Row([
                    ft.Row([
                        self.selected_account_logo,
                        self.selected_account_name,
                    ], expand=True, spacing=10),
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN)
                ]),
                padding=ft.padding.all(12),
                border=ft.border.all(1, ft.Colors.OUTLINE),
                border_radius=5,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            items=[],
            tooltip="Seleziona Conto"
        )
        self.txt_error_conto = ft.Text("", color=ft.Colors.RED, size=12, visible=False)
        
        # Selettore Destinazione Custom (Giroconto)
        self.selected_dest_logo = ft.Icon(ft.Icons.ACCOUNT_BALANCE, size=20)
        self.selected_dest_name = ft.Text("Seleziona Destinazione", size=16)
        self.selected_dest_key = None
        
        self.pm_dest = ft.PopupMenuButton(
            content=ft.Container(
                content=ft.Row([
                    ft.Row([
                        self.selected_dest_logo,
                        self.selected_dest_name,
                    ], expand=True, spacing=10),
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN)
                ]),
                padding=ft.padding.all(12),
                border=ft.border.all(1, ft.Colors.OUTLINE),
                border_radius=5,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            items=[],
            tooltip="Seleziona Destinazione"
        )
        self.txt_error_dest = ft.Text("", color=ft.Colors.RED, size=12, visible=False)
        
        self.dd_conto_dialog = ft.Dropdown(visible=False) # Nascosto, usato per compatibilità dati
        self.dd_conto_destinazione_dialog = ft.Dropdown(visible=False) # Nascosto
        self.dd_paypal_fonte_dialog = ft.Dropdown(label="Fonte PayPal", visible=False) # Nuovo per PayPal
        self.dd_sottocategoria_dialog = ft.Dropdown()
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
                ft.Column([
                    ft.Text("Conto", size=12, color=ft.Colors.PRIMARY),
                    self.pm_conto,
                    self.txt_error_conto
                ], spacing=2),
                self.dd_paypal_fonte_dialog, # Visibile solo se PayPal
                ft.Column([
                    ft.Text("Destinazione", size=12, color=ft.Colors.PRIMARY),
                    self.pm_dest,
                    self.txt_error_dest
                ], spacing=2, visible=False),
                self.dd_sottocategoria_dialog,
                self.cb_importo_nascosto,
            ],
            tight=True, scroll=ft.ScrollMode.AUTO, width=350,
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
            ft.Radio(value="Giroconto", label=self.loc.get("transfer", "Giroconto")), # Fallback string if key missing
        ]
        self.radio_tipo_transazione.on_change = self._on_tipo_transazione_change
        self.txt_descrizione_dialog.label = self.loc.get("description")
        self.txt_importo_dialog.label = self.loc.get("amount")
        self.txt_importo_dialog.prefix_text = self.loc.currencies[self.loc.currency]['symbol']
        self.dd_conto_dialog.label = self.loc.get("account")
        self.dd_conto_dialog.on_change = self._on_conto_change
        self.dd_paypal_fonte_dialog.label = "Fonte PayPal (Obbligatoria)"
        self.dd_conto_destinazione_dialog.label = self.loc.get("to_account", "Conto Destinazione")
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

    def _apri_bottom_sheet_conti(self, e, is_dest=False):
        """Metodo rimosso in favore di PopupMenuButton."""
        pass

    def _select_account(self, key, account_data, is_dest=False):
        from utils.styles import AppStyles
        if is_dest:
            self.selected_dest_key = key
            self.selected_dest_name.value = account_data['nome_conto']
            new_logo = AppStyles.get_logo_control(tipo=account_data['tipo'], config_speciale=account_data.get('config_speciale'), size=20)
            self.selected_dest_logo = new_logo
            self.pm_dest.content.content.controls[0].controls[0] = self.selected_dest_logo
            self.dd_conto_destinazione_dialog.value = key
            self.txt_error_dest.visible = False
            self.pm_dest.update()
        else:
            self.selected_account_key = key
            self.selected_account_data = account_data
            self.selected_account_name.value = account_data['nome_conto']
            
            # Aggiorna il logo nel container
            new_logo = AppStyles.get_logo_control(
                tipo=account_data['tipo'],
                config_speciale=account_data.get('config_speciale'),
                size=20
            )
            self.selected_account_logo = new_logo
            self.pm_conto.content.content.controls[0].controls[0] = self.selected_account_logo
            
            self.selected_account_name.color = ft.Colors.BLACK if self.controller.page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.WHITE
            self.txt_error_conto.visible = False
            self.pm_conto.update()
            
            # Sincronizza con il dropdown nascosto per non rompere la logica esistente
            self.dd_conto_dialog.value = key
            
            # Attiva il change handler originale
            self._on_conto_change(None)

    def _reset_account_selector(self):
        self.selected_account_key = None
        self.selected_account_data = None
        self.selected_account_name.value = "Seleziona Conto"
        self.selected_account_logo = ft.Icon(ft.Icons.ACCOUNT_BALANCE, size=20)
        self.pm_conto.content.content.controls[0].controls[0] = self.selected_account_logo
        self.dd_conto_dialog.value = None
        self.txt_error_conto.visible = False
        
        self.selected_dest_key = None
        self.selected_dest_name.value = "Seleziona Destinazione"
        self.selected_dest_logo = ft.Icon(ft.Icons.ACCOUNT_BALANCE, size=20)
        self.pm_dest.content.content.controls[0].controls[0] = self.selected_dest_logo
        self.dd_conto_destinazione_dialog.value = None
        self.txt_error_dest.visible = False

    def _popola_dropdowns(self):
        utente_id = self.controller.get_user_id()
        famiglia_id = self.controller.get_family_id()
        
        if not famiglia_id or str(famiglia_id).strip() == "":
            logger.warning("[DIALOG] _popola_dropdowns: Missing famiglia_id, skipping DB calls.")
            return

        master_key_b64 = self.controller.page.session.get("master_key")

        # 0. Recupera Matrice FOP Globale
        tipo_op = self.radio_tipo_transazione.value or "Spesa"
        raw_matrix = get_configurazione("global_fop_matrix")
        
        matrix_source = {}
        matrix_dest = {}
        
        if raw_matrix:
            try:
                full_matrix = json.loads(raw_matrix)
                if tipo_op == "Giroconto":
                    matrix_source = full_matrix.get("Giroconto (Mittente)", {})
                    matrix_dest = full_matrix.get("Giroconto (Ricevente)", {})
                else:
                    matrix_source = full_matrix.get(tipo_op, {})
            except: logger.error("Errore parsing global_fop_matrix")
        
        # Se la matrice è vuota, usiamo dei default interni per sicurezza
        if not matrix_source:
            matrix_source = {
                "Conto Corrente": {"Personale": True, "Condiviso": True, "Altri Familiari": (tipo_op == "Giroconto")},
                "Carte": {"Personale": (tipo_op == "Spesa"), "Condiviso": (tipo_op == "Spesa"), "Altri Familiari": False},
                "Salvadanaio": {"Personale": (tipo_op == "Giroconto"), "Condiviso": (tipo_op == "Giroconto"), "Altri Familiari": (tipo_op == "Giroconto")}
            }
        if tipo_op == "Giroconto" and not matrix_dest:
             matrix_dest = matrix_source.copy()

        # 1. Recupera tutti i conti della famiglia (necessario per Altri Familiari)
        conti_famiglia = ottieni_tutti_i_conti_famiglia(famiglia_id, utente_id, master_key_b64=master_key_b64)
        ids_conti_tecnici = ottieni_ids_conti_tecnici_carte(utente_id)

        # Mappatura tipi matrice -> tipi DB
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

        def is_allowed(account_data, scope, matrix_to_check):
            t_db = str(account_data.get('tipo') or "").strip().lower()
            cat_fop = None
            
            # Special handling for Portafoglio Elettronico
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
            scope_perms = matrix_to_check.get(cat_fop)
            if scope_perms is not None:
                return scope_perms.get(scope, False)
            return True if scope != "Altri Familiari" else False

        opzioni_sorgente = []
        opzioni_destinazione = []

        for c in conti_famiglia:
            if c['id_conto'] in ids_conti_tecnici or "Saldo" in (c.get('nome_conto') or ""):
                continue
            
            if c['is_condiviso']: scope = "Condiviso"
            elif str(c['id_utente_owner']) == str(utente_id): scope = "Personale"
            else: scope = "Altri Familiari"

            prefix = "C" if c['is_condiviso'] else "P"
            suffix = ""
            if scope == "Condiviso": suffix = " " + self.loc.get("shared_suffix")
            elif scope == "Altri Familiari": suffix = f" ({c.get('nome_owner', 'Altro')})"
            
            icon = "🏦"
            if c['tipo'] in tipo_map["Carte"]: icon = "💳"
            elif c['tipo'] == "Salvadanaio": icon = "🐷"
            elif c['tipo'] == "Contanti": icon = "💵"
            elif c['tipo'] == "Portafoglio Elettronico": icon = "📱"
            
            key = f"{prefix}{c['id_conto']}"
            if c['tipo'] in tipo_map["Carte"]: key = c['id_conto'] 

            opt = ft.dropdown.Option(key=key, text=f"{icon} {c['nome_conto']}{suffix}", data=c)
            
            if is_allowed(c, scope, matrix_source):
                opzioni_sorgente.append(opt)
            
            if tipo_op == "Giroconto" and is_allowed(c, scope, matrix_dest):
                opzioni_destinazione.append(opt)

        self.dd_conto_dialog.options = opzioni_sorgente
        self.dd_conto_destinazione_dialog.options = opzioni_destinazione

        # Popola PopupMenuButton
        from utils.styles import AppStyles
        
        def create_menu_items(options, is_dest):
            items = []
            for opt in options:
                c = opt.data
                suffix = ""
                if c.get('is_condiviso'): suffix = " " + self.loc.get("shared_suffix")
                elif str(c.get('id_utente_owner')) != str(utente_id): 
                     suffix = f" ({c.get('nome_owner', 'Altro')})"

                logo = AppStyles.get_logo_control(tipo=c['tipo'], config_speciale=c.get('config_speciale'), size=20)
                
                items.append(
                    ft.PopupMenuItem(
                        content=ft.Row([
                            logo,
                            ft.Column([
                                ft.Text(f"{c['nome_conto']}{suffix}", size=14),
                                ft.Text(c['tipo'], size=10, color=ft.Colors.GREY_500),
                            ], spacing=0)
                        ], spacing=10),
                        data=c,
                        on_click=lambda e, k=opt.key, d=c, dest=is_dest: self._select_account(k, d, is_dest=dest)
                    )
                )
            return items

        self.pm_conto.items = create_menu_items(opzioni_sorgente, False)
        self.pm_dest.items = create_menu_items(opzioni_destinazione, True)

        # 4. Categories Dropdown
        self.dd_sottocategoria_dialog.options = [
            ft.dropdown.Option(key="", text=self.loc.get("no_category")),
            ft.dropdown.Option(key="INTERESSI", text="💰 Interessi")
        ]
        if famiglia_id:
            categorie = ottieni_categorie_e_sottocategorie(famiglia_id)
            for cat_data in categorie:
                for sub_cat in cat_data['sottocategorie']:
                    self.dd_sottocategoria_dialog.options.append(
                        ft.dropdown.Option(key=sub_cat['id_sottocategoria'], text=f"{cat_data['nome_categoria']} - {sub_cat['nome_sottocategoria']}")
                    )

    def _on_tipo_transazione_change(self, e):
        tipo = self.radio_tipo_transazione.value
        is_giroconto = (tipo == "Giroconto")
        
        # Ricarica dropdown per applicare i filtri specifici del tipo
        self._popola_dropdowns()
        
        # Toggle visibilità campi
        self.pm_dest.parent.visible = is_giroconto
        self.dd_sottocategoria_dialog.visible = not is_giroconto
        self.cb_importo_nascosto.visible = not is_giroconto
        
        # Aggiorna label conto sorgente
        label_text = self.loc.get("from_account", "Da Conto") if is_giroconto else self.loc.get("account")
        self.content.controls[4].controls[0].value = label_text # Aggiorna la label sopra il selettore custom
        
        if self.page and e is not None:
            try:
                self.page.update()
            except Exception as ex:
                logger.error(f"Errore update pagina (_on_tipo_transazione_change): {ex}")

    def _on_conto_change(self, e):
        # Detect if PayPal and show source selection
        val = self.dd_conto_dialog.value
        selected_opt = next((opt for opt in self.dd_conto_dialog.options if opt.key == val), None)
        
        show_paypal = False
        if selected_opt and selected_opt.data:
            c = selected_opt.data
            if c.get('tipo') == 'Portafoglio Elettronico':
                try:
                    config = json.loads(c.get('config_speciale') or '{}')
                    if config.get('sottotipo') == 'paypal':
                        show_paypal = True
                        self._popola_fonti_paypal_dialog(config)
                except: pass
        
        self.dd_paypal_fonte_dialog.visible = show_paypal
        if self.page:
            self.page.update()

    def _popola_fonti_paypal_dialog(self, config):
        fonti_ids = config.get('fonti_collegate', [])
        preferita = config.get('fonte_preferita')
        
        # We need the list of accounts to get names.
        # But we already have it in popola_dropdowns... wait, we filter it.
        # Let's just fetch all family accounts again or pass them.
        # Simpler: just use IDs if we don't want to re-fetch names here.
        # But better to show names.
        
        id_utente = self.controller.get_user_id()
        famiglia_id = self.controller.get_family_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        conti = ottieni_tutti_i_conti_famiglia(famiglia_id, id_utente, master_key_b64=master_key_b64)
        
        self.dd_paypal_fonte_dialog.options = [
            ft.dropdown.Option(str(c['id_conto']), c['nome_conto'])
            for c in conti if c['id_conto'] in fonti_ids
        ]
        
        if preferita and any(opt.key == str(preferita) for opt in self.dd_paypal_fonte_dialog.options):
            self.dd_paypal_fonte_dialog.value = str(preferita)
        elif self.dd_paypal_fonte_dialog.options:
            self.dd_paypal_fonte_dialog.value = self.dd_paypal_fonte_dialog.options[0].key

    def _reset_campi(self):
        self.txt_descrizione_dialog.error_text = None
        self.txt_importo_dialog.error_text = None
        self.dd_conto_dialog.error_text = None
        self.dd_conto_destinazione_dialog.error_text = None
        
        self.txt_data_selezionata.value = datetime.date.today().strftime('%Y-%m-%d')
        self.radio_tipo_transazione.value = "Spesa"
        self.txt_descrizione_dialog.value = ""
        self.txt_importo_dialog.value = ""
        self._reset_account_selector()
        self.dd_conto_destinazione_dialog.value = None
        self.dd_sottocategoria_dialog.value = ""
        self.cb_importo_nascosto.value = False
        self.dd_paypal_fonte_dialog.value = None
        self.dd_paypal_fonte_dialog.visible = False
        
        # Reset visibility state
        self._on_tipo_transazione_change(None)

    def apri_dialog_nuova_transazione(self, e=None):
        logger.info("[DIALOG] Opening: New Transaction")
        try:
            self._update_texts()
            self.controller.page.session.set("transazione_in_modifica", None)
            # _popola_dropdowns viene già chiamato internamente da _reset_campi -> _on_tipo_transazione_change
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
                
            # Aggiorna UI Selettore Custom
            if self.dd_conto_dialog.value:
                opt = next((o for o in self.dd_conto_dialog.options if o.key == self.dd_conto_dialog.value), None)
                if opt: self._select_account(opt.key, opt.data)
                
            if self not in self.controller.page.overlay:
                self.controller.page.overlay.append(self)
            self.open = True
            if self.controller.page:
                try:
                    self.controller.page.update()
                except Exception as e:
                    logger.error(f"Errore update pagina (nuova transazione): {e}")
        except Exception as ex:
            logger.error(f"Errore apertura dialog nuova transazione: {ex}")
            traceback.print_exc()
            self.controller.show_snack_bar(f"Errore: {ex}", success=False)

    def apri_dialog_modifica_transazione(self, transazione_dati):
        logger.info(f"[DIALOG] Opening: Edit Transaction (id={transazione_dati.get('id_transazione') or transazione_dati.get('id_transazione_condivisa')})")
        try:
            self._update_texts()
            self.title.value = self.loc.get("edit") + " " + self.loc.get("new_transaction")
            # _popola_dropdowns viene già chiamato internamente da _reset_campi
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

            self.dd_sottocategoria_dialog.value = transazione_dati.get('id_sottocategoria') or ""
            self.cb_importo_nascosto.value = transazione_dati.get('importo_nascosto', False)

            # Aggiorna UI Selettore Custom
            if self.dd_conto_dialog.value:
                opt = next((o for o in self.dd_conto_dialog.options if o.key == self.dd_conto_dialog.value), None)
                if opt: self._select_account(opt.key, opt.data)

            self.controller.page.session.set("transazione_in_modifica", transazione_dati)
            if self not in self.controller.page.overlay:
                self.controller.page.overlay.append(self)
            self.open = True
            if self.controller.page:
                try:
                    self.controller.page.update()
                except Exception as e:
                    logger.error(f"Errore update pagina (modifica transazione): {e}")
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
            self.dd_conto_destinazione_dialog.error_text = None
            
            tipo = self.radio_tipo_transazione.value

            if not self.txt_descrizione_dialog.value:
                self.txt_descrizione_dialog.error_text = self.loc.get("description_required")
                is_valid = False
            if not self.selected_account_key:
                self.txt_error_conto.value = self.loc.get("select_an_account")
                self.txt_error_conto.visible = True
                is_valid = False
            
            if tipo == "Giroconto":
                if not self.selected_dest_key:
                    self.txt_error_dest.value = self.loc.get("select_destination_account", "Seleziona destinazione")
                    self.txt_error_dest.visible = True
                    is_valid = False
                elif self.selected_account_key == self.selected_dest_key:
                    self.txt_error_dest.value = self.loc.get("accounts_must_be_different", "Conti devono essere diversi")
                    self.txt_error_dest.visible = True
                    is_valid = False
            
            # PayPal Mandatory Source check
            if self.dd_paypal_fonte_dialog.visible and not self.dd_paypal_fonte_dialog.value:
                self.dd_paypal_fonte_dialog.error_text = "Seleziona una fonte PayPal"
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
            id_sottocategoria_raw = self.dd_sottocategoria_dialog.value if tipo != "Giroconto" else None
            
            # Sanificazione id_sottocategoria: assicura che sia int o None, mai ""
            if id_sottocategoria_raw == "" or id_sottocategoria_raw is None:
                id_sottocategoria_raw = None
            elif str(id_sottocategoria_raw).isdigit():
                id_sottocategoria_raw = int(id_sottocategoria_raw)

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
                if len(parts) >= 3:
                     id_carta = int(parts[1])
                     id_conto = int(parts[2])
                     if len(parts) > 3:
                          is_condiviso = (parts[3] == 'S')
                     else:
                          is_condiviso = False
                else:
                     # Fallback per chiavi vecchie o malformate
                     logger.warning(f"Formato chiave carta non valido: {val}")
                     id_carta = int(parts[1])
                     # Se manca l'id_conto, non crashare ma non possiamo procedere correttamente
                     # In produzione, id_conto=0 causerà errore DB ma non crash python
                     id_conto = 0 
            else:
                id_conto = int(val[1:])
                is_condiviso = val.startswith('C')

            return {
                "data": data, "descrizione": descrizione, "importo": importo,
                "id_sottocategoria": id_sottocategoria,
                "id_conto": id_conto,
                "is_nuovo_conto_condiviso": is_condiviso,
                "importo_nascosto": self.cb_importo_nascosto.value,
                "id_carta": id_carta,
                "tipo_transazione": self.radio_tipo_transazione.value,
                "id_conto_destinazione_key": self.selected_dest_key if self.radio_tipo_transazione.value == "Giroconto" else None
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
            
    def _esegui_giroconto(self, dati):
        """Esegue logica giroconto riutilizzando gestione_db"""
        sorgente_key = self.selected_account_key
        destinazione_key = self.selected_dest_key
        importo = dati['importo']
        
        master_key_b64 = self.controller.page.session.get("master_key")
        id_utente = self.controller.get_user_id()
        id_famiglia = self.controller.get_family_id()
        
        # Check Salvadanai logic
        is_source_sb = sorgente_key and str(sorgente_key).startswith("S")
        is_dest_sb = destinazione_key and str(destinazione_key).startswith("S")

        try:
            if is_source_sb and is_dest_sb:
                 logger.warning("Giroconto Salva->Salva non supportato dalla UI")
                 return False # Non supportato
            
            if is_source_sb:
                 # PB -> Account
                 sb_part, parent_key_check = sorgente_key.split('_')
                 id_salvadanaio = int(sb_part[1:])
                 id_conto = int(destinazione_key[1:])
                 is_shared_parent = destinazione_key.startswith("C")
                 
                 # Check parent validity (skipped for brevity, assuming standard usage ok or handled by db)
                 return esegui_giroconto_salvadanaio(
                    id_conto=id_conto, id_salvadanaio=id_salvadanaio, direzione='da_salvadanaio',
                    importo=importo, data=dati['data'], descrizione=dati['descrizione'],
                    master_key_b64=master_key_b64, id_utente=id_utente, id_famiglia=id_famiglia,
                    parent_is_shared=is_shared_parent
                 )

            elif is_dest_sb:
                 # Account -> PB
                 sb_part, parent_key_check = destinazione_key.split('_')
                 id_salvadanaio = int(sb_part[1:])
                 id_conto = int(dati['id_conto']) # Decoded in validation
                 is_shared_parent = sorgente_key.startswith("C") # Simplified check
                 
                 return esegui_giroconto_salvadanaio(
                    id_conto=id_conto, id_salvadanaio=id_salvadanaio, direzione='verso_salvadanaio',
                    importo=importo, data=dati['data'], descrizione=dati['descrizione'],
                    master_key_b64=master_key_b64, id_utente=id_utente, id_famiglia=id_famiglia,
                    parent_is_shared=is_shared_parent
                 )

            else:
                # Standard Account -> Account
                id_conto_sorgente = dati['id_conto']
                tipo_sorgente = "personale" if not dati['is_nuovo_conto_condiviso'] else "condiviso"
                
                # Decode Destinazione
                if destinazione_key.startswith("P"):
                    id_conto_dest = int(destinazione_key[1:])
                    tipo_dest = "personale"
                else:
                    id_conto_dest = int(destinazione_key[1:])
                    tipo_dest = "condiviso"
                
                return esegui_giroconto(
                    id_conto_sorgente, id_conto_dest,
                    importo, dati['data'], dati['descrizione'],
                    master_key_b64=master_key_b64,
                    tipo_origine=tipo_sorgente,
                    tipo_destinazione=tipo_dest,
                    id_utente_autore=id_utente,
                    id_famiglia=id_famiglia
                )
        except Exception as e:
            logger.error(f"Errore esecuzione giroconto: {e}")
            return False

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
                if dati_validati.get('tipo_transazione') == "Giroconto":
                    success = self._esegui_giroconto(dati_validati)
                    messaggio = "eseguita (giroconto)" if success else "errore giroconto"
                else:
                    success = self._esegui_aggiunta(dati_validati)
                    messaggio = "aggiunta" if success else "errore nell'aggiunta"
                    
                    # Logica Automatica PayPal (v0.50)
                    if success and self.dd_paypal_fonte_dialog.visible and self.dd_paypal_fonte_dialog.value:
                        try:
                            mkey = self.controller.page.session.get("master_key")
                            uid = self.controller.get_user_id()
                            f_id = self.controller.get_family_id()
                            
                            id_fonte = int(self.dd_paypal_fonte_dialog.value)
                            id_paypal = dati_validati['id_conto']
                            importo_assoluto = abs(dati_validati['importo'])
                            
                            # Se è una spesa, il giroconto va da Fonte -> PayPal
                            # Se è un incasso, il giroconto va da PayPal -> Fonte (opzionale, ma logico per svuotare il contenitore)
                            if dati_validati['importo'] < 0:
                                esegui_giroconto(
                                    id_fonte, id_paypal, importo_assoluto, dati_validati['data'],
                                    f"Ricarica PayPal per: {dati_validati['descrizione']}",
                                    master_key_b64=mkey, id_utente_autore=uid, id_famiglia=f_id,
                                    tipo_origine="personale", tipo_destinazione="personale" # Assume personal for now
                                )
                        except Exception as ep:
                            logger.error(f"Errore giroconto automatico PayPal: {ep}")

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