import flet as ft
from tabs.tab_personale import PersonaleTab
from tabs.tab_conti import ContiTab
from utils.logger import setup_logger

logger = setup_logger("WebDashboardView")

class WebDashboardView:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc

        # Tabs available in mobile view
        self.tab_personale = PersonaleTab(controller)
        self.tab_conti = ContiTab(controller)
        
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

        # Bottom Navigation Bar for Mobile Experience
        self.nav_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME, label="Home"),
                ft.NavigationBarDestination(icon=ft.Icons.ADD_CIRCLE, label="Aggiungi", ),
                ft.NavigationBarDestination(icon=ft.Icons.ACCOUNT_BALANCE_WALLET, label="Conti"),
            ],
            on_change=self._on_nav_change,
            selected_index=0
        )

        return ft.View(
            "/dashboard",
            controls=[self.content_area],
            appbar=app_bar,
            navigation_bar=self.nav_bar,
            # bgcolor=ft.Colors.BACKGROUND,
            padding=0 # Maximize space
        )

    def _on_nav_change(self, e):
        idx = e.control.selected_index
        logger.info(f"[WEB] Nav changed to {idx}")
        
        if idx == 0: # Home
            self.content_area.content = self.tab_personale
            self.tab_personale.update_view_data()
        elif idx == 1: # Add (Dialog)
            # Reset selection to previous to keep UI consistent or stay on Add? 
            # Better to open dialog and stay on current tab
            # But NavigationBar forces selection. Let's switch back to previous or stay.
            # Strategy: Open Dialog, then manually reset nav bar index?
            # Or just let it be a "tab" that opens a dialog.
            
            # Let's try opening the dialog and keeping the User on the current view (Home or Conti)
            # We need to know where we came from.
            # Simple hack: Always go back to Home (0) after closing?
            
            self.controller.transaction_dialog.apri_dialog_nuova_transazione()
            # Reset nav bar to 0 (Home) visually
            self.nav_bar.selected_index = 0
            self.page.update()
            return 
            
        elif idx == 2: # Conti
            self.content_area.content = self.tab_conti
            self.tab_conti.update_view_data()

        self.page.update()

    def update_all_tabs_data(self, is_initial_load=False):
        """Called by controller to refresh data"""
        # Refresh current visible tab
        if self.nav_bar.selected_index == 0:
            self.tab_personale.update_view_data(is_initial_load)
        elif self.nav_bar.selected_index == 2:
            self.tab_conti.update_view_data(is_initial_load)
        
    def update_sidebar(self):
        pass # No sidebar in web view
