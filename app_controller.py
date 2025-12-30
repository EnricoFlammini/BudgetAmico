import flet as ft
import datetime
import os
import traceback
import time
import shutil
import subprocess
import sys
from urllib.parse import urlparse, parse_qs
import threading

# Viste, Dialoghi e Utility
from views.auth_view import AuthView
from views.dashboard_view import DashboardView
from views.export_view import ExportView
from dialogs.transaction_dialog import TransactionDialog
from dialogs.conto_dialog import ContoDialog
from dialogs.admin_dialogs import AdminDialogs
from dialogs.portafoglio_dialogs import PortafoglioDialogs
from dialogs.prestito_dialogs import PrestitoDialogs
from dialogs.immobile_dialog import ImmobileDialog
from dialogs.fondo_pensione_dialog import FondoPensioneDialog
from dialogs.giroconto_dialog import GirocontoDialog
from dialogs.conto_condiviso_dialog import ContoCondivisoDialog
from dialogs.spesa_fissa_dialog import SpesaFissaDialog
from utils.localization import LocalizationManager
from utils.styles import LoadingOverlay
from db.gestione_db import (
    ottieni_prima_famiglia_utente, ottieni_ruolo_utente, check_e_paga_rate_scadute,
    check_e_processa_spese_fisse, get_user_count, crea_famiglia_e_admin,
    aggiungi_categorie_iniziali, cerca_utente_per_username, aggiungi_utente_a_famiglia,
    ottieni_versione_db, crea_invito, ottieni_invito_per_token,
    ottieni_utenti_senza_famiglia, ensure_family_key, trigger_budget_history_update
)

from utils.logger import setup_logger

logger = setup_logger("AppController")

URL_BASE = os.environ.get("FLET_APP_URL", "http://localhost:8550")
VERSION = "0.27.00"


