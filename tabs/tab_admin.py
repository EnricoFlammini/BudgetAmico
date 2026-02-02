import flet as ft
import json
from functools import partial
from utils.styles import AppColors, AppStyles, PageConstants
from db.gestione_db import (
    ottieni_categorie_e_sottocategorie, 
    ottieni_membri_famiglia, 
    rimuovi_utente_da_famiglia, 
    ottieni_budget_famiglia, 
    get_smtp_config, 
    save_smtp_config, 
    esporta_dati_famiglia,
    esporta_dati_famiglia,
    get_impostazioni_budget_famiglia,
    get_server_family_key,
    enable_server_automation,
    disable_server_automation
)
from utils.email_sender import send_email
from tabs.admin_tabs.subtab_budget_manager import AdminSubTabBudgetManager
from utils.async_task import AsyncTask

class AdminTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page
        
        self.tabs_admin = ft.Tabs(
            tabs=[],
            expand=1,
            divider_color=ft.Colors.TRANSPARENT,
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SECONDARY
        )

        # UI Controls for Email Settings
        self.dd_email_provider = ft.Dropdown(
            label="Provider Email",
            options=[
                ft.dropdown.Option("gmail", "Gmail"),
                ft.dropdown.Option("outlook", "Outlook / Hotmail"),
                ft.dropdown.Option("yahoo", "Yahoo Mail"),
                ft.dropdown.Option("icloud", "iCloud Mail"),
                ft.dropdown.Option("custom", "Altro / Personalizzato"),
            ],
            border_color=ft.Colors.OUTLINE
        )
        self.dd_email_provider.on_change = self._provider_email_cambiato
        self.txt_smtp_server = ft.TextField(label="Server SMTP", border_color=ft.Colors.OUTLINE)
        self.txt_smtp_port = ft.TextField(label="Porta SMTP", border_color=ft.Colors.OUTLINE)
        self.txt_smtp_user = ft.TextField(label="Username / Email", border_color=ft.Colors.OUTLINE)
        self.txt_smtp_password = ft.TextField(label="Password / App Password", password=True, can_reveal_password=True, border_color=ft.Colors.OUTLINE)
        self.txt_gmail_hint = AppStyles.body_text("Per Gmail, devi usare una 'App Password' se hai la 2FA attiva.", color=AppColors.PRIMARY)
        self.txt_gmail_hint.visible = False

        self.btn_test_email = ft.ElevatedButton("Test Email", icon=ft.Icons.SEND, on_click=self._test_email_cliccato)
        self.btn_salva_email = ft.ElevatedButton("Salva Configurazione", icon=ft.Icons.SAVE, on_click=self._salva_email_cliccato, bgcolor=AppColors.PRIMARY, color=AppColors.ON_PRIMARY)

        self.lv_categorie = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        self.lv_membri = ft.Column(scroll=ft.ScrollMode.AUTO)
        
        # Subtab Budget Manager
        self.subtab_budget_manager = AdminSubTabBudgetManager(controller)
        
        # Stato Automazione
        self.server_automation_enabled = False
        self.switch_automation = ft.Switch(
            value=False,
            on_change=self._toggle_automation_click
        )
        self.container_force_check = ft.Container(
             visible=False,
             content=ft.OutlinedButton(
                "Esegui Check Ora (Forza Aggiornamento)",
                icon=ft.Icons.REFRESH,
                on_click=self._force_background_check_click,
                style=ft.ButtonStyle(color=AppColors.PRIMARY)
             ),
             padding=ft.padding.only(left=5)
        )

        self.content = ft.Column(
            [self.tabs_admin],
            expand=True
        )

    def build_tabs(self):
        # ... (unchanged)
        return tabs

    # ... (skipping unchanged methods until _on_export_ready)

    def _esporta_dati_cliccato(self, e):
        # 1. Disable button and show loading
        btn = e.control
        original_text = btn.text
        original_icon = btn.icon
        btn.text = "Generazione Backup..."
        btn.icon = ft.Icons.HOURGLASS_EMPTY
        btn.disabled = True
        if self.page: self.page.update()

        famiglia_id = self.controller.get_family_id()
        master_key = self.controller.page.session.get("master_key")
        user_id = self.controller.get_user_id()
        
        print("[DEBUG] Inizio export dati...")

        def _generate_export():
            try:
                # Esegue export sincrono in background
                return esporta_dati_famiglia(famiglia_id, user_id, master_key)
            except Exception as ex:
                return f"ERROR: {str(ex)}"

        def _on_export_ready(result):
            # Restore button state
            btn.text = original_text
            btn.icon = original_icon
            btn.disabled = False
            
            # Unpack result
            if isinstance(result, str) and result.startswith("ERROR:"):
                 data_export = None
                 error_msg = result
            elif isinstance(result, tuple):
                 data_export, error_msg = result
            else:
                 data_export = None
                 error_msg = "Risultato imprevisto"

            if error_msg:
                print(f"[ERROR] Export fallito: {error_msg}")
                if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar(f"Errore export: {error_msg}", AppColors.ERROR)
            
            elif data_export:
                import json
                try:
                    # Serialize to JSON
                    json_str = json.dumps(data_export, indent=2, default=str)
                    print(f"[DEBUG] Dati export pronti. Dimensione: {len(json_str)} chars")
                    
                    # Store data
                    self.temp_export_data = json_str
                    
                    # Filename
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"budget_amico_backup_{timestamp}.json"
                    
                    print(f"[DEBUG] Apro dialog salvataggio (Global Picker)...")
                    
                    # Usa il picker globale del controller
                    picker = self.controller.file_picker_salva_excel
                    
                    # Ensure in overlay
                    if picker not in self.page.overlay:
                        self.page.overlay.append(picker)
                        self.page.update()
                        
                    # Setup callback
                    picker.on_result = self._on_export_file_result
                    
                    # Save File - Simplest call possible
                    picker.save_file(
                        dialog_title="Salva Backup",
                        file_name=filename,
                    )
                except Exception as e_json:
                    print(f"[ERROR] Export Dialog Error: {e_json}")
                    self.controller.show_error_dialog(f"Errore: {e_json}")

            else:
                 if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar("Nessun dato da esportare.", AppColors.ERROR)
            
            if self.page: self.page.update()

        # Run async
        task = AsyncTask(target=_generate_export, callback=_on_export_ready)
        task.start()

    def build_tabs(self):
        loc = self.controller.loc
        tabs = []
        
        # 1. Categories
        t_cat = ft.Tab(
            text=loc.get("categories_management"),
            icon=ft.Icons.CATEGORY,
            content=ft.Column(expand=True, controls=[
                ft.Row([
                    ft.Container(),  # Spacer
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip=loc.get("add_category"),
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self.controller.admin_dialogs.apri_dialog_categoria()
                    )
                ], alignment=ft.MainAxisAlignment.END),
                AppStyles.page_divider(),
                self.lv_categorie
            ])
        )
        tabs.append(t_cat)

        # 2. Budget
        t_bud = ft.Tab(
            text="Gestione Budget",
            icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
            content=self.subtab_budget_manager
        )
        tabs.append(t_bud)

        # 3. Members
        t_mem = ft.Tab(
            text=loc.get("members_management"),
            icon=ft.Icons.PEOPLE,
            content=ft.Column([
                ft.Row([
                    ft.Container(),  # Spacer
                    ft.IconButton(
                        icon=ft.Icons.PERSON_ADD,
                        tooltip=loc.get("invite_member"),
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self.controller.admin_dialogs.apri_dialog_invito()
                    )
                ], alignment=ft.MainAxisAlignment.END),
                AppStyles.page_divider(),
                self.lv_membri
            ])
        )
        tabs.append(t_mem)

        # 4. Email
        t_email = ft.Tab(
            text="Email / SMTP",
            icon=ft.Icons.EMAIL,
            content=ft.Column([
                AppStyles.page_divider(),
                self.dd_email_provider,
                self.txt_gmail_hint,
                ft.ResponsiveRow([
                    ft.Column([self.txt_smtp_server], col={"xs": 12, "sm": 8}), 
                    ft.Column([self.txt_smtp_port], col={"xs": 12, "sm": 4})
                ]),
                ft.ResponsiveRow([
                    ft.Column([self.txt_smtp_user], col={"xs": 12, "sm": 6}), 
                    ft.Column([self.txt_smtp_password], col={"xs": 12, "sm": 6})
                ]),
                ft.Row([self.btn_test_email, self.btn_salva_email], spacing=10, wrap=True),
            ], scroll=ft.ScrollMode.AUTO)
        )
        tabs.append(t_email)
        
        # 5. Backup
        t_back = ft.Tab(
            text="Backup / Export",
            icon=ft.Icons.BACKUP,
            content=ft.Column([
                AppStyles.page_divider(),
                ft.Container(
                    content=ft.ElevatedButton(
                        "Esporta Family Key e Configurazioni",
                        icon=ft.Icons.DOWNLOAD,
                        on_click=self._esporta_dati_cliccato,
                        bgcolor=AppColors.PRIMARY,
                        color=AppColors.ON_PRIMARY
                    ),
                    padding=20
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.WARNING_AMBER, color=AppColors.WARNING, size=32),
                        AppStyles.body_text(
                            "ATTENZIONE: Il file esportato contiene la chiave di crittografia della famiglia. "
                            "Conservalo in un luogo sicuro e non condividerlo con persone non autorizzate.",
                            color=AppColors.WARNING
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    border=ft.border.all(1, AppColors.WARNING),
                    border_radius=10
                ),
                ft.Divider(height=30),
                AppStyles.subheader_text("Impostazioni Sistema"),
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text("Abilita Logging", weight=ft.FontWeight.W_500),
                            ft.Text("Genera file di log per debug. Richiede riavvio app.", 
                                   size=12, color=AppColors.TEXT_SECONDARY)
                        ], expand=True),
                        ft.Switch(
                            value=self._get_logging_enabled(),
                            on_change=self._toggle_logging
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=15,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=10
                ),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Text("Automazione Cloud (Koyeb)", weight=ft.FontWeight.W_500),
                                ft.Icon(ft.Icons.CLOUD_QUEUE, color=AppColors.PRIMARY, size=16),
                                ft.Container(
                                    content=ft.Text("BETA", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                    bgcolor=AppColors.SECONDARY,
                                    padding=ft.padding.symmetric(horizontal=4, vertical=2),
                                    border_radius=4
                                )
                            ], spacing=5),
                            ft.Text("Esegui spese fisse e aggiorna asset in background.", 
                                   size=12, color=AppColors.TEXT_SECONDARY)
                        ], expand=True),
                        self.switch_automation  # Usa riferimento salvato
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=15,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=10
                ),
                ft.Container(height=5),
                self.container_force_check  # Usa riferimento salvato
            ], scroll=ft.ScrollMode.AUTO)
        )
        tabs.append(t_back)
        
        return tabs

    def update_all_admin_tabs_data(self, is_initial_load=False):
        """Avvia il caricamento asincrono di tutti i dati per le tab Admin."""
        self.tabs_admin.tabs = self.build_tabs()
        
        # Mostra loading nelle liste
        self.lv_categorie.controls = [ft.ProgressRing()]
        self.lv_membri.controls = [ft.ProgressRing()]
        if self.page:
            self.page.update()

        famiglia_id = self.controller.get_family_id()
        if not famiglia_id: return

        master_key_b64 = self.controller.page.session.get("master_key")
        id_utente = self.controller.get_user_id()

        task = AsyncTask(
            target=self._fetch_all_data,
            args=(famiglia_id, master_key_b64, id_utente),
            callback=self._on_data_loaded,
            error_callback=self._on_error
        )
        task.start()

    def _fetch_all_data(self, famiglia_id, master_key_b64, id_utente):
        """Recupera tutti i dati necessari per le sotto-schede in un unico passaggio background."""
        return {
            'categorie': ottieni_categorie_e_sottocategorie(famiglia_id),
            'membri': ottieni_membri_famiglia(famiglia_id, master_key_b64, id_utente),
            'smtp_config': get_smtp_config(famiglia_id, master_key_b64, id_utente),
            'impostazioni_budget': get_impostazioni_budget_famiglia(famiglia_id),
            'budget_impostati': ottieni_budget_famiglia(famiglia_id, master_key_b64, id_utente),
            'server_key': get_server_family_key(famiglia_id)
        }

    def _on_data_loaded(self, result):
        try:
            # 1. Popola Categorie
            self._populate_tab_categorie(result['categorie'])
            
            # 2. Popola Membri
            self._populate_tab_membri(result['membri'])
            
            # 3. Popola Email
            self._populate_tab_email(result['smtp_config'])
            
            # 4. Popola Budget Manager
            self.subtab_budget_manager.update_view_data(prefetched_data=result)
            
            # 5. Stato Automazione - aggiorna switch e container
            self.server_automation_enabled = result.get('server_key') is not None
            self.switch_automation.value = self.server_automation_enabled
            self.container_force_check.visible = self.server_automation_enabled
            
            if self.page:
                self.page.update()
        except Exception as e:
            self._on_error(e)

    def _on_error(self, e):
        print(f"Errore AdminTab: {e}")
        try:
            err_msg = AppStyles.body_text(f"Errore caricamento: {e}", color=AppColors.ERROR)
            self.lv_categorie.controls = [err_msg]
            self.lv_membri.controls = [err_msg]
            if self.page:
                self.page.update()
        except:
            pass

    def _populate_tab_categorie(self, categorie_data):
        loc = self.controller.loc
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        self.lv_categorie.controls.clear()

        if not categorie_data:
            self.lv_categorie.controls.append(AppStyles.body_text(loc.get("no_categories_found")))
        else:
            for cat_info in categorie_data:
                cat_id = cat_info['id_categoria']
                sottocategorie_list = ft.Column()
                for sub in cat_info['sottocategorie']:
                    sottocategorie_list.controls.append(
                        ft.Row([
                            ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT, size=16, color=AppColors.TEXT_SECONDARY),
                            ft.Text(sub['nome_sottocategoria'], expand=True),

                            ft.IconButton(icon=ft.Icons.EDIT, icon_size=16, tooltip=loc.get("edit"), data=sub, icon_color=AppColors.PRIMARY, on_click=lambda e: self.controller.admin_dialogs.apri_dialog_sottocategoria(sub_cat_data=e.control.data)),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_size=16, tooltip=loc.get("delete"), icon_color=AppColors.ERROR, data=sub['id_sottocategoria'], on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.controller.admin_dialogs.elimina_sottocategoria_cliccato, e))),
                        ])
                    )
                
                self.lv_categorie.controls.append(
                    ft.ExpansionPanelList(
                        expand_icon_color=theme.primary,
                        elevation=0,
                        divider_color=ft.Colors.TRANSPARENT,
                        controls=[
                            ft.ExpansionPanel(
                                header=ft.Row([
                                    AppStyles.subheader_text(cat_info['nome_categoria']),
                                    ft.Row([
                                        ft.IconButton(icon=ft.Icons.ADD, tooltip=loc.get("add_subcategory"), data=cat_id, icon_color=AppColors.PRIMARY, on_click=lambda e: self.controller.admin_dialogs.apri_dialog_sottocategoria(id_categoria=e.control.data)),
                                        ft.IconButton(icon=ft.Icons.EDIT, tooltip=loc.get("edit"), data={'id_categoria': cat_id, 'nome_categoria': cat_info['nome_categoria']}, icon_color=AppColors.PRIMARY, on_click=lambda e: self.controller.admin_dialogs.apri_dialog_categoria(e.control.data)),
                                        ft.IconButton(icon=ft.Icons.DELETE, tooltip=loc.get("delete"), icon_color=AppColors.ERROR, data=cat_id, on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.controller.admin_dialogs.elimina_categoria_cliccato, e))),
                                    ])
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                content=ft.Container(
                                    content=sottocategorie_list,
                                    padding=ft.padding.only(left=15, bottom=10)
                                ),
                                bgcolor=AppColors.SURFACE_VARIANT
                            )
                        ]
                    )
                )
            self.lv_categorie.controls.append(ft.Container(height=80))

    def _populate_tab_membri(self, membri):
        loc = self.controller.loc
        current_user_id = self.controller.get_user_id()
        self.lv_membri.controls.clear()

        if len(membri) <= 1:
            self.lv_membri.controls.append(AppStyles.body_text(loc.get("no_members_found")))
        else:
            for membro in membri:
                if membro['id_utente'] == current_user_id:
                    continue

                # Bottoni azione per il membro (Wrap=True per gestirli se sono tanti)
                action_buttons = ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.SEND,
                        tooltip="Rimanda Credenziali",
                        data=membro,
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self._rimanda_credenziali_cliccato(e)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT,
                        tooltip=loc.get("edit") + " " + loc.get("role"),
                        data=membro,
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self.controller.admin_dialogs.apri_dialog_modifica_ruolo(
                            e.control.data)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE,
                        tooltip=loc.get("remove_from_family"),
                        icon_color=AppColors.ERROR,
                        data=membro,
                        on_click=lambda e: self.controller.open_confirm_delete_dialog(
                            partial(self.rimuovi_membro_cliccato, e)
                        )
                    )
                ], spacing=0, wrap=True, alignment=ft.MainAxisAlignment.END)

                content = ft.ResponsiveRow(
                    [
                        # Col 1: Icona + Info Utente
                        ft.Column(
                            [
                                ft.Row([
                                    ft.Icon(ft.Icons.PERSON, color=AppColors.PRIMARY),
                                    ft.Column([
                                            AppStyles.subheader_text(membro['nome_visualizzato']),
                                            ft.Text(membro['ruolo'], color=AppColors.TEXT_SECONDARY)
                                    ], spacing=2)
                                ])
                            ], 
                            col={"xs": 12, "sm": 8}
                        ),
                        
                        # Col 2: Bottoni
                        ft.Column(
                            [action_buttons], 
                            col={"xs": 12, "sm": 4},
                            horizontal_alignment=ft.CrossAxisAlignment.END
                        )
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
                
                self.lv_membri.controls.append(
                    AppStyles.card_container(content, padding=15)
                )

    def _populate_tab_email(self, smtp_settings):
        if smtp_settings:
            provider = smtp_settings.get('provider', 'custom')
            self.dd_email_provider.value = provider
            self.txt_smtp_server.value = smtp_settings.get('server', '')
            self.txt_smtp_port.value = smtp_settings.get('port', '')
            self.txt_smtp_user.value = smtp_settings.get('user', '')
            self.txt_smtp_password.value = smtp_settings.get('password', '')
            self.txt_gmail_hint.visible = (provider == "gmail")

    def _provider_email_cambiato(self, e):
        provider = self.dd_email_provider.value
        self.txt_gmail_hint.visible = (provider == "gmail")
        
        # Autofill Logic
        if provider == "gmail":
            self.txt_smtp_server.value = "smtp.gmail.com"
            self.txt_smtp_port.value = "587"
        elif provider == "outlook":
            self.txt_smtp_server.value = "smtp.office365.com"
            self.txt_smtp_port.value = "587"
        elif provider == "yahoo":
            self.txt_smtp_server.value = "smtp.mail.yahoo.com"
            self.txt_smtp_port.value = "465"
        elif provider == "icloud":
            self.txt_smtp_server.value = "smtp.mail.me.com"
            self.txt_smtp_port.value = "587"
        elif provider == "custom":
            # Don't clear, user might have typed something
            pass
            
        if self.page:
            self.page.update()

    def _test_email_cliccato(self, e):
        # Collect settings from UI
        settings = {
            'provider': self.dd_email_provider.value,
            'server': self.txt_smtp_server.value,
            'port': self.txt_smtp_port.value,
            'user': self.txt_smtp_user.value,
            'password': self.txt_smtp_password.value,
        }
        
        # Validation
        if not all([settings['server'], settings['port'], settings['user'], settings['password']]):
            if hasattr(self.controller, 'show_snack_bar'):
                self.controller.show_snack_bar("Compila tutti i campi prima di inviare il test.", AppColors.ERROR)
            return

        # Disable button during test
        self.btn_test_email.disabled = True
        self.btn_test_email.text = "Invio in corso..."
        if self.page: self.page.update()

        def _run_test():
            try:
                # Send to self (the user who is configuring it)
                to_addr = settings['user']
                subject = "Test Configurazione SMTP - Budget Amico"
                body = "<h3>Test Riuscito!</h3><p>La configurazione SMTP sembra corretta.</p>"
                
                success, error = send_email(to_addr, subject, body, smtp_config=settings)
                
                return success, error
            except Exception as ex:
                return False, str(ex)

        def _on_test_complete(result):
            success, error = result
            self.btn_test_email.disabled = False
            self.btn_test_email.text = "Test Email"
            
            if success:
                if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar(f"Email inviata con successo a {settings['user']}!", AppColors.SUCCESS)
            else:
                if hasattr(self.controller, 'show_error_dialog'):
                    self.controller.show_error_dialog(f"Errore Test Email: {error}")
            
            if self.page: self.page.update()

        # Run async to avoid blocking UI
        task = AsyncTask(
            target=_run_test,
            args=(),
            callback=_on_test_complete,
            error_callback=lambda e: _on_test_complete((False, str(e)))
        )
        task.start()

    def _salva_email_cliccato(self, e):
        # Disable button to prevent double submission
        self.btn_salva_email.disabled = True
        self.btn_salva_email.text = "Salvataggio..."
        if self.page:
            self.page.update()

        settings = {
            'provider': self.dd_email_provider.value,
            'server': self.txt_smtp_server.value,
            'port': self.txt_smtp_port.value,
            'user': self.txt_smtp_user.value,
            'password': self.txt_smtp_password.value,
        }
        famiglia_id = self.controller.get_family_id()

        def _run_save():
            """Esegue il salvataggio in background."""
            try:
                if famiglia_id:
                    # Save as FAMILY CONFIG (Family-Specific)
                    # Each family has its own SMTP configuration.
                    # SMTP credentials are encrypted with SERVER_KEY (not family_key),
                    # so they can be decrypted for password reset without user context.
                    success = save_smtp_config(settings, id_famiglia=famiglia_id)
                    return success, None
                else:
                    return False, "Errore: contesto famiglia non disponibile."
            except Exception as ex:
                return False, str(ex)

        def _on_save_complete(result):
            """Callback chiamato quando il salvataggio è completato."""
            success, error = result
            
            # Re-enable button
            self.btn_salva_email.disabled = False
            self.btn_salva_email.text = "Salva Configurazione"
            
            if success:
                if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar("Configurazione SMTP salvata.", AppColors.SUCCESS)
            else:
                if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar(f"Errore salvataggio: {error}", AppColors.ERROR)
            
            if self.page:
                self.page.update()

        # Run async to avoid blocking UI
        task = AsyncTask(
            target=_run_save,
            args=(),
            callback=_on_save_complete,
            error_callback=lambda ex: _on_save_complete((False, str(ex)))
        )
        task.start()

    def _esporta_dati_cliccato(self, e):
        # 1. Disable button and show loading
        btn = e.control
        # Store original handler/style to restore later if needed
        if not hasattr(self, '_original_export_btn_data'):
            self._original_export_btn_data = {
                'text': btn.text,
                'icon': btn.icon,
                'on_click': btn.on_click,
                'bgcolor': btn.bgcolor
            }
            
        btn.text = "Generazione Backup..."
        btn.icon = ft.Icons.HOURGLASS_EMPTY
        btn.disabled = True
        if self.page: self.page.update()

        famiglia_id = self.controller.get_family_id()
        master_key = self.controller.page.session.get("master_key")
        user_id = self.controller.get_user_id()
        
        print("[DEBUG] Inizio export dati...")

        def _generate_export():
            try:
                # Esegue export sincrono in background
                return esporta_dati_famiglia(famiglia_id, user_id, master_key)
            except Exception as ex:
                return f"ERROR: {str(ex)}"

        def _on_export_ready(result):
            # Unpack result
            data_export = None
            error_msg = None
            
            if isinstance(result, str) and result.startswith("ERROR:"):
                 error_msg = result
            elif isinstance(result, tuple):
                 data_export, error_msg = result
            else:
                 error_msg = "Risultato imprevisto"

            if error_msg:
                # Restore original state on error
                self._ripristina_bottone_export(btn)
                print(f"[ERROR] Export fallito: {error_msg}")
                if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar(f"Errore export: {error_msg}", AppColors.ERROR)
            
            elif data_export:
                import json
                try:
                    # Serialize to JSON string then bytes
                    json_str = json.dumps(data_export, indent=2, default=str)
                    json_bytes = json_str.encode('utf-8')
                    print(f"[DEBUG] Dati export pronti. Dimensione: {len(json_bytes)} bytes")
                    
                    # Store data in SESSION
                    self.controller.page.session.set("excel_export_data", json_bytes)
                    
                    # Transform button to "SAVE" button
                    btn.text = "💾 Salva Backup"
                    btn.icon = ft.Icons.SAVE_ALT
                    btn.disabled = False
                    btn.bgcolor = "green"
                    btn.on_click = self._apri_dialog_salvataggio # New Handler
                    
                    self.controller.show_snack_bar("Backup generato! Clicca su 'Salva Backup' per scaricarlo.", AppColors.SUCCESS)

                except Exception as e_json:
                    self._ripristina_bottone_export(btn)
                    print(f"[ERROR] Serialization Error: {e_json}")
                    self.controller.show_error_dialog(f"Errore: {e_json}")

            else:
                 self._ripristina_bottone_export(btn)
                 if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar("Nessun dato da esportare.", AppColors.ERROR)
            
            if self.page: self.page.update()

        # Run async
        task = AsyncTask(target=_generate_export, callback=_on_export_ready)
        task.start()

    def _ripristina_bottone_export(self, btn):
        if hasattr(self, '_original_export_btn_data'):
            orig = self._original_export_btn_data
            btn.text = orig['text']
            btn.icon = orig['icon']
            btn.on_click = orig['on_click']
            btn.bgcolor = orig['bgcolor']
            btn.disabled = False

    def _apri_dialog_salvataggio(self, e):
        """
        Handler for the 'Save' button click.
        """
        print("[DEBUG] Direct Save Mode activated.")
        
        try:
            # 1. Recupera dati dalla sessione
            file_data = self.controller.page.session.get("excel_export_data")
            if not file_data:
                self.controller.show_snack_bar("Dati export non trovati!", AppColors.ERROR)
                return

            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"budget_amico_backup_{timestamp}.json"

            # 2. Gestione WEB vs DESKTOP
            if self.controller.page.web:
                # WEB: JS Download (Client Side)
                from utils.file_downloader import download_file_web
                
                print(f"[DEBUG] [WEB] Launching JS Download for {filename}...")
                success = download_file_web(self.controller.page, filename, file_data, "application/json")
                
                if success:
                    self.controller.show_snack_bar("Download avviato!", AppColors.SUCCESS)
                else:
                    self.controller.show_snack_bar("Errore avvio download web.", AppColors.ERROR)
                
                # Cleanup session
                self.controller.page.session.remove("excel_export_data")
                
                # Restore button
                self._ripristina_bottone_export(e.control)
                self.page.update()
                
            else:
                # DESKTOP: Salva in Downloads (Robust Fallback)
                from utils.file_downloader import download_file_desktop
                
                success, result = download_file_desktop(self.controller.page, filename, file_data)
                
                if success:
                    print(f"[DEBUG] [DESKTOP] File saved via utility: {result}")
                    self.controller.show_snack_bar(f"Backup salvato in: {result}", AppColors.SUCCESS)
                else:
                    self.controller.show_error_dialog(f"Errore salvataggio: {result}")
                
                # Cleanup session
                self.controller.page.session.remove("excel_export_data")
                
                # Restore button
                self._ripristina_bottone_export(e.control)
                self.page.update()

        except Exception as ex:
            print(f"[ERROR] Save failed: {ex}")
            self.controller.show_error_dialog(f"Errore salvataggio: {ex}")
            
            print(f"[DEBUG] File salvato correttamente in: {full_path}")
            
            # 4. Notifica e apri cartella
            self.controller.show_snack_bar(f"Backup salvato in Download", AppColors.SUCCESS)
            
            # Apri la cartella (Solo Windows)
            import platform
            if platform.system() == "Windows":
                os.startfile(docs_dir)
            
            # Clean session
            self.controller.page.session.remove("excel_export_data")
            
            # Disable button again
            e.control.disabled = True
            e.control.text = "Salvato!"
            e.control.bgcolor = "grey"
            e.control.update()
            
        except Exception as ex:
            print(f"[ERROR] Direct Save failed: {ex}")
            self.controller.show_error_dialog(f"Errore salvataggio diretto: {ex}")


    def _on_export_file_result(self, e: ft.FilePickerResultEvent):
        print(f"[DEBUG] _on_export_file_result: path={e.path}")
        if e.path:
            try:
                with open(e.path, 'w', encoding='utf-8') as f:
                    f.write(self.temp_export_data)
                
                self.controller.show_snack_bar(f"Backup salvato in: {e.path}", AppColors.SUCCESS)
            except Exception as ex:
                self.controller.show_snack_bar(f"Errore durante il salvataggio del file: {ex}", AppColors.ERROR)
            finally:
                self.temp_export_data = None
        else:
            # Create a clean up even if cancelled to free memory
            self.temp_export_data = None

    def rimuovi_membro_cliccato(self, e):
        # When called via partial(request_delete, e), e is the control event
        if hasattr(e, 'control') and e.control and e.control.data:
            id_membro = e.control.data.get('id_utente')
            if id_membro:
                famiglia_id = self.controller.get_family_id()
                # NOTA: l'ordine dei parametri è (id_utente, id_famiglia)
                success = rimuovi_utente_da_famiglia(id_membro, famiglia_id)
                if success:
                    # Aggiorna la lista membri immediatamente
                    self.update_all_admin_tabs_data()
                    if hasattr(self.controller, 'show_snack_bar'):
                        self.controller.show_snack_bar("Membro disabilitato e rimosso dalla famiglia.", AppColors.SUCCESS)
                else:
                    if hasattr(self.controller, 'show_snack_bar'):
                        self.controller.show_snack_bar("Errore durante la rimozione del membro.", AppColors.ERROR)
                if self.page:
                    self.page.update()

    def _rimanda_credenziali_cliccato(self, e):
        """Rimanda le credenziali di accesso a un membro della famiglia."""
        if not hasattr(e, 'control') or not e.control or not e.control.data:
            print("[DEBUG] _rimanda_credenziali: Nessun dato nel controllo")
            return
        
        membro = e.control.data
        email = membro.get('email')
        id_utente_membro = membro.get('id_utente')
        nome = membro.get('nome_visualizzato', 'Utente')
        
        print(f"[DEBUG] Rimanda credenziali per: {nome}, email: {email}, id: {id_utente_membro}")
        
        if not email or email.startswith('removed_') or '@disabled.local' in str(email):
            if hasattr(self.controller, 'show_snack_bar'):
                self.controller.show_snack_bar("Email del membro non disponibile o account disabilitato.", AppColors.ERROR)
            return
        
        # Disabilita il pulsante durante l'invio
        e.control.disabled = True
        if self.page:
            self.page.update()
        
        def _invia_credenziali():
            try:
                from db.gestione_db import get_smtp_config, imposta_password_temporanea
                from utils.email_sender import send_email
                import secrets
                
                famiglia_id = self.controller.get_family_id()
                master_key_b64 = self.controller.page.session.get("master_key")
                id_utente = self.controller.get_user_id()
                
                print(f"[DEBUG] Recupero config SMTP per famiglia: {famiglia_id}")
                
                # Recupera configurazione SMTP
                smtp_config = get_smtp_config(famiglia_id, master_key_b64, id_utente)
                
                print(f"[DEBUG] SMTP config - server: {smtp_config.get('server')}, user: {smtp_config.get('user')}")
                
                if not smtp_config.get('server') or not smtp_config.get('password'):
                    return False, "Configurazione SMTP non completa. Configura prima le impostazioni email."
                
                # Genera una password temporanea
                temp_password = secrets.token_urlsafe(8)
                print(f"[DEBUG] Password temporanea generata")
                
                # Imposta la password temporanea per l'utente
                print(f"[DEBUG] Chiamata imposta_password_temporanea per utente ID: {id_utente_membro}")
                if not imposta_password_temporanea(id_utente_membro, temp_password):
                    return False, "Impossibile generare le credenziali temporanee. Verificare che l'utente abbia un backup key."
                
                print(f"[DEBUG] Password temporanea impostata, invio email a: {email}")
                
                # Costruisci l'email
                subject = "Budget Amico - Le tue credenziali di accesso"
                body = f"""
                <h2>Ciao {nome}!</h2>
                <p>L'amministratore della tua famiglia ti ha inviato le credenziali per accedere a Budget Amico.</p>
                <p>Ecco la tua password temporanea:</p>
                <p style="font-size: 18px; font-weight: bold; background-color: #f0f0f0; padding: 10px; border-radius: 5px;">{temp_password}</p>
                <p>Al prossimo accesso ti verrà chiesto di impostare una nuova password personale.</p>
                <br>
                <p><small>Se non hai richiesto questo messaggio, contatta l'amministratore della tua famiglia.</small></p>
                """
                
                success, error = send_email(email, subject, body, smtp_config=smtp_config)
                print(f"[DEBUG] Risultato invio email: success={success}, error={error}")
                return success, error
                
            except Exception as ex:
                print(f"[ERRORE] Eccezione in _invia_credenziali: {ex}")
                import traceback
                traceback.print_exc()
                return False, str(ex)
        
        def _on_invio_complete(result):
            success, error = result
            
            # Riabilita il pulsante
            e.control.disabled = False
            
            if success:
                if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar(f"Credenziali inviate a {email}", AppColors.SUCCESS)
            else:
                if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar(f"Errore invio: {error}", AppColors.ERROR)
            
            if self.page:
                self.page.update()
        
        # Esegui in background
        task = AsyncTask(
            target=_invia_credenziali,
            args=(),
            callback=_on_invio_complete,
            error_callback=lambda ex: _on_invio_complete((False, str(ex)))
        )
        task.start()

    def _get_logging_enabled(self):
        """Ottiene lo stato del logging dalle impostazioni."""
        from utils.logger import is_logging_enabled
        return is_logging_enabled()
    
    def _toggle_logging(self, e):
        """Cambia lo stato del logging."""
        from utils.logger import set_logging_enabled
        enabled = e.control.value
        if set_logging_enabled(enabled):
            stato = "abilitato" if enabled else "disabilitato"
            if hasattr(self.controller, 'show_snack_bar'):
                self.controller.show_snack_bar(
                    f"Logging {stato}. Riavvia l'app per applicare.", 
                    success=True
                )
        else:
            if hasattr(self.controller, 'show_snack_bar'):
                self.controller.show_snack_bar(
                    "Errore nel salvataggio dell'impostazione.", 
                    success=False
                )
    def _toggle_automation_click(self, e):
        """Gestisce il click sullo switch Automazione."""
        switch = e.control
        is_enabling = switch.value
        
        if is_enabling:
            # Revert UI temporarily until confirmed
            switch.value = False
            switch.update()
            
            # Show confirmation dialog
            def close_dlg(e):
                dlg.open = False
                self.controller.page.update()

            def confirm_enable(e):
                dlg.open = False
                self.controller.page.update()
                self._execute_toggle_automation(True, switch)

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Attivare Automazione Cloud?"),
                content=ft.Column([
                    ft.Text("Abilitando questa funzione, accetti di salvare una copia criptata della tua chiave di famiglia sul server."),
                    ft.Text("Questo permette al server di:", size=12, weight=ft.FontWeight.BOLD),
                    ft.Text("- Pagare le spese fisse alla scadenza", size=12),
                    ft.Text("- Aggiornare i prezzi degli asset", size=12),
                    ft.Container(height=10),
                    ft.Text("Nota: La chiave è protetta dalla chiave segreta del server, ma non è più Zero-Knowledge pura.", 
                           color=AppColors.WARNING, size=12, italic=True),
                ], tight=True),
                actions=[
                    ft.TextButton("Annulla", on_click=close_dlg),
                    ft.TextButton("Accetto e Attiva", on_click=confirm_enable),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self.controller.page.open(dlg)
            self.controller.page.update()
        else:
            # Execute disable immediately
            self._execute_toggle_automation(False, switch)

    def _force_background_check_click(self, e):
        """Forza l'esecuzione immediata dei task di background (solo se automazione attiva)."""
        if not self.server_automation_enabled:
            return

        # Disable button
        btn = e.control
        btn.disabled = True
        btn.text = "Esecuzione in corso..."
        btn.update()

        def _run_force_job():
            try:
                # Import here to avoid circular dependencies if any
                from services.background_service import BackgroundService
                # We can instantiate a temporary service or use a static method if we had one.
                # Since BackgroundService is designed to be singleton-like or safe to instantiate:
                service = BackgroundService()
                
                # Run for THIS family specifically?
                # The service runs for ALL families. But that's fine for an admin action 
                # (it effectively wakes up the server worker).
                # Alternatively, we could call specific logic for this family.
                # But to keep it consistent with the "Server Automation" feature,
                # let's run the global job logic.
                
                service.run_all_jobs_now()
                return True, "Task eseguiti con successo."
            except Exception as ex:
                return False, str(ex)

        def _on_force_complete(result):
            success, msg = result
            btn.disabled = False
            btn.text = "Esegui Check Ora (Forza Aggiornamento)"
            
            if hasattr(self.controller, 'show_snack_bar'):
                color = AppColors.SUCCESS if success else AppColors.ERROR
                self.controller.show_snack_bar(msg, success=success)
            
            if self.page: self.page.update()

        task = AsyncTask(target=_run_force_job, callback=_on_force_complete)
        task.start()

    def _execute_toggle_automation(self, enable, switch_control):
        id_famiglia = self.controller.get_family_id()
        id_utente = self.controller.get_user_id()
        master_key = self.controller.page.session.get("master_key")
        
        success = False
        if enable:
            success = enable_server_automation(id_famiglia, master_key, id_utente)
            msg = "Automazione Attivata!" if success else "Errore attivazione. Controlla i log."
        else:
            success = disable_server_automation(id_famiglia)
            msg = "Automazione Disattivata." if success else "Errore disattivazione."
            
        # Update UI state
        if success:
            switch_control.value = enable
            self.server_automation_enabled = enable
            if hasattr(self.controller, 'show_snack_bar'):
                self.controller.show_snack_bar(msg, success=True)
        else:
            switch_control.value = not enable # Revert
            if hasattr(self.controller, 'show_snack_bar'):
                self.controller.show_snack_bar(msg, success=False)
        
        switch_control.update()
