import flet as ft
from tabs.tab_personale import PersonaleTab
from tabs.tab_conti import ContiTab
from tabs.tab_investimenti import InvestimentiTab
from tabs.tab_budget import BudgetTab
from tabs.tab_famiglia import FamigliaTab
from tabs.tab_divisore_pro import DivisoreProTab
from tabs.tab_spese_fisse import SpeseFisseTab
from tabs.tab_accantonamenti import AccantonamentiTab
from tabs.tab_accantonamenti import AccantonamentiTab
from tabs.tab_carte import TabCarte
from tabs.tab_contatti import ContattiTab
from tabs.tab_prestiti import PrestitiTab
from tabs.tab_immobili import ImmobiliTab
from tabs.tab_calcolatrice import CalcolatriceTab
from utils.logger import setup_logger
from utils.styles import AppColors

logger = setup_logger("WebDashboardView")

from tabs.tab_admin import AdminTab
from tabs.tab_impostazioni import ImpostazioniTab
from tabs.tab_info import InfoTab

class WebDashboardView:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc

        # Tabs available
        self.tab_personale = PersonaleTab(controller)
        self.tab_conti = ContiTab(controller)
        self.tab_investimenti = InvestimentiTab(controller)
        self.tab_budget = BudgetTab(controller)

        self.tab_famiglia = FamigliaTab(controller)
        self.tab_divisore_pro = DivisoreProTab(controller)
        self.tab_accantonamenti = AccantonamentiTab(controller)
        self.tab_carte = TabCarte(controller)
        self.tab_carte = TabCarte(controller)
        self.tab_contatti = ContattiTab(controller)
        self.tab_spese_fisse = SpeseFisseTab(controller)
        self.tab_prestiti = PrestitiTab(controller)
        self.tab_immobili = ImmobiliTab(controller)
        self.tab_calcolatrice = CalcolatriceTab(controller)
        self.tab_admin = AdminTab(controller)
        self.tab_impostazioni = ImpostazioniTab(controller)
        self.tab_info = InfoTab(controller)
        
        # Current selected index
        self.selected_index = 0
        
        # Main content area
        self.content_area = ft.Container(
            content=self.tab_personale,
            expand=True,
            padding=5
        )

        # Dynamic tabs list: (ViewInstance, Icon, Label)
        self.active_tabs = []
        
        # Drawer reference
        self.drawer = None

    def _build_drawer(self) -> ft.NavigationDrawer:
        """Costruisce il Drawer con tutte le voci di navigazione."""
        ruolo = self.controller.get_user_role()
        
        # Define available tabs: (View, Icon, Label)
        # Define available tabs: (View, Icon, Label)
        # Filtro visibilità
        from db.gestione_db import get_disabled_features
        id_famiglia = self.controller.get_family_id()
        disabled = get_disabled_features(id_famiglia) if id_famiglia else []

        possible_tabs = [
            (self.tab_personale, ft.Icons.HOME, "Home"),
        ]
        
        # Budget
        if "budget" not in disabled:
            possible_tabs.append((self.tab_budget, ft.Icons.PIE_CHART, "Budget"))
            
        # Conti
        possible_tabs.append((self.tab_conti, ft.Icons.ACCOUNT_BALANCE_WALLET, "Conti"))
        
        # Carte
        if "carte" not in disabled:
            possible_tabs.append((self.tab_carte, ft.Icons.CREDIT_CARD, "Carte"))
            
        # Spese Fisse
        if "spese_fisse" not in disabled:
            possible_tabs.append((self.tab_spese_fisse, ft.Icons.CALENDAR_MONTH, "Spese Fisse"))
            
        # Investimenti
        if "investimenti" not in disabled:
             possible_tabs.append((self.tab_investimenti, ft.Icons.TRENDING_UP, "Investimenti"))
        
        # Prestiti
        if "prestiti" not in disabled:
             possible_tabs.append((self.tab_prestiti, ft.Icons.MONEY_OFF, "Prestiti"))
        
        # Immobili
        if "immobili" not in disabled:
             possible_tabs.append((self.tab_immobili, ft.Icons.HOME_WORK, "Immobili"))
        
        # Risparmi
        if "accantonamenti" not in disabled:
             possible_tabs.append((self.tab_accantonamenti, ft.Icons.SAVINGS, "Risparmi"))
        
        # Famiglia
        if "famiglia" not in disabled:
             possible_tabs.append((self.tab_famiglia, ft.Icons.DIVERSITY_3, "Famiglia"))
        
        # Divisore
        if "divisore" not in disabled:
             possible_tabs.append((self.tab_divisore_pro, ft.Icons.CALCULATE, "Divisore"))
        
        # Contatti
        if "contatti" not in disabled:
             possible_tabs.append((self.tab_contatti, ft.Icons.CONTACT_PHONE, "Contatti"))
        
        
        # Add Calcolatrice (Solo ID 16)
        if str(self.controller.get_user_id()) == '16':
             possible_tabs.append((self.tab_calcolatrice, ft.Icons.CALCULATE_OUTLINED, "Calcolatrice"))
        
        # Add Admin if authorized
        if ruolo == 'admin':
             possible_tabs.append((self.tab_admin, ft.Icons.ADMIN_PANEL_SETTINGS, "Amministrazione"))
        
        # Add Info & Settings (Always)
        possible_tabs.append((self.tab_impostazioni, ft.Icons.SETTINGS, "Impostazioni"))
        possible_tabs.append((self.tab_info, ft.Icons.INFO_OUTLINE, "Info & Download"))

        self.active_tabs = possible_tabs
        
        # Build drawer destinations
        drawer_controls = [
            # Header con info utente
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=48, color=AppColors.PRIMARY),
                    ft.Text(
                        self.page.session.get("nome_visualizzato") or "Utente",
                        weight=ft.FontWeight.BOLD,
                        size=16
                    ),
                    # ft.Text(
                    #     f"ID: {self.controller.get_user_id() or 'N/A'}",
                    #     size=12,
                    #     color=AppColors.TEXT_SECONDARY
                    # ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                padding=20,
                bgcolor=AppColors.SURFACE_VARIANT,
                width=280
            ),
            ft.Divider(height=1),
        ]
        
        # Add navigation destinations
        for idx, (view, icon, label) in enumerate(possible_tabs):
            drawer_controls.append(
                ft.NavigationDrawerDestination(
                    icon=icon,
                    label=label,
                    selected_icon=icon
                )
            )
        
        # Divider before logout
        drawer_controls.append(ft.Divider(height=1))
        
        return ft.NavigationDrawer(
            controls=drawer_controls,
            selected_index=self.selected_index,
            on_change=self._on_drawer_change,
        )

    def build_view(self) -> ft.View:
        from app_controller import VERSION
        
        # Build Drawer
        self.drawer = self._build_drawer()
        
        # App Bar with hamburger menu
        app_bar = ft.AppBar(
            leading=ft.IconButton(
                icon=ft.Icons.MENU,
                on_click=self._open_drawer,
                tooltip="Menu"
            ),
            title=ft.Row(
                [
                    ft.Text("Budget Amico", weight=ft.FontWeight.BOLD, size=18),
                    ft.Container(
                        content=ft.Text(f"v{VERSION}", size=10, weight=ft.FontWeight.NORMAL),
                        padding=ft.padding.only(top=3, left=5),
                        opacity=0.6
                    )
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            center_title=False,
            bgcolor=ft.Colors.SURFACE,
            actions=[
                ft.IconButton(
                    ft.Icons.LOGOUT,
                    on_click=self.controller.logout,
                    tooltip="Logout"
                )
            ]
        )
        
        # Floating Action Button for "Add" Menu
        fab = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            tooltip=self.loc.get("add"),
            on_click=self._open_add_menu,
            bgcolor=ft.Colors.PRIMARY,
        )

        return ft.View(
            "/dashboard",
            controls=[self.content_area],
            appbar=app_bar,
            drawer=self.drawer,
            floating_action_button=fab,
            padding=0
        )

    def _open_drawer(self, e):
        """Apre il drawer."""
        self.page.open(self.drawer)

    def _on_drawer_change(self, e):
        """Gestisce la selezione di una voce dal drawer."""
        idx = e.control.selected_index
        logger.info(f"[WEB] Drawer nav changed to {idx}")
        
        self.selected_index = idx
        
        if 0 <= idx < len(self.active_tabs):
            selected_view = self.active_tabs[idx][0]
            self.content_area.content = selected_view
            
            if hasattr(selected_view, 'update_view_data'):
                selected_view.update_view_data()
            elif hasattr(selected_view, 'update_all_admin_tabs_data'):
                selected_view.update_all_admin_tabs_data()
        
        # Chiudi il drawer dopo la selezione
        self.page.close(self.drawer)
        self.page.update()

    def navigate_to_tab(self, tab_key: str):
        """
        Naviga a una tab specifica tramite chiave identificativa.
        Chiavi supportate: 'home', 'budget', 'conti', 'carte', 'spese_fisse', 
        'investimenti', 'prestiti', 'immobili', 'accantonamenti', 'famiglia', 'contatti', 'admin', 'impostazioni'.
        """
        # Mappa chiavi -> Viste
        key_map = {
            "home": self.tab_personale,
            "budget": self.tab_budget,
            "conti": self.tab_conti,
            "carte": self.tab_carte,
            "spese_fisse": self.tab_spese_fisse,
            "investimenti": self.tab_investimenti,
            "prestiti": self.tab_prestiti,
            "immobili": self.tab_immobili,
            "accantonamenti": self.tab_accantonamenti,
            "famiglia": self.tab_famiglia,
            "contatti": self.tab_contatti,
            "admin": self.tab_admin,
            "impostazioni": self.tab_impostazioni,
            "info": self.tab_info
        }
        
        target_view = key_map.get(tab_key.lower())
        if not target_view:
            logger.warning(f"[WEB] Navigate to tab: key '{tab_key}' not found.")
            return

        # Trova l'indice corretto basandosi sulla active_tabs corrente
        for i, (view, icon, label) in enumerate(self.active_tabs):
            if view == target_view:
                logger.info(f"[WEB] Navigating to tab {tab_key} (index {i})")
                self.selected_index = i
                self.content_area.content = view
                
                # Aggiorna il Drawer se presente
                if self.drawer:
                    self.drawer.selected_index = i
                
                if hasattr(view, 'update_view_data'):
                    view.update_view_data()
                elif hasattr(view, 'update_all_admin_tabs_data'):
                    view.update_all_admin_tabs_data()
                
                self.page.update()
                return
        
        logger.warning(f"[WEB] Navigate to tab: view for key '{tab_key}' not present in active tabs.")

    def _open_add_menu(self, e):
        """Apre un BottomSheet con le opzioni di aggiunta."""
        logger.info("[WEB] FAB '+' clicked: Opening add menu")
        loc = self.controller.loc
        
        # Filtro visibilità
        from db.gestione_db import get_disabled_features
        id_famiglia = self.controller.get_family_id()
        disabled = get_disabled_features(id_famiglia) if id_famiglia else []

        def go_to_action(action_callback):
            """Helper to close sheet and run action"""
            bs.open = False
            bs.update()
            if action_callback:
                action_callback()

        items = [
             ft.ListTile(
                title=ft.Text(loc.get("new_transaction", "Nuova Transazione")),
                leading=ft.Icon(ft.Icons.PAYMENT),
                on_click=lambda _: go_to_action(self.controller.open_new_transaction_dialog)
            ),
            ft.ListTile(
                title=ft.Text(loc.get("new_account", "Nuovo Conto")),
                leading=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET),
                on_click=lambda _: go_to_action(self.controller.open_new_account_dialog)
            ),
        ]
        
        if "carte" not in disabled:
             items.append(ft.ListTile(
                title=ft.Text(loc.get("new_card", "Nuova Carta")),
                leading=ft.Icon(ft.Icons.CREDIT_CARD),
                on_click=lambda _: go_to_action(self.controller.open_new_card_dialog)
            ))

        if "accantonamenti" not in disabled:
             items.append(ft.ListTile(
                title=ft.Text(loc.get("new_savings", "Nuovo Risparmio")),
                leading=ft.Icon(ft.Icons.SAVINGS),
                on_click=lambda _: go_to_action(self.controller.open_new_savings_dialog)
            ))
            
        if "spese_fisse" not in disabled:
             items.append(ft.ListTile(
                title=ft.Text(loc.get("new_fixed_expense", "Nuova Spesa Fissa")),
                leading=ft.Icon(ft.Icons.REPEAT),
                on_click=lambda _: go_to_action(self.controller.open_new_fixed_expense_dialog)
            ))

        if "prestiti" not in disabled:
             items.append(ft.ListTile(
                title=ft.Text(loc.get("new_loan", "Nuovo Prestito")),
                leading=ft.Icon(ft.Icons.MONEY_OFF),
                on_click=lambda _: go_to_action(self.controller.open_new_loan_dialog)
            ))

        if "immobili" not in disabled:
             items.append(ft.ListTile(
                title=ft.Text(loc.get("new_property", "Nuovo Immobile")),
                leading=ft.Icon(ft.Icons.HOME_WORK),
                on_click=lambda _: go_to_action(self.controller.open_new_property_dialog)
            ))

        if "contatti" not in disabled:
             items.append(ft.ListTile(
                title=ft.Text(loc.get("new_contact", "Nuovo Contatto")),
                leading=ft.Icon(ft.Icons.CONTACT_PHONE),
                on_click=lambda _: go_to_action(self.controller.open_new_contact_dialog)
            ))

        bs = ft.BottomSheet(
            ft.Container(
                ft.Column(items, tight=True),
                padding=20, 
                border_radius=ft.border_radius.only(top_left=20, top_right=20)
            ),
            open=True,
            on_dismiss=lambda e: logger.debug("Bottom sheet dismissed")
        )
        self.page.overlay.append(bs)
        self.page.update()

    def update_all_tabs_data(self, is_initial_load=False):
        """Called by controller to refresh data"""
        if 0 <= self.selected_index < len(self.active_tabs):
            selected_view = self.active_tabs[self.selected_index][0]
            if hasattr(selected_view, 'update_view_data'):
                selected_view.update_view_data(is_initial_load)
            elif hasattr(selected_view, 'update_all_admin_tabs_data'):
                selected_view.update_all_admin_tabs_data(is_initial_load)
    
    def update_sidebar(self):
        pass # No sidebar in web view
