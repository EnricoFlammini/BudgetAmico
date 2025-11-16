import flet as ft
import datetime
import os
from dateutil import parser as date_parser
import time
import shutil  # Per copiare i file
from urllib.parse import urlparse, parse_qs
import threading  # Importa il modulo per il multithreading

# Importa le VISTE (Pagine)
from views.auth_view import AuthView
from views.dashboard_view import DashboardView
from views.export_view import ExportView

# Importa i DIALOGHI (Popup)
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

# --- UTILITY AGGIUNTE ---
from utils.gmail_sender import send_email_via_gmail_api
from utils.localization import LocalizationManager
from db.migration_manager import migra_database

# Recupera l'URL base (aggiorna se necessario)
URL_BASE = os.environ.get("FLET_APP_URL", "http://localhost:8550")

# --- VERSIONE PROGRAMMA ---
VERSION = "1.0.0"

# --- IMPORT GESTIONE DB (AGGIORNATI) ---
from db.gestione_db import (
    ottieni_prima_famiglia_utente,
    ottieni_ruolo_utente,
    check_e_paga_rate_scadute,
    check_e_processa_spese_fisse,
    get_user_count,
    crea_famiglia_e_admin,
    aggiungi_conto,
    aggiungi_categorie_iniziali,
    # Funzioni di gestione Inviti/Membri
    cerca_utente_per_username,
    aggiungi_utente_a_famiglia,
    ottieni_versione_db,
    crea_invito,
    ottieni_invito_per_token,
    # Funzioni per Setup Minimo
    aggiungi_saldo_iniziale,
    DB_FILE
)
from db.crea_database import setup_database

# --- ALTRI IMPORT... ---
import google_auth_manager
import google_drive_manager


class AppController:
    def __init__(self, page: ft.Page):
        # Imposta la pagina come PRIMA cosa, così è disponibile per tutti gli altri componenti.
        self.page = page

        # --- NUOVO: Gestore della Localizzazione ---
        self.loc = LocalizationManager()

        # --- Variabili per la vista di setup (SETUP MINIMO) ---
        self.txt_nome_famiglia = ft.TextField(label="Nome della tua Famiglia", autofocus=True)
        self.txt_errore_setup = ft.Text(value="", color=ft.Colors.RED_500, visible=False)

        # --- Variabili per il Setup Iniziale del Conto (se lo si reintroducesse)
        self.txt_nome_conto = ft.TextField(label="Nome Conto Principale", value="Conto Principale")
        self.txt_saldo_iniziale = ft.TextField(
            label="Saldo Iniziale",
            prefix="€",
            value="0.00",
            keyboard_type=ft.KeyboardType.NUMBER
        )

        # --- NUOVO DIALOGO DI CONFERMA SYNC ---
        self.confirm_download_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Versione più recente trovata"),
            content=ft.Text(
                "Su Google Drive è presente una versione più recente del database.\n\nVuoi scaricarla e sovrascrivere i dati locali?"),
            actions=[
                ft.TextButton("Sì, Scarica", on_click=self._download_confirmato),
                ft.TextButton("No, ignora", on_click=self._download_rifiutato),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.remote_file_to_download_id = None

        # --- NUOVI DIALOGHI E PICKER PER BACKUP/RESTORE ---
        self.file_picker_salva_backup = ft.FilePicker(on_result=self._on_backup_dati_result)
        self.file_picker_apri_backup = ft.FilePicker(on_result=self._on_ripristina_dati_result)
        self.confirm_restore_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Conferma Ripristino"),
            content=ft.Text(
                "Sei sicuro di voler ripristinare i dati da questo backup?\nTutti i dati attuali verranno sovrascritti."),
            actions=[
                ft.TextButton("Sì, Ripristina", on_click=self._ripristino_confermato),
                ft.TextButton("Annulla", on_click=self._chiudi_dialog_conferma_ripristino),
            ],
        )
        self.backup_path_da_ripristinare = None  # Variabile per memorizzare il percorso

        # --- NUOVO DIALOGO INFO ---
        self.info_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Informazioni"),
            content=ft.Text(""),  # Contenuto dinamico
            actions=[
                ft.TextButton("Chiudi", on_click=self._chiudi_info_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # --- NUOVO DIALOGO DI ERRORE GENERICO ---
        self.error_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(self.loc.get("error_dialog_title")),
            content=ft.Text(""),  # Contenuto dinamico
            actions=[
                ft.TextButton(self.loc.get("close"), on_click=self._close_error_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # --- NUOVO DIALOGO DI CONFERMA ELIMINAZIONE ---
        self.confirm_delete_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Conferma Eliminazione"),
            content=ft.Text("Sei sicuro di voler eliminare questo elemento? L'azione è irreversibile."),
            actions=[
                ft.TextButton("Sì, Elimina", on_click=self._esegui_eliminazione_confermata,
                              style=ft.ButtonStyle(color=ft.Colors.RED)),
                ft.TextButton("Annulla", on_click=self._chiudi_dialog_conferma_eliminazione),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 1. Inizializza i Dialoghi
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

        # 2. Inizializza le Viste principali
        self.auth_view = AuthView(self)
        self.dashboard_view = DashboardView(self)
        self.export_view = ExportView(self)

        # 3. Aggiungi gli overlay globali (Dialoghi e Picker)
        self.date_picker = ft.DatePicker(
            on_change=self.transaction_dialog.on_date_picker_change,
            first_date=datetime.datetime(2020, 1, 1),
            last_date=datetime.datetime(2030, 12, 31),
            value=datetime.datetime.now()
        )
        self.file_picker_salva_excel = ft.FilePicker(on_result=self.on_file_picker_result)

        page.overlay.extend([
            self.transaction_dialog,
            self.conto_dialog,
            self.admin_dialogs.dialog_modifica_cat,
            self.admin_dialogs.dialog_modifica_ruolo,
            self.admin_dialogs.dialog_invito_membri,
            self.admin_dialogs.dialog_imposta_budget,
            self.portafoglio_dialogs.dialog_portafoglio,
            self.portafoglio_dialogs.dialog_operazione_asset,
            self.portafoglio_dialogs.dialog_aggiorna_prezzo,
            self.portafoglio_dialogs.dialog_modifica_asset,
            self.date_picker,
            self.file_picker_salva_excel,
            self.prestito_dialogs.dialog_prestito,
            self.prestito_dialogs.dialog_paga_rata,
            self.immobile_dialog,
            self.fondo_pensione_dialog,
            self.giroconto_dialog,
            self.conto_condiviso_dialog,
            self.spesa_fissa_dialog,
            self.confirm_download_dialog,
            self.file_picker_salva_backup,
            self.file_picker_apri_backup,
            self.confirm_restore_dialog,
            self.confirm_delete_dialog,
            self.info_dialog,
            self.error_dialog  # Aggiunto agli overlay
        ])

    def on_file_picker_result(self, e: ft.FilePickerResultEvent):
        """ Callback per il salvataggio file """
        try:
            file_data = self.page.session.get("excel_export_data")
            if e.path and file_data:
                with open(e.path, "wb") as f:
                    f.write(file_data)
                self.show_snack_bar(f"File salvato in: {e.path}", success=True)
                self.page.session.remove("excel_export_data")
            else:
                self.show_snack_bar("Salvataggio annullato.", success=False)
        except Exception as ex:
            self.show_error_dialog(f"Errore durante il salvataggio: {ex}")
            print(f"Errore on_file_picker_result: {ex}")

    def route_change(self, route):
        """ Gestore del routing principale """
        self.page.views.clear()

        parsed_url = urlparse(route.route)
        route_path = parsed_url.path
        query_params = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}

        if query_params.get("token") and route_path == "/registrazione":
            token = query_params["token"]
            invito_data = ottieni_invito_per_token(token)
            if invito_data:
                self.page.session.set("invito_attivo", invito_data)
                self.page.snack_bar = ft.SnackBar(
                    ft.Text(
                        f"Invito per la famiglia ID: {invito_data['id_famiglia']} caricato. Completa la registrazione."),
                    open=True
                )
                self.page.views.append(self.auth_view.get_registration_view())
            else:
                self.show_snack_bar("Link di invito non valido o già utilizzato.", success=False)
                self.page.go("/")
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
            self.page.views.append(self.auth_view.get_force_change_password_view())
        else:
            self.page.go("/")

        self.page.update()

    def _carica_dashboard(self):
        print("Caricamento Dashboard...")
        self.page.views.clear()
        dashboard_view_instance = self.dashboard_view.build_view()
        self.page.views.append(dashboard_view_instance)
        self.dashboard_view.update_tabs_list()

        # Carica le impostazioni di lingua/valuta PRIMA di aggiornare le viste
        saved_lang = self.page.client_storage.get("settings.language")
        if saved_lang:
            self.loc.set_language(saved_lang)
        saved_currency = self.page.client_storage.get("settings.currency")
        if saved_currency:
            self.loc.set_currency(saved_currency)

        id_famiglia = self.get_family_id()
        pagamenti_fatti = 0
        spese_fisse_eseguite = 0
        if id_famiglia:
            print(f"ℹ️ Controllo pagamenti automatici rate per famiglia {id_famiglia}...")
            pagamenti_fatti = check_e_paga_rate_scadute(id_famiglia)
            if pagamenti_fatti == 0:
                print("✅ Controllo pagamenti automatici completato. 0 pagamenti eseguiti.")
            else:
                print(f"✅ Controllo pagamenti automatici completato. {pagamenti_fatti} pagamenti eseguiti.")

            print(f"ℹ️ Controllo spese fisse per famiglia {id_famiglia}...")
            spese_fisse_eseguite = check_e_processa_spese_fisse(id_famiglia)
            if spese_fisse_eseguite > 0:
                print(f"✅ Controllo spese fisse completato. {spese_fisse_eseguite} spese eseguite.")

        self.update_all_views(is_initial_load=True)

        if pagamenti_fatti > 0:
            self.show_snack_bar(f"{pagamenti_fatti} pagamenti rata automatici eseguiti.", success=True)
        if spese_fisse_eseguite > 0:
            self.show_snack_bar(f"{spese_fisse_eseguite} spese fisse automatiche eseguite.", success=True)

        self.page.update()

    def _download_confirmato(self, e, auto=False):
        pass

    def _download_rifiutato(self, e):
        pass

    # --- LOGICA DI BACKUP ---
    def backup_dati_clicked(self):
        """Apre il file picker per salvare il file di backup."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_picker_salva_backup.save_file(
            dialog_title="Salva Backup Database",
            file_name=f"budget_backup_{timestamp}.db",
            allowed_extensions=["db"]
        )

    def _on_backup_dati_result(self, e: ft.FilePickerResultEvent):
        """Callback che esegue la copia del file di backup."""
        if not e.path:
            self.show_snack_bar("Operazione di backup annullata.", success=False)
            return

        try:
            shutil.copyfile(DB_FILE, e.path)
            self.show_snack_bar(f"Backup creato con successo in: {e.path}", success=True)
        except Exception as ex:
            print(f"❌ Errore durante la creazione del backup: {ex}")
            self.show_error_dialog(f"Errore durante la creazione del backup: {ex}")

    # --- LOGICA DI RIPRISTINO ---
    def ripristina_dati_clicked(self):
        """Apre il file picker per selezionare un file di backup da ripristinare."""
        self.file_picker_apri_backup.pick_files(
            dialog_title="Seleziona un file di Backup (.db)",
            allow_multiple=False,
            allowed_extensions=["db"]
        )

    def _on_ripristina_dati_result(self, e: ft.FilePickerResultEvent):
        """Callback che gestisce il file di backup selezionato."""
        if not e.files:
            self.show_snack_bar("Nessun file di backup selezionato.", success=False)
            return

        self.backup_path_da_ripristinare = e.files[0].path

        # Apri il dialogo di conferma
        self.page.dialog = self.confirm_restore_dialog
        self.confirm_restore_dialog.open = True
        self.page.update()

    def _chiudi_dialog_conferma_ripristino(self, e):
        self.confirm_restore_dialog.open = False
        self.backup_path_da_ripristinare = None
        self.page.update()

    def _ripristino_confermato(self, e):
        """Esegue il ripristino dopo la conferma dell'utente."""
        backup_path = self.backup_path_da_ripristinare
        self.confirm_restore_dialog.open = False
        self.page.update()

        if not backup_path: return

        try:
            # --- NUOVA LOGICA DI MIGRAZIONE ---
            # 1. Ottieni la versione dell'app (creando un DB temporaneo con lo schema attuale)
            temp_db_path = DB_FILE + ".temp_schema"
            setup_database(temp_db_path)
            versione_app = ottieni_versione_db(temp_db_path)
            os.remove(temp_db_path)

            # 2. Ottieni la versione del backup
            versione_backup = ottieni_versione_db(backup_path)

            print(f"Versione App: {versione_app}, Versione Backup: {versione_backup}")

            if versione_backup > versione_app:
                self.show_error_dialog("Errore: Il backup è di una versione più recente dell'app!")
                return

            if versione_backup < versione_app:
                print("Avvio migrazione database di backup...")
                migrazione_success = migra_database(backup_path, versione_backup, versione_app)
                if not migrazione_success:
                    self.show_error_dialog("❌ Errore critico durante la migrazione del database.")
                    return
                print("Migrazione del file di backup completata.")

            # 3. Esegui il ripristino
            shutil.copyfile(backup_path, DB_FILE)
            self.show_snack_bar("Ripristino completato. L'app verrà ricaricata.", success=True)
            time.sleep(2)
            self.page.go("/")

        except Exception as ex:
            print(f"❌ Errore durante il ripristino del database: {ex}")
            self.show_error_dialog(f"Errore durante il ripristino: {ex}")
        finally:
            self.backup_path_da_ripristinare = None

    # --- LOGICA DIALOGO INFO ---
    def open_info_dialog(self, e):
        """Apre il dialogo con le informazioni sulla versione."""
        db_version = ottieni_versione_db()
        self.info_dialog.content = ft.Text(
            f"Versione App: {VERSION}\n"
            f"Versione Database: {db_version}\n\n"
            f"Sviluppato da Enrico Flammini."
        )
        self.page.dialog = self.info_dialog
        self.info_dialog.open = True
        self.page.update()

    def _chiudi_info_dialog(self, e):
        self.info_dialog.open = False
        self.page.update()

    # --- LOGICA DIALOGO ERRORE ---
    def _close_error_dialog(self, e):
        self.error_dialog.open = False
        self.page.update()

    def show_error_dialog(self, message):
        """Mostra un dialogo di errore generico."""
        self.error_dialog.content.value = str(message)
        self.page.dialog = self.error_dialog
        self.error_dialog.open = True
        self.page.update()

    # --- LOGICA DI CONFERMA ELIMINAZIONE ---
    def open_confirm_delete_dialog(self, delete_callback):
        """
        Apre un dialogo di conferma generico.
        :param delete_callback: Una funzione lambda o parziale che esegue l'eliminazione effettiva.
        """
        self.page.session.set("delete_callback", delete_callback)
        self.page.dialog = self.confirm_delete_dialog
        self.confirm_delete_dialog.open = True
        self.page.update()

    def _chiudi_dialog_conferma_eliminazione(self, e):
        self.confirm_delete_dialog.open = False
        self.page.update()

    def _esegui_eliminazione_confermata(self, e):
        delete_callback = self.page.session.get("delete_callback")
        if callable(delete_callback):
            delete_callback()
        self.confirm_delete_dialog.open = False
        self.page.update()

    def post_login_setup(self, utente):
        id_utente = utente['id']
        id_famiglia = ottieni_prima_famiglia_utente(id_utente)
        self.page.session.set("utente_loggato", utente)

        if utente.get("forza_cambio_password"):
            print(f"Utente {id_utente} deve cambiare la password.")
            self.page.go("/force-change-password")
            return

        if id_famiglia:
            ruolo = ottieni_ruolo_utente(id_utente, id_famiglia)
            self.page.session.set("id_famiglia", id_famiglia)
            self.page.session.set("ruolo_utente", ruolo)
            nome_famiglia_db = "Famiglia"
            self.page.session.set("nome_famiglia", nome_famiglia_db)
            self.page.go("/dashboard")
        else:
            user_count = get_user_count()
            if user_count == 1:
                print(f"Utente {id_utente} è il PRIMO UTENTE. Avvio setup admin minimo...")
                self.page.go("/setup-admin")
            else:
                print(f"Utente {id_utente} è in attesa di approvazione.")
                self.page.go("/in-attesa")

    def build_setup_view(self) -> ft.View:
        self.txt_nome_famiglia.value = ""
        self.txt_errore_setup.visible = False

        return ft.View(
            "/setup-admin",
            [
                ft.Column(
                    [
                        ft.Text("Benvenuto!", size=30, weight=ft.FontWeight.BOLD),
                        ft.Text("Sei il primo utente. Configura la tua famiglia per iniziare."),
                        ft.Container(height=20),
                        self.txt_nome_famiglia,
                        self.txt_errore_setup,
                        ft.Container(height=10),
                        ft.ElevatedButton(
                            "Crea Famiglia e Continua",
                            icon=ft.Icons.ROCKET_LAUNCH,
                            on_click=self._completa_setup_admin,
                            width=350
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True,
                    width=350
                )
            ],
            vertical_alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _completa_setup_admin(self, e):
        self.txt_errore_setup.visible = False
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
            print("Esecuzione setup admin minimo...")
            new_family_id = crea_famiglia_e_admin(nome_famiglia, utente['id'])
            if not new_family_id:
                raise Exception("Creazione famiglia fallita. Nome duplicato?")

            aggiungi_categorie_iniziali(new_family_id)

            self.page.session.set("id_famiglia", new_family_id)
            self.page.session.set("ruolo_utente", "admin")
            self.page.session.set("nome_famiglia", nome_famiglia)

            self.show_snack_bar(f"Famiglia '{nome_famiglia}' creata! Ora crea il tuo primo conto.", success=True)
            self.page.go("/dashboard")

        except Exception as ex:
            print(f"Errore in _completa_setup_admin: {ex}")
            self.txt_errore_setup.value = f"Errore: {ex}"
            self.txt_errore_setup.visible = True
            self.page.update()

    def gestisci_invito_o_sblocco(self, username_o_email, ruolo):
        id_famiglia = self.get_family_id()
        nome_famiglia_session = self.page.session.get("nome_famiglia")
        nome_famiglia = nome_famiglia_session if nome_famiglia_session else "N/A"  # Gestione esplicita di None

        if not id_famiglia:
            return "Errore: ID Famiglia non trovato in sessione. Riprova il login.", False

        input_value = username_o_email.strip()
        utente_esistente = cerca_utente_per_username(input_value)

        if utente_esistente:
            success = aggiungi_utente_a_famiglia(
                id_famiglia=id_famiglia,
                id_utente=utente_esistente['id_utente'],
                ruolo=ruolo
            )
            if success:
                email_utente = utente_esistente['username']
                html_body = f"""
                <html><body>
                    <p>Ciao {utente_esistente['nome_visualizzato']},</p>
                    <p>Il tuo accesso all'app Budget Familiare è stato attivato.</p>
                    <p>Sei stato aggiunto alla famiglia <b>{nome_famiglia}</b> con ruolo: <b>{ruolo}</b>.</p>
                    <p>Puoi effettuare il login <a href="{URL_BASE}">cliccando qui</a>.</p>
                </body></html>
                """
                send_email_via_gmail_api(email_utente, "Il tuo accesso è stato attivato!", html_body)
                return f"Utente '{input_value}' aggiunto e sbloccato con successo. Email inviata.", True
            else:
                return "Errore DB: Impossibile aggiungere l'utente alla famiglia.", False
        elif "@" in input_value and "." in input_value:
            email_invito = input_value.lower()
            token = crea_invito(id_famiglia, email_invito, ruolo)
            if token:
                invitation_link = f"{URL_BASE}/registrazione?token={token}"
                html_body = f"""
                <html><body>
                    <p>Ciao,</p>
                    <p>Sei stato invitato a unirti alla famiglia <b>{nome_famiglia}</b> nell'app Budget Familiare.</p>
                    <p>Ti è stato assegnato il ruolo: <b>{ruolo}</b>.</p>
                    <p>Per registrarti e completare l'iscrizione, <a href="{invitation_link}">cliccando qui</a>.</p>
                    <p>Questo link è valido per un solo utilizzo.</p>
                </body></html>
                """
                if send_email_via_gmail_api(email_invito, "Invito Budget Familiare", html_body):
                    return f"Invito inviato con successo a {email_invito}.", True
                else:
                    return f"Invito creato, ma invio email fallito per {email_invito}. Controlla i log di Google API.", False
            else:
                return "Errore DB: Impossibile creare il token di invito (Invito duplicato?).", False
        else:
            return "Input non valido. Inserisci un Username esistente non associato o un'Email valida per l'invito.", False

    def build_attesa_view(self) -> ft.View:
        utente = self.page.session.get("utente_loggato")
        username = utente['username'] if utente else "utente"

        return ft.View(
            "/in-attesa",
            [
                ft.Column(
                    [
                        ft.Icon(ft.Icons.TIMER, size=60, color=ft.Colors.ORANGE_500),
                        ft.Text(f"Ciao, {username}!", size=30, weight=ft.FontWeight.BOLD),
                        ft.Text("La tua registrazione è completata.", size=18),
                        ft.Text("Chiedi all'amministratore della tua famiglia di aggiungerti.",
                                text_align=ft.TextAlign.CENTER, width=300),
                        ft.Text(f"L'amministratore dovrà cercarti usando il tuo username: '{username}'",
                                text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.BOLD, width=300),
                        ft.Container(height=20),
                        ft.TextButton("Logout", icon=ft.Icons.LOGOUT, on_click=self.logout)
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True,
                    spacing=10
                )
            ],
            vertical_alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def logout(self, e=None):
        self.page.session.clear()
        self.page.go("/")

    def logout_google(self, e):
        """Esegue il logout da Google, revocando il token."""
        success = google_auth_manager.logout()
        if success:
            self.show_snack_bar("Account Google disconnesso con successo.", success=True)
        else:
            self.show_error_dialog("Errore durante la disconnessione dell'account Google.")
        # Aggiorna l'interfaccia per riflettere il nuovo stato
        self.update_all_views()

    def update_all_views(self, is_initial_load=False):
        print("CALLBACK: Aggiornamento di tutte le viste...")
        if self.dashboard_view:
            self.dashboard_view.update_all_tabs_data(is_initial_load)
        if not is_initial_load:
            self.page.update()

    def db_write_operation(self):
        """
        Metodo centralizzato da chiamare dopo ogni operazione di scrittura sul DB.
        Aggiorna le viste e avvia la sincronizzazione automatica.
        """
        print("CALLBACK: Operazione di scrittura DB rilevata. Aggiornamento e sincronizzazione...")
        self.update_all_views()
        self.trigger_auto_sync()

    def trigger_auto_sync(self):
        """
        Avvia la sincronizzazione del DB su Google Drive in un thread separato,
        se l'utente è autenticato.
        """
        if self.page.session.get("google_auth_token_present"):
            # Mostra l'icona di caricamento
            if self.dashboard_view.sync_status_icon:
                self.dashboard_view.sync_status_icon.icon = ft.Icons.SYNC
                self.dashboard_view.sync_status_icon.rotate = ft.Rotate(angle=0, alignment=ft.alignment.center)
                self.page.update()

            def _run_sync_thread():
                google_drive_manager.upload_db(controller=self)  # Passa il controller per aggiornare l'UI

            sync_thread = threading.Thread(target=_run_sync_thread)
            sync_thread.start()

    def show_snack_bar(self, messaggio, success=True):
        self.page.snack_bar = ft.SnackBar(
            ft.Text(messaggio),
            bgcolor=ft.Colors.GREEN_500 if success else ft.Colors.RED_500
        )
        self.page.snack_bar.open = True
        self.page.update()

    def get_user_id(self):
        utente = self.page.session.get("utente_loggato")
        return utente['id'] if utente else None

    def get_family_id(self):
        return self.page.session.get("id_famiglia")

    def get_user_role(self):
        return self.page.session.get("ruolo_utente")