import flet as ft
import datetime
import os
import traceback
import time
import shutil
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
    ottieni_utenti_senza_famiglia, ensure_family_key
)

URL_BASE = os.environ.get("FLET_APP_URL", "http://localhost:8550")
VERSION = "0.12.0"


class AppController:
    def __init__(self, page: ft.Page):
        self.page = page
        self.loc = LocalizationManager()

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
        self.info_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Informazioni"),
            content=ft.Text(""),
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
            self.file_picker_salva_backup, self.file_picker_apri_backup, self.error_dialog, self.info_dialog,
            self.loading_overlay
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
        except Exception as ex:
            self.show_error_dialog(f"Errore durante il salvataggio: {ex}")

    def route_change(self, route):
        try:
            self.page.views.clear()
            # self.page.overlay.clear()  # Removed because it deletes global dialogs!
            
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
            print(f"[ERRORE CRITICO] Errore in route_change: {e}")
            traceback.print_exc()

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
        # Mostra spinner durante il caricamento della dashboard
        self.show_loading("Caricamento dati...")
        
        try:
            self.page.views.clear()
            self.page.views.append(self.dashboard_view.build_view())
            self.dashboard_view.update_sidebar()

            saved_lang = self.page.client_storage.get("settings.language")
            if saved_lang: self.loc.set_language(saved_lang)
            saved_currency = self.page.client_storage.get("settings.currency")
            if saved_currency: self.loc.set_currency(saved_currency)

            id_famiglia = self.get_family_id()
            if id_famiglia:
                pagamenti_fatti = check_e_paga_rate_scadute(id_famiglia)
                master_key_b64 = self.page.session.get("master_key")
                id_utente = self.get_user_id()
                spese_fisse_eseguite = check_e_processa_spese_fisse(id_famiglia, master_key_b64=master_key_b64, id_utente=id_utente)
                if pagamenti_fatti > 0: self.show_snack_bar(f"{pagamenti_fatti} pagamenti rata automatici eseguiti.", success=True)
                if spese_fisse_eseguite > 0: self.show_snack_bar(f"{spese_fisse_eseguite} spese fisse automatiche eseguite.", success=True)

            self.update_all_views(is_initial_load=True)
            self.page.update()
        finally:
            self.hide_loading()

    def _download_confirmato(self, e): pass
    def _download_rifiutato(self, e): pass

    def backup_dati_clicked(self):
        self.show_snack_bar("Funzionalità di backup non disponibile con PostgreSQL.", success=False)
        # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # self.file_picker_salva_backup.save_file(
        #     dialog_title="Salva Backup Database",
        #     file_name=f"budget_backup_{timestamp}.db",
        #     allowed_extensions=["db"]
        # )

    def _on_backup_dati_result(self, e: ft.FilePickerResultEvent):
        if not e.path:
            self.show_snack_bar("Operazione di backup annullata.", success=False)
            return
        try:
            shutil.copyfile(DB_FILE, e.path)
            self.show_snack_bar(f"Backup creato con successo in: {e.path}", success=True)
        except Exception as ex:
            self.show_error_dialog(f"Errore durante la creazione del backup: {ex}")

    def ripristina_dati_clicked(self):
        self.show_snack_bar("Funzionalità di ripristino non disponibile con PostgreSQL.", success=False)
        # self.file_picker_apri_backup.pick_files(
        #     dialog_title="Seleziona un file di Backup (.db)",
        #     allow_multiple=False,
        #     allowed_extensions=["db"]
        # )

    def _on_ripristina_dati_result(self, e: ft.FilePickerResultEvent):
        if not e.files:
            self.show_snack_bar("Nessun file di backup selezionato.", success=False)
            return
        self.backup_path_da_ripristinare = e.files[0].path
        self.backup_path_da_ripristinare = e.files[0].path
        if self.confirm_restore_dialog not in self.page.overlay:
            self.page.overlay.append(self.confirm_restore_dialog)
        self.confirm_restore_dialog.open = True
        self.page.update()

    def _chiudi_dialog_conferma_ripristino(self, e):
        self.confirm_restore_dialog.open = False
        self.backup_path_da_ripristinare = None
        self.page.update()
        if self.confirm_restore_dialog in self.page.overlay:
            self.page.overlay.remove(self.confirm_restore_dialog)
        self.page.update()

    def _ripristino_confermato(self, e):
        backup_path = self.backup_path_da_ripristinare
        self.confirm_restore_dialog.open = False
        self.page.update()
        if self.confirm_restore_dialog in self.page.overlay:
            self.page.overlay.remove(self.confirm_restore_dialog)
        self.page.update()
        if not backup_path: return

        try:
            temp_db_path = DB_FILE + ".temp_schema"
            setup_database(temp_db_path)
            versione_app = ottieni_versione_db(temp_db_path)
            os.remove(temp_db_path)
            versione_backup = ottieni_versione_db(backup_path)

            if versione_backup > versione_app:
                self.show_error_dialog("Errore: Il backup è di una versione più recente dell'app!")
                return

            if versione_backup < versione_app:
                if not migra_database(backup_path, versione_backup, versione_app):
                    self.show_error_dialog("❌ Errore critico durante la migrazione del database.")
                    return

            shutil.copyfile(backup_path, DB_FILE)
            self.show_snack_bar("Ripristino completato. L'app verrà ricaricata.", success=True)
            time.sleep(2)
            self.page.go("/")
        except Exception as ex:
            self.show_error_dialog(f"Errore durante il ripristino: {ex}")
        finally:
            self.backup_path_da_ripristinare = None

    def open_info_dialog(self, e):
        db_version = ottieni_versione_db()
        self.info_dialog.content.value = f"Versione App: {VERSION}\nVersione Database: {db_version}\n\nSviluppato da Iscavar79."
        self.info_dialog.content.value = f"Versione App: {VERSION}\nVersione Database: {db_version}\n\nSviluppato da Iscavar79."
        if self.info_dialog not in self.page.overlay:
            self.page.overlay.append(self.info_dialog)
        self.info_dialog.open = True
        self.page.update()

    def _chiudi_info_dialog(self, e):
        self.info_dialog.open = False
        self.hide_loading()  # Safety: nasconde loading se visibile
        self.page.update()
        if self.info_dialog in self.page.overlay:
            self.page.overlay.remove(self.info_dialog)
        self.page.update()

    def _close_error_dialog(self, e):
        self.error_dialog.open = False
        self.page.update()
        if self.error_dialog in self.page.overlay:
            self.page.overlay.remove(self.error_dialog)
        self.page.update()

    def show_error_dialog(self, message):
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
        self.show_loading("Attendere...")
        try:
            delete_callback = self.page.session.get("delete_callback")
            if callable(delete_callback): delete_callback()
        finally:
            self.hide_loading()

    def post_login_setup(self, utente):
        id_utente = utente['id']
        id_famiglia = ottieni_prima_famiglia_utente(id_utente)
        self.page.session.set("utente_loggato", utente)
        
        # Save master_key to session for encryption/decryption
        if utente.get("master_key"):
            print(f"[DEBUG] Salvataggio Master Key in sessione. Valore: {utente['master_key'][:10]}...")
            self.page.session.set("master_key", utente["master_key"])
        else:
            print("[DEBUG] ATTENZIONE: Nessuna Master Key trovata nell'oggetto utente!")

        if utente.get("forza_cambio_password"):
            self.page.go("/force-change-password")
            return

        if id_famiglia:
            # Ensure encryption key for family exists
            if utente.get("master_key"):
                ensure_family_key(id_utente, id_famiglia, utente["master_key"])

            self.page.session.set("id_famiglia", id_famiglia)
            self.page.session.set("ruolo_utente", ottieni_ruolo_utente(id_utente, id_famiglia))
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
        self.page.session.clear()
        self.page.go("/")

    def update_all_views(self, is_initial_load=False):
        if self.dashboard_view:
            self.dashboard_view.update_all_tabs_data(is_initial_load)
        if not is_initial_load:
            self.page.update()

    def db_write_operation(self):
        """Chiamato dopo operazioni di scrittura sul database."""
        self.show_loading("Attendere...")
        try:
            self.update_all_views()
        finally:
            self.hide_loading()

    def show_snack_bar(self, messaggio, success=True):
        theme = self._get_current_theme_scheme() or ft.ColorScheme()
        self.page.snack_bar = ft.SnackBar(
            ft.Text(messaggio),
            bgcolor=theme.primary_container if success else theme.error_container
        )
        self.page.snack_bar.open = True
        self.page.update()

    def show_loading(self, messaggio: str = "Attendere..."):
        """Mostra l'overlay di caricamento che blocca l'interfaccia."""
        self.loading_overlay.show(messaggio)
        self.page.update()

    def hide_loading(self):
        """Nasconde l'overlay di caricamento."""
        self.loading_overlay.hide()
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