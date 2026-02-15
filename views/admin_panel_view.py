"""
Admin Panel View - Pannello di amministrazione di sistema per BudgetAmico Web.

Questo modulo fornisce un'interfaccia web per gli amministratori di sistema
per visualizzare i log, gestire utenti e famiglie, e configurare impostazioni globali.
"""

import flet as ft
import os
from datetime import datetime, timedelta
from typing import Optional
from utils.db_logger import get_logs, get_log_stats, get_distinct_components, cleanup_old_logs
from utils.db_log_handler import get_all_components, update_logger_config, invalidate_config_cache
from utils.styles import AppColors
from db.gestione_db import ottieni_versione_db


def verifica_admin_sistema(username: str, password: str) -> bool:
    """
    Verifica le credenziali dell'admin di sistema.
    Le credenziali sono definite tramite variabili d'ambiente.
    """
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    print(f"[DEBUG] Login Check - EnvUser: {admin_username}, EnvPassSet: {bool(admin_password)}")
    print(f"[DEBUG] Input - User: {username}, PassMatch: {password == admin_password}")

    if not admin_password:
        print("[ADMIN] ADMIN_PASSWORD non configurata in .env")
        return False
    
    return username == admin_username and password == admin_password


# Whitelist delle tabelle da mostrare nelle statistiche
PROGRAM_TABLES = [
    "appartenenza_famiglia", "risorsa", "budget", "budget_storico", "carte", 
    "categorie", "condivisionecontatto", "config_logger", "configurazioni", 
    "contatti", "conti", "conticondivisi", "famiglie", "immobili", "infodb", 
    "inviti", "log_sistema", "obiettivi_risparmio", "partecipazionecontocondiviso", 
    "pianoammortamento", "prestiti", "quoteimmobili", "quoteprestiti", 
    "salvadanai", "sottocategorie", "spesefisse", "storico_asset", 
    "storicoassetglobale", "storicomassimalicarte", "storicopagamentirate", 
    "transazioni", "transazionicondivise", "utenti"
]