class AppController:
    def __init__(self, page: ft.Page):
        self.page = page
        self.loc = LocalizationManager()
        
        logger.info(f"AppController initialized. Version: {VERSION}")

        # Controlli UI
        self.txt_nome_famiglia = ft.TextField(label="Nome della tua Famiglia", autofocus=True)
        self.txt_errore_setup = ft.Text(value="", visible=False)
        
        # Overlay di caricamento globale
        self.loading_overlay = LoadingOverlay()
        
        # Inizializza tutti i dialoghi e le viste
        self._init_dialogs_and_views()

    def _get_current_theme_scheme(self):
        """Restituisce lo schema di colori corrente in modo sicuro."""
        if self.page.theme_mode == ft.ThemeMode.DARK and self.page.dark_theme:
            return self.page.dark_theme.color_scheme
        if self.page.theme:
            return self.page.theme.color_scheme
        # Fallback di emergenza se nessun tema è ancora stato impostato
        return ft.ColorScheme()

    def _init_dialogs_and_views(self):
        # Inizializza i dialoghi
        self.transaction_dialog = TransactionDialog(self)
        self.conto_dialog = ContoDialog(self)
        self.admin_dialogs = AdminDialogs(self)
        self.portafoglio_dialogs = PortafoglioDialogs(self)
        self.prestito_dialogs = PrestitoDialogs(self)
        self.immobile_dialog = ImmobileDialog(self)
        self.fondo_pensione_dialog = FondoPensioneDialog(self)
        self.conto_condiviso_dialog = ContoCondivisoDialog(self)
        self.giroconto_dialog = GirocontoDialog(self)
        self.spesa_fissa_dialog = SpesaFissaDialog(self)

        # Inizializza le viste
        self.auth_view = AuthView(self)
        self.dashboard_view = DashboardView(self)
        self.export_view = ExportView(self)

        # Inizializza i dialoghi di conferma e picker
        self._init_global_dialogs()

    def _init_global_dialogs(self):
        # Aggiungi gli overlay globali una sola volta
        self.date_picker = ft.DatePicker(
            first_date=datetime.datetime(2020, 1, 1),
            last_date=datetime.datetime(2030, 12, 31),
            value=datetime.datetime.now()
        )
        self.file_picker_salva_excel = ft.FilePicker(on_result=self.on_file_picker_result)
        self.file_picker_salva_backup = ft.FilePicker(on_result=self._on_backup_dati_result)
        self.file_picker_apri_backup = ft.FilePicker(on_result=self._on_ripristina_dati_result)

        self.confirm_delete_dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Conferma Eliminazione"),
            content=ft.Text("Sei sicuro di voler eliminare questo elemento? L'azione è irreversibile."),
            actions=[
                ft.TextButton("Sì, Elimina", on_click=self._esegui_eliminazione_confermata),
                ft.TextButton("Annulla", on_click=self._chiudi_dialog_conferma_eliminazione),
            ], actions_alignment=ft.MainAxisAlignment.END
        )
        self.error_dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Errore"), content=ft.Text(""),
            actions=[ft.TextButton("Chiudi", on_click=self._close_error_dialog)]
        )
        # Info dialog con pulsanti manuali
        self.info_dialog_content = ft.Column([
            ft.Text("", key="version_text"),
            ft.Divider(height=20),
            ft.Text("📚 Manuali Utente", weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.ElevatedButton(
                    "📖 Guida Rapida",
                    icon=ft.Icons.MENU_BOOK,
                    on_click=lambda e: self._apri_manuale("guida_rapida")
                ),
                ft.ElevatedButton(
                    "📚 Manuale Completo",
                    icon=ft.Icons.LIBRARY_BOOKS,
                    on_click=lambda e: self._apri_manuale("manuale_completo")
                ),
            ], wrap=True, spacing=10),
        ], tight=True, spacing=10)
        
        self.info_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Informazioni"),
            content=self.info_dialog_content,
            actions=[ft.TextButton("Chiudi", on_click=self._chiudi_info_dialog)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.extend([
            self.transaction_dialog, self.conto_dialog, self.conto_dialog.dialog_rettifica_saldo,
            self.admin_dialogs.dialog_modifica_cat, self.admin_dialogs.dialog_sottocategoria,
            self.admin_dialogs.dialog_modifica_ruolo, self.admin_dialogs.dialog_invito_membri,
            self.portafoglio_dialogs.dialog_portafoglio,
            self.portafoglio_dialogs.dialog_operazione_asset, self.portafoglio_dialogs.dialog_aggiorna_prezzo,
            self.portafoglio_dialogs.dialog_modifica_asset, self.date_picker, self.file_picker_salva_excel,
            self.prestito_dialogs.dialog_prestito, self.prestito_dialogs.dialog_paga_rata,
            self.immobile_dialog, self.fondo_pensione_dialog, self.giroconto_dialog,
            self.conto_condiviso_dialog, self.spesa_fissa_dialog, self.confirm_delete_dialog,
            self.file_picker_salva_backup, self.file_picker_apri_backup, self.error_dialog
            # NOTE: info_dialog e loading_overlay sono gestiti dinamicamente
        ])

    def on_file_picker_result(self, e: ft.FilePickerResultEvent):
        try:
            file_data = self.page.session.get("excel_export_data")
            if e.path and file_data:
                with open(e.path, "wb") as f: f.write(file_data)
                self.show_snack_bar(f"File salvato in: {e.path}", success=True)
                self.page.session.remove("excel_export_data")
            else:
                self.show_snack_bar("Salvataggio annullato.", success=False)
        except PermissionError:
            logger.error(f"Errore permesso salvataggio file: {e.path}")
            filename = os.path.basename(e.path) if e.path else "il file"
            self.show_error_dialog(f"Impossibile salvare il file.\nÈ probabile che '{filename}' sia aperto in un altro programma (es. Excel).\nChiudilo e riprova.")
        except Exception as ex:
            logger.error(f"Errore durante il salvataggio file: {ex}")
            self.show_error_dialog(f"Errore durante il salvataggio: {ex}")
        finally:
            self.page.update()

    def route_change(self, route):
        try:
            self.page.views.clear()
            logger.debug(f"Route changed to: {route.route}")
            
            parsed_url = urlparse(route.route)
            route_path = parsed_url.path
            query_params = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}

            if query_params.get("token") and route_path == "/registrazione":
                self._handle_registration_token(query_params["token"])
            elif route_path == "/":
                self.page.views.append(self.auth_view.get_login_view())
            elif route_path == "/registrazione":
                self.page.views.append(self.auth_view.get_registration_view())
            elif route_path == "/setup-admin":
                self.page.views.append(self.build_setup_view())
            elif route_path == "/in-attesa":
                self.page.views.append(self.build_attesa_view())
            elif route_path == "/dashboard":
                if not self.get_user_id() or not self.get_family_id():
                    self.page.go("/")
                    return
                self._carica_dashboard()
            elif route_path == "/export":
                if not self.get_user_id() or not self.get_family_id():
                    self.page.go("/")
                    return
                self.export_view.update_view_data()
                self.page.views.append(self.export_view.build_view())
            elif route_path == "/password-recovery":
                self.page.views.append(self.auth_view.get_password_recovery_view())
            elif route_path == "/force-change-password":
                if not self.get_user_id():
                    self.page.go("/")
                    return
                self.page.views.append(self.auth_view.get_force_change_password_view())
            else:
                self.page.go("/")
            self.page.update()
        except Exception as e:
            logger.critical(f"Errore in route_change: {e}")
            logger.error(traceback.format_exc())
        finally:
            self.hide_loading()

    def _handle_registration_token(self, token):
        invito_data = ottieni_invito_per_token(token)
        if invito_data:
            self.page.session.set("invito_attivo", invito_data)
            self.show_snack_bar(f"Invito per la famiglia ID: {invito_data['id_famiglia']} caricato.", success=True)
            self.page.views.append(self.auth_view.get_registration_view())
        else:
            self.show_snack_bar("Link di invito non valido o già utilizzato.", success=False)
            self.page.go("/")

    def _carica_dashboard(self):
        self.page.views.clear()
        
        # RE-CREATE DASHBOARD VIEW TO ENSURE FRESH STATE (Fixes data leakage)
        # Re-inizializza la vista e tutte le tab per garantire che non ci siano dati residui
        self.dashboard_view = DashboardView(self)
        
        self.page.views.append(self.dashboard_view.build_view())
        self.dashboard_view.update_sidebar()
        
        # Force immediate UI update to show dashboard structure and remove spinner
        self.page.update()
        self.hide_loading()

        saved_lang = self.page.client_storage.get("settings.language")
        if saved_lang: self.loc.set_language(saved_lang)
        saved_currency = self.page.client_storage.get("settings.currency")
        if saved_currency: self.loc.set_currency(saved_currency)

        id_famiglia = self.get_family_id()
        if id_famiglia:
            # Note: These checks are still synchronous but usually fast. 
            # Could be moved to async if needed, but low priority.
            pagamenti_fatti = check_e_paga_rate_scadute(id_famiglia)
            master_key_b64 = self.page.session.get("master_key")
            id_utente = self.get_user_id()
            spese_fisse_eseguite = check_e_processa_spese_fisse(id_famiglia, master_key_b64=master_key_b64, id_utente=id_utente)
            if pagamenti_fatti > 0: self.show_snack_bar(f"{pagamenti_fatti} pagamenti rata automatici eseguiti.", success=True)
            if spese_fisse_eseguite > 0: self.show_snack_bar(f"{spese_fisse_eseguite} spese fisse automatiche eseguite.", success=True)

        self.update_all_views(is_initial_load=True)
        self.page.update()
        
        # Aggiorna prezzi asset in background (non blocca UI)
        self._aggiorna_prezzi_asset_in_background()
        
        # Controlla aggiornamenti in background
        self._controlla_aggiornamenti_in_background()

    def _aggiorna_prezzi_asset_in_background(self):
        """Aggiorna i prezzi degli asset nel portafoglio in background."""
        from utils.async_task import AsyncTask
        from utils.yfinance_manager import ottieni_prezzi_multipli
        from db.gestione_db import ottieni_dettagli_conti_utente, ottieni_portafoglio, aggiorna_prezzo_manuale_asset
        
        utente_id = self.get_user_id()
        master_key_b64 = self.page.session.get("master_key")
        
        if not utente_id:
            return
        
        def _sync_prezzi():
            try:
                # Ottieni tutti i conti di investimento
                conti_utente = ottieni_dettagli_conti_utente(utente_id, master_key_b64=master_key_b64)
                conti_investimento = [c for c in conti_utente if c['tipo'] == 'Investimento']
                
                # Raccogli tutti i ticker unici
                tutti_asset = []
                for conto in conti_investimento:
                    portafoglio = ottieni_portafoglio(conto['id_conto'], master_key_b64=master_key_b64)
                    tutti_asset.extend(portafoglio)
                
                if not tutti_asset:
                    return 0
                
                # Ottieni prezzi per tutti i ticker
                tickers = list(set([asset['ticker'] for asset in tutti_asset]))
                logger.info(f"Aggiornamento automatico prezzi per {len(tickers)} ticker...")
                prezzi = ottieni_prezzi_multipli(tickers)
                
                # Aggiorna i prezzi nel database
                aggiornati = 0
                for asset in tutti_asset:
                    ticker = asset['ticker']
                    if ticker in prezzi and prezzi[ticker] is not None:
                        aggiorna_prezzo_manuale_asset(asset['id_asset'], prezzi[ticker])
                        aggiornati += 1
                
                return aggiornati
            except Exception as e:
                logger.error(f"Errore aggiornamento prezzi in background: {e}")
                return 0
        
        def _on_complete(aggiornati):
            if aggiornati > 0:
                logger.info(f"Prezzi asset aggiornati: {aggiornati}")
                self.show_snack_bar(f"Prezzi asset aggiornati ({aggiornati})", success=True)
                # Refresh tab investimenti se visibile
                if hasattr(self.dashboard_view, 'tab_contents') and 'Investimenti' in self.dashboard_view.tab_contents:
                    self.dashboard_view.tab_contents['Investimenti'].update_view_data()
        
        def _on_error(e):
            logger.error(f"Errore sync prezzi: {e}")
        
        # Avvia in background
        task = AsyncTask(target=_sync_prezzi, callback=_on_complete, error_callback=_on_error)
        task.start()

    def _controlla_aggiornamenti_in_background(self):
        """Controlla se ci sono aggiornamenti disponibili su GitHub."""
        from utils.async_task import AsyncTask
        from utils.update_checker import check_for_updates
        
        def _check_updates():
            return check_for_updates(VERSION)
        
        def _on_update_available(update_info):
            if update_info:
                logger.info(f"Aggiornamento disponibile: {update_info['version']}")
                self._mostra_banner_aggiornamento(update_info)
        
        def _on_error(e):
            logger.debug(f"Controllo aggiornamenti fallito: {e}")
        
        # Avvia in background
        task = AsyncTask(target=_check_updates, callback=_on_update_available, error_callback=_on_error)
        task.start()
    
    def _mostra_banner_aggiornamento(self, update_info):
        """Mostra un banner nella dashboard per l'aggiornamento disponibile."""
        import webbrowser
        
        version = update_info.get('version', 'Nuova versione')
        download_url = update_info.get('download_url') or update_info.get('html_url')
        
        def _on_scarica(e):
            if download_url:
                webbrowser.open(download_url)
                self.show_snack_bar("Apertura pagina download...", success=True)
        
        def _on_ignora(e):
            # Rimuovi il banner
            if hasattr(self.dashboard_view, 'update_banner') and self.dashboard_view.update_banner:
                self.dashboard_view.update_banner.visible = False
                self.page.update()
        
        # Crea il banner
        banner = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SYSTEM_UPDATE, color=ft.Colors.WHITE),
                ft.Text(
                    f"🎉 Nuova versione {version} disponibile!",
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.BOLD,
                    expand=True
                ),
                ft.TextButton(
                    "Scarica",
                    style=ft.ButtonStyle(color=ft.Colors.WHITE),
                    on_click=_on_scarica
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_color=ft.Colors.WHITE,
                    on_click=_on_ignora
                )
            ], alignment=ft.MainAxisAlignment.START),
            bgcolor=ft.Colors.BLUE_700,
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
            border_radius=ft.border_radius.only(bottom_left=8, bottom_right=8),
        )
        
        # Aggiungi alla dashboard
        if hasattr(self.dashboard_view, 'set_update_banner'):
            self.dashboard_view.set_update_banner(banner)
            self.page.update()

    def _download_confirmato(self, e): pass
    def _download_rifiutato(self, e): pass

    def backup_dati_clicked(self):
        self.show_snack_bar("Funzionalità di backup non disponibile con PostgreSQL.", success=False)

    def _on_backup_dati_result(self, e: ft.FilePickerResultEvent):
        if not e.path:
            self.show_snack_bar("Operazione di backup annullata.", success=False)
            return
        try:
            # shutil.copyfile(DB_FILE, e.path) # No direct file copy for Postgres
             self.show_snack_bar(f"Backup creato con successo in: {e.path}", success=True)
        except Exception as ex:
            logger.error(f"Errore backup: {ex}")
            self.show_error_dialog(f"Errore durante la creazione del backup: {ex}")

    def ripristina_dati_clicked(self):
        self.show_snack_bar("Funzionalità di ripristino non disponibile con PostgreSQL.", success=False)

    def _on_ripristina_dati_result(self, e: ft.FilePickerResultEvent):
        pass # Placeholder

    def _chiudi_dialog_conferma_ripristino(self, e):
        pass # Placeholder

    def _ripristino_confermato(self, e):
        pass # Placeholder

    def open_info_dialog(self, e):
        logger.debug(f"[OVERLAY] open_info_dialog called.")
        db_version = ottieni_versione_db()
        # Aggiorna il testo della versione nel dialog
        version_text = self.info_dialog_content.controls[0]
        version_text.value = f"Versione App: {VERSION}\nVersione Database: {db_version}\n\nSviluppato da Iscavar79."
        # Usa page.open() - pattern moderno di Flet
        self.page.open(self.info_dialog)
    
    def _apri_manuale(self, tipo: str):
        """Apre il manuale (HTML, PDF o Markdown)."""
        try:
            # Determina il nome base del file
            if tipo == "guida_rapida":
                basename = "Guida_Rapida_Budget_Amico"
            else:
                basename = "Manuale_Completo_Budget_Amico"
            
            # Ordine di preferenza: HTML > PDF > Markdown
            extensions = [".html", ".pdf", ".md"]
            
            # Cerca il file nella cartella docs con le diverse estensioni
            found_path = None
            found_filename = None
            
            for ext in extensions:
                filename = basename + ext
                possible_paths = [
                    # Percorso in sviluppo
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", filename),
                    # Percorso in produzione (PyInstaller --onedir)
                    os.path.join(os.path.dirname(sys.executable), "docs", filename),
                    # Percorso alternativo PyInstaller
                    os.path.join(getattr(sys, '_MEIPASS', ''), "docs", filename) if hasattr(sys, '_MEIPASS') else None,
                ]
                
                for path in possible_paths:
                    if path and os.path.exists(path):
                        found_path = path
                        found_filename = filename
                        break
                
                if found_path:
                    break
            
            if found_path:
                logger.info(f"Apertura manuale: {found_path}")
                # Apri con l'applicazione predefinita
                if sys.platform == 'win32':
                    os.startfile(found_path)
                elif sys.platform == 'darwin':  # macOS
                    subprocess.run(['open', found_path])
                else:  # Linux
                    subprocess.run(['xdg-open', found_path])
                self.show_snack_bar(f"Apertura {found_filename}...", success=True)
            else:
                self.show_snack_bar("Manuale non trovato. Verifica l'installazione.", success=False)
                logger.warning(f"Manuale non trovato: {basename}")
        except Exception as ex:
            logger.error(f"Errore apertura manuale: {ex}")
            self.show_snack_bar(f"Errore apertura manuale: {ex}", success=False)

    def _chiudi_info_dialog(self, e):
        logger.debug("[OVERLAY] _chiudi_info_dialog called.")
        # Usa page.close() - rimuove automaticamente dall'overlay
        self.page.close(self.info_dialog)

    def _close_error_dialog(self, e):
        self.error_dialog.open = False
        self.page.update()
        if self.error_dialog in self.page.overlay:
            self.page.overlay.remove(self.error_dialog)
        self.page.update()

    def show_error_dialog(self, message):
        logger.error(f"[UI ERROR] {message}")
        self.error_dialog.content.value = str(message)
        if self.error_dialog not in self.page.overlay:
            self.page.overlay.append(self.error_dialog)
        self.error_dialog.open = True
        self.page.update()

    def open_confirm_delete_dialog(self, delete_callback):
        theme = self._get_current_theme_scheme() or ft.ColorScheme()
        self.confirm_delete_dialog.actions[0].style = ft.ButtonStyle(color=theme.error)
        self.page.session.set("delete_callback", delete_callback)
        if self.confirm_delete_dialog not in self.page.overlay:
            self.page.overlay.append(self.confirm_delete_dialog)
        self.confirm_delete_dialog.open = True
        self.page.update()

    def _chiudi_dialog_conferma_eliminazione(self, e):
        self.confirm_delete_dialog.open = False
        self.page.update()

    def _esegui_eliminazione_confermata(self, e):
        # Prima chiudo il dialog
        self.confirm_delete_dialog.open = False
        self.page.update()
        # Poi mostro lo spinner per l'operazione
        self.show_loading("Eliminazione in corso...")
        try:
            delete_callback = self.page.session.get("delete_callback")
            if callable(delete_callback): delete_callback()
        except Exception as ex:
             logger.error(f"Errore durant eliminazione: {ex}")
             self.show_error_dialog(f"Errore imprevisto: {ex}")
        finally:
            self.hide_loading()

    def post_login_setup(self, utente):
        id_utente = utente['id']
        id_famiglia = ottieni_prima_famiglia_utente(id_utente)
        self.page.session.set("utente_loggato", utente)
        
        # Save master_key to session for encryption/decryption
        if utente.get("master_key"):
            logger.debug(f"Salvataggio Master Key in sessione (masked).")
            self.page.session.set("master_key", utente["master_key"])
        else:
            logger.warning("ATTENZIONE: Nessuna Master Key trovata nell'oggetto utente!")

        if utente.get("forza_cambio_password"):
            self.page.go("/force-change-password")
            return

        if id_famiglia:
            # Ensure encryption key for family exists
            if utente.get("master_key"):
                ensure_family_key(id_utente, id_famiglia, utente["master_key"])

            self.page.session.set("id_famiglia", id_famiglia)
            self.page.session.set("ruolo_utente", ottieni_ruolo_utente(id_utente, id_famiglia))
            
            # --- Auto-Update History Snapshot on Login ---
            try:
                from utils.async_task import AsyncTask
                def _bg_budget_update():
                    master_key_b64 = utente.get("master_key")
                    now = datetime.datetime.now()
                    trigger_budget_history_update(id_famiglia, now, master_key_b64, id_utente)
                
                AsyncTask(target=_bg_budget_update).start()
            except Exception as e:
                logger.warning(f"Failed background budget update on login: {e}")

            self.page.go("/dashboard")
        else:
            # Se l'utente non ha una famiglia, lo reindirizziamo alla creazione
            self.page.go("/setup-admin")

    def build_setup_view(self) -> ft.View:
        self.txt_nome_famiglia.value = ""
        self.txt_errore_setup.visible = False
        theme = self._get_current_theme_scheme() or ft.ColorScheme()
        self.txt_errore_setup.color = theme.error

        return ft.View("/setup-admin", [
            ft.Column([
                ft.Text("Benvenuto!", size=30, weight=ft.FontWeight.BOLD),
                ft.Text("Crea la tua Famiglia per iniziare."),
                ft.Container(height=20),
                self.txt_nome_famiglia,
                self.txt_errore_setup,
                ft.Container(height=10),
                ft.ElevatedButton("Crea Famiglia e Continua", icon=ft.Icons.ROCKET_LAUNCH, on_click=self._completa_setup_admin, width=350),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, expand=True, width=350)
        ], vertical_alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _completa_setup_admin(self, e):
        nome_famiglia = self.txt_nome_famiglia.value
        if not nome_famiglia:
            self.txt_errore_setup.value = "Il nome della famiglia è obbligatorio."
            self.txt_errore_setup.visible = True
            self.page.update()
            return

        utente = self.page.session.get("utente_loggato")
        if not utente:
            self.page.go("/")
            return

        try:
            master_key_b64 = self.page.session.get("master_key")
            new_family_id = crea_famiglia_e_admin(nome_famiglia, utente['id'], master_key_b64=master_key_b64)
            if not new_family_id: raise Exception("Creazione famiglia fallita. Nome duplicato?")
            
            aggiungi_categorie_iniziali(new_family_id)
            self.page.session.set("id_famiglia", new_family_id)
            self.page.session.set("ruolo_utente", "admin")
            self.show_snack_bar(f"Famiglia '{nome_famiglia}' creata! Ora crea il tuo primo conto.", success=True)
            self.page.go("/dashboard")
        except Exception as ex:
            logger.error(f"Errore creazione famiglia: {ex}")
            self.txt_errore_setup.value = f"Errore: {ex}"
            self.txt_errore_setup.visible = True
            self.page.update()

    def build_attesa_view(self) -> ft.View:
        utente = self.page.session.get("utente_loggato")
        username = utente['username'] if utente else "utente"
        theme = self._get_current_theme_scheme() or ft.ColorScheme()
        return ft.View("/in-attesa", [
            ft.Column([
                ft.Icon(ft.Icons.TIMER, size=60, color=theme.secondary),
                ft.Text(f"Ciao, {username}!", size=30, weight=ft.FontWeight.BOLD),
                ft.Text("La tua registrazione è completata."),
                ft.Text("Chiedi all'amministratore della tua famiglia di aggiungerti.", text_align=ft.TextAlign.CENTER, width=300),
                ft.Text(f"L'amministratore dovrà cercarti usando il tuo username: '{username}'", text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.BOLD, width=300),
                ft.Container(height=20),
                ft.TextButton("Logout", icon=ft.Icons.LOGOUT, on_click=self.logout)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, expand=True, spacing=10)
        ], vertical_alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def logout(self, e=None):
        logger.info("User logged out")
        self.page.session.clear()
        self.page.go("/")

    def update_all_views(self, is_initial_load=False):
        if self.dashboard_view:
            self.dashboard_view.update_all_tabs_data(is_initial_load)
        if not is_initial_load:
            self.page.update()

    def db_write_operation(self):
        """Chiamato dopo operazioni di scrittura sul database."""
        self.show_loading("Salvataggio...")
        try:
            self.update_all_views()
        finally:
            self.hide_loading()

    def show_snack_bar(self, messaggio, success=True):
        logger.debug(f"show_snack_bar: messaggio='{messaggio}', success={success}")
        theme = self._get_current_theme_scheme() or ft.ColorScheme()
        snack = ft.SnackBar(
            content=ft.Text(messaggio),
            bgcolor=theme.primary_container if success else theme.error_container,
            duration=3000  # 3 secondi
        )
        # Usa page.open() - pattern moderno di Flet
        self.page.open(snack)

    def show_loading(self, messaggio: str = "Attendere..."):
        """Mostra l'overlay di caricamento che blocca l'interfaccia."""
        logger.debug(f"[OVERLAY] show_loading called: msg={messaggio}")
        # Aggiungi all'overlay se non presente
        if self.loading_overlay not in self.page.overlay:
            self.page.overlay.append(self.loading_overlay)
        self.loading_overlay.show(messaggio)
        self.page.update()

    def hide_loading(self):
        """Nasconde e rimuove l'overlay di caricamento."""
        logger.debug("[OVERLAY] hide_loading called")
        self.loading_overlay.hide()
        # Rimuovi dall'overlay per evitare il rettangolo grigio
        if self.loading_overlay in self.page.overlay:
            self.page.overlay.remove(self.loading_overlay)
        self.page.update()

    def get_user_id(self):
        utente = self.page.session.get("utente_loggato")
        return utente['id'] if utente else None

    def get_family_id(self):
        return self.page.session.get("id_famiglia")

    def get_user_role(self):
        return self.page.session.get("ruolo_utente")

    def gestisci_invito_o_sblocco(self, input_val, ruolo):
        """
        Gestisce l'invito di un nuovo membro o l'aggiunta di un utente esistente.
        input_val: username o email
        ruolo: ruolo da assegnare
        """
        id_famiglia = self.get_family_id()
        if not id_famiglia:
            return "Errore: Nessuna famiglia selezionata.", False

        # 1. Cerca se esiste un utente con questo username
        utente_esistente = cerca_utente_per_username(input_val)
        
        if utente_esistente:
            # Utente trovato e non ha famiglia -> Aggiungi direttamente
            success = aggiungi_utente_a_famiglia(id_famiglia, utente_esistente['id_utente'], ruolo)
            if success:
                return f"Utente {input_val} aggiunto alla famiglia!", True
            else:
                return "Errore durante l'aggiunta dell'utente.", False
        
        # 2. Se non è un utente esistente, prova a creare un invito via email
        if "@" in input_val and "." in input_val:
            utente = self.page.session.get("utente_loggato")
            master_key_b64 = self.page.session.get("master_key")
            token = crea_invito(id_famiglia, input_val, ruolo, id_admin=utente['id'] if utente else None, master_key_b64=master_key_b64)
            if token:
                link_invito = f"{URL_BASE}/registrazione?token={token}"
                self.page.set_clipboard(link_invito)
                return f"Invito creato! Link copiato negli appunti.", True
            else:
                return "Errore durante la creazione dell'invito.", False
        
        return "Utente non trovato e indirizzo email non valido.", False

    def get_users_without_family(self):
        """Restituisce la lista di username degli utenti senza famiglia."""
        return ottieni_utenti_senza_famiglia()