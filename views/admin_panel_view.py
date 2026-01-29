"""
Admin Panel View - Pannello di amministrazione di sistema per BudgetAmico Web.

Questo modulo fornisce un'interfaccia web per gli amministratori di sistema
per visualizzare i log e gestire configurazioni.
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
    
    if not admin_password:
        print("[ADMIN] ADMIN_PASSWORD non configurata in .env")
        return False
    
    return username == admin_username and password == admin_password


class AdminPanelView:
    """Vista del pannello di amministrazione di sistema."""
    
    def __init__(self, page: ft.Page, on_logout):
        self.page = page
        self.on_logout = on_logout
        
        # Stato
        self.current_filter_level = None
        self.current_filter_component = None
        self.current_page = 0
        self.logs_per_page = 50
        
        # Componenti UI
        self.logs_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Timestamp", size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Livello", size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Componente", size=12, weight=ft.FontWeight.BOLD)),
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
        
        # Dropdown filtri
        self.level_dropdown = ft.Dropdown(
            label="Livello",
            width=150,
            options=[
                ft.dropdown.Option("", "Tutti"),
                ft.dropdown.Option("DEBUG", "DEBUG"),
                ft.dropdown.Option("INFO", "INFO"),
                ft.dropdown.Option("WARNING", "WARNING"),
                ft.dropdown.Option("ERROR", "ERROR"),
                ft.dropdown.Option("CRITICAL", "CRITICAL"),
            ],
            value="",
            on_change=self._on_filter_change
        )
        
        self.component_dropdown = ft.Dropdown(
            label="Componente",
            width=200,
            options=[ft.dropdown.Option("", "Tutti")],
            value="",
            on_change=self._on_filter_change
        )
        
        # Container per configurazione logger (chip toggle)
        self.config_expanded = False
        self.config_content = ft.Container(visible=False)  # Contenitore espandibile
        self.expand_icon = ft.IconButton(
            icon=ft.Icons.EXPAND_MORE,
            tooltip="Espandi/Comprimi",
            on_click=self._toggle_config_section,
            icon_size=18,
        )
    
    def _build_logger_config_section(self) -> ft.Container:
        """Costruisce la sezione di configurazione dei logger."""
        components = get_all_components()
        
        chips = []
        for comp in components:
            chip = ft.Chip(
                label=ft.Text(comp['componente'], size=11),
                selected=comp['abilitato'],
                on_select=lambda e, c=comp['componente']: self._toggle_logger(c, e.control.selected),
                bgcolor=ft.Colors.GREY_200,
                selected_color=ft.Colors.GREEN_100,
            )
            chips.append(chip)
        
        # Aggiorna il contenuto espandibile
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
            padding=10,
            bgcolor=ft.Colors.AMBER_50,
            border_radius=8,
            border=ft.border.all(1, ft.Colors.AMBER_200),
        )
    
    def _toggle_config_section(self, e):
        """Espande/comprime la sezione configurazione."""
        self.config_expanded = not self.config_expanded
        self.config_content.visible = self.config_expanded
        self.expand_icon.icon = ft.Icons.EXPAND_LESS if self.config_expanded else ft.Icons.EXPAND_MORE
        self.page.update()
    
    def _toggle_logger(self, componente: str, abilitato: bool):
        """Attiva/disattiva un logger."""
        if update_logger_config(componente, abilitato):
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Logger '{componente}' {'abilitato' if abilitato else 'disabilitato'}"),
                bgcolor=ft.Colors.GREEN_400 if abilitato else ft.Colors.GREY_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    def _get_level_badge(self, level: str) -> ft.Container:
        """Restituisce un badge colorato per il livello di log."""
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
            bgcolor=bg,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=4,
        )
    
    def _load_components(self):
        """Carica la lista dei componenti distinti per il filtro."""
        components = get_distinct_components()
        self.component_dropdown.options = [ft.dropdown.Option("", "Tutti")]
        for comp in components:
            self.component_dropdown.options.append(ft.dropdown.Option(comp, comp))
    
    def _load_logs(self):
        """Carica i log dal database con i filtri correnti."""
        # Gestisce sia stringa vuota che "Tutti" come None
        level_val = self.level_dropdown.value
        level = None if not level_val or level_val == "Tutti" else level_val
        
        comp_val = self.component_dropdown.value
        component = None if not comp_val or comp_val == "Tutti" else comp_val
        
        print(f"[ADMIN] Loading logs - livello: {level}, componente: {component}, page: {self.current_page}")
        
        logs = get_logs(
            livello=level,
            componente=component,
            limit=self.logs_per_page,
            offset=self.current_page * self.logs_per_page
        )
        
        print(f"[ADMIN] Retrieved {len(logs)} logs")
        
        # Aggiorna la tabella - usa lista nuova invece di clear()
        new_rows = []
        
        for log in logs:
            timestamp = log.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    ts_str = timestamp[:19]
                else:
                    ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                ts_str = "-"
            
            messaggio = log.get("messaggio", "")
            if len(messaggio) > 100:
                messaggio = messaggio[:100] + "..."
            
            new_rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(ts_str, size=11)),
                        ft.DataCell(self._get_level_badge(log.get("livello", "INFO"))),
                        ft.DataCell(ft.Text(log.get("componente", "-"), size=11)),
                        ft.DataCell(ft.Text(messaggio, size=11)),
                    ],
                    on_select_changed=lambda e, l=log: self._show_log_details(l)
                )
            )
        
        self.logs_table.rows = new_rows
        self.pagination_text.value = f"Pagina {self.current_page + 1}"
    
    def _load_stats(self):
        """Carica le statistiche dei log."""
        stats = get_log_stats()
        
        if stats:
            counts = stats.get("count_per_livello", {})
            total = stats.get("totale_log", 0)
            
            stats_parts = [f"Totale: {total}"]
            for level in ["ERROR", "WARNING", "INFO"]:
                if level in counts:
                    stats_parts.append(f"{level}: {counts[level]}")
            
            self.stats_text.value = " | ".join(stats_parts)
        else:
            self.stats_text.value = "Nessuna statistica disponibile"
    
    def _on_filter_change(self, e):
        """Gestisce il cambio di filtro."""
        self.current_page = 0
        self._load_logs()
        self.page.update()
    
    def _on_prev_page(self, e):
        """Pagina precedente."""
        if self.current_page > 0:
            self.current_page -= 1
            self._load_logs()
            self.page.update()
    
    def _on_next_page(self, e):
        """Pagina successiva."""
        self.current_page += 1
        self._load_logs()
        self.page.update()
    
    def _on_refresh(self, e):
        """Ricarica i log."""
        self._load_logs()
        self._load_stats()
        self.page.update()
    
    def _on_cleanup_logs(self, e):
        """Esegue la pulizia manuale dei log vecchi."""
        deleted = cleanup_old_logs(days=30)
        self._load_logs()
        self._load_stats()
        self.page.update()
        
        # Mostra snackbar
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Eliminati {deleted} log più vecchi di 30 giorni"),
            bgcolor=ft.Colors.GREEN_400
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _show_log_details(self, log: dict):
        """Mostra i dettagli di un log in un dialog."""
        details = log.get("dettagli", {})
        details_text = ""
        
        if details:
            if isinstance(details, dict):
                for k, v in details.items():
                    details_text += f"{k}: {v}\n"
            else:
                details_text = str(details)
        else:
            details_text = "Nessun dettaglio disponibile"
        
        def close_dialog(e):
            self.page.close(dialog)
        
        dialog = ft.AlertDialog(
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
                ft.Text(details_text, size=10, selectable=True),
            ], scroll=ft.ScrollMode.AUTO, width=500, height=400),
            actions=[
                ft.TextButton("Chiudi", on_click=close_dialog)
            ]
        )
        
        self.page.open(dialog)
    
    def _close_dialog(self, dialog):
        """Chiude un dialog."""
        self.page.close(dialog)
    
    def build_view(self) -> ft.View:
        """Costruisce la vista del pannello admin."""
        # Carica dati iniziali
        self._load_components()
        self._load_logs()
        self._load_stats()
        
        return ft.View(
            "/admin",
            [
                ft.AppBar(
                    title=ft.Text("🔧 Admin Panel - Budget Amico", color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.BLUE_GREY_900,
                    actions=[
                        ft.IconButton(
                            icon=ft.Icons.LOGOUT,
                            icon_color=ft.Colors.WHITE,
                            tooltip="Logout Admin",
                            on_click=lambda e: self.on_logout()
                        )
                    ]
                ),
                ft.Container(
                    content=ft.Column([
                        # Header con statistiche
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.ANALYTICS, color=ft.Colors.BLUE_400),
                                self.stats_text,
                            ]),
                            padding=10,
                            bgcolor=ft.Colors.BLUE_GREY_50,
                            border_radius=8,
                        ),
                        
                        ft.Divider(),
                        
                        # Configurazione Logger
                        self._build_logger_config_section(),
                        
                        ft.Divider(),
                        
                        # Filtri
                        ft.Row([
                            self.level_dropdown,
                            self.component_dropdown,
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="Ricarica",
                                on_click=self._on_refresh
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_SWEEP,
                                tooltip="Pulisci log vecchi (>30 giorni)",
                                on_click=self._on_cleanup_logs
                            ),
                        ]),
                        
                        # Tabella log
                        ft.Container(
                            content=self.logs_table,
                            expand=True,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=8,
                        ),
                        
                        # Paginazione
                        ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_LEFT,
                                on_click=self._on_prev_page
                            ),
                            self.pagination_text,
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_RIGHT,
                                on_click=self._on_next_page
                            ),
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        
                    ], expand=True),
                    padding=20,
                    expand=True,
                )
            ],
            scroll=ft.ScrollMode.AUTO,
        )


class AdminLoginView:
    """Vista di login per l'admin di sistema."""
    
    def __init__(self, page: ft.Page, on_login_success):
        self.page = page
        self.on_login_success = on_login_success
        
        self.txt_username = ft.TextField(
            label="Username Admin",
            autofocus=True,
            width=300,
            on_submit=self._on_login
        )
        self.txt_password = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            width=300,
            on_submit=self._on_login
        )
        self.txt_error = ft.Text(visible=False, color=ft.Colors.RED_400)
    
    def _on_login(self, e):
        """Gestisce il tentativo di login."""
        username = self.txt_username.value.strip()
        password = self.txt_password.value
        
        if not username or not password:
            self.txt_error.value = "Inserisci username e password"
            self.txt_error.visible = True
            self.page.update()
            return
        
        if verifica_admin_sistema(username, password):
            self.page.session.set("admin_authenticated", True)
            self.on_login_success()
        else:
            self.txt_error.value = "Credenziali non valide"
            self.txt_error.visible = True
            self.page.update()
    
    def build_view(self) -> ft.View:
        """Costruisce la vista di login admin."""
        return ft.View(
            "/admin/login",
            [
                ft.Column([
                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS, size=80, color=ft.Colors.BLUE_400),
                    ft.Text("Admin Login", size=30, weight=ft.FontWeight.BOLD),
                    ft.Text("Accesso riservato agli amministratori di sistema", 
                           size=12, color=ft.Colors.GREY_600),
                    ft.Container(height=20),
                    self.txt_username,
                    self.txt_password,
                    self.txt_error,
                    ft.Container(height=10),
                    ft.ElevatedButton(
                        "Login",
                        icon=ft.Icons.LOGIN,
                        on_click=self._on_login,
                        width=300,
                    ),
                    ft.TextButton(
                        "Torna alla Home",
                        on_click=lambda e: self.page.go("/")
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                expand=True),
            ],
            vertical_alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
