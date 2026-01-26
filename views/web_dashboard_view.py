import flet as ft
from tabs.tab_personale import PersonaleTab
from tabs.tab_conti import ContiTab
from tabs.tab_investimenti import InvestimentiTab
from tabs.tab_budget import BudgetTab
from tabs.tab_famiglia import FamigliaTab
from tabs.tab_divisore_pro import DivisoreProTab
from tabs.tab_spese_fisse import SpeseFisseTab
from tabs.tab_accantonamenti import AccantonamentiTab
from tabs.tab_carte import TabCarte
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
        self.tab_spese_fisse = SpeseFisseTab(controller)
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
        possible_tabs = [
            (self.tab_personale, ft.Icons.HOME, "Home"),
            (self.tab_budget, ft.Icons.PIE_CHART, "Budget"),
            (self.tab_conti, ft.Icons.ACCOUNT_BALANCE_WALLET, "Conti"),
            (self.tab_carte, ft.Icons.CREDIT_CARD, "Carte"),
            (self.tab_accantonamenti, ft.Icons.SAVINGS, "Risparmi"),
            (self.tab_spese_fisse, ft.Icons.CALENDAR_MONTH, "Spese Fisse"),
            (self.tab_famiglia, ft.Icons.DIVERSITY_3, "Famiglia"),
            (self.tab_investimenti, ft.Icons.TRENDING_UP, "Investimenti"),
            (self.tab_divisore_pro, ft.Icons.CALCULATE, "Divisore"),
        ]
        
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
                    ft.Text(
                        f"ID: {self.controller.get_user_id() or 'N/A'}",
                        size=12,
                        color=AppColors.TEXT_SECONDARY
                    ),
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
        
        # Floating Action Button for "Add Transaction"
        fab = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            text="Aggiungi",
            on_click=lambda _: self.controller.transaction_dialog.apri_dialog_nuova_transazione(),
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
