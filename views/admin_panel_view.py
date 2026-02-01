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
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD), numeric=True, on_sort=self._on_users_sort),
                ft.DataColumn(ft.Text("Famiglie ID", weight=ft.FontWeight.BOLD), on_sort=self._on_users_sort),
                ft.DataColumn(ft.Text("Sospeso", weight=ft.FontWeight.BOLD), on_sort=self._on_users_sort),
                ft.DataColumn(ft.Text("Algo", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Username", weight=ft.FontWeight.BOLD), on_sort=self._on_users_sort),
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

    def _build_users_tab_content(self):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Gestione Utenti", size=20, weight=ft.FontWeight.BOLD),
                    ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Ricarica Lista", on_click=lambda e: self._load_users_refresh())
                ]),
                ft.Row([self.users_search]),
                ft.Container(content=self.users_table, expand=True, border=ft.border.all(1, ft.Colors.GREY_200), border_radius=8)
            ]),
            padding=20, expand=True
        )

    def _load_users(self, use_cache=False):
        # Lazy import to avoid circular dependency
        from db.gestione_db import get_all_users
        
        if not use_cache or not self._cached_users:
            self._cached_users = get_all_users()

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
        
        # Keys for sorting based on column index
        # 0:ID, 1:Famiglie, 2:Sospeso, 3:Username, 4:Email, 5:Nome
        sort_keys = {0: 'id_utente', 1: 'famiglie', 2: 'sospeso', 3: 'username', 4: 'email', 5: 'nome'}
        sort_key = sort_keys.get(col_index, 'id_utente')
        
        filtered_users.sort(
            key=lambda x: (x.get(sort_key) if x.get(sort_key) is not None else "") if isinstance(x.get(sort_key), str) else (x.get(sort_key) or 0), 
            reverse=not ascending
        )

        # 3. Build Rows
        self.users_table.rows = []
        for u in filtered_users:
            self.users_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(u['id_utente']))),
                    ft.DataCell(ft.Text(str(u.get('famiglie', '-')))), # Ensure string
                    ft.DataCell(
                        ft.Container(
                            content=ft.Text("SI" if u.get('sospeso') else "NO", color=ft.Colors.WHITE, size=10, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.RED if u.get('sospeso') else ft.Colors.GREEN,
                            padding=5, border_radius=4, alignment=ft.alignment.center
                        )
                    ),
                    ft.DataCell(ft.Text(u.get('algo', 'sha256'), size=11, color=ft.Colors.GREY_700)),
                    ft.DataCell(ft.Text(u['username'])),
                    ft.DataCell(ft.Text(u['email'])),
                    ft.DataCell(ft.Text(f"{(u.get('nome') or '')} {(u.get('cognome') or '')}")),
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
        def do_delete():
            from db.gestione_db import delete_user
            success, msg = delete_user(user_id)
            if success:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Utente {username} eliminato correttamente: {msg}"), bgcolor=ft.Colors.GREEN)
                self.page.snack_bar.open = True
                self._load_users_refresh()
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore eliminazione: {msg}"), bgcolor=ft.Colors.RED)
                self.page.snack_bar.open = True
            self.page.update()

        self._open_admin_auth_dialog(f"Conferma Eliminazione {username}", do_delete)

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
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD), numeric=True, on_sort=self._on_families_sort),
                ft.DataColumn(ft.Text("Cloud", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Nome Famiglia", weight=ft.FontWeight.BOLD), on_sort=self._on_families_sort),
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
        
        # 0:ID, 1:Nome
        sort_keys = {0: 'id_famiglia', 1: 'nome_famiglia'}
        sort_key = sort_keys.get(col_index, 'id_famiglia')
        
        filtered_families.sort(
            key=lambda x: (x.get(sort_key) if x.get(sort_key) is not None else "") if isinstance(x.get(sort_key), str) else (x.get(sort_key) or 0), 
            reverse=not ascending
        )

        # 3. Build Rows
        self.families_table.rows = []
        for f in filtered_families:
            self.families_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(f['id_famiglia']))),
                    ft.DataCell(ft.Icon(ft.Icons.CLOUD_QUEUE if f.get('cloud_enabled') else ft.Icons.CLOUD_OFF, 
                                       color=ft.Colors.BLUE if f.get('cloud_enabled') else ft.Colors.GREY_400, size=20)),
                    ft.DataCell(ft.Text(f['nome_famiglia'])),
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
        self.smtp_test_email = ft.TextField(label="Email Destinatario Test")

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
                ft.ElevatedButton("Salva Configurazione", icon=ft.Icons.SAVE, on_click=self._save_config),
                ft.Divider(height=40),
                ft.Text("Test Invio Email", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.smtp_test_email,
                    ft.ElevatedButton("Invia Test", icon=ft.Icons.SEND, on_click=self._send_test_email)
                ])
            ], scroll=ft.ScrollMode.AUTO),
            padding=20, expand=True
        )

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

    def _save_config(self, e):
        from db.gestione_db import save_system_config
        
        # Save each key using save_system_config
        try:
             # Save Global Config
             save_system_config('system_default_cloud_automation', 'true' if self.switch_default_cloud.value else 'false')
        
             # Save SMTP Config
             save_system_config('smtp_server', self.smtp_server.value)
             save_system_config('smtp_port', self.smtp_port.value)
             save_system_config('smtp_user', self.smtp_user.value)
             save_system_config('smtp_password', self.smtp_password.value)
             save_system_config('smtp_provider', 'custom')
             
             self.page.snack_bar = ft.SnackBar(ft.Text("Configurazione salvata con successo!"), bgcolor=ft.Colors.GREEN)
        except Exception as ex:
             self.page.snack_bar = ft.SnackBar(ft.Text(f"Errore salvataggio configurazione: {ex}"), bgcolor=ft.Colors.RED)
             
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
            body="<h1>Test Riuscito</h1><p>Se leggi questa email, la configurazione SMTP è corretta.</p>"
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
                    content=self.total_db_size_text,
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
            
            # NORMALIZZAZIONE: Crea set lowercase per controllo veloce
            whitelist_set = set(t.lower() for t in PROGRAM_TABLES)
            
            for t in raw_tables:
                t_name = t.get("table_name", "").lower()
                # Verifica se il nome tabella è nella whitelist (o inizia con 'program_' se volgiamo essere laschi, ma qui usiamo exact match list)
                if t_name in whitelist_set:
                    self._cached_db_stats_tables.append(t)
        
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
