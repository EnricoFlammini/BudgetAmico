import flet as ft

# Importa TUTTE le classi delle schede
from tabs.tab_personale import PersonaleTab
from tabs.tab_famiglia import FamigliaTab
from tabs.tab_conti import ContiTab
from tabs.tab_conti_condivisi import ContiCondivisiTab
from tabs.tab_budget import BudgetTab
from tabs.tab_admin import AdminTab
from tabs.tab_prestiti import PrestitiTab
from tabs.tab_immobili import ImmobiliTab
from tabs.tab_impostazioni import ImpostazioniTab
from tabs.tab_spese_fisse import SpeseFisseTab


class DashboardView:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page

        # 1. Inizializza TUTTE le schede
        self.tab_personale = PersonaleTab(controller)
        self.tab_famiglia = FamigliaTab(controller)
        self.tab_conti = ContiTab(controller)
        self.tab_conti_condivisi = ContiCondivisiTab(controller)
        self.tab_budget = BudgetTab(controller)
        self.tab_admin = AdminTab(controller)
        self.tab_prestiti = PrestitiTab(controller)
        self.tab_immobili = ImmobiliTab(controller)
        self.tab_impostazioni = ImpostazioniTab(controller)
        self.tab_spese_fisse = SpeseFisseTab(controller)

        # 2. Definisci il contenitore dei Tabs
        self.tabs_control = ft.Tabs(
            selected_index=0,
            expand=True,
            tabs=[],
            on_change=self._tab_changed
        )

        # 3. Aggiungi un contenitore per le viste speciali (Admin/Impostazioni)
        self.special_view_container = ft.Container(
            content=None,
            expand=True,
            visible=False
        )

        # 4. Memorizza i componenti dell'AppBar
        self.appbar_title = ft.Text()  # Il testo verrà impostato dinamicamente
        self.appbar_leading = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            on_click=self.hide_special_view,
            visible=False
        )
        # Pulsante Admin nell'AppBar
        self.appbar_admin_button = ft.IconButton(
            icon=ft.Icons.ADMIN_PANEL_SETTINGS,
            tooltip="Admin",
            on_click=lambda e: self.show_special_view("admin"),
            visible=False
        )
        # Icona per lo stato della sincronizzazione
        self.sync_status_icon = ft.IconButton(
            icon=ft.Icons.CLOUD_DONE,
            tooltip="Stato Sincronizzazione Google Drive",
            visible=False
        )

    def build_view(self) -> ft.View:
        """
        Costruisce e restituisce la vista del Dashboard.
        """
        loc = self.controller.loc
        self.appbar_title.value = loc.get("app_title")

        return ft.View(
            "/dashboard",
            [
                ft.Stack(
                    [
                        self.tabs_control,
                        self.special_view_container
                    ],
                    expand=True
                )
            ],
            appbar=ft.AppBar(
                title=self.appbar_title,
                leading=self.appbar_leading,
                actions=[
                    ft.IconButton(
                        icon=ft.Icons.INFO_OUTLINE,
                        tooltip=loc.get("info"),
                        on_click=self.controller.open_info_dialog
                    ),
                    self.sync_status_icon,
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS,
                        tooltip=loc.get("settings"),
                        on_click=lambda e: self.show_special_view("impostazioni")
                    ),
                    self.appbar_admin_button,
                    ft.IconButton(
                        icon=ft.Icons.DOWNLOAD,
                        tooltip=loc.get("export_data"),
                        on_click=lambda _: self.page.go("/export")
                    ),
                    ft.IconButton(
                        icon=ft.Icons.LOGOUT,
                        tooltip=loc.get("logout"),
                        on_click=self.controller.logout
                    ),
                ]
            ),
            floating_action_button=ft.FloatingActionButton(
                icon=ft.Icons.ADD,
                tooltip=self.controller.loc.get("add"),
                on_click=self._open_add_menu
            )
        )

    def show_special_view(self, view_name):
        """Mostra una vista speciale (Admin o Impostazioni) e nasconde le tab."""
        loc = self.controller.loc
        if view_name == "admin":
            self.special_view_container.content = self.tab_admin
            self.appbar_title.value = loc.get("admin_panel_title")
        elif view_name == "impostazioni":
            self.special_view_container.content = self.tab_impostazioni
            self.appbar_title.value = loc.get("settings")

        self.tabs_control.visible = False
        self.special_view_container.visible = True
        self.appbar_leading.visible = True
        self.page.update()

    def hide_special_view(self, e=None):
        """Nasconde la vista speciale e mostra di nuovo le tab."""
        self.tabs_control.visible = True
        self.special_view_container.visible = False
        self.appbar_leading.visible = False
        self.appbar_title.value = self.controller.loc.get("app_title")
        self.page.update()

    def _open_add_menu(self, e):
        """Apre un BottomSheet con le opzioni di aggiunta."""
        loc = self.controller.loc

        def close_bs(e):
            bs.open = False
            bs.update()

        bs = ft.BottomSheet(
            ft.Container(
                ft.Column(
                    [
                        ft.ListTile(
                            title=ft.Text(loc.get("new_transaction")),
                            leading=ft.Icon(ft.Icons.ADD),
                            on_click=lambda _: [close_bs(_),
                                                self.controller.transaction_dialog.apri_dialog_nuova_transazione()]
                        ),
                        ft.ListTile(
                            title=ft.Text(loc.get("new_transfer")),
                            leading=ft.Icon(ft.Icons.SWAP_HORIZ),
                            on_click=lambda _: [close_bs(_), self.controller.giroconto_dialog.apri_dialog()]
                        ),
                    ], tight=True
                ), padding=10
            ),
            open=True,
        )
        self.page.overlay.append(bs)
        self.page.update()

    def _tab_changed(self, e):
        """
        Callback per l'evento di cambio tab. Aggiorna i dati della tab selezionata.
        """
        selected_index = e.control.selected_index

        # Mappa il testo della tab (che ora è tradotto) alla funzione di aggiornamento
        # Usiamo le chiavi di localizzazione per un mapping robusto
        tab_key_map = {
            self.controller.loc.get("my_data"): self.tab_personale.update_view_data,
            self.controller.loc.get("budget"): self.tab_budget.update_view_data,
            self.controller.loc.get("personal_accounts"): self.tab_conti.update_view_data,
            self.controller.loc.get("shared_accounts"): self.tab_conti_condivisi.update_view_data,
            self.controller.loc.get("fixed_expenses"): self.tab_spese_fisse.update_view_data,
            self.controller.loc.get("loans"): self.tab_prestiti.update_view_data,
            self.controller.loc.get("properties"): self.tab_immobili.update_view_data,
            self.controller.loc.get("family"): self.tab_famiglia.update_view_data,
        }

        if selected_index < len(self.tabs_control.tabs):
            selected_tab_text = self.tabs_control.tabs[selected_index].text
            update_function = tab_key_map.get(selected_tab_text)
            if update_function:
                print(f"Tab '{selected_tab_text}' selezionata. Aggiornamento dati...")
                update_function()

    def update_tabs_list(self):
        """
        Aggiorna la lista di ft.Tab visibili in base al ruolo dell'utente.
        """
        loc = self.controller.loc
        ruolo = self.controller.get_user_role()
        tabs_list = []

        # Schede visibili a tutti
        tabs_list.append(ft.Tab(text=loc.get("my_data"), icon=ft.Icons.PERSON, content=self.tab_personale))
        tabs_list.append(ft.Tab(text=loc.get("budget"), icon=ft.Icons.PIE_CHART, content=self.tab_budget))
        tabs_list.append(
            ft.Tab(text=loc.get("personal_accounts"), icon=ft.Icons.ACCOUNT_BALANCE_WALLET, content=self.tab_conti))
        tabs_list.append(ft.Tab(text=loc.get("shared_accounts"), icon=ft.Icons.GROUP, content=self.tab_conti_condivisi))
        tabs_list.append(
            ft.Tab(text=loc.get("fixed_expenses"), icon=ft.Icons.CALENDAR_MONTH, content=self.tab_spese_fisse))
        tabs_list.append(ft.Tab(text=loc.get("loans"), icon=ft.Icons.CREDIT_CARD, content=self.tab_prestiti))
        tabs_list.append(ft.Tab(text=loc.get("properties"), icon=ft.Icons.HOME_WORK, content=self.tab_immobili))

        # Schede con visibilità basata sul ruolo
        if ruolo in ['admin', 'livello1', 'livello2']:
            tabs_list.append(ft.Tab(text=loc.get("family"), icon=ft.Icons.DIVERSITY_3, content=self.tab_famiglia))

        self.appbar_admin_button.visible = (ruolo == 'admin')
        self.tabs_control.tabs = tabs_list

        if self.tabs_control.selected_index >= len(self.tabs_control.tabs):
            self.tabs_control.selected_index = 0

        if self.tabs_control.page:
            self.tabs_control.update()

        if self.page.appbar:
            self.page.appbar.update()

    def update_all_tabs_data(self, is_initial_load=False):
        """
        Questo è il "callback" principale.
        Dice a OGNI scheda di ricaricare i propri dati dal DB.
        """
        print("DashboardView: Aggiornamento dati di tutte le schede...")

        # Prima ridisegna le etichette delle tab con la lingua corretta
        self.update_tabs_list()

        # Aggiorna il titolo principale dell'app
        self.appbar_title.value = self.controller.loc.get("app_title")

        self.tab_personale.update_view_data(is_initial_load)
        self.tab_famiglia.update_view_data(is_initial_load)
        self.tab_conti.update_view_data(is_initial_load)
        self.tab_conti_condivisi.update_view_data(is_initial_load)
        self.tab_spese_fisse.update_view_data(is_initial_load)
        self.tab_budget.update_view_data(is_initial_load)
        self.tab_prestiti.update_view_data(is_initial_load)
        self.tab_immobili.update_view_data(is_initial_load)
        self.tab_impostazioni.update_view_data(is_initial_load)

        if self.controller.get_user_role() == 'admin':
            self.tab_admin.update_all_admin_tabs_data(is_initial_load)

        if self.special_view_container.visible:
            self.hide_special_view()