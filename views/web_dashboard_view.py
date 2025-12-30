import flet as ft
from tabs.tab_personale import PersonaleTab
from tabs.tab_conti import ContiTab
from tabs.tab_investimenti import InvestimentiTab
from tabs.tab_budget import BudgetTab
from tabs.tab_famiglia import FamigliaTab
from utils.logger import setup_logger

logger = setup_logger("WebDashboardView")

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
        
        # We will use a simplified view index
        self.selected_index = 0
        
        # Main content area
        self.content_area = ft.Container(
            content=self.tab_personale,
            expand=True,
            padding=5
        )

    def build_view(self) -> ft.View:
        # App Bar
        app_bar = ft.AppBar(
            title=ft.Text("Budget Amico Web"),
            center_title=True,
            bgcolor=ft.Colors.SURFACE,
            actions=[
                ft.IconButton(ft.Icons.LOGOUT, on_click=self.controller.logout)
            ]
        )

        # Bottom Navigation Bar
        self.nav_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME, label="Home"),
                ft.NavigationBarDestination(icon=ft.Icons.ACCOUNT_BALANCE_WALLET, label="Conti"),
                ft.NavigationBarDestination(icon=ft.Icons.TRENDING_UP, label="Investimenti"),
                ft.NavigationBarDestination(icon=ft.Icons.PIE_CHART, label="Budget"),
                ft.NavigationBarDestination(icon=ft.Icons.PEOPLE, label="Famiglia"),
            ],
            on_change=self._on_nav_change,
            selected_index=0
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
            navigation_bar=self.nav_bar,
            floating_action_button=fab,
            # bgcolor=ft.Colors.BACKGROUND,
            padding=0 # Maximize space
        )

    def _on_nav_change(self, e):
        idx = e.control.selected_index
        logger.info(f"[WEB] Nav changed to {idx}")
        
        if idx == 0: # Home
            self.content_area.content = self.tab_personale
            self.tab_personale.update_view_data()
        elif idx == 1: # Conti
            self.content_area.content = self.tab_conti
            self.tab_conti.update_view_data()
        elif idx == 2: # Investimenti
            self.content_area.content = self.tab_investimenti
            self.tab_investimenti.update_view_data()
        elif idx == 3: # Budget
            self.content_area.content = self.tab_budget
            self.tab_budget.update_view_data()
        elif idx == 4: # Famiglia
            self.content_area.content = self.tab_famiglia
            self.tab_famiglia.update_view_data()

        self.page.update()

    def update_all_tabs_data(self, is_initial_load=False):
        """Called by controller to refresh data"""
        idx = self.nav_bar.selected_index
        # Refresh current visible tab
        if idx == 0:
            self.tab_personale.update_view_data(is_initial_load)
        elif idx == 1:
            self.tab_conti.update_view_data(is_initial_load)
        elif idx == 2:
            self.tab_investimenti.update_view_data(is_initial_load)
        elif idx == 3:
            self.tab_budget.update_view_data(is_initial_load)
        elif idx == 4:
            self.tab_famiglia.update_view_data(is_initial_load)
        
    def update_sidebar(self):
        pass # No sidebar in web view