class AdminPanelView:
    """Vista del pannello di amministrazione di sistema."""
    
    def __init__(self, page: ft.Page, on_logout):
        self.page = page
        self.on_logout = on_logout
        
        # --- LOGS VARIABLES ---
        self.current_filter_level = None
        self.current_filter_component = None
        self.current_page = 0
        self.logs_per_page = 50
        
        # --- TAB CONTROLLER ---
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[],  # Will be populated in build()
            expand=True,
        )

        # --- UI INITIALIZATION ---
        self._init_logs_tab_ui()
        self._init_users_tab_ui()
        self._init_families_tab_ui()
        self._init_config_tab_ui()
        self._init_db_stats_tab_ui()
        self._init_fop_tab_ui()
        self._init_access_stats_ui()
        self._init_sorting_tab_ui()
        self._init_version_tab_ui()

    def _sort_datatable(self, e, table: ft.DataTable, data_list: list, update_method):
        """Helper generico per ordinare le tabelle."""
        # Se clicco sulla stessa colonna, inverto l'ordine
        if table.sort_column_index == e.column_index:
            table.sort_ascending = not table.sort_ascending
        else:
            table.sort_column_index = e.column_index
            table.sort_ascending = True

        update_method()
        self.page.update()

    def build_view(self) -> ft.View:
        """Costruisce la UI della pagina."""
        # Popola il dropdown componenti per i log
        self._load_components()
        
        # Carica dati iniziali per le tab
        self._load_logs()
        self._load_stats()
        # Utenti e famiglie verranno caricati quando richiesto (o refresh per semplicità caricare tutto init)
        self._load_users()
        self._load_families()
        self._load_config()
        self._load_db_stats()
        self._load_fop_matrix()
        self._load_version_info()
        self._load_sorting_data()

        # Definisci le tabs
        self.tabs.tabs = [
            ft.Tab(
                text="Log Sistema",
                icon=ft.Icons.MONITOR_HEART,
                content=self._build_logs_tab_content()
            ),
            ft.Tab(
                text="Utenti",
                icon=ft.Icons.PEOPLE,
                content=self._build_users_tab_content()
            ),
            ft.Tab(
                text="Famiglie",
                icon=ft.Icons.FAMILY_RESTROOM,
                content=self._build_families_tab_content()
            ),
            ft.Tab(
                text="DB Stats",
                icon=ft.Icons.STORAGE,
                content=self._build_db_stats_tab_content()
            ),
            ft.Tab(
                text="Koyeb Status",
                icon=ft.Icons.CLOUD_CIRCLE,
                content=self._build_koyeb_tab_content()
            ),
            ft.Tab(
                text="Configurazione",
                icon=ft.Icons.SETTINGS,
                content=self._build_config_tab_content()
            ),
            ft.Tab(
                text="Gestione FOP",
                icon=ft.Icons.LIST_ALT,
                content=self._build_fop_tab_content()
            ),
            ft.Tab(
                text="Ordinamento",
                icon=ft.Icons.SORT,
                content=self._build_sorting_tab_content()
            ),
            ft.Tab(
                text="Versione",
                icon=ft.Icons.INFO_OUTLINE,
                content=self._build_version_tab_content()
            ),
        ]

        app_bar = ft.AppBar(
            title=ft.Text("🔧 Admin Panel - Budget Amico", color=ft.Colors.WHITE),
            center_title=True,
            bgcolor=ft.Colors.BLUE_GREY_900,
            actions=[
                ft.IconButton(
                    icon=ft.Icons.LOGOUT, 
                    tooltip="Logout",
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda e: self.on_logout()
                )
            ],
            color=ft.Colors.WHITE
        )



        return ft.View(
            "/admin",
            [
                app_bar,
                self.tabs
            ],
            scroll=ft.ScrollMode.HIDDEN # Tabs handles scrolling internally inside contents if needed
        )

    # =========================================================================
    # --- LOGS TAB LOGIC ---
    # =========================================================================
    def _init_logs_tab_ui(self):
        # Table
        self.logs_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Timestamp", size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Livello", size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Componente", size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Utente", size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Famiglia", size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Messaggio", size=12, weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=8,
            horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_200),
            heading_row_color=ft.Colors.BLUE_GREY_100,
            show_checkbox_column=False,
        )
        self.stats_text = ft.Text("Caricamento statistiche...")
        self.pagination_text = ft.Text("Pagina 1")
        
        # Filters
        self.level_dropdown = ft.Dropdown(
            label="Livello", width=150,
            options=[
                ft.dropdown.Option("", "Tutti"), ft.dropdown.Option("DEBUG", "DEBUG"),
                ft.dropdown.Option("INFO", "INFO"), ft.dropdown.Option("WARNING", "WARNING"),
                ft.dropdown.Option("ERROR", "ERROR"), ft.dropdown.Option("CRITICAL", "CRITICAL"),
            ],
            value="", on_change=self._on_filter_change
        )
        self.component_dropdown = ft.Dropdown(
            label="Componente", width=200,
            options=[ft.dropdown.Option("", "Tutti")],
            value="", on_change=self._on_filter_change
        )
        
        # Config Section (Chips)
        self.config_expanded = False
        self.config_content = ft.Container(visible=False)
        self.expand_icon = ft.IconButton(
            icon=ft.Icons.EXPAND_MORE, tooltip="Espandi/Comprimi",
            on_click=self._toggle_config_section, icon_size=18,
        )

    def _build_logs_tab_content(self):
        return ft.Container(
            content=ft.Column([
                # Filters & Config Row
                ft.Row([
                    self.level_dropdown,
                    self.component_dropdown,
                    ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Aggiorna", on_click=self._on_refresh),
                    ft.IconButton(icon=ft.Icons.DELETE_SWEEP, tooltip="Pulisci log vecchi (>30gg)",
                                  icon_color=ft.Colors.RED_400, on_click=self._on_cleanup_logs),
                ], alignment=ft.MainAxisAlignment.START),
                
                # Config Logger Section
                self._build_logger_config_section(),
                
                # Stats
                ft.Container(
                    content=self.stats_text,
                    padding=10, bgcolor=ft.Colors.BLUE_50, border_radius=5,
                ),
                
                # Table Container
                ft.Container(
                    content=self.logs_table,
                    expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8,
                ),
                
                # Pagination
                ft.Row([
                    ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=self._on_prev_page),
                    self.pagination_text,
                    ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=self._on_next_page),
                ], alignment=ft.MainAxisAlignment.CENTER),
                
            ], expand=True),
            padding=20, expand=True,
        )

    def _build_logger_config_section(self) -> ft.Container:
        components = get_all_components()
        chips = []
        for comp in components:
            chip = ft.Chip(
                label=ft.Text(comp['componente'], size=11),
                selected=comp['abilitato'],
                on_select=lambda e, c=comp['componente']: self._toggle_logger(c, e.control.selected),
                bgcolor=ft.Colors.GREY_200, selected_color=ft.Colors.GREEN_100,
            )
            chips.append(chip)
        
        self.config_content.content = ft.Column([
            ft.Text("Seleziona i componenti da monitorare:", size=11, color=ft.Colors.GREY_600),
            ft.Row(chips, wrap=True, spacing=5, run_spacing=5),
        ])
        self.config_content.padding = ft.padding.only(top=10)
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.SETTINGS, color=ft.Colors.BLUE_400, size=18),
                    ft.Text("Configurazione Logger", weight=ft.FontWeight.BOLD, size=14),
                    self.expand_icon,
                ], alignment=ft.MainAxisAlignment.START),
                self.config_content,
            ]),
            padding=10, bgcolor=ft.Colors.AMBER_50, border_radius=8, border=ft.border.all(1, ft.Colors.AMBER_200),
        )

    def _toggle_config_section(self, e):
        self.config_expanded = not self.config_expanded
        self.config_content.visible = self.config_expanded
        self.expand_icon.icon = ft.Icons.EXPAND_LESS if self.config_expanded else ft.Icons.EXPAND_MORE
        self.page.update()

    def _toggle_logger(self, componente: str, abilitato: bool):
        if update_logger_config(componente, abilitato):
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Logger '{componente}' {'abilitato' if abilitato else 'disabilitato'}"),
                bgcolor=ft.Colors.GREEN_400 if abilitato else ft.Colors.GREY_400
            )
            invalidate_config_cache()
            self._build_logger_config_section()
            self.page.update()

    def _get_level_badge(self, level: str) -> ft.Container:
        colors = {
            "DEBUG": (ft.Colors.GREY_400, ft.Colors.BLACK),
            "INFO": (ft.Colors.BLUE_400, ft.Colors.WHITE),
            "WARNING": (ft.Colors.ORANGE_400, ft.Colors.WHITE),
            "ERROR": (ft.Colors.RED_400, ft.Colors.WHITE),
            "CRITICAL": (ft.Colors.RED_900, ft.Colors.WHITE),
        }
        bg, fg = colors.get(level, (ft.Colors.GREY, ft.Colors.BLACK))
        return ft.Container(
            content=ft.Text(level, size=10, color=fg, weight=ft.FontWeight.BOLD),
            bgcolor=bg, padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=4,
        )

    def _load_components(self):
        components = get_distinct_components()
        self.component_dropdown.options = [ft.dropdown.Option("", "Tutti")]
        for comp in components:
            self.component_dropdown.options.append(ft.dropdown.Option(comp, comp))

    def _load_logs(self):
        level_val = self.level_dropdown.value
        level = None if not level_val or level_val == "Tutti" else level_val
        comp_val = self.component_dropdown.value
        component = None if not comp_val or comp_val == "Tutti" else comp_val
        
        logs = get_logs(
            livello=level, componente=component,
            limit=self.logs_per_page, offset=self.current_page * self.logs_per_page
        )
        
        new_rows = []
        for log in logs:
            timestamp = log.get("timestamp")
            if timestamp:
                ts_str = timestamp[:19] if isinstance(timestamp, str) else timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                ts_str = "-"
            
            messaggio = log.get("messaggio", "")
            if len(messaggio) > 100: messaggio = messaggio[:100] + "..."
            
            new_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(ts_str, size=11)),
                        ft.DataCell(self._get_level_badge(log.get("livello", "INFO"))),
                        ft.DataCell(ft.Text(log.get("componente", "-"), size=11)),
                        ft.DataCell(ft.Text(str(log.get("id_utente")) if log.get("id_utente") else "-", size=11)),
                        ft.DataCell(ft.Text(str(log.get("id_famiglia")) if log.get("id_famiglia") else "-", size=11)),
                        ft.DataCell(ft.Text(messaggio, size=11)),
                    ],
                    on_select_changed=lambda e, l=log: self._show_log_details(l)
                )
            )
        
        self.logs_table.rows = new_rows
        self.pagination_text.value = f"Pagina {self.current_page + 1}"

    def _load_stats(self):
        stats = get_log_stats()
        if stats:
            counts = stats.get("count_per_livello", {})
            total = stats.get("totale_log", 0)
            stats_parts = [f"Totale: {total}"]
            for level in ["ERROR", "WARNING", "INFO"]:
                if level in counts: stats_parts.append(f"{level}: {counts[level]}")
            self.stats_text.value = " | ".join(stats_parts)
        else:
            self.stats_text.value = "Nessuna statistica disponibile"

    def _on_filter_change(self, e):
        self.current_page = 0
        self._load_logs()
        self.page.update()

    def _on_prev_page(self, e):
        if self.current_page > 0:
            self.current_page -= 1
            self._load_logs()
            self.page.update()

    def _on_next_page(self, e):
        self.current_page += 1
        self._load_logs()
        self.page.update()

    def _on_refresh(self, e):
        self._load_logs()
        self._load_stats()
        self._load_users()
        self._load_families()
        self.page.update()

    def _on_cleanup_logs(self, e):
        deleted = cleanup_old_logs(days=30)
        self._load_logs()
        self._load_stats()
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Eliminati {deleted} log più vecchi di 30 giorni"),
            bgcolor=ft.Colors.GREEN_400
        )
        self.page.snack_bar.open = True
        self.page.update()

    def _show_log_details(self, log: dict):
        details = log.get("dettagli", {})
        details_text = ""
        if details:
            if isinstance(details, dict):
                for k, v in details.items(): details_text += f"{k}: {v}\n"
            else:
                details_text = str(details)
        else:
            details_text = "Nessun dettaglio disponibile"
        
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Log #{log.get('id_log', 'N/A')}", weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.Text(f"Timestamp: {log.get('timestamp')}", size=12),
                ft.Text(f"Livello: {log.get('livello')}", size=12),
                ft.Text(f"Componente: {log.get('componente')}", size=12),
                ft.Text(f"Famiglia: {log.get('id_famiglia', '-')}", size=12),
                ft.Text(f"Utente: {log.get('id_utente', '-')}", size=12),
                ft.Divider(),
                ft.Text("Messaggio:", weight=ft.FontWeight.BOLD, size=12),
                ft.Text(log.get("messaggio", "-"), size=11),
                ft.Divider(),
                ft.Text("Dettagli:", weight=ft.FontWeight.BOLD, size=12),
                ft.Container(
                    content=ft.Text(details_text, font_family="monospace", size=10),
                    bgcolor=ft.Colors.GREY_100, padding=5, border_radius=4
                )
            ], scroll=ft.ScrollMode.AUTO, height=400, width=600),
            actions=[ft.TextButton("Chiudi", on_click=lambda e: self.page.close(dlg))],
        )
        self.page.open(dlg)

    # =========================================================================
    # --- USERS TAB LOGIC ---
    # =========================================================================
    def _init_users_tab_ui(self):
        self.users_search = ft.TextField(
            label="Cerca Utente...", 
            prefix_icon=ft.Icons.SEARCH,
            width=300,
            on_change=lambda e: self._load_users(use_cache=True)
        )

        self.users_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Sospeso", weight=ft.FontWeight.BOLD), on_sort=self._on_users_sort),
                ft.DataColumn(ft.Text("Algo", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Username", weight=ft.FontWeight.BOLD), on_sort=self._on_users_sort),
                ft.DataColumn(ft.Text("Cod. Utente", weight=ft.FontWeight.BOLD), on_sort=self._on_users_sort),
                ft.DataColumn(ft.Text("Cod. Famiglia", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Email", weight=ft.FontWeight.BOLD), on_sort=self._on_users_sort),
                ft.DataColumn(ft.Text("Nome", weight=ft.FontWeight.BOLD), on_sort=self._on_users_sort),
                ft.DataColumn(ft.Text("Azioni", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            heading_row_color=ft.Colors.BLUE_GREY_50,
            sort_column_index=0,
            sort_ascending=True,
        )
        self._cached_users = []

    def _init_access_stats_ui(self):
        self.stats_attivi_ora = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN)
        self.stats_24h = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE)
        self.stats_48h = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY)
        self.stats_72h = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER)
        self.stats_7d  = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO)
        self.stats_30d = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE)
        self.stats_1y  = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.DEEP_ORANGE)
        self.stats_all = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BROWN)
        
        # Inizializza i container delle card
        self.card_attivi_ora = self._stat_card("Attivi Ora", self.stats_attivi_ora, ft.Icons.WEB_OUTLINED)
        self.card_24h = self._stat_card("24 Ore", self.stats_24h, ft.Icons.HISTORY)
        self.card_48h = self._stat_card("48 Ore", self.stats_48h, ft.Icons.HISTORY)
        self.card_72h = self._stat_card("72 Ore", self.stats_72h, ft.Icons.HISTORY)
        self.card_7d  = self._stat_card("Settimana", self.stats_7d, ft.Icons.CALENDAR_MONTH)
        self.card_30d = self._stat_card("Mese", self.stats_30d, ft.Icons.CALENDAR_MONTH)
        self.card_1y  = self._stat_card("Anno", self.stats_1y, ft.Icons.CALENDAR_MONTH)
        self.card_all = self._stat_card("Totale", self.stats_all, ft.Icons.ALL_INCLUSIVE)

    def _stat_card(self, label, control, icon, tooltip=None):
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(icon, size=16), ft.Text(label, size=12, weight=ft.FontWeight.W_500)], spacing=5),
                control
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=ft.Colors.BLUE_GREY_50,
            padding=10,
            border_radius=8,
            width=140,
            tooltip=tooltip
        )

    def _build_access_stats_row(self):
        return ft.Row([
            self.card_attivi_ora,
            self.card_24h,
            self.card_48h,
            self.card_72h,
            self.card_7d,
            self.card_30d,
            self.card_1y,
            self.card_all,
        ], wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.START)


    def _build_users_tab_content(self):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Gestione Utenti", size=20, weight=ft.FontWeight.BOLD),
                    ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Ricarica Lista", on_click=lambda e: self._load_users_refresh())
                ]),
                self._build_access_stats_row(),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.Row([self.users_search]),
                ft.Container(content=self.users_table, expand=True, border=ft.border.all(1, ft.Colors.GREY_200), border_radius=8)
            ]),
            padding=20, expand=True
        )

    def _load_users(self, use_cache=False):
        # Lazy import to avoid circular dependency
        from db.gestione_db import get_all_users, ottieni_statistiche_accessi
        
        if not use_cache or not self._cached_users:
            self._cached_users = get_all_users()
            
            # Carica anche le statistiche degli accessi
            stats = ottieni_statistiche_accessi()
            self.stats_attivi_ora.value = str(stats.get('attivi_ora', 0))
            
            attivi_list = [str(u) for u in stats.get('lista_attivi', []) if u]
            if attivi_list:
                tooltip_text = "Utenti attivi:\n" + "\n".join(attivi_list)
                if stats.get('attivi_ora', 0) > len(attivi_list):
                    tooltip_text += f"\n...e altri {stats['attivi_ora'] - len(attivi_list)}"
                self.card_attivi_ora.tooltip = tooltip_text
            else:
                self.card_attivi_ora.tooltip = "Nessun utente attivo"

            def format_stat(period):
                s = stats.get(period, {'unici': 0, 'totali': 0})
                return f"{s['unici']} / {s['totali']}"

            self.stats_24h.value = format_stat('24h')
            self.stats_48h.value = format_stat('48h')
            self.stats_72h.value = format_stat('72h')
            self.stats_7d.value = format_stat('7d')
            self.stats_30d.value = format_stat('30d')
            self.stats_1y.value = format_stat('1y')
            self.stats_all.value = format_stat('sempre')
            
            # Aggiorna il tooltip della prima card
            # (Lo facciamo dopo perché _build_access_stats_row usa il valore iniziale del tooltip)
            # In realtà il tooltip è legato al Container, non al Text.
            # Dobbiamo aggiornare il tooltip del Container se vogliamo che cambi dinamicamente.
            # Ma Flet aggiorna il tooltip se cambiamo la proprietà tooltip della card.
            # Vediamo come è costruita la card.

        # 1. Search Filter
        search_query = self.users_search.value.lower() if self.users_search.value else ""
        filtered_users = []
        
        for u in self._cached_users:
            # Combine fields for search
            full_text = f"{u['id_utente']} {u['username']} {u['email']} {u.get('nome','')} {u.get('cognome','')}".lower()
            if search_query in full_text:
                filtered_users.append(u)

        # 2. Sorting
        col_index = self.users_table.sort_column_index
        ascending = self.users_table.sort_ascending
        
        # 0:Sospeso, 1:Algo, 2:Username, 3:Cod.Utente, 4:Cod.Famiglia (not sortable), 5:Email, 6:Nome
        sort_keys = {0: 'sospeso', 2: 'username', 3: 'codice_utente', 5: 'email', 6: 'nome'}
        sort_key = sort_keys.get(col_index, 'username')
        
        filtered_users.sort(
            key=lambda x: (x.get(sort_key) if x.get(sort_key) is not None else "") if isinstance(x.get(sort_key), str) else (x.get(sort_key) or 0), 
            reverse=not ascending
        )

        # 3. Build Rows
        self.users_table.rows = []
        for u in filtered_users:
            self.users_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(
                        ft.Container(
                            content=ft.Text("SI" if u.get('sospeso') else "NO", color=ft.Colors.WHITE, size=10, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.RED if u.get('sospeso') else ft.Colors.GREEN,
                            padding=5, border_radius=4, alignment=ft.alignment.center
                        )
                    ),
                    ft.DataCell(ft.Text(u.get('algo', 'sha256'), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)),
                    ft.DataCell(ft.Text(u['username'], weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)),
                    ft.DataCell(ft.Text(u.get('codice_utente', '-'), weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)),
                    ft.DataCell(ft.Text(u.get('famiglie', '-'), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)),
                    ft.DataCell(ft.Text(u['email'], weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)),
                    ft.DataCell(ft.Text(f"{(u.get('nome') or '')} {(u.get('cognome') or '')}", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)),
                    ft.DataCell(ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.LOCK_RESET, tooltip="Invia Credenziali / Reset Password",
                            icon_color=ft.Colors.BLUE,
                            on_click=lambda e, uid=u['id_utente'], uname=u['username']: self._confirm_password_reset(uid, uname)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.BLOCK if not u.get('sospeso') else ft.Icons.CHECK_CIRCLE,
                            tooltip="Sospendi Utente" if not u.get('sospeso') else "Riattiva Utente",
                            icon_color=ft.Colors.ORANGE if not u.get('sospeso') else ft.Colors.GREEN,
                            on_click=lambda e, uid=u['id_utente'], uname=u['username'], susp=u.get('sospeso'): self._confirm_user_suspension(uid, uname, susp)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE, tooltip="Elimina Utente",
                            icon_color=ft.Colors.RED,
                            on_click=lambda e, uid=u['id_utente'], uname=u['username']: self._confirm_delete_user(uid, uname)
                        ),
                    ]))
                ])
            )
            
        self.page.update()

    def _on_users_sort(self, e):
        self._sort_datatable(e, self.users_table, [], lambda: self._load_users(use_cache=True))

    def _load_users_refresh(self):
        self._load_users(use_cache=False) # Force reload from DB

    def _open_admin_auth_dialog(self, title, action_callback):
        """Apre un dialog che richiede la password admin per confermare un'azione."""
        from db.gestione_db import verify_admin_password
        
        txt_password = ft.TextField(label="Password Admin", password=True, width=200)
        txt_error = ft.Text("", color=ft.Colors.RED, size=12, visible=False)
        
        def on_confirm(e):
            if verify_admin_password(txt_password.value):
                self.page.close(dlg)
                action_callback()
            else:
                txt_error.value = "Password errata."
                txt_error.visible = True
                self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.Text("Questa azione richiede conferma.", size=14),
                ft.Container(height=10),
                txt_password,
                txt_error
            ], tight=True, width=300),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self.page.close(dlg)),
                ft.ElevatedButton("Conferma", on_click=on_confirm, color=ft.Colors.WHITE, bgcolor=ft.Colors.RED),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def _confirm_delete_user(self, user_id, username):
        from db.gestione_db import verify_admin_password, delete_user
        
        txt_password = ft.TextField(label="Password Admin per Confermare", password=True, width=300)
        txt_error = ft.Text("", color=ft.Colors.RED, size=12, visible=False)
        
        def on_confirm(e):
            if verify_admin_password(txt_password.value):
                self.page.close(dlg)
                success, msg = delete_user(user_id)
                if success:
                    self.page.snack_bar = ft.SnackBar(ft.Text(f"Utente {username} e tutti i suoi dati eliminati correttamente."), bgcolor=ft.Colors.GREEN)
                    self._load_users_refresh()
                else:
                    self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore eliminazione: {msg}"), bgcolor=ft.Colors.RED)
                self.page.snack_bar.open = True
                self.page.update()
            else:
                txt_error.value = "Password admin errata."
                txt_error.visible = True
                self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.WARNING, color=ft.Colors.RED),
                ft.Text(f"Eliminazione Utente: {username}")
            ]),
            content=ft.Column([
                ft.Text(f"Sei sicuro di voler eliminare permanentemente l'utente '{username}'?"),
                ft.Text("Questa azione cancellerà tutti i suoi dati personali:", weight=ft.FontWeight.BOLD),
                ft.Text("• Tutti i Conti e le relative Transazioni", size=12),
                ft.Text("• Tutte le Carte e i massimali", size=12),
                ft.Text("• Asset e Portafoglio investimenti", size=12),
                ft.Text("• Contatti e Rubrica", size=12),
                ft.Text("• Log di sistema dell'utente", size=12),
                ft.Container(height=10),
                txt_password,
                txt_error
            ], tight=True, spacing=5, width=400),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self.page.close(dlg)),
                ft.ElevatedButton("ELIMINA DEFINITIVAMENTE", on_click=on_confirm, color=ft.Colors.WHITE, bgcolor=ft.Colors.RED),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def _confirm_user_suspension(self, user_id, username, is_suspended):
        action = "riattivare" if is_suspended else "sospendere"
        def do_suspend():
            from db.gestione_db import toggle_user_suspension
            if toggle_user_suspension(user_id, not is_suspended):
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Utente {username} {action} con successo!"), bgcolor=ft.Colors.GREEN)
                self.page.snack_bar.open = True
                self._load_users() # Refresh
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore durante l'operazione."), bgcolor=ft.Colors.RED)
                self.page.snack_bar.open = True
            self.page.update()
            
        self._open_admin_auth_dialog(f"Conferma {action} {username}", do_suspend)

    def _confirm_password_reset(self, user_id, username):
        def do_reset():
            from db.gestione_db import reset_user_password
            success, msg = reset_user_password(user_id)
            self.page.close(dlg)
            if success:
                self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=ft.Colors.GREEN)
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=ft.Colors.RED)
            self.page.snack_bar.open = True
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Conferma Reset Password"),
            content=ft.Text(f"Vuoi resettare la password per '{username}' e inviare le nuove credenziali via email?"),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self.page.close(dlg)),
                ft.TextButton("Reset e Invia", on_click=lambda e: do_reset()),
            ]
        )
        self.page.open(dlg)


    # =========================================================================
    # --- FAMILIES TAB LOGIC ---
    # =========================================================================
    def _init_families_tab_ui(self):
        self.families_search = ft.TextField(
            label="Cerca Famiglia...", 
            prefix_icon=ft.Icons.SEARCH,
            width=300,
            on_change=lambda e: self._load_families(use_cache=True)
        )

        self.families_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Nome Famiglia", weight=ft.FontWeight.BOLD), on_sort=self._on_families_sort),
                ft.DataColumn(ft.Text("Codice Famiglia", weight=ft.FontWeight.BOLD), on_sort=self._on_families_sort),
                ft.DataColumn(ft.Text("Cloud", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Utenti", weight=ft.FontWeight.BOLD), numeric=True, on_sort=self._on_families_sort),
                ft.DataColumn(ft.Text("Azioni", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            heading_row_color=ft.Colors.BLUE_GREY_50,
            sort_column_index=0,
            sort_ascending=True,
        )
        self._cached_families = []

    def _build_families_tab_content(self):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Gestione Famiglie", size=20, weight=ft.FontWeight.BOLD),
                    ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Ricarica Lista", on_click=lambda e: self._load_families_refresh())
                ]),
                ft.Row([self.families_search]),
                ft.Container(content=self.families_table, expand=True, border=ft.border.all(1, ft.Colors.GREY_200), border_radius=8)
            ]),
            padding=20, expand=True
        )

    def _load_families(self, use_cache=False):
        from db.gestione_db import get_all_families
        
        if not use_cache or not self._cached_families:
            self._cached_families = get_all_families()

        # 1. Search Filter
        search_query = self.families_search.value.lower() if self.families_search.value else ""
        filtered_families = []
        
        for f in self._cached_families:
             # Combine fields for search
            full_text = f"{f['id_famiglia']} {f['nome_famiglia']}".lower()
            if search_query in full_text:
                filtered_families.append(f)

        # 2. Sorting
        col_index = self.families_table.sort_column_index
        ascending = self.families_table.sort_ascending
        
        # 0:Nome, 1:Codice, 2:Cloud (not sortable), 3:Utenti
        sort_keys = {0: 'nome_famiglia', 1: 'codice_famiglia', 3: 'num_membri'}
        sort_key = sort_keys.get(col_index, 'nome_famiglia')
        
        filtered_families.sort(
            key=lambda x: (x.get(sort_key) if x.get(sort_key) is not None else "") if isinstance(x.get(sort_key), str) else (x.get(sort_key) or 0), 
            reverse=not ascending
        )

        # 3. Build Rows
        self.families_table.rows = []
        for f in filtered_families:
            self.families_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(f['nome_famiglia'], weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)),
                    ft.DataCell(ft.Text(f.get('codice_famiglia', '-'), weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)),
                    ft.DataCell(ft.Icon(ft.Icons.CLOUD_QUEUE if f.get('cloud_enabled') else ft.Icons.CLOUD_OFF, 
                                       color=ft.Colors.BLUE if f.get('cloud_enabled') else ft.Colors.GREY_400, size=20)),
                    ft.DataCell(ft.Text(str(f.get('num_membri', 0)), weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)),
                    ft.DataCell(
                        ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.DELETE, tooltip="Elimina Famiglia",
                                icon_color=ft.Colors.RED,
                                on_click=lambda e, fid=f['id_famiglia'], fname=f['nome_famiglia']: self._confirm_delete_family(fid, fname)
                            ),
                            ft.IconButton(
                                icon=ft.Icons.VISIBILITY, tooltip="Gestisci Funzioni (Visibilità)",
                                icon_color=ft.Colors.BLUE,
                                on_click=lambda e, fid=f['id_famiglia'], fname=f['nome_famiglia']: self._open_feature_visibility_dialog(fid, fname)
                            )
                        ], spacing=0)
                    )
                ])
            )
            
        self.page.update()

    def _on_families_sort(self, e):
         self._sort_datatable(e, self.families_table, [], lambda: self._load_families(use_cache=True))

    def _load_families_refresh(self):
        self._load_families(use_cache=False)
        self.page.update()

    def _confirm_delete_family(self, family_id, family_name):
        def do_delete():
            from db.gestione_db import delete_family
            success, msg = delete_family(family_id)
            if success:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Famiglia {family_name} eliminata."), bgcolor=ft.Colors.GREEN)
                self._load_families_refresh()
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore: {msg}"), bgcolor=ft.Colors.RED)
            self.page.snack_bar.open = True
            self.page.update()
            
        self._open_admin_auth_dialog(f"Elimina Famiglia {family_name}", do_delete)

    def _open_feature_visibility_dialog(self, family_id, family_name):
        """Apre il dialogo per gestire la visibilità delle funzioni per una famiglia."""
        from db.gestione_db import get_disabled_features, set_disabled_features, CONTROLLABLE_FEATURES
        
        # Recupera feature disabilitate correnti
        disabled_features = get_disabled_features(family_id)
        
        # Dizionario per tracciare lo stato dei checkbox (True = ABILITATO, False = DISABILITATO)
        # Nota: Nel DB salviamo quelle DISABILITATE. Quindi Checkbox CHECKED = Feature ABILITATA (non presente nella lista disabled)
        checkboxes = {}
        
        content_column = ft.Column(scroll=ft.ScrollMode.AUTO, height=400)
        
        for feature in CONTROLLABLE_FEATURES:
            key = feature['key']
            label = feature['label']
            icon_name = feature.get('icon', 'CIRCLE')
            
            is_enabled = key not in disabled_features
            
            cb = ft.Checkbox(label=label, value=is_enabled)
            checkboxes[key] = cb
            
            row = ft.Row([
                ft.Icon(getattr(ft.Icons, icon_name, ft.Icons.CIRCLE), size=20, color=ft.Colors.BLUE_GREY),
                cb
            ])
            content_column.controls.append(row)
            
        def on_save(e):
            # Calcola la nuova lista di feature DISABILITATE (checkbox deselezionati)
            new_disabled_list = []
            for key, cb in checkboxes.items():
                if not cb.value:
                    new_disabled_list.append(key)
            
            if set_disabled_features(family_id, new_disabled_list):
                 self.page.snack_bar = ft.SnackBar(ft.Text(f"Visibilità funzioni aggiornata per {family_name}"), bgcolor=ft.Colors.GREEN)
                 self.page.close(dlg)
            else:
                 self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore salvataggio."), bgcolor=ft.Colors.RED)
            
            self.page.snack_bar.open = True
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Gestione Funzioni - {family_name}", size=18, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Seleziona le funzioni da rendere visibili per questa famiglia:", size=12, color=ft.Colors.GREY),
                    ft.Divider(),
                    content_column
                ], tight=True),
                width=400
            ),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self.page.close(dlg)),
                ft.ElevatedButton("Salva Modifiche", on_click=on_save, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)



    # =========================================================================
    # --- CONFIG TAB LOGIC (EMAIL) ---
    # =========================================================================
    def _init_config_tab_ui(self):
        # General Config
        self.switch_default_cloud = ft.Switch(label="Abilita Automazione Cloud per Nuove Famiglie (Default)")
        
        # Email Config
        self.smtp_server = ft.TextField(label="SMTP Server (es. smtp.gmail.com)")
        self.smtp_port = ft.TextField(label="SMTP Port (es. 587)")
        self.smtp_user = ft.TextField(label="SMTP User (Email)")
        self.smtp_password = ft.TextField(label="SMTP Password", password=True, can_reveal_password=True)
        self.smtp_sender = ft.TextField(label="SMTP Sender (Email Mittente Verificata)", hint_text="Es. flammini.enrico@gmail.it")
        self.smtp_test_email = ft.TextField(label="Email Destinatario Test")
        
        # Password Complexity
        self.pwd_min_length = ft.TextField(label="Lunghezza Minima Password", value="8", width=200)
        self.pwd_require_special = ft.Switch(label="Richiedi Caratteri Speciali (@#$...)")
        self.pwd_require_digits = ft.Switch(label="Richiedi Numeri (0-9)")
        self.pwd_require_uppercase = ft.Switch(label="Richiedi Lettere Maiuscole (A-Z)")

    def _build_config_tab_content(self):
        return ft.Container(
            content=ft.Column([
                ft.Text("Impostazioni Generali", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=self.switch_default_cloud,
                    bgcolor=ft.Colors.BLUE_50, padding=10, border_radius=5
                ),
                ft.Divider(height=40),
                
                ft.Text("Configurazione Email (SMTP)", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("Queste credenziali verranno usate per inviare notifiche e reset password.", size=12, color=ft.Colors.GREY),
                ft.Divider(),
                self.smtp_server,
                self.smtp_port,
                self.smtp_user,
                self.smtp_password,
                self.smtp_sender,
                ft.Text("Test Invio Email", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.smtp_test_email,
                    ft.ElevatedButton("Invia Test", icon=ft.Icons.SEND, on_click=self._send_test_email)
                ]),
                ft.Divider(height=20),
                
                ft.Text("Sicurezza Password", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("Imposta i requisiti minimi per le password degli utenti.", size=12, color=ft.Colors.GREY),
                ft.Divider(),
                self.pwd_min_length,
                self.pwd_require_special,
                self.pwd_require_digits,
                self.pwd_require_uppercase,
                ft.Container(height=10),
                
                ft.ElevatedButton("Salva Configurazione", icon=ft.Icons.SAVE, on_click=self._save_config, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE),
                ft.Divider(height=40),
            ], scroll=ft.ScrollMode.AUTO),
            padding=20, expand=True
        )

    # =========================================================================
    # --- FOP TAB LOGIC ---
    # =========================================================================
    def _init_fop_tab_ui(self):
        self.fop_matrix = {} # operation -> {type -> {scope -> checkbox}}
        self.fop_container = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    def _build_fop_tab_content(self):
        return ft.Container(
            content=ft.Column([
                ft.Text("Matrice Gestione Forme di Pagamento (FOP)", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("Definisci quali tipi di conto e quali ambiti sono visibili per ogni operazione.", size=12, color=ft.Colors.GREY),
                ft.ElevatedButton("Salva Matrice FOP", icon=ft.Icons.SAVE, on_click=self._save_fop_matrix, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE),
                ft.Divider(),
                self.fop_container
            ], expand=True),
            padding=20, expand=True
        )

    def _load_fop_matrix(self):
        from db.gestione_db import get_configurazione
        import json
        
        raw = get_configurazione("global_fop_matrix")
        saved_data = {}
        if raw:
            try: saved_data = json.loads(raw)
            except: logger.error("Errore parsing global_fop_matrix")

        operations = ["Spesa", "Incasso", "Giroconto (Mittente)", "Giroconto (Ricevente)", "Spesa Fissa", "Prestiti", "Accantonamenti", "Satispay (Collegamento)", "PayPal (Fonti)"]
        types = ["Conto Corrente", "Carte", "Risparmio", "Investimenti", "Contanti", "Fondo Pensione", "Salvadanaio", "Satispay", "PayPal"]
        scopes = ["Personale", "Condiviso", "Altri Familiari"]
        
        self.fop_container.controls.clear()
        self.fop_matrix = {}

        for op in operations:
            op_data = saved_data.get(op, {})
            self.fop_matrix[op] = {}
            
            op_section = ft.Column([
                ft.Text(f"📌 {op}", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800),
                ft.Divider(height=10)
            ], spacing=5)
            
            # Header per gli ambiti
            header_row = ft.Row([
                ft.Container(width=150), # Spazio per il tipo
                ft.Container(content=ft.Text("Personale", size=10, weight=ft.FontWeight.BOLD), width=80, alignment=ft.alignment.center),
                ft.Container(content=ft.Text("Condiviso", size=10, weight=ft.FontWeight.BOLD), width=80, alignment=ft.alignment.center),
                ft.Container(content=ft.Text("Altri", size=10, weight=ft.FontWeight.BOLD), width=80, alignment=ft.alignment.center),
            ])
            op_section.controls.append(header_row)

            for t in types:
                self.fop_matrix[op][t] = {}
                row_controls = [ft.Container(content=ft.Text(t, size=12), width=150)]
                
                for s in scopes:
                    # Default values if not in DB
                    default = False
                    if op == "Incasso" and t == "Conto Corrente" and s != "Altri Familiari": default = True
                    if op == "Spesa" and t in ["Conto Corrente", "Carte", "Satispay", "PayPal"] and s != "Altri Familiari": default = True
                    if op in ["Giroconto (Mittente)", "Giroconto (Ricevente)"] and t in ["Conto Corrente", "Salvadanaio"]: default = True
                    if op == "Satispay (Collegamento)" and t == "Conto Corrente" and s != "Altri Familiari": default = True
                    if op == "PayPal (Fonti)" and t in ["Conto Corrente", "Carte"] and s != "Altri Familiari": default = True
                    if op == "Accantonamenti" and t in ["Conto Corrente", "Risparmio"] and s != "Altri Familiari": default = True
                    
                    val = op_data.get(t, {}).get(s, default)
                    cb = ft.Checkbox(value=val, data={"op": op, "type": t, "scope": s})
                    self.fop_matrix[op][t][s] = cb
                    row_controls.append(ft.Container(content=cb, width=80, alignment=ft.alignment.center))
                
                op_section.controls.append(ft.Row(row_controls, vertical_alignment=ft.CrossAxisAlignment.CENTER))
            
            self.fop_container.controls.append(ft.Container(content=op_section, padding=15, bgcolor=ft.Colors.WHITE, border_radius=8, border=ft.border.all(1, ft.Colors.BLUE_GREY_100)))
            self.fop_container.controls.append(ft.Container(height=20))

    def _save_fop_matrix(self, e):
        from db.gestione_db import save_system_config
        import json
        
        matrix_to_save = {}
        for op, types in self.fop_matrix.items():
            matrix_to_save[op] = {}
            for t, scopes in types.items():
                matrix_to_save[op][t] = {}
                for s, cb in scopes.items():
                    matrix_to_save[op][t][s] = cb.value
        
        json_data = json.dumps(matrix_to_save)
        
        # User context for RLS
        current_user_id = self.page.client_storage.get("user_id") or 1
        
        if save_system_config("global_fop_matrix", json_data, id_utente=current_user_id):
            self.page.snack_bar = ft.SnackBar(ft.Text("Matrice FOP salvata con successo!"), bgcolor=ft.Colors.GREEN)
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("Errore durante il salvataggio."), bgcolor=ft.Colors.RED)
        
        self.page.snack_bar.open = True
        self.page.update()

    # =========================================================================
    # --- SORTING TAB LOGIC ---
    # =========================================================================
    
    # Lista predefinita di tutti i tipi di strumenti finanziari
    DEFAULT_INSTRUMENT_TYPES = [
        {"key": "conto_corrente",        "label": "Conto Corrente",           "icon": "🏦"},
        {"key": "conto_risparmio",       "label": "Conto Risparmio",          "icon": "🐷"},
        {"key": "carta_credito",         "label": "Carta di Credito",         "icon": "💳"},
        {"key": "carta_debito",          "label": "Carta di Debito",          "icon": "💳"},
        {"key": "contanti",              "label": "Contanti",                 "icon": "💵"},
        {"key": "satispay",              "label": "Satispay",                 "icon": "📱"},
        {"key": "paypal",                "label": "PayPal",                   "icon": "🅿️"},
        {"key": "investimento",          "label": "Conto Investimento",       "icon": "📈"},
        {"key": "fondo_pensione",        "label": "Fondo Pensione",           "icon": "🏖️"},
        {"key": "portafoglio_elettronico","label": "Portafoglio Elettronico", "icon": "📲"},
    ]

    def _init_sorting_tab_ui(self):
        self.sorting_items_list = []  # List of dict {key, label, icon}
        self.sorting_list_container = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=5)

    def _build_sorting_tab_content(self):
        return ft.Container(
            content=ft.Column([
                ft.Text("Ordinamento Tipologie Strumenti", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Definisci l'ordine di visualizzazione delle tipologie di conti e carte nei menu dropdown. "
                    "Questa impostazione è globale e si applica a tutte le famiglie.",
                    size=12, color=ft.Colors.GREY
                ),
                ft.Divider(),
                ft.Row([
                    ft.ElevatedButton("Salva Ordinamento", icon=ft.Icons.SAVE, on_click=self._save_sorting, bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE),
                    ft.TextButton("Reset Default", icon=ft.Icons.REFRESH, on_click=self._reset_sorting)
                ]),
                self.sorting_list_container
            ], expand=True),
            padding=20, expand=True
        )

    def _load_sorting_data(self):
        """Carica l'ordinamento globale dei tipi di strumenti."""
        from db.gestione_db import get_configurazione
        import json
        
        # Carica ordine salvato
        raw = get_configurazione("global_fop_sort_order")
        saved_order = []
        if raw:
            try:
                saved_order = json.loads(raw)  # lista di keys
            except:
                pass
        
        # Costruisci items dal default, applicando l'ordine salvato
        all_types = list(self.DEFAULT_INSTRUMENT_TYPES)
        
        if saved_order:
            def get_index(item):
                try:
                    return saved_order.index(item['key'])
                except ValueError:
                    return 999
            all_types.sort(key=get_index)
        
        self.sorting_items_list = [dict(t) for t in all_types]  # copy
        self._refresh_sorting_ui()

    def _refresh_sorting_ui(self):
        self.sorting_list_container.controls.clear()
        for idx, item in enumerate(self.sorting_items_list):
            row = ft.Container(
                content=ft.Row([
                    ft.Row([
                        ft.Text(item['icon'], size=20),
                        ft.Text(item['label'], size=14, weight=ft.FontWeight.W_500),
                    ], expand=True, spacing=10),
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.ARROW_UPWARD, 
                            on_click=lambda e, i=idx: self._move_sorting_item(i, -1), 
                            visible=(idx > 0),
                            tooltip="Sposta su"
                        ),
                        ft.IconButton(
                            ft.Icons.ARROW_DOWNWARD, 
                            on_click=lambda e, i=idx: self._move_sorting_item(i, 1), 
                            visible=(idx < len(self.sorting_items_list)-1),
                            tooltip="Sposta giù"
                        ),
                    ], spacing=0)
                ]),
                padding=10,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=8,
                bgcolor=ft.Colors.WHITE
            )
            self.sorting_list_container.controls.append(row)

    def _move_sorting_item(self, index, direction):
        new_index = index + direction
        if 0 <= new_index < len(self.sorting_items_list):
            self.sorting_items_list[index], self.sorting_items_list[new_index] = self.sorting_items_list[new_index], self.sorting_items_list[index]
            self._refresh_sorting_ui()
            self.page.update()

    def _save_sorting(self, e):
        from db.gestione_db import save_system_config
        import json
        
        order_keys = [item['key'] for item in self.sorting_items_list]
        json_data = json.dumps(order_keys)
        
        current_user_id = self.page.client_storage.get("user_id") or 1
        
        if save_system_config("global_fop_sort_order", json_data, id_utente=current_user_id):
            self.page.snack_bar = ft.SnackBar(ft.Text("Ordinamento salvato con successo!"), bgcolor=ft.Colors.GREEN)
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("Errore durante il salvataggio."), bgcolor=ft.Colors.RED)
        self.page.snack_bar.open = True
        self.page.update()

    def _reset_sorting(self, e):
        """Ripristina l'ordine predefinito."""
        self.sorting_items_list = [dict(t) for t in self.DEFAULT_INSTRUMENT_TYPES]
        self._refresh_sorting_ui()
        self.page.update()

    # =========================================================================
    # --- ICONS TAB LOGIC ---
    # =========================================================================
    def _init_icons_tab_ui(self):
        pass # No longer needed, removed content

    def _load_config(self):
        from db.gestione_db import get_smtp_config, get_configurazione
        
        # Load Global Config
        default_cloud = get_configurazione("system_default_cloud_automation")
        self.switch_default_cloud.value = (default_cloud == "true")
        
        # Load SMTP Config
        config = get_smtp_config() # retrieves global config
        if config:
            self.smtp_server.value = config.get('server') or ""
            self.smtp_port.value = config.get('port') or ""
            self.smtp_user.value = config.get('user') or ""
            self.smtp_password.value = config.get('password') or ""
            self.smtp_sender.value = config.get('sender') or ""
            
        # Load Password Complexity
        from db.gestione_db import get_password_complexity_config
        pwd_cfg = get_password_complexity_config()
        self.pwd_min_length.value = str(pwd_cfg.get("min_length", 8))
        self.pwd_require_special.value = pwd_cfg.get("require_special", False)
        self.pwd_require_digits.value = pwd_cfg.get("require_digits", False)
        self.pwd_require_uppercase.value = pwd_cfg.get("require_uppercase", False)

    def _save_config(self, e):
        from db.gestione_db import save_system_config
        
        # Save each key using save_system_config
        success_all = True
        errors = []
        
        # Recupera ID utente per RLS context
        try:
            current_user_id = self.page.client_storage.get("user_id")
            if not current_user_id:
                current_user_id = 1 # Fallback admin
        except:
             current_user_id = 1
        
        try:
             configs_to_save = [
                 ('system_default_cloud_automation', 'true' if self.switch_default_cloud.value else 'false'),
                 ('smtp_server', self.smtp_server.value),
                 ('smtp_port', self.smtp_port.value),
                 ('smtp_user', self.smtp_user.value),
                 ('smtp_password', self.smtp_password.value),
                 ('smtp_sender', self.smtp_sender.value),
                 ('smtp_provider', 'custom'),
                 ('pwd_min_length', self.pwd_min_length.value),
                 ('pwd_require_special', 'true' if self.pwd_require_special.value else 'false'),
                 ('pwd_require_digits', 'true' if self.pwd_require_digits.value else 'false'),
                 ('pwd_require_uppercase', 'true' if self.pwd_require_uppercase.value else 'false')
             ]
             
             for key, value in configs_to_save:
                 if not save_system_config(key, value, id_utente=current_user_id):
                     success_all = False
                     errors.append(key)
        
             if success_all:
                 self.page.snack_bar = ft.SnackBar(ft.Text("Configurazione salvata con successo!"), bgcolor=ft.Colors.GREEN)
             else:
                 self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore salvataggio chiavi: {', '.join(errors)}"), bgcolor=ft.Colors.RED)
                 
        except Exception as ex:
             self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore imprevisto: {ex}"), bgcolor=ft.Colors.RED)
             
        self.page.snack_bar.open = True
        self.page.update()

    def _send_test_email(self, e):
        from utils.email_sender import send_email
        if not self.smtp_test_email.value:
            self.page.snack_bar = ft.SnackBar(ft.Text("Inserisci un'email per il test."), bgcolor=ft.Colors.RED)
            self.page.snack_bar.open = True
            self.page.update()
            return

        self.page.snack_bar = ft.SnackBar(ft.Text("Invio email in corso..."), bgcolor=ft.Colors.BLUE)
        self.page.snack_bar.open = True
        self.page.update()
            
        success, error = send_email(
            to_email=self.smtp_test_email.value,
            subject="BudgetAmico - Test Email",
            body="<h1>Test Riuscito</h1><p>Se leggi questa email, la configurazione SMTP è corretta.</p>",
            smtp_config={
                'server': self.smtp_server.value,
                'port': self.smtp_port.value,
                'user': self.smtp_user.value,
                'password': self.smtp_password.value,
                'sender': self.smtp_sender.value
            }
        )
        
        if success:
             self.page.snack_bar = ft.SnackBar(ft.Text("Email di test inviata! Controlla la posta."), bgcolor=ft.Colors.GREEN)
        else:
             self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore invio: {error}"), bgcolor=ft.Colors.RED)
        self.page.snack_bar.open = True
        self.page.update()


    # =========================================================================
    # --- DB STATS TAB LOGIC ---
    # =========================================================================
    def _init_db_stats_tab_ui(self):
        self.db_stats_search = ft.TextField(
            label="Cerca Tabella...", 
            prefix_icon=ft.Icons.SEARCH,
            width=300,
            on_change=lambda e: self._load_db_stats(use_cache=True)
        )
        
        self.db_stats_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Tabella", weight=ft.FontWeight.BOLD), on_sort=self._on_db_stats_sort),
                ft.DataColumn(ft.Text("Righe (Stima)", weight=ft.FontWeight.BOLD), numeric=True, on_sort=self._on_db_stats_sort),
                ft.DataColumn(ft.Text("Dimensione", weight=ft.FontWeight.BOLD), numeric=True, on_sort=self._on_db_stats_sort),
            ],
            rows=[],
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            heading_row_color=ft.Colors.BLUE_GREY_50,
            sort_column_index=2, # Default sort by Size
            sort_ascending=False,
        )
        self.total_db_size_text = ft.Text("Dimensione Totale DB: -", size=16, weight=ft.FontWeight.BOLD)
        self.pool_metrics_text = ft.Text("Pool Connessioni: -", size=14, color=ft.Colors.BLUE_GREY_600)
        
        # Cache locale per i dati grezzi (per evitare query continue su search/sort)
        self._cached_db_stats_tables = []

    def _build_db_stats_tab_content(self):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Statistiche Database", size=20, weight=ft.FontWeight.BOLD),
                    ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Aggiorna Statistiche", on_click=lambda e: self._load_db_stats())
                ]),
                ft.Row([self.db_stats_search]),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Column([
                        self.total_db_size_text,
                        self.pool_metrics_text
                    ], spacing=5),
                    bgcolor=ft.Colors.BLUE_50, padding=10, border_radius=5
                ),
                ft.Container(height=10),
                ft.Container(
                    content=self.db_stats_table,
                    expand=True, border=ft.border.all(1, ft.Colors.GREY_200), border_radius=8,
                    padding=5
                )
            ]),
            padding=20, expand=True
        )

    def _load_db_stats(self, use_cache=False):
        from db.gestione_db import get_database_statistics
        
        if not use_cache:
            self.page.snack_bar = ft.SnackBar(ft.Text("Caricamento statistiche DB..."), bgcolor=ft.Colors.BLUE_GREY_400, duration=1000)
            self.page.snack_bar.open = True
            self.page.update()
            
            stats = get_database_statistics()
            total_bytes = stats.get("total_size_bytes", 0)
            self.total_db_size_text.value = f"Dimensione Totale DB: {self._format_bytes(total_bytes)}"
            
            # Filtra e salva in cache locale
            raw_tables = stats.get("tables", [])
            self._cached_db_stats_tables = []
            
            for t in raw_tables:
                t_name = t.get("table_name", "").lower()
                if t_name in PROGRAM_TABLES:
                    self._cached_db_stats_tables.append(t)
            
            # 3. Recupera metriche pool
            from db.supabase_manager import SupabaseManager
            m = SupabaseManager.get_metrics()
            self.pool_metrics_text.value = (
                f"Connessioni Pool: {m['pool_idle']} idle, {m['active_now']} attive | "
                f"Totale: {m['created']} create, {m['expired']} scadute/chiuse"
            )
        
        # 1. Filtro Search
        search_query = self.db_stats_search.value.lower() if self.db_stats_search.value else ""
        filtered_tables = [
            t for t in self._cached_db_stats_tables 
            if search_query in t.get("table_name", "").lower()
        ]
        
        # 2. Ordinamento
        col_index = self.db_stats_table.sort_column_index
        ascending = self.db_stats_table.sort_ascending
        
        # Mappa indice colonna -> chiave dizionario
        sort_keys = {0: "table_name", 1: "row_count", 2: "size_bytes"}
        sort_key = sort_keys.get(col_index, "size_bytes")
        
        filtered_tables.sort(
            key=lambda x: x.get(sort_key, 0) if sort_key != "table_name" else x.get(sort_key, "").lower(), 
            reverse=not ascending
        )
        
        # 3. Costruzione Righe
        self.db_stats_table.rows = []
        for t in filtered_tables:
            name = t.get("table_name", "-")
            rows = t.get("row_count", 0)
            size = t.get("size_bytes", 0)
            
            self.db_stats_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(name)),
                    ft.DataCell(ft.Text(f"{rows:,}")),
                    ft.DataCell(ft.Text(self._format_bytes(size))),
                ])
            )
            
        self.page.update()

    def _on_db_stats_sort(self, e):
        self._sort_datatable(e, self.db_stats_table, [], lambda: self._load_db_stats(use_cache=True))

    def _format_bytes(self, size):
        power = 2**10
        n = 0
        power_labels = {0 : '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels.get(n, 'PB')}"

    # =========================================================================
    # --- KOYEB STATUS TAB LOGIC ---
    # =========================================================================
    def _build_koyeb_tab_content(self):
        # Nessuna API Key disponibile, usiamo link diretto
        koyeb_url = "https://app.koyeb.com/services"
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Stato Servizi Koyeb", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("Monitoraggio performance e stato del servizio web.", size=14, color=ft.Colors.GREY_700),
                ft.Divider(),
                ft.Container(height=20),
                ft.Column([
                    ft.Icon(ft.Icons.CLOUD_DONE, size=64, color=ft.Colors.BLUE_GREY),
                    ft.Text("Gestione Cloud Platform", size=16, weight=ft.FontWeight.BOLD),
                    ft.Text("Per visualizzare metriche dettagliate (CPU, RAM, Latenza), accedi alla dashboard di Koyeb.", text_align=ft.TextAlign.CENTER),
                    ft.Container(height=10),
                    ft.ElevatedButton(
                        "Apri Dashboard Koyeb", 
                        icon=ft.Icons.OPEN_IN_NEW,
                        on_click=lambda e: self.page.launch_url(koyeb_url),
                        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_800)
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
                
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=40, expand=True
        )


    # =========================================================================
    # --- VERSION TAB LOGIC ---
    # =========================================================================
    def _init_version_tab_ui(self):
        self.app_version_text = ft.Text("Versione Applicazione: -", size=18, weight=ft.FontWeight.BOLD)
        self.db_version_text = ft.Text("Versione Database: -", size=18, weight=ft.FontWeight.BOLD)
        self.env_type_text = ft.Text("Ambiente: -", size=14, italic=True)

    def _build_version_tab_content(self):
        return ft.Container(
            content=ft.Column([
                ft.Container(height=20),
                ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=32, color=ft.Colors.BLUE),
                    ft.Text("Informazioni Versione", size=24, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(height=40),
                
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.APP_REGISTRATION, color=ft.Colors.BLUE_800),
                            self.app_version_text
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([
                            ft.Icon(ft.Icons.STORAGE, color=ft.Colors.GREEN_800),
                            self.db_version_text
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Container(height=10),
                        ft.Row([
                            ft.Icon(ft.Icons.DASHBOARD_CUSTOMIZE, color=ft.Colors.GREY_700, size=16),
                            self.env_type_text
                        ], alignment=ft.MainAxisAlignment.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
                    padding=40,
                    bgcolor=ft.Colors.BLUE_GREY_50,
                    border_radius=15,
                    border=ft.border.all(1, ft.Colors.BLUE_GREY_100),
                ),
                
                ft.Container(height=40),
                ft.Text("Note di Rilascio", size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Ultimo aggiornamento schema: v30 (Crittografia Selettiva & Tipi Numerici)", size=12, color=ft.Colors.GREY_600),
                
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO),
            padding=40,
            expand=True,
        )

    def _load_version_info(self):
        try:
            from app_controller import VERSION
            self.app_version_text.value = f"Versione Applicazione: v{VERSION}"
        except Exception as e:
            self.app_version_text.value = "Versione Applicazione: N/A"
            print(f"Errore caricamento versione app: {e}")

        try:
            db_ver = ottieni_versione_db()
            self.db_version_text.value = f"Versione Database: Schema v{db_ver}"
        except Exception as e:
            self.db_version_text.value = "Versione Database: Errore"
            print(f"Errore caricamento versione DB: {e}")
            
        # Info Ambiente avanzate
        is_dev = os.getenv("DEBUG", "false").lower() == "true"
        supabase_url = os.getenv("SUPABASE_URL", "") or os.getenv("SUPABASE_DB_URL", "")
        
        # Identificazione DB (basata su project ID Supabase)
        db_type = "Ambiente Personalizzato"
        if "rcwdfjayzotvsbqpubcm" in supabase_url:
            db_type = "Ambiente di TEST (rcwdf...)"
        elif "zvuesichckiryhkbztgr" in supabase_url:
            db_type = "Ambiente di PRODUZIONE (zvues...)"
            
        # Identificazione Branch
        branch_name = "N/A"
        try:
            # Tenta di leggere la branch corrente se git è disponibile
            import subprocess
            branch_name = subprocess.check_output(["git", "branch", "--show-current"], 
                                                stderr=subprocess.DEVNULL).decode().strip()
        except:
            pass

        env_str = f"{db_type}"
        if is_dev:
            env_str += " [DEBUG MODE]"
        if branch_name != "N/A":
            env_str += f" | Branch: {branch_name}"
            
        self.env_type_text.value = env_str
        self.page.update()


class AdminLoginView:
    """Vista di login per l'admin di sistema."""
    
    def __init__(self, page: ft.Page, on_login_success):
        self.page = page
        self.on_login_success = on_login_success
        
        self.txt_username = ft.TextField(
            label="Username Admin",
            autofocus=True,
            width=300
        )
        self.txt_password = ft.TextField(
            label="Password Admin",
            password=True,
            can_reveal_password=True,
            width=300,
            on_submit=self._on_login_click
        )
        self.error_text = ft.Text(color=ft.Colors.RED, size=12)
    
    def _on_login_click(self, e):
        username = self.txt_username.value
        password = self.txt_password.value
        
        if verifica_admin_sistema(username, password):
            self.on_login_success()
        else:
            self.error_text.value = "Credenziali non valide."
            self.page.update()
            
    def build_view(self) -> ft.View:
        return ft.View(
            "/admin/login",
            [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS, size=64, color=ft.Colors.BLUE),
                        ft.Text("Admin Login", size=24, weight=ft.FontWeight.BOLD),
                        ft.Container(height=20),
                        self.txt_username,
                        self.txt_password,
                        self.error_text,
                        ft.Container(height=20),
                        ft.ElevatedButton(
                            "Accedi",
                            on_click=self._on_login_click,
                            width=300
                        ),
                        ft.TextButton(
                            "Torna alla Home",
                            on_click=lambda e: self.page.go("/")
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
                    alignment=ft.alignment.center,
                    expand=True
                )
            ]
        )
