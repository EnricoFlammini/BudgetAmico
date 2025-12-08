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
from tabs.tab_investimenti import InvestimentiTab


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
        self.tab_investimenti = InvestimentiTab(controller)

        # 2. Sidebar personalizzata (sostituisce NavigationRail)
        self.selected_index = 0
        self.sidebar_items = []  # Lista di voci della sidebar
        
        # Container per la sidebar scrollabile
        self.sidebar_listview = ft.ListView(
            spacing=0,
            padding=ft.padding.symmetric(vertical=10),
        )

        # 3. Area Contenuti Principale
        self.content_area = ft.Container(
            content=self.tab_personale, # Default view
            expand=True,
            padding=10
        )

        # 4. Memorizza i componenti dell'AppBar
        self.appbar_title = ft.Text()
        
        # Icona per lo stato della sincronizzazione
        self.sync_status_icon = ft.IconButton(
            icon=ft.Icons.CLOUD_DONE,
            tooltip="Stato Sincronizzazione Google Drive",
            visible=False
        )

    def _create_sidebar_item(self, icon, selected_icon, label, view_instance, index):
        """Crea un elemento della sidebar personalizzata."""
        is_selected = (index == self.selected_index)
        
        return ft.Container(
            content=ft.ListTile(
                leading=ft.Icon(
                    selected_icon if is_selected else icon,
                    color=ft.Colors.PRIMARY if is_selected else None
                ),
                title=ft.Text(
                    label,
                    weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL,
                    color=ft.Colors.PRIMARY if is_selected else None
                ),
                selected=is_selected,
                on_click=lambda e, idx=index, view=view_instance: self._sidebar_item_clicked(idx, view),
            ),
            bgcolor=ft.Colors.PRIMARY_CONTAINER if is_selected else None,
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=5),
        )

    def _sidebar_item_clicked(self, index, view_instance):
        """Gestisce il click su un elemento della sidebar."""
        # Mostra spinner durante il caricamento
        self.controller.show_loading("Caricamento...")
        
        try:
            self.selected_index = index
            self.content_area.content = view_instance
            
            # Aggiorna i dati della vista selezionata
            if hasattr(view_instance, 'update_view_data'):
                view_instance.update_view_data()
            elif hasattr(view_instance, 'update_all_admin_tabs_data'):
                view_instance.update_all_admin_tabs_data()
            
            # Ricostruisci la sidebar per aggiornare la selezione
            self.update_sidebar()
            self.page.update()
        finally:
            self.controller.hide_loading()

    def build_view(self) -> ft.View:
        """
        Costruisce e restituisce la vista del Dashboard con sidebar personalizzata.
        """
        loc = self.controller.loc
        self.appbar_title.value = loc.get("app_title")

        return ft.View(
            "/dashboard",
            [
                ft.Row(
                    [
                        # Sidebar personalizzata scrollabile
                        ft.Container(
                            content=self.sidebar_listview,
                            width=220,
                            bgcolor=ft.Colors.SURFACE,
                            padding=5,
                        ),
                        ft.VerticalDivider(width=1),
                        self.content_area
                    ],
                    expand=True
                )
            ],
            appbar=ft.AppBar(
                title=self.appbar_title,
                center_title=False,
                actions=[
                    ft.IconButton(
                        icon=ft.Icons.INFO_OUTLINE,
                        tooltip=loc.get("info"),
                        on_click=self.controller.open_info_dialog
                    ),
                    self.sync_status_icon,
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

    def update_sidebar(self):
        """
        Aggiorna la sidebar personalizzata in base al ruolo.
        """
        loc = self.controller.loc
        ruolo = self.controller.get_user_role()
        
        # Costruisci la lista di voci
        self.sidebar_items = []
        index = 0

        # 1. Nome utente (prima voce)
        utente = self.controller.page.session.get("utente_loggato")
        nome_utente = utente.get('nome', loc.get("my_data")) if utente else loc.get("my_data")
        self.sidebar_items.append({
            'icon': ft.Icons.PERSON_OUTLINE,
            'selected_icon': ft.Icons.PERSON,
            'label': nome_utente,
            'view': self.tab_personale,
            'index': index
        })
        index += 1
        
        # 2. Budget
        self.sidebar_items.append({
            'icon': ft.Icons.PIE_CHART_OUTLINE,
            'selected_icon': ft.Icons.PIE_CHART,
            'label': loc.get("budget"),
            'view': self.tab_budget,
            'index': index
        })
        index += 1

        # 3. Conti Personali
        self.sidebar_items.append({
            'icon': ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
            'selected_icon': ft.Icons.ACCOUNT_BALANCE_WALLET,
            'label': loc.get("personal_accounts"),
            'view': self.tab_conti,
            'index': index
        })
        index += 1

        # 4. Conti Condivisi
        self.sidebar_items.append({
            'icon': ft.Icons.GROUP_OUTLINED,
            'selected_icon': ft.Icons.GROUP,
            'label': loc.get("shared_accounts"),
            'view': self.tab_conti_condivisi,
            'index': index
        })
        index += 1

        # 5. Spese Fisse
        self.sidebar_items.append({
            'icon': ft.Icons.CALENDAR_MONTH_OUTLINED,
            'selected_icon': ft.Icons.CALENDAR_MONTH,
            'label': loc.get("fixed_expenses"),
            'view': self.tab_spese_fisse,
            'index': index
        })
        index += 1

        # 6. Investimenti
        self.sidebar_items.append({
            'icon': ft.Icons.TRENDING_UP_OUTLINED,
            'selected_icon': ft.Icons.TRENDING_UP,
            'label': loc.get("investments"),
            'view': self.tab_investimenti,
            'index': index
        })
        index += 1

        # 7. Prestiti
        self.sidebar_items.append({
            'icon': ft.Icons.CREDIT_CARD_OUTLINED,
            'selected_icon': ft.Icons.CREDIT_CARD,
            'label': loc.get("loans"),
            'view': self.tab_prestiti,
            'index': index
        })
        index += 1

        # 8. Immobili
        self.sidebar_items.append({
            'icon': ft.Icons.HOME_WORK_OUTLINED,
            'selected_icon': ft.Icons.HOME_WORK,
            'label': loc.get("properties"),
            'view': self.tab_immobili,
            'index': index
        })
        index += 1

        # 9. Famiglia (Solo se autorizzato)
        if ruolo in ['admin', 'livello1', 'livello2']:
            self.sidebar_items.append({
                'icon': ft.Icons.DIVERSITY_3_OUTLINED,
                'selected_icon': ft.Icons.DIVERSITY_3,
                'label': loc.get("family"),
                'view': self.tab_famiglia,
                'index': index
            })
            index += 1

        # 10. Admin (Solo Admin)
        if ruolo == 'admin':
            self.sidebar_items.append({
                'icon': ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
                'selected_icon': ft.Icons.ADMIN_PANEL_SETTINGS,
                'label': loc.get("admin_panel_title"),
                'view': self.tab_admin,
                'index': index
            })
            index += 1

        # 11. Impostazioni (Sempre visibile, in fondo)
        self.sidebar_items.append({
            'icon': ft.Icons.SETTINGS_OUTLINED,
            'selected_icon': ft.Icons.SETTINGS,
            'label': loc.get("settings"),
            'view': self.tab_impostazioni,
            'index': index
        })

        # Ricostruisci i controlli della ListView
        self.sidebar_listview.controls.clear()
        for item in self.sidebar_items:
            self.sidebar_listview.controls.append(
                self._create_sidebar_item(
                    item['icon'],
                    item['selected_icon'],
                    item['label'],
                    item['view'],
                    item['index']
                )
            )
        
        # Reset selezione se fuori range
        if self.selected_index >= len(self.sidebar_items):
            self.selected_index = 0
            
        if self.sidebar_listview.page:
            self.sidebar_listview.update()

    def update_all_tabs_data(self, is_initial_load=False):
        """
        Aggiorna i dati di tutte le viste e della sidebar.
        """
        print("DashboardView: Aggiornamento dati completo...")

        # Aggiorna la sidebar (lingue, ruoli)
        self.update_sidebar()

        # Aggiorna il titolo
        self.appbar_title.value = self.controller.loc.get("app_title")

        # Aggiorna i dati di TUTTE le schede (così sono pronte quando ci clicchi)
        # Nota: Potremmo ottimizzare aggiornando solo la visibile e le altre on-demand,
        # ma per ora manteniamo la logica "eager" per semplicità.
        self.tab_personale.update_view_data(is_initial_load)
        self.tab_famiglia.update_view_data(is_initial_load)
        self.tab_conti.update_view_data(is_initial_load)
        self.tab_conti_condivisi.update_view_data(is_initial_load)
        self.tab_spese_fisse.update_view_data(is_initial_load)
        self.tab_budget.update_view_data(is_initial_load)
        self.tab_investimenti.update_view_data(is_initial_load)
        self.tab_prestiti.update_view_data(is_initial_load)
        self.tab_immobili.update_view_data(is_initial_load)
        self.tab_impostazioni.update_view_data(is_initial_load)

        if self.controller.get_user_role() == 'admin':
            self.tab_admin.update_all_admin_tabs_data(is_initial_load)

        if self.page:
            self.page.update()