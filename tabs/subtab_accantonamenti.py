import flet as ft
import datetime
from dateutil.relativedelta import relativedelta
from utils.styles import AppStyles, AppColors
from db.gestione_db import (
    crea_obiettivo, ottieni_obiettivi, aggiorna_obiettivo, elimina_obiettivo,
    crea_salvadanaio, ottieni_salvadanai_obiettivo, elimina_salvadanaio,
    crea_salvadanaio, ottieni_salvadanai_obiettivo, elimina_salvadanaio,
    ottieni_conti, ottieni_asset_conto, ottieni_salvadanai_conto,
    collega_salvadanaio_obiettivo, ottieni_prima_famiglia_utente,
    ottieni_conti_condivisi_famiglia, scollega_salvadanaio_obiettivo
)

class AccantonamentiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=10, expand=True)
        self.controller = controller
        
        # --- UI Components ---
        self.lista_obiettivi = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
        self.txt_no_obiettivi = AppStyles.empty_state(ft.Icons.MONEY_OFF, "Nessun obiettivo di risparmio definito.")
        
        # --- Dialog Crea/Modifica Obiettivo ---
        self.dialog_obiettivo = None
        self.tf_nome = ft.TextField(label="Nome Obiettivo", autofocus=True)
        self.tf_importo = ft.TextField(label="Importo Target (€)", keyboard_type=ft.KeyboardType.NUMBER)
        self.cb_suggerimento = ft.Checkbox(label="Mostra suggerimento mensile", value=True)
        self.dp_data = ft.DatePicker(
            first_date=datetime.datetime.now(),
            last_date=datetime.datetime.now() + relativedelta(years=30),
            on_change=self._on_date_change
        )
        self.btn_data = ft.ElevatedButton(
            "Seleziona Scadenza",
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=lambda _: self.controller.page.open(self.dp_data)
        )
        self.txt_data_selected = ft.Text("Nessuna data selezionata")
        self.tf_note = ft.TextField(label="Note", multiline=True, min_lines=2)
        self.selected_objective_id = None 

        # --- Dialog Gestione Fondi (Salvadanai) ---
        self.dialog_fondi = None
        self.dd_conti = ft.Dropdown(label="Fonte (Conto)", options=[]) # Solo conti per ora
        self.tf_importo_fondo = ft.TextField(label="Importo da assegnare (€)", keyboard_type=ft.KeyboardType.NUMBER)
        self.tf_nome_fondo = ft.TextField(label="Etichetta (es. Quota Auto)", value="Accantonamento")
        self.lista_salvadanai_view = ft.Column(spacing=5)
        self.current_obj_for_funds = None

        # Main Layout
        self.content = ft.Column([
            ft.Row([
                AppStyles.subheader_text("Obiettivi di Risparmio"),
                ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=AppColors.PRIMARY, tooltip="Aggiungi Obiettivo", on_click=self._apri_dialog_creazione)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            self.lista_obiettivi
        ], expand=True)

    def update_view_data(self):
        """Carica la lista degli obiettivi."""
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return

        self.lista_obiettivi.controls.clear()
        
        master_key_b64 = self.controller.page.session.get("master_key")
        id_utente = self.controller.get_user_id()
        
        obiettivi = ottieni_obiettivi(id_famiglia, master_key_b64, id_utente)
        
        if not obiettivi:
            self.lista_obiettivi.controls.append(self.txt_no_obiettivi)
        else:
            for obj in obiettivi:
                self.lista_obiettivi.controls.append(self._crea_card_obiettivo(obj))
        
        if self.page: self.page.update()

    def _crea_card_obiettivo(self, obj):
        loc = self.controller.loc
        
        target = obj['importo_obiettivo']
        accumulated = obj['importo_accumulato']
        goal_date = obj['data_obiettivo']
        show_suggestion = obj.get('mostra_suggerimento_mensile', True)
        
        if isinstance(goal_date, str):
            goal_date = datetime.datetime.strptime(goal_date, "%Y-%m-%d").date()
            
        today = datetime.date.today()
        
        # Progress
        progress = accumulated / target if target > 0 else 0
        progress_clamped = min(progress, 1.0)
        
        # Monthly Calc
        months_remaining = (goal_date.year - today.year) * 12 + (goal_date.month - today.month)
        remaining_amount = target - accumulated
        monthly_needed = 0
        
        if remaining_amount > 0 and months_remaining > 0:
            monthly_needed = remaining_amount / months_remaining
        
        color_progress = AppColors.PRIMARY
        if progress >= 1.0: color_progress = AppColors.SUCCESS
        
        date_str = goal_date.strftime("%d/%m/%Y")
        
        rows_details = [
            ft.Text(f"{loc.format_currency(accumulated)} su {loc.format_currency(target)}", size=14, weight=ft.FontWeight.BOLD),
            ft.ProgressBar(value=progress_clamped, color=color_progress, bgcolor=AppColors.SURFACE_VARIANT, height=10, border_radius=5),
            ft.Container(height=5),
            ft.Row([
                ft.Text(f"{progress*100:.1f}% Raggiunto", size=12, color=color_progress),
                ft.TextButton("Gestisci Fondi", icon=ft.Icons.ACCOUNT_BALANCE_WALLET, on_click=lambda e: self._apri_dialog_fondi(obj), style=ft.ButtonStyle(visual_density=ft.VisualDensity.COMPACT))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ]

        if show_suggestion and remaining_amount > 0:
            if months_remaining > 0:
                rows_details.append(
                    ft.Row([
                        ft.Icon(ft.Icons.SAVINGS, size=16, color=AppColors.SECONDARY),
                        ft.Text(f"Risparmio mensile consigliato: {loc.format_currency(monthly_needed)}", size=12, color=AppColors.SECONDARY, weight=ft.FontWeight.W_500)
                    ], spacing=5)
                )
            else:
                 rows_details.append(
                    ft.Text("Scadenza superata!", size=12, color=AppColors.ERROR, weight=ft.FontWeight.BOLD)
                )

        return AppStyles.card_container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        AppStyles.subheader_text(obj['nome']),
                        AppStyles.small_text(f"Scadenza: {date_str}")
                    ], expand=True),
                    ft.PopupMenuButton(
                        items=[
                            ft.PopupMenuItem(text="Modifica", icon=ft.Icons.EDIT, on_click=lambda e: self._apri_dialog_modifica(obj)),
                            ft.PopupMenuItem(text="Elimina", icon=ft.Icons.DELETE, on_click=lambda e: self._conferma_eliminazione(obj)),
                        ]
                    )
                ]),
                ft.Divider(),
                *rows_details
            ]),
            padding=15
        )

    # --- Dialog Obiettivo ---
    
    def _init_dialog_obiettivo(self):
        if not self.dialog_obiettivo:
            self.dialog_obiettivo = ft.AlertDialog(
                title=ft.Text("Obiettivo"),
                content=ft.Column([
                    self.tf_nome,
                    self.tf_importo,
                    ft.Row([self.btn_data, self.txt_data_selected], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.cb_suggerimento,
                    self.tf_note
                ], tight=True, width=400),
                actions=[
                    ft.TextButton("Annulla", on_click=lambda e: self.controller.page.close(self.dialog_obiettivo)),
                    ft.ElevatedButton("Salva", on_click=self._salva_obiettivo)
                ]
            )

    def _on_date_change(self, e):
        if self.dp_data.value:
            self.txt_data_selected.value = self.dp_data.value.strftime("%d/%m/%Y")
            self.dp_data.update()
            if self.dialog_obiettivo: self.dialog_obiettivo.update()

    def _apri_dialog_creazione(self, e):
        self._init_dialog_obiettivo()
        self.selected_objective_id = None
        self.dialog_obiettivo.title.value = "Nuovo Obiettivo"
        self.tf_nome.value = ""
        self.tf_importo.value = ""
        self.tf_note.value = ""
        self.cb_suggerimento.value = True
        self.dp_data.value = None
        self.txt_data_selected.value = "Seleziona Data"
        self.controller.page.open(self.dialog_obiettivo)

    def _apri_dialog_modifica(self, obj):
        self._init_dialog_obiettivo()
        self.selected_objective_id = obj['id']
        self.dialog_obiettivo.title.value = "Modifica Obiettivo"
        self.tf_nome.value = obj['nome']
        self.tf_importo.value = str(obj['importo_obiettivo'])
        self.tf_note.value = obj['note']
        self.cb_suggerimento.value = obj.get('mostra_suggerimento_mensile', True)
        
        d = obj['data_obiettivo']
        if isinstance(d, str): d = datetime.datetime.strptime(d, "%Y-%m-%d").date()
        self.dp_data.value = datetime.datetime(d.year, d.month, d.day)
        self.txt_data_selected.value = d.strftime("%d/%m/%Y")
        
        self.controller.page.open(self.dialog_obiettivo)

    def _salva_obiettivo(self, e):
        try:
            nome = self.tf_nome.value
            if not nome:
                self.tf_nome.error_text = "Campo obbligatorio"
                self.tf_nome.update()
                return

            try:
                importo = float(self.tf_importo.value.replace(",", "."))
            except:
                self.tf_importo.error_text = "Valore non valido"
                self.tf_importo.update()
                return
            
            if not self.dp_data.value:
                self.controller.show_snack_bar("Data mancante", success=False)
                return
                
            data_obj = self.dp_data.value.strftime("%Y-%m-%d")
            
            id_famiglia = self.controller.get_family_id()
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            
            if self.selected_objective_id:
                success = aggiorna_obiettivo(
                    self.selected_objective_id, id_famiglia, nome, importo, data_obj, 
                    self.tf_note.value, master_key_b64, id_utente, self.cb_suggerimento.value
                )
                msg = "Obiettivo aggiornato"
            else:
                success = crea_obiettivo(
                    id_famiglia, nome, importo, data_obj, self.tf_note.value, 
                    master_key_b64, id_utente, self.cb_suggerimento.value
                )
                msg = "Obiettivo creato"
            
            if success:
                self.controller.show_snack_bar(msg, success=True)
                self.controller.page.close(self.dialog_obiettivo)
                self.update_view_data()
                
        except Exception as ex:
            self.controller.show_snack_bar(f"Errore: {ex}", success=False)

    # --- Dialog Fondi (Salvadanai) ---
    
    def _apri_dialog_fondi(self, obj):
        self.current_obj_for_funds = obj
        self._init_dialog_fondi()
        
        # Load Salvadanai
        self._refresh_salvadanai_list(update_ui=False)
        
        # Load Sources (Conti)
        self._load_conti_options(update_ui=False)
        
        self.tf_importo_fondo.value = ""
        self.tf_nome_fondo.value = f"Quota {obj['nome']}"
        self.controller.page.open(self.dialog_fondi)

    def _init_dialog_fondi(self):
        if not self.dialog_fondi:
            self.dialog_fondi = ft.AlertDialog(
                title=ft.Text("Gestione Fondi Assegnati"),
                content=ft.Column([
                    ft.Text("Fondi attualmente assegnati:"),
                    ft.Container(
                        content=self.lista_salvadanai_view,
                        height=150,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=5,
                        padding=5,
                        tooltip="Lista Salvadanai"
                    ),
                    ft.Divider(),
                    ft.Text("Aggiungi Fondi", weight=ft.FontWeight.BOLD),
                    self.dd_conti,
                    self.tf_nome_fondo,
                    self.tf_importo_fondo,
                ], tight=True, width=450, scroll=ft.ScrollMode.AUTO),
                actions=[
                    ft.TextButton("Chiudi", on_click=lambda e: self.controller.page.close(self.dialog_fondi)),
                    ft.ElevatedButton("Assegna", on_click=self._assegna_fondo)
                ]
            )

    def _load_conti_options(self, update_ui=True):
        id_utente = self.controller.get_user_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        id_famiglia = ottieni_prima_famiglia_utente(id_utente)
        
        conti = ottieni_conti(id_utente, master_key_b64)
        
        if id_famiglia:
            condivisi = ottieni_conti_condivisi_famiglia(id_famiglia, id_utente, master_key_b64)
            conti.extend(condivisi)
        
        # Get currently assigned sources to filter duplicates
        assigned_pbs = ottieni_salvadanai_obiettivo(self.current_obj_for_funds['id'], id_famiglia, master_key_b64, id_utente)
        used_accounts = set()
        used_shared_accounts = set()
        used_assets = set()
        
        for pb in assigned_pbs:
            if pb.get('id_conto'): used_accounts.add(pb['id_conto'])
            if pb.get('id_conto_condiviso'): used_shared_accounts.add(pb['id_conto_condiviso'])
            if pb.get('id_asset'): used_assets.add(pb['id_asset'])
            
        options = []
        for c in conti:
            if c['tipo'] == 'Investimento':
                # Drill down to Assets
                is_shared_acc = c.get('condiviso', False)
                assets = ottieni_asset_conto(c['id_conto'], master_key_b64, is_shared=is_shared_acc, id_utente=id_utente)
                if not assets:
                    # Option to select Broker itself? Maybe not if user wants specific asset.
                    # check if broker account is used (unlikely for assets but possible if we support it)
                    if c['id_conto'] not in used_accounts:
                        options.append(ft.dropdown.Option(key=f"account_{c['id_conto']}", text=f"{c['nome_conto']} (Vuoto)"))
                else:
                    for a in assets:
                         if a['id'] in used_assets: continue
                         options.append(ft.dropdown.Option(
                             key=f"asset_{a['id']}", 
                             text=f"Asset: {a['ticker']} - {a['nome']} ({c['nome_conto']})"
                         ))
            else:
                # Standard Account
                is_shared = c.get('condiviso', False)
                target_id = c.get('id_conto_condiviso') if is_shared else c['id_conto']
                
                # Check if already used
                if is_shared:
                    if target_id in used_shared_accounts: continue
                    key_prefix = "account_S_"
                else:
                    if target_id in used_accounts: continue
                    key_prefix = "account_P_"
                
                options.append(ft.dropdown.Option(key=f"{key_prefix}{target_id}", text=c['nome_conto']))
                
                # Associated PBs ?
                if id_famiglia:
                     pbs = ottieni_salvadanai_conto(c['id_conto'], id_famiglia, master_key_b64, id_utente, is_condiviso=is_shared)
                     for pb in pbs:
                         # Exclude if already assigned to THIS goal
                         if pb.get('id_obiettivo') == self.current_obj_for_funds['id']:
                             continue
                             
                         # Warning: if assigned to OTHER goal? Maybe show it?
                         text = f"Salvadanaio: {pb['nome']} ({c['nome_conto']})"
                         if pb.get('id_obiettivo'):
                             text += " [In uso]"
                             
                         options.append(ft.dropdown.Option(
                             key=f"pb_{pb['id']}", 
                             text=text
                         ))
        
        self.dd_conti.options = options
        if options: self.dd_conti.value = options[0].key
        if update_ui and self.dialog_fondi: self.dialog_fondi.update()

    def _refresh_salvadanai_list(self, update_ui=True):
        if not self.current_obj_for_funds: return
        
        self.lista_salvadanai_view.controls.clear()
        
        id_famiglia = self.controller.get_family_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        id_utente = self.controller.get_user_id()
        
        salvadanai = ottieni_salvadanai_obiettivo(self.current_obj_for_funds['id'], id_famiglia, master_key_b64, id_utente)
        
        if not salvadanai:
            self.lista_salvadanai_view.controls.append(ft.Text("Nessun fondo assegnato.", italic=True, size=12))
        else:
            for s in salvadanai:
                self.lista_salvadanai_view.controls.append(
                    ft.Row([
                        ft.Column([
                            ft.Text(s['nome'], weight=ft.FontWeight.BOLD, size=12),
                            ft.Text(s['source'], size=10, color=AppColors.TEXT_SECONDARY)
                        ], expand=True),
                        ft.Text(self.controller.loc.format_currency(s['importo']), weight=ft.FontWeight.BOLD),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=20, icon_color=ft.Colors.RED_400, 
                                      on_click=lambda e, sid=s['id']: self._rimuovi_fondo(sid))
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
        if update_ui and self.dialog_fondi: self.dialog_fondi.update()

    def _assegna_fondo(self, e):
        try:
            val = self.tf_importo_fondo.value.strip()
            
            importo = 0.0
            usa_saldo_totale = False
            
            if not val:
                 usa_saldo_totale = True
                 # Importo 0 placeholder, won't be used if flag is True
            else:
                 try:
                     importo = float(val.replace(",", "."))
                     if importo < 0: return # Negative assignments not allowed?
                 except ValueError:
                     return # Invalid number
            
            if not self.dd_conti.value: return
            
            selection_key = self.dd_conti.value
            
            id_famiglia = self.controller.get_family_id()
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            
            success = False
            msg = ""
            
            if selection_key.startswith("pb_"):
                # Linking existing PB
                pb_id = int(selection_key.split("_")[1])
                success = collega_salvadanaio_obiettivo(pb_id, self.current_obj_for_funds['id'], id_famiglia)
                # Note: Linking doesn't change usa_saldo_totale of the existing PB. 
                # If user wants to change it, they should edit the PB settings (future feature).
                msg = "Salvadanaio collegato!"
                
            elif selection_key.startswith("asset_"):
                # Create PB linked to Asset
                asset_id = int(selection_key.split("_")[1])
                nome = self.tf_nome_fondo.value
                success = crea_salvadanaio(
                    id_famiglia, nome, importo, 
                    id_obiettivo=self.current_obj_for_funds['id'],
                    id_asset=asset_id,
                    master_key_b64=master_key_b64, 
                    id_utente=id_utente,
                    incide_su_liquidita=False,
                    usa_saldo_totale=usa_saldo_totale
                )
                msg = "Fondo Asset assegnato!"
                
            elif selection_key.startswith("account_"):
                # Parse Key: account_TYPE_ID
                parts = selection_key.split("_")
                # parts[0] = account
                # parts[1] = P or S
                # parts[2] = ID
                
                acc_type = parts[1]
                id_conto = int(parts[2])
                nome = self.tf_nome_fondo.value
                
                target_id_conto = None
                target_id_shared = None
                
                if acc_type == 'P':
                    target_id_conto = id_conto
                    params = {'id_conto': id_conto}
                elif acc_type == 'S':
                    target_id_shared = id_conto
                    params = {'id_conto_condiviso': id_conto}
                else:
                    # Legacy fallback
                    return


                # If transferring money (Account PB + Not Dynamic + Amount > 0)
                should_transfer = (not usa_saldo_totale) and (importo > 0)
                
                # 1. Create (Start with 0 if transferring)
                initial_importo = 0.0 if should_transfer else importo
                
                new_id = crea_salvadanaio(
                    id_famiglia, nome, initial_importo, 
                    id_obiettivo=self.current_obj_for_funds['id'],
                    master_key_b64=master_key_b64, 
                    id_utente=id_utente,
                    incide_su_liquidita=False,
                    usa_saldo_totale=usa_saldo_totale,
                    **params
                )
                
                if new_id and should_transfer:
                    # 2. Transfer Funds
                    from db.gestione_db import esegui_giroconto_salvadanaio
                    target_id = target_id_shared if target_id_shared else target_id_conto
                    is_shared_parent = bool(target_id_shared)
                    
                    success_transfer = esegui_giroconto_salvadanaio(
                        id_conto=target_id,
                        id_salvadanaio=new_id,
                        direzione='verso_salvadanaio',
                        importo=importo,
                        descrizione=f"Assegnazione a {self.current_obj_for_funds['nome']}",
                        master_key_b64=master_key_b64,
                        id_utente=id_utente,
                        id_famiglia=id_famiglia,
                        parent_is_shared=is_shared_parent
                    )
                    
                    if not success_transfer:
                        msg = "Salvadanaio creato ma ERRORE nel trasferimento fondi!"
                        # Warning: PB exists with 0. User can fix manually.
                        success = True # We still return success as PB exists? Or valid partial success.
                    else:
                        msg = "Fondo Conto assegnato e importo scalato!"
                        success = True
                else:
                    success = bool(new_id)
                    msg = "Fondo Conto assegnato!"
            
            if success:
                self.tf_importo_fondo.value = ""
                # self._refresh_salvadanai_list() # Not needed if closing
                self.update_view_data() # Update parent view totals
                self.controller.show_snack_bar(msg, success=True)
                
                # Close the dialog as requested
                self.controller.page.close(self.dialog_fondi)
            else:
                self.controller.show_snack_bar("Errore", success=False)
                
        except Exception as ex:
             self.controller.show_snack_bar(f"Errore input: {ex}", success=False)

    def _rimuovi_fondo(self, id_salvadanaio):
        id_famiglia = self.controller.get_family_id()
        # Unlink instead of delete
        if scollega_salvadanaio_obiettivo(id_salvadanaio, id_famiglia):
            self._refresh_salvadanai_list()
            self.update_view_data()
        else:
            self.controller.show_snack_bar("Errore rimozione", success=False)

    def _conferma_eliminazione(self, obj):
        def delete():
            id_famiglia = self.controller.get_family_id()
            if elimina_obiettivo(obj['id'], id_famiglia):
                self.update_view_data()
                self.controller.show_snack_bar("Eliminato", success=True)
        self.controller.open_confirm_delete_dialog(delete)
