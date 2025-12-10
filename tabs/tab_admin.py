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
    get_impostazioni_budget_famiglia
)
from utils.email_sender import send_email
from tabs.admin_tabs.subtab_budget_manager import AdminSubTabBudgetManager
from utils.async_task import AsyncTask

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
            'budget_impostati': ottieni_budget_famiglia(famiglia_id, master_key_b64, id_utente)
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
        self.txt_gmail_hint.visible = (self.dd_email_provider.value == "gmail")
        if self.page:
            self.page.update()

    def _test_email_cliccato(self, e):
        # Placeholder for test email
        if hasattr(self.controller, 'show_snack_bar'):
             self.controller.show_snack_bar("Funzionalità Test Email non ancora completata.", ft.Colors.ORANGE)

    def _salva_email_cliccato(self, e):
        settings = {
            'provider': self.dd_email_provider.value,
            'server': self.txt_smtp_server.value,
            'port': self.txt_smtp_port.value,
            'user': self.txt_smtp_user.value,
            'password': self.txt_smtp_password.value,
        }
        famiglia_id = self.controller.get_family_id()
        master_key = self.controller.page.session.get("master_key")
        user_id = self.controller.get_user_id()
        
        try:
            save_smtp_config(settings, famiglia_id, master_key, user_id)
            if hasattr(self.controller, 'show_snack_bar'):
                self.controller.show_snack_bar("Configurazione SMTP salvata.", AppColors.SUCCESS)
        except Exception as ex:
             if hasattr(self.controller, 'show_snack_bar'):
                self.controller.show_snack_bar(f"Errore salvataggio: {ex}", AppColors.ERROR)

    def _esporta_dati_cliccato(self, e):
        # Placeholder for export
        famiglia_id = self.controller.get_family_id()
        master_key = self.controller.page.session.get("master_key")
        user_id = self.controller.get_user_id()
        
        try:
            data = esporta_dati_famiglia(famiglia_id, user_id, master_key)
            if data:
                 if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar("Esportazione riuscita (Salvataggio file non implementato).", AppColors.SUCCESS)
            else:
                 if hasattr(self.controller, 'show_snack_bar'):
                    self.controller.show_snack_bar("Nessun dato da esportare.", AppColors.ERROR)
        except Exception as ex:
             if hasattr(self.controller, 'show_snack_bar'):
                self.controller.show_snack_bar(f"Errore esportazione: {ex}", AppColors.ERROR)

    def rimuovi_membro_cliccato(self, e):
        # When called via partial(request_delete, e), e is the control event
        if hasattr(e, 'control') and e.control and e.control.data:
            id_membro = e.control.data.get('id_utente')
            if id_membro:
                famiglia_id = self.controller.get_family_id()
                rimuovi_utente_da_famiglia(famiglia_id, id_membro)
                self.update_all_admin_tabs_data()
                if hasattr(self.controller, 'show_snack_bar'):
                     self.controller.show_snack_bar("Membro rimosso con successo.", AppColors.SUCCESS)
