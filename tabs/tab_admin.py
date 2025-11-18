import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_categorie_e_sottocategorie,
    ottieni_membri_famiglia,
    rimuovi_utente_da_famiglia,
    modifica_ruolo_utente
)
import google_auth_manager


class AdminTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=10, expand=True)
        self.controller = controller
        self.page = controller.page

        # Controlli per la gestione categorie
        self.lv_categorie = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=10)

        # Controlli per la gestione membri
        self.lv_membri = ft.ListView(expand=True, spacing=10)

        # Controlli per la gestione Google
        self.google_status_text = ft.Text()
        self.google_auth_button = ft.ElevatedButton()
        self.sync_button = ft.ElevatedButton()

        # Tabs interni
        self.tabs_admin = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[],  # Verranno popolati dinamicamente
            expand=1,
        )

        self.content = ft.Column(
            [self.tabs_admin],
            expand=True
        )

    def update_all_admin_tabs_data(self, is_initial_load=False):
        """Aggiorna i dati di tutte le sotto-schede."""
        self.tabs_admin.tabs = self.build_tabs()
        self.update_tab_categorie()
        self.update_tab_membri()
        self.update_tab_google()
        if self.page:
            self.page.update()

    def build_tabs(self):
        """Costruisce e restituisce la lista di controlli per le sotto-schede."""
        loc = self.controller.loc
        return [
            ft.Tab(
                text=loc.get("categories_management"),
                icon=ft.Icons.CATEGORY,
                content=ft.Column([
                    ft.Row([
                        ft.Text(loc.get("categories_management"), size=20, weight=ft.FontWeight.BOLD, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.MONETIZATION_ON,
                            tooltip=loc.get("set_budget"),
                            on_click=lambda e: self.controller.admin_dialogs.apri_dialog_imposta_budget()
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ADD,
                            tooltip=loc.get("add_category"),
                            on_click=lambda e: self.controller.admin_dialogs.apri_dialog_categoria()
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(),
                    self.lv_categorie
                ])
            ),
            ft.Tab(
                text=loc.get("members_management"),
                icon=ft.Icons.PEOPLE,
                content=ft.Column([
                    ft.Row([
                        ft.Text(loc.get("members_management"), size=20, weight=ft.FontWeight.BOLD),
                        ft.IconButton(
                            icon=ft.Icons.PERSON_ADD,
                            tooltip=loc.get("invite_member"),
                            on_click=lambda e: self.controller.admin_dialogs.apri_dialog_invito()
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(),
                    self.lv_membri
                ])
            ),
            ft.Tab(
                text=loc.get("admin_google_settings"),
                icon=ft.Icons.CLOUD_QUEUE, # icona corretta
                content=ft.Column([
                    ft.Text(loc.get("google_settings"), size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(loc.get("google_settings_desc")),
                    ft.Divider(),
                    ft.Row([
                        self.google_status_text,
                        self.google_auth_button,
                    ], spacing=10),
                    ft.Row([
                        self.sync_button,
                    ], spacing=10),
                ])
            )
        ]

    def update_tab_categorie(self):
        loc = self.controller.loc
        theme = self.controller._get_current_theme_scheme()
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return

        self.lv_categorie.controls.clear()
        categorie_data = ottieni_categorie_e_sottocategorie(id_famiglia)

        if not categorie_data:
            self.lv_categorie.controls.append(ft.Text(loc.get("no_categories_found")))
        else:
            for cat_id, cat_info in categorie_data.items():
                sottocategorie_list = ft.Column()
                for sub in cat_info['sottocategorie']:
                    sottocategorie_list.controls.append(
                        ft.Row([
                            ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT, size=16),
                            ft.Text(sub['nome_sottocategoria'], expand=True),
                            ft.IconButton(icon=ft.Icons.EDIT, icon_size=16, tooltip=loc.get("edit"), data=sub, on_click=lambda e: self.controller.admin_dialogs.apri_dialog_sottocategoria(sub_cat_data=e.control.data)),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_size=16, tooltip=loc.get("delete"), icon_color=theme.error, data=sub['id_sottocategoria'], on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.controller.admin_dialogs.elimina_sottocategoria_cliccato, e))),
                        ])
                    )
                
                self.lv_categorie.controls.append(
                    ft.ExpansionPanelList(
                        expand_icon_color=theme.primary,
                        elevation=4,
                        divider_color=theme.outline,
                        controls=[
                            ft.ExpansionPanel(
                                header=ft.Row([
                                    ft.Text(cat_info['nome_categoria'], weight=ft.FontWeight.BOLD),
                                    ft.Row([
                                        ft.IconButton(icon=ft.Icons.ADD, tooltip=loc.get("add_subcategory"), data=cat_id, on_click=lambda e: self.controller.admin_dialogs.apri_dialog_sottocategoria(id_categoria=e.control.data)),
                                        ft.IconButton(icon=ft.Icons.EDIT, tooltip=loc.get("edit"), data={'id_categoria': cat_id, 'nome_categoria': cat_info['nome_categoria']}, on_click=lambda e: self.controller.admin_dialogs.apri_dialog_categoria(e.control.data)),
                                        ft.IconButton(icon=ft.Icons.DELETE, tooltip=loc.get("delete"), icon_color=theme.error, data=cat_id, on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.controller.admin_dialogs.elimina_categoria_cliccato, e))),
                                    ])
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                content=ft.Container(
                                    content=sottocategorie_list,
                                    padding=ft.padding.only(left=15)
                                )
                            )
                        ]
                    )
                )

    def update_tab_membri(self):
        loc = self.controller.loc
        theme = self.controller._get_current_theme_scheme()
        id_famiglia = self.controller.get_family_id()
        current_user_id = self.controller.get_user_id()
        if not id_famiglia: return

        self.lv_membri.controls.clear()
        membri = ottieni_membri_famiglia(id_famiglia)

        if len(membri) <= 1:
            self.lv_membri.controls.append(ft.Text(loc.get("no_members_found")))
        else:
            for membro in membri:
                if membro['id_utente'] == current_user_id:
                    continue

                self.lv_membri.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.PERSON),
                                ft.Column(
                                    [
                                        ft.Text(membro['nome_visualizzato'], weight=ft.FontWeight.BOLD),
                                        ft.Text(membro['ruolo'], color=theme.on_surface_variant)
                                    ],
                                    expand=True
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.EDIT,
                                    tooltip=loc.get("edit") + " " + loc.get("role"),
                                    data=membro,
                                    on_click=lambda e: self.controller.admin_dialogs.apri_dialog_modifica_ruolo(
                                        e.control.data)
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE,
                                    tooltip=loc.get("remove_from_family"),
                                    icon_color=theme.error,
                                    data=membro,
                                    on_click=lambda e: self.controller.open_confirm_delete_dialog(
                                        partial(self.rimuovi_membro_cliccato, e)
                                    )
                                )
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER
                        ),
                        padding=ft.padding.symmetric(vertical=5, horizontal=15),
                        border=ft.border.all(1, theme.outline),
                        border_radius=5
                    )
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

    def update_tab_google(self):
        """Aggiorna la scheda delle impostazioni Google."""
        loc = self.controller.loc
        theme = self.controller._get_current_theme_scheme()
        is_auth = google_auth_manager.is_authenticated()
        self.controller.page.session.set("google_auth_token_present", is_auth)

        self.sync_button.text = loc.get("sync_db_drive")
        self.sync_button.icon = ft.Icons.SYNC
        self.sync_button.on_click = lambda e: self.controller.trigger_auto_sync()
        self.sync_button.tooltip = loc.get("sync_db_drive_tooltip")

        if is_auth:
            self.google_status_text.value = loc.get("status_connected")
            self.google_status_text.color = theme.primary
            self.google_auth_button.text = loc.get("disconnect_google_account")
            self.google_auth_button.on_click = self.controller.logout_google
            self.sync_button.visible = True
        else:
            self.google_status_text.value = loc.get("status_disconnected")
            self.google_status_text.color = theme.error
            self.google_auth_button.text = loc.get("connect_google_account")
            self.google_auth_button.on_click = self.controller.auth_view.login_google
            self.sync_button.visible = False