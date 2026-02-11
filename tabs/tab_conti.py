
import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_dettagli_conti_utente,
    elimina_conto,
    ottieni_prima_famiglia_utente,
    ottieni_salvadanai_conto,
    crea_salvadanaio,
    elimina_conto_condiviso,
    ottieni_conti_condivisi_famiglia
)
from utils.async_task import AsyncTask
from utils.styles import AppStyles, AppColors, PageConstants
from utils.color_utils import get_color_from_string, get_type_color, MATERIAL_COLORS
from dialogs.account_transactions_dialog import AccountTransactionsDialog
import datetime

class ContiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page

        # --- Dialog Crea Salvadanaio ---
        self.dialog_crea_salvadanaio = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nuovo Salvadanaio"),
            actions=[
                ft.TextButton("Annulla", on_click=self._chiudi_dialog_salvadanaio),
                ft.TextButton("Crea", on_click=self._salva_nuovo_salvadanaio)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.tf_nome_salvadanaio = ft.TextField(label="Nome Salvadanaio", width=300)
        self.current_conto_id_for_sb = None

        # Main content - Grid View
        self.main_view = ft.Column(
            expand=True, 
            spacing=10, 
            scroll=ft.ScrollMode.ADAPTIVE
        )
        
        # Grid for cards
        self.grid_conti = ft.GridView(
            expand=1,
            runs_count=5,
            max_extent=400,
            child_aspect_ratio=1.0,
            spacing=10,
            run_spacing=10,
        )

        self.loading_view = ft.Container(
            content=ft.Column([
                ft.ProgressRing(color=AppColors.PRIMARY),
                AppStyles.body_text(self.controller.loc.get("loading"), color=AppColors.TEXT_SECONDARY)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment(0, 0),
            expand=True,
            visible=False
        )

        self.content = ft.Stack([
            self.main_view,
            self.loading_view
        ], expand=True)


    def update_view_data(self, is_initial_load=False):
        master_key_b64 = self.controller.page.session.get("master_key")
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        loc = self.controller.loc

        self.main_view.controls = [
            ft.Row([
                AppStyles.title_text("Gestione Conti"),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            AppStyles.page_divider(),
            self.grid_conti,
            ft.Container(height=50) # Spacer
        ]
        
        utente_id = self.controller.get_user_id()
        if not utente_id: return

        self.main_view.visible = False
        self.loading_view.visible = True
        if self.controller.page:
            self.controller.page.update()

        task = AsyncTask(
            target=self._fetch_data,
            args=(utente_id, master_key_b64),
            callback=partial(self._on_data_loaded, theme),
            error_callback=self._on_error
        )
        task.start()

    def _fetch_data(self, utente_id, master_key_b64):
        conti = ottieni_dettagli_conti_utente(utente_id, master_key_b64=master_key_b64)
        personali = [c for c in conti if c['tipo'] not in ['Investimento', 'Carta di Credito']]
        
        id_famiglia = ottieni_prima_famiglia_utente(utente_id)
        
        if id_famiglia:
            for c in personali:
                c['salvadanai'] = ottieni_salvadanai_conto(c['id_conto'], id_famiglia, master_key_b64, utente_id, is_condiviso=False)
        
        condivisi = []
        if id_famiglia:
            condivisi = ottieni_conti_condivisi_famiglia(id_famiglia, utente_id, master_key_b64=master_key_b64)
            for c in condivisi:
                 c['salvadanai'] = ottieni_salvadanai_conto(c['id_conto'], id_famiglia, master_key_b64, utente_id, is_condiviso=True)
            
        return personali, condivisi

    def _on_data_loaded(self, theme, result):
        conti_personali, conti_condivisi = result
        self.grid_conti.controls.clear()
        
        has_accounts = False

        all_accounts = []
        for c in conti_personali:
            c['is_shared'] = False
            all_accounts.append(c)
        for c in conti_condivisi:
            c['is_shared'] = True
            all_accounts.append(c)

        if all_accounts:

            for idx, conto in enumerate(all_accounts):
                # Pick color from palette sequentially to ensure uniqueness in this list
                # Imported MATERIAL_COLORS at module level (Need to check imports)
                color = MATERIAL_COLORS[idx % len(MATERIAL_COLORS)]
                self.grid_conti.controls.append(self._crea_card_conto(conto, theme, assigned_color=color))
            has_accounts = True

        if not has_accounts:
             self.grid_conti.controls.append(AppStyles.body_text(self.controller.loc.get("no_accounts_yet")))

        self.loading_view.visible = False
        self.main_view.visible = True
        if self.controller.page:
            self.controller.page.update()

    def _on_error(self, e):
        print(f"Errore ContiTab: {e}")
        self.loading_view.visible = False
        self.main_view.controls = [AppStyles.body_text(f"Errore caricamento: {e}", color=AppColors.ERROR)]
        self.main_view.visible = True
        if self.controller.page:
            self.controller.page.update()

    def _apri_dialog_aggiungi(self, e):
        """Apre il dialog per aggiungere un nuovo conto."""
        try:
            self.controller.conto_dialog.apri_dialog_conto(e, escludi_investimento=True)
        except Exception as ex:
            print(f"Errore apertura dialog aggiungi conto: {ex}")

    def _crea_card_conto(self, conto: dict, theme, assigned_color: str = None) -> ft.Card:
        is_shared = conto.get('is_shared', False)
        tipo = conto['tipo']
        nome = conto['nome_conto']
        id_conto = conto['id_conto']
        print(f"[DEBUG] UI Building Card for Account {id_conto} ({nome}). DB Icon: {conto.get('icona')}, DB Color: {conto.get('colore')}")
        
        # Determine colors
        # Background: Use user defined color OR assigned unique color
        db_color = conto.get('colore')
        db_icon = conto.get('icona')
        print(f"[DEBUG] ContiTab - Account {nome} (id:{id_conto}): DB_Color='{db_color}', DB_Icon='{db_icon}'")
        
        if db_color and str(db_color).strip():
            bg_color = db_color
            print(f"[DEBUG]  -> Using DB Color: {bg_color}")
        elif assigned_color:
            bg_color = assigned_color
            print(f"[DEBUG]  -> Using Assigned Color: {bg_color}")
        else:
            bg_color = get_color_from_string(str(id_conto) + nome)
            print(f"[DEBUG]  -> Using Hash Color: {bg_color}")
        
        # Type Indicator Color
        type_color = get_type_color(tipo)
        
        # Is Investment/Pension?
        is_investimento = tipo == 'Investimento'
        is_fondo = tipo == 'Fondo Pensione'
        is_corrente = tipo in ['Corrente', 'Risparmio', 'Contanti']

        # Icon logic
        icon = ft.Icons.ACCOUNT_BALANCE
        if tipo == 'Contanti': icon = ft.Icons.MONEY
        elif tipo == 'Risparmio': icon = ft.Icons.SAVINGS
        elif is_shared: icon = ft.Icons.GROUP
        
        # E-Wallet Specialization
        if tipo == 'Portafoglio Elettronico':
            import json
            try:
                config = json.loads(conto.get('config_speciale') or '{}')
                sottotipo = config.get('sottotipo', '').lower()
                if sottotipo == 'satispay':
                    icon = ft.Icons.PHONELINK_RING
                    if not assigned_color: bg_color = ft.Colors.RED_400 # Satispay Red-ish
                elif sottotipo == 'paypal':
                    icon = ft.Icons.PAYMENTS
                    if not assigned_color: bg_color = ft.Colors.BLUE_800 # PayPal Blue
            except:
                icon = ft.Icons.SMARTPHONE

        saldo_val = conto['saldo_calcolato']
        
        # Salvadanai breakdown logic
        pb_liquidita = 0.0
        pb_risparmio = 0.0
        salvadanai_list = conto.get('salvadanai', [])
        
        for s in salvadanai_list:
            if s.get('incide_su_liquidita', False):
                pb_liquidita += s['importo']
            else:
                pb_risparmio += s['importo']

        # Totale Effettivo (Saldo DB + Money in PBs) assuming saldo_db is net
        # If saldo_db already has PB deducted (as transfers):
        available = saldo_val + pb_liquidita 
        # Total Worth = Available + Savings PBs
        total_worth = available + pb_risparmio
        
        # Logo/Icon selection
        logo_control = AppStyles.get_logo_control(
            tipo=tipo, 
            config_speciale=conto.get('config_speciale'),
            size=30,
            color=ft.Colors.WHITE,
            icona=conto.get('icona'),
            colore=conto.get('colore')
        )

        # Content Column
        content_col = [
            ft.Row([
                ft.Row([
                    logo_control,
                    ft.Container(width=5), # Small spacer
                    AppStyles.subheader_text(nome, color=ft.Colors.WHITE),
                ], expand=True),
                
                # Type Indicator (Colored dot/badge)
                ft.Container(
                    content=ft.Text(tipo[:1], color=ft.Colors.BLACK, size=10, weight="bold"),
                    bgcolor=type_color,
                    width=20, height=20, border_radius=10,
                    alignment=ft.alignment.center,
                    tooltip=f"Tipo: {tipo}"
                )
            ]),
            AppStyles.small_text(f"{'IBAN: ' + conto['iban'] if conto.get('iban') else 'Nessun IBAN'}", color=ft.Colors.WHITE70),
        ]
        
        # Balance Section
        content_col.append(ft.Container(height=10))
        content_col.append(
            ft.Column([
                ft.Text(f"€ {total_worth:,.2f}", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, font_family="Roboto"),
                AppStyles.small_text("Saldo Totale", color=ft.Colors.WHITE70)
            ], spacing=0)
        )
        
        # removed inline progress/breakdown to save space

        # Actions Section (Bottom)
        actions = []
        
        # Statement Button (NEW)
        actions.append(
             ft.IconButton(
                icon=ft.Icons.LIST_ALT, 
                icon_color=ft.Colors.WHITE, 
                tooltip="Estratto Conto Mensile", 
                on_click=lambda e: self._apri_estratto_conto(conto)
            )
        )

        # Realign Balance Button (Restored)
        actions.append(
            ft.IconButton(
                icon=ft.Icons.TUNE,
                tooltip="Riallinea Saldo",
                icon_color=ft.Colors.WHITE,
                data=conto,
                on_click=lambda e: self.controller.conto_dialog.apri_dialog_rettifica_saldo(e.control.data, is_condiviso=is_shared)
            )
        )

        # Piggy Bank create
        if not is_investimento and not is_fondo:
             # Menù salvadanai
             menu_items = []
             menu_items.append(ft.PopupMenuItem(content=ft.Text("Risparmi:", weight=ft.FontWeight.BOLD), disabled=True))
             
             if pb_risparmio > 0:
                 for s in salvadanai_list:
                     # Mostra solo i salvadanai di risparmio (non liquidità) che compongono la cifra risparmiata
                     if not s.get('incide_su_liquidita', False):
                        menu_items.append(
                             ft.PopupMenuItem(
                                 content=ft.Row([
                                     ft.Icon(ft.Icons.SAVINGS, size=16, color=ft.Colors.AMBER),
                                     ft.Text(f"{s['nome']}: € {s['importo']:,.2f}")
                                 ], spacing=5)
                             )
                        )
                 menu_items.append(ft.PopupMenuItem(content=ft.Divider(height=1), disabled=True))
                 menu_items.append(
                     ft.PopupMenuItem(
                         content=ft.Row([
                             ft.Icon(ft.Icons.MONETIZATION_ON, size=16, color=ft.Colors.GREEN),
                             ft.Text(f"Totale: € {pb_risparmio:,.2f}", weight=ft.FontWeight.BOLD)
                         ], spacing=5), disabled=True
                     )
                 )
             else:
                  menu_items.append(ft.PopupMenuItem(text="Nessun risparmio attivo", disabled=True))

             menu_items.append(ft.PopupMenuItem(content=ft.Divider(height=1), disabled=True))
             menu_items.append(
                 ft.PopupMenuItem(
                     text="Nuovo Salvadanaio",
                     icon=ft.Icons.ADD,
                     data=(id_conto, is_shared),
                     on_click=self._apri_dialog_salvadanaio
                 )
             )

             actions.append(
                ft.PopupMenuButton(
                    icon=ft.Icons.SAVINGS,
                    tooltip="Menu Salvadanai",
                    icon_color=ft.Colors.WHITE,
                    items=menu_items
                )
             )

        # Edit
        actions.append(
            ft.IconButton(
                icon=ft.Icons.EDIT, 
                tooltip="Modifica", 
                icon_color=ft.Colors.WHITE, 
                data=conto,
                on_click=lambda e: self.controller.conto_dialog.apri_dialog_conto(e, e.control.data, escludi_investimento=True, is_shared_edit=is_shared)
            )
        )
        
        # Delete
        actions.append(
             ft.IconButton(
                icon=ft.Icons.DELETE, 
                tooltip="Elimina",
                icon_color=ft.Colors.WHITE, 
                data=(id_conto, is_shared),
                on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.elimina_conto_cliccato, e))
            )
        )

        content_col.append(ft.Container(expand=True)) # Spacer
        content_col.append(ft.Row(actions, alignment=ft.MainAxisAlignment.END))

        # Main Card Container with unique color
        # Add visual "Type" strip on left? Or just use the badge? 
        # User asked for "corner or something". Badge is good.
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column(content_col),
                padding=15,
                bgcolor=bg_color,
                border_radius=10,
                # border=ft.border.only(left=ft.border.BorderSide(5, type_color)) # Optional: Colored strip on left
            ),
            elevation=5
        )

    def _apri_estratto_conto(self, conto):
        # Open Dialog
        master_key = self.controller.page.session.get("master_key")
        is_shared = conto.get('is_shared', False)
        
        dlg = AccountTransactionsDialog(
            page=self.controller.page,
            id_conto=conto['id_conto'],
            nome_conto=conto['nome_conto'],
            master_key_b64=master_key,
            controller=self.controller,
            is_shared=is_shared
        )
        self.controller.page.open(dlg)

    def _apri_dialog_salvadanaio(self, e):
        if isinstance(e.control.data, tuple):
             self.current_conto_id_for_sb = e.control.data
        else:
             self.current_conto_id_for_sb = (e.control.data, False)

        self.tf_nome_salvadanaio.value = ""
        
        self.dialog_crea_salvadanaio.content = ft.Container(
            content=ft.Column([
                ft.Text("Nuovo salvadanaio per questo conto.", size=14),
                ft.Container(height=10),
                self.tf_nome_salvadanaio,
                ft.Container(height=10),
                ft.Text("Il salvadanaio verrà creato vuoto.\nUsa 'Giroconto' per versare fondi.", size=11, color="grey", italic=True)
            ], tight=True),
            width=350,
            padding=10
        )
        self.controller.page.open(self.dialog_crea_salvadanaio)

    def _chiudi_dialog_salvadanaio(self, e):
        self.controller.page.close(self.dialog_crea_salvadanaio)

    def _salva_nuovo_salvadanaio(self, e):
        nome = self.tf_nome_salvadanaio.value
        if not nome: return
        
        id_famiglia = self.controller.get_family_id()
        id_utente = self.controller.get_user_id()
        master_key = self.controller.page.session.get("master_key")
        
        id_conto, is_shared = self.current_conto_id_for_sb
        
        self.controller.show_loading("Creazione salvadanaio...")
        
        success = crea_salvadanaio(
            id_famiglia, nome, 0.0, 
            id_conto=id_conto if not is_shared else None, 
            id_conto_condiviso=id_conto if is_shared else None,  
            master_key_b64=master_key, 
            id_utente=id_utente,
            incide_su_liquidita=False
        )
        
        self.controller.hide_loading()
        self._chiudi_dialog_salvadanaio(None)
        
        if success:
            self.controller.show_snack_bar("Salvadanaio creato!", success=True)
            self.update_view_data()
        else:
             self.controller.show_snack_bar("Errore creazione salvadanaio.", success=False)

    def elimina_conto_cliccato(self, e):
        id_conto, is_shared = e.control.data
        utente_id = self.controller.get_user_id()
        
        if is_shared:
             risultato = elimina_conto_condiviso(id_conto)
             if risultato is True:
                self.controller.show_snack_bar("Conto condiviso eliminato.", success=True)
                self.controller.db_write_operation()
             else:
                 self.controller.show_error_dialog("Errore durante l'eliminazione del conto condiviso.")
        else:
            risultato = elimina_conto(id_conto, utente_id)

            if risultato is True:
                self.controller.show_snack_bar("Conto personale eliminato.", success=True)
                self.controller.db_write_operation()
            elif risultato == "NASCOSTO":
                self.controller.show_snack_bar("✅ Conto nascosto. Storico mantenuto.", success=True)
                self.controller.db_write_operation()
            elif risultato == "SALDO_NON_ZERO":
                self.controller.show_snack_bar("❌ Errore: Il saldo non è 0.", success=False)
            elif isinstance(risultato, tuple) and not risultato[0]:
                self.controller.show_error_dialog(risultato[1])
            else:
                self.controller.show_error_dialog("Errore sconosciuto.")