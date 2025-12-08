import flet as ft
import json
# Google Auth rimosso - ora usiamo Supabase PostgreSQL
from functools import partial
from utils.styles import AppColors, AppStyles, PageConstants
from db.gestione_db import ottieni_categorie_e_sottocategorie, ottieni_membri_famiglia, rimuovi_utente_da_famiglia, ottieni_budget_famiglia, get_smtp_config, save_smtp_config, esporta_dati_famiglia
from utils.email_sender import send_email
from tabs.admin_tabs.subtab_budget_manager import AdminSubTabBudgetManager

class AdminTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.page = controller.page
        
        self.tabs_admin = ft.Tabs(
            tabs=[],  # Verranno popolati dinamicamente
            expand=1,
            divider_color=ft.Colors.TRANSPARENT,
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SECONDARY
        )

        # UI Controls for Email Settings (initialized here to be available)
        self.dd_email_provider = ft.Dropdown(
            label="Provider Email",
            options=[
                ft.dropdown.Option("gmail", "Gmail"),
                ft.dropdown.Option("outlook", "Outlook / Hotmail"),
                ft.dropdown.Option("yahoo", "Yahoo Mail"),
                ft.dropdown.Option("icloud", "iCloud Mail"),
                ft.dropdown.Option("custom", "Altro / Personalizzato"),
            ],
            on_change=self._provider_email_cambiato,
            border_color=ft.Colors.OUTLINE
        )
        self.txt_smtp_server = ft.TextField(label="Server SMTP", border_color=ft.Colors.OUTLINE)
        self.txt_smtp_port = ft.TextField(label="Porta SMTP", border_color=ft.Colors.OUTLINE)
        self.txt_smtp_user = ft.TextField(label="Username / Email", border_color=ft.Colors.OUTLINE)
        self.txt_smtp_password = ft.TextField(label="Password / App Password", password=True, can_reveal_password=True, border_color=ft.Colors.OUTLINE)
        self.txt_gmail_hint = AppStyles.body_text("Per Gmail, devi usare una 'App Password' se hai la 2FA attiva.", color=AppColors.PRIMARY)
        self.txt_gmail_hint.visible = False

        self.btn_test_email = ft.ElevatedButton("Test Email", icon=ft.Icons.SEND, on_click=self._test_email_cliccato)
        self.btn_salva_email = ft.ElevatedButton("Salva Configurazione", icon=ft.Icons.SAVE, on_click=self._salva_email_cliccato, bgcolor=AppColors.PRIMARY, color=AppColors.ON_PRIMARY)

        # UI Controls for Google Settings - RIMOSSI (Google Drive deprecato)

        self.lv_categorie = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        self.lv_membri = ft.Column(scroll=ft.ScrollMode.AUTO)
        
        # Nuovo subtab Gestione Budget
        self.subtab_budget_manager = AdminSubTabBudgetManager(controller)

        self.content = ft.Column(
            [self.tabs_admin],
            expand=True
        )

    def build_tabs(self):
        loc = self.controller.loc
        return [
            ft.Tab(
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
            ),
            ft.Tab(
                text="Gestione Budget",
                icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
                content=self.subtab_budget_manager
            ),
            ft.Tab(
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
            ),
            ft.Tab(
                text="Email / SMTP",
                icon=ft.Icons.EMAIL,
                content=ft.Column([
                    AppStyles.page_divider(),
                    self.dd_email_provider,
                    self.txt_gmail_hint,
                    ft.Row([self.txt_smtp_server, self.txt_smtp_port], spacing=10),
                    ft.Row([self.txt_smtp_user, self.txt_smtp_password], spacing=10),
                    ft.Row([self.btn_test_email, self.btn_salva_email], spacing=10),
                ], scroll=ft.ScrollMode.AUTO)
            ),
            ft.Tab(
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
                                "⚠️ ATTENZIONE: Il file esportato contiene la chiave di crittografia della famiglia. "
                                "Conservalo in un luogo sicuro e non condividerlo con persone non autorizzate.",
                                color=AppColors.WARNING
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=20,
                        border=ft.border.all(1, AppColors.WARNING),
                        border_radius=10
                    )
                ], scroll=ft.ScrollMode.AUTO)
            )
        ]

    def update_tab_categorie(self):
        loc = self.controller.loc
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return

        self.lv_categorie.controls.clear()
        categorie_data = ottieni_categorie_e_sottocategorie(id_famiglia)

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


            # Aggiungi spazio in basso per evitare interferenze con il pulsante +

            self.lv_categorie.controls.append(ft.Container(height=80))


    def update_tab_membri(self):
        loc = self.controller.loc
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        id_famiglia = self.controller.get_family_id()
        current_user_id = self.controller.get_user_id()
        if not id_famiglia: return

        self.lv_membri.controls.clear()
        membri = ottieni_membri_famiglia(id_famiglia)

        if len(membri) <= 1:
            self.lv_membri.controls.append(AppStyles.body_text(loc.get("no_members_found")))
        else:
            for membro in membri:
                if membro['id_utente'] == current_user_id:
                    continue

                content = ft.Row(
                    [
                        ft.Icon(ft.Icons.PERSON, color=AppColors.PRIMARY),
                        ft.Column(
                            [
                                AppStyles.subheader_text(membro['nome_visualizzato']),
                                ft.Text(membro['ruolo'], color=AppColors.TEXT_SECONDARY)
                            ],
                            expand=True
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
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
                
                self.lv_membri.controls.append(
                    AppStyles.card_container(content, padding=15)
                )

    def rimuovi_membro_cliccato(self, e):
        membro_data = e.control.data
        id_famiglia = self.controller.get_family_id()
        success = rimuovi_utente_da_famiglia(membro_data['id_utente'], id_famiglia)
        if success:
            self.controller.show_snack_bar(f"Membro '{membro_data['nome_visualizzato']}' rimosso.", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore durante la rimozione del membro.", success=False)

    # Metodo update_tab_google rimosso - Google Drive deprecato

    def _provider_email_cambiato(self, e):
        """Precompila i campi SMTP in base al provider selezionato."""
        provider = self.dd_email_provider.value
        self.txt_gmail_hint.visible = (provider == "gmail")

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
        
        self.page.update()

    def _test_email_cliccato(self, e):
        """Invia un'email di prova con le impostazioni correnti."""
        server = self.txt_smtp_server.value
        port = self.txt_smtp_port.value
        user = self.txt_smtp_user.value
        password = self.txt_smtp_password.value
        
        if not all([server, port, user, password]):
            self.controller.show_snack_bar("Compila tutti i campi prima di provare.", success=False)
            return

        # Usa l'email dell'utente come destinatario, se disponibile, altrimenti usa l'email SMTP stessa
        destinatario = user # Default
        dati_utente = self.controller.page.session.get("utente_loggato")
        if dati_utente and dati_utente.get('email'):
             destinatario = dati_utente.get('email')
        
        smtp_config = {
            'server': server,
            'port': port,
            'user': user,
            'password': password
        }

        # Mostra spinner durante il test
        self.controller.show_loading("Invio email di test...")
        
        try:
            successo, errore = send_email(
                to_email=destinatario,
                subject="Test Configurazione Email - BudgetAmico",
                body="Se leggi questa email, la configurazione SMTP è corretta!",
                smtp_config=smtp_config
            )
            
            if successo:
                self.controller.show_snack_bar(f"Email di prova inviata a {destinatario}!", success=True)
            else:
                self.controller.show_error_dialog(f"Errore invio email: {errore}")
        except Exception as ex:
            self.controller.show_error_dialog(f"Eccezione durante il test: {str(ex)}")
        finally:
            self.controller.hide_loading()

    def _salva_email_cliccato(self, e):
        """Salva la configurazione email."""
        server = self.txt_smtp_server.value
        port = self.txt_smtp_port.value
        user = self.txt_smtp_user.value
        password = self.txt_smtp_password.value
        provider = self.dd_email_provider.value

        if not all([server, port, user, password]):
            self.controller.show_snack_bar("Tutti i campi email sono obbligatori.", success=False)
            return

        smtp_settings = {
            'server': server,
            'port': port,
            'user': user,
            'password': password,
            'provider': provider
        }

        # Mostra spinner durante il salvataggio
        self.controller.show_loading("Salvataggio configurazione...")
        
        try:
            id_famiglia = self.controller.get_family_id()
            master_key_b64 = self.controller.page.session.get("master_key")
            current_user_id = self.controller.get_user_id()
            if save_smtp_config(smtp_settings, id_famiglia, master_key_b64, current_user_id):
                self.controller.show_snack_bar("Configurazione email salvata con successo!", success=True)
            else:
                self.controller.show_snack_bar("Errore durante il salvataggio della configurazione.", success=False)
        finally:
            self.controller.hide_loading()

    def _esporta_dati_cliccato(self, e):
        """Esporta la family_key e le configurazioni in un file JSON."""
        id_famiglia = self.controller.get_family_id()
        id_utente = self.controller.get_user_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        
        if not all([id_famiglia, id_utente, master_key_b64]):
            self.controller.show_snack_bar("Sessione non valida. Effettua nuovamente il login.", success=False)
            return
        
        # Mostra spinner durante l'export
        self.controller.show_loading("Esportazione dati...")
        
        try:
            export_data, errore = esporta_dati_famiglia(id_famiglia, id_utente, master_key_b64)
        finally:
            self.controller.hide_loading()
        
        if errore:
            self.controller.show_snack_bar(f"Errore: {errore}", success=False)
            return
        
        # Usa FilePicker per salvare il file
        def save_file_result(result: ft.FilePickerResultEvent):
            if result.path:
                try:
                    with open(result.path, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False)
                    self.controller.show_snack_bar(f"File esportato: {result.path}", success=True)
                except Exception as ex:
                    self.controller.show_snack_bar(f"Errore salvataggio: {ex}", success=False)
        
        file_picker = ft.FilePicker(on_result=save_file_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        
        # Genera nome file con data
        from datetime import datetime
        nome_file = f"backup_famiglia_{export_data.get('nome_famiglia', 'export')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_picker.save_file(
            dialog_title="Salva Backup Famiglia",
            file_name=nome_file,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["json"]
        )

    def update_tab_email(self):
        """Popola i campi email con i dati salvati."""
        id_famiglia = self.controller.get_family_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        current_user_id = self.controller.get_user_id()
        smtp_settings = get_smtp_config(id_famiglia, master_key_b64, current_user_id)
        if smtp_settings:
            provider = smtp_settings.get('provider', 'custom')
            self.dd_email_provider.value = provider
            self.txt_smtp_server.value = smtp_settings.get('server', '')
            self.txt_smtp_port.value = smtp_settings.get('port', '')
            self.txt_smtp_user.value = smtp_settings.get('user', '')
            self.txt_smtp_password.value = smtp_settings.get('password', '')
            self.txt_gmail_hint.visible = (provider == "gmail")

    def update_all_admin_tabs_data(self, is_initial_load=False):
        """Aggiorna i dati di tutte le sotto-schede."""
        self.tabs_admin.tabs = self.build_tabs()
        self.update_tab_categorie()
        self.update_tab_membri()
        # update_tab_google rimosso - Google Drive deprecato
        self.update_tab_email()
        self.subtab_budget_manager.update_view_data(is_initial_load)
        if self.page:
            self.page.update()
