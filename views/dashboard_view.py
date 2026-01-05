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
from tabs.tab_carte import TabCarte
from utils.logger import setup_logger
from utils.cache_manager import cache_manager

logger = setup_logger("DashboardView")


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
        self.tab_carte = TabCarte(controller)

        # 2. Sidebar personalizzata (sostituisce NavigationRail)
        self.selected_index = 0
        self.sidebar_items = []  # Lista di voci della sidebar
        self.is_sidebar_extended = False # Default collapsed

        # Container per la sidebar scrollabile
        self.sidebar_listview = ft.ListView(
            spacing=0,
            padding=ft.padding.symmetric(vertical=10),
        )
        
        # Container wrapper per la sidebar (riferimento per cambiarne la width)
        self.sidebar_container = None

        # 3. Area Contenuti Principale
        self.content_area = ft.Container(
            content=self.tab_personale, # Default view
            expand=True,
            padding=10
        )
        
        # 4. Banner per notifiche di aggiornamento
        self.update_banner = None
        self.update_banner_container = ft.Container(visible=False)

        # 4. Memorizza i componenti dell'AppBar
        self.appbar_title = ft.Text()
        
        # Icona per lo stato della sincronizzazione
        self.sync_status_icon = ft.IconButton(
            icon=ft.Icons.CLOUD_DONE,
            tooltip="Stato Sincronizzazione Google Drive",
            visible=False
        )

        self.btn_export = ft.IconButton(
            icon=ft.Icons.DOWNLOAD,
            tooltip="Esporta Dati",
            on_click=lambda _: self.page.go("/export"),
            visible=True # Default visible, managed by role
        )

    def reset_state(self):
        """Resetta lo stato della vista (es. selezione sidebar) ai valori iniziali."""
        self.selected_index = 0
        self.content_area.content = self.tab_personale
        logger.debug("DashboardView state reset to initial (Index 0).")

    def _safe_update(self, control):
        """Esegue l'update di un controllo gestendo eventuali errori di loop chiuso."""
        if not self.page: return
        try:
            control.update()
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.debug("Tentativo di update a loop chiuso ignorato.")
            else:
                logger.error(f"Errore update UI: {e}")
        except Exception as e:
            logger.debug(f"Update fallito (app in chiusura?): {e}")

    def _toggle_sidebar(self, e):
        """Espande o riduce la sidebar."""
        self.is_sidebar_extended = not self.is_sidebar_extended
        if self.sidebar_container:
            self.sidebar_container.width = 220 if self.is_sidebar_extended else 65
            self.update_sidebar() # Ricostruisci items per mostrare/nascondere testo
            self.sidebar_container.update()
            
    def _create_sidebar_item(self, icon, selected_icon, label, view_instance, index):
        """Crea un elemento della sidebar personalizzata."""
        is_selected = (index == self.selected_index)
        
        # Se ridotta, mostra solo icona e usa tooltip
        content = ft.ListTile(
            leading=ft.Icon(
                selected_icon if is_selected else icon,
                color=ft.Colors.PRIMARY if is_selected else None,
                tooltip=label if not self.is_sidebar_extended else None
            ),
            title=ft.Text(
                label,
                weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL,
                color=ft.Colors.PRIMARY if is_selected else None,
                no_wrap=True
            ) if self.is_sidebar_extended else ft.Container(),
            selected=is_selected,
            on_click=lambda e, idx=index, view=view_instance: self._sidebar_item_clicked(idx, view),
            content_padding=ft.padding.only(left=10) if not self.is_sidebar_extended else None,
        )

        return ft.Container(
            content=content,
            bgcolor=ft.Colors.PRIMARY_CONTAINER if is_selected else None,
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=5),
        )

    def _sidebar_item_clicked(self, index, view_instance):
        """Gestisce il click su un elemento della sidebar."""
        # Get the label for logging
        label = self.sidebar_items[index]['label'] if index < len(self.sidebar_items) else f"index_{index}"
        logger.info(f"[NAV] Tab clicked: '{label}' (index={index})")
        
        self.selected_index = index
        self.content_area.content = view_instance
        
        # Aggiorna i dati della vista selezionata
        if hasattr(view_instance, 'update_view_data'):
            view_instance.update_view_data()
        elif hasattr(view_instance, 'update_all_admin_tabs_data'):
            view_instance.update_all_admin_tabs_data()
        elif hasattr(view_instance, 'load_cards'): # For TabCarte
            view_instance.load_cards()
        
        # Ricostruisci la sidebar per aggiornare la selezione
        self.update_sidebar()
        self._safe_update(self.page)

    def build_view(self) -> ft.View:
        """
        Costruisce e restituisce la vista del Dashboard con sidebar personalizzata.
        """
        loc = self.controller.loc
        self.appbar_title.value = loc.get("app_title")

        # Inizializza il container della sidebar
        self.sidebar_container = ft.Container(
            content=self.sidebar_listview,
            width=65, # Default width (collapsed)
            bgcolor=ft.Colors.SURFACE,
            padding=5,
            animate=ft.Animation(200, "easeOut"),
        )

        # Area contenuto con banner opzionale sopra
        main_content = ft.Column([
            self.update_banner_container,  # Banner aggiornamenti (nascosto di default)
            ft.Row(
                [
                    # Sidebar personalizzata scrollabile
                    self.sidebar_container,
                    ft.VerticalDivider(width=1),
                    self.content_area
                ],
                expand=True
            )
        ], expand=True, spacing=0)

        return ft.View(
            "/dashboard",
            [main_content],
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    icon=ft.Icons.MENU,
                    tooltip="Menu",
                    on_click=self._toggle_sidebar
                ),
                title=self.appbar_title,
                center_title=False,
                actions=[
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip=loc.get("refresh_data", "Aggiorna dati"),
                        on_click=self._refresh_all_data
                    ),
                    ft.IconButton(
                        icon=ft.Icons.INFO_OUTLINE,
                        tooltip=loc.get("info"),
                        on_click=self.controller.open_info_dialog
                    ),
                    self.sync_status_icon,
                    self.btn_export,
                    ft.IconButton(
                        icon=ft.Icons.LOGOUT,
                        tooltip=loc.get("logout"),
                        on_click=self.controller.logout
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        tooltip="Chiudi Applicazione",
                        on_click=self._close_app
                    ),
                ]
            ),
            floating_action_button=ft.FloatingActionButton(
                icon=ft.Icons.ADD,
                tooltip=self.controller.loc.get("add"),
                on_click=self._open_add_menu
            )
        )
    
    def set_update_banner(self, banner: ft.Container):
        """Mostra un banner di aggiornamento nella dashboard."""
        self.update_banner = banner
        self.update_banner_container.content = banner
        self.update_banner_container.visible = True
        if self.page:
            self._safe_update(self.page)

    def _close_app(self, e):
        """Chiude l'applicazione."""
        logger.info("===== CHIUSURA APPLICAZIONE =====")
        self.page.window.close()

    def _open_add_menu(self, e):
        """Apre un BottomSheet con le opzioni di aggiunta."""
        logger.info("[ACTION] FAB '+' clicked: Opening add menu")
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
        self._safe_update(self.page)

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
        
        # 2. Budget (Livello 2+)
        if ruolo in ['admin', 'livello1', 'livello2']:
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
        
        # 3b. Carte (Cards)
        self.sidebar_items.append({
            'icon': ft.Icons.CREDIT_CARD_OUTLINED,
            'selected_icon': ft.Icons.CREDIT_CARD,
            'label': "Carte", # Localization needed ideally
            'view': self.tab_carte,
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

        # 6. Investimenti (Livello 2+)
        if ruolo in ['admin', 'livello1', 'livello2']:
            self.sidebar_items.append({
                'icon': ft.Icons.TRENDING_UP_OUTLINED,
                'selected_icon': ft.Icons.TRENDING_UP,
                'label': loc.get("investments"),
                'view': self.tab_investimenti,
                'index': index
            })
            index += 1

        # 7. Prestiti (Livello 2+)
        if ruolo in ['admin', 'livello1', 'livello2']:
            self.sidebar_items.append({
                'icon': ft.Icons.MONEY_OFF_OUTLINED,
                'selected_icon': ft.Icons.MONEY_OFF,
                'label': loc.get("loans"),
                'view': self.tab_prestiti,
                'index': index
            })
            index += 1

        # 8. Immobili (Livello 2+)
        if ruolo in ['admin', 'livello1', 'livello2']:
            self.sidebar_items.append({
                'icon': ft.Icons.HOME_WORK_OUTLINED,
                'selected_icon': ft.Icons.HOME_WORK,
                'label': loc.get("properties"),
                'view': self.tab_immobili,
                'index': index
            })
            index += 1

        # 9. Famiglia (Livello 2+)
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
            self._safe_update(self.sidebar_listview)

    def _refresh_all_data(self, e=None):
        """
        Forza l'aggiornamento di tutti i dati (pulsante refresh nell'AppBar).
        Invalida la cache e ricarica tutto dal database.
        """
        logger.info("[ACTION] Refresh button clicked: forcing data reload")
        self.controller.show_loading("Aggiornamento dati...")
        
        try:
            # Invalida la cache per questa famiglia
            id_famiglia = self.controller.get_family_id()
            if id_famiglia:
                cache_manager.invalidate_all(id_famiglia)
            
            # Ricarica tutti i dati
            self.update_all_tabs_data(is_initial_load=False)
            self.controller.show_snack_bar("Dati aggiornati!", success=True)
        finally:
            self.controller.hide_loading()

    def update_all_tabs_data(self, is_initial_load=False):
        """
        Aggiorna i dati di tutte le viste e della sidebar.
        
        Se is_initial_load=True, carica i dati dalla cache per UI immediata.
        I dati verranno aggiornati dal DB quando l'utente accede alle singole tabs.
        """
        logger.debug(f"Updating all tabs data... (is_initial_load={is_initial_load})")

        # Aggiorna la sidebar (lingue, ruoli)
        self.update_sidebar()

        # Aggiorna il titolo
        self.appbar_title.value = self.controller.loc.get("app_title")

        # Pattern: Stale-While-Revalidate
        # - All'avvio: carica solo la tab corrente (tab_personale)
        # - Le altre tabs si aggiorneranno quando l'utente ci clicca
        if is_initial_load:
            # Carica solo la tab visibile inizialmente per avvio rapido
            logger.debug("Initial load: loading only visible tab (PersonaleTab)")
            self.tab_personale.update_view_data(is_initial_load)
        else:
            # Aggiornamento completo (richiesto esplicitamente)
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
            self.tab_carte.load_cards() # Refresh cards too

            if self.controller.get_user_role() == 'admin':
                self.tab_admin.update_all_admin_tabs_data(is_initial_load)
            
            # Manage Export Button Visibility
            ruolo = self.controller.get_user_role()
            self.btn_export.visible = (ruolo != 'livello3')
            self.btn_export.update()

        if self.page:
            self._safe_update(self.page)