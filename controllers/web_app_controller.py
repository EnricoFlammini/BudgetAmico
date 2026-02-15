import flet as ft
import datetime
from app_controller import AppController
from views.web_dashboard_view import WebDashboardView
# Import dialogs (reusing existing ones)
from dialogs.transaction_dialog import TransactionDialog
from dialogs.conto_dialog import ContoDialog
from dialogs.conto_dialog import ContoDialog
from dialogs.spesa_fissa_dialog import SpesaFissaDialog
from dialogs.immobile_dialog import ImmobileDialog
from dialogs.prestito_dialogs import PrestitoDialogs
from dialogs.portafoglio_dialogs import PortafoglioDialogs
from dialogs.card_dialog import CardDialog
from dialogs.admin_dialogs import AdminDialogs
from dialogs.onboarding_dialog import OnboardingDialog
from views.auth_view import AuthView
from views.privacy_view import PrivacyView
from views.export_view import ExportView
from utils.logger import setup_logger

logger = setup_logger("WebAppController")

class WebAppController(AppController):
    def __init__(self, page: ft.Page):
        # Initialize parent AppController
        # Note: We don't call super().__init__ directly because it calls _init_dialogs_and_views 
        # which we want to customize. 
        self.page = page
        from utils.localization import LocalizationManager
        from utils.styles import LoadingOverlay
        
        self.loc = LocalizationManager()
        logger.info("WebAppController initialized.")
        
        # UI Controls specific to setup (reused)
        self.txt_nome_famiglia = ft.TextField(label="Nome della tua Famiglia", autofocus=True)
        self.txt_errore_setup = ft.Text(value="", visible=False)
        
        self.loading_overlay = LoadingOverlay()
        
        self._init_dialogs_and_views()

    def _init_dialogs_and_views(self):
        # We only init the dialogs we strictly need for the mobile Lite version
        self.transaction_dialog = TransactionDialog(self)
        self.conto_dialog = ContoDialog(self) 
        self.card_dialog = CardDialog(page=self.page, callback=self.update_all_views) # Fixed: using callback directly
        self.spesa_fissa_dialog = SpesaFissaDialog(self)
        self.immobile_dialog = ImmobileDialog(self)
        self.prestito_dialogs = PrestitoDialogs(self)
        self.portafoglio_dialogs = PortafoglioDialogs(self)
        self.admin_dialogs = AdminDialogs(self)
        self.onboarding_dialog = OnboardingDialog(self)
        
        # Init Views
        self.auth_view = AuthView(self)
        self.dashboard_view = WebDashboardView(self) # USE WEB VIEW
        self.privacy_view = PrivacyView(self)
        self.export_view = ExportView(self)
        
        # Re-use global dialogs init (Overridden below)
        self._init_global_dialogs()

    def _init_global_dialogs(self):
        # Override to initialize only necessary global dialogs for Web/Mobile
        
        self.date_picker = ft.DatePicker(
            first_date=datetime.datetime(2020, 1, 1),
            last_date=datetime.datetime(2030, 12, 31),
            value=datetime.datetime.now()
        )
        self.file_picker_salva_excel = ft.FilePicker()
        self.file_picker = ft.FilePicker() # Generic file picker just in case 

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
        
        # Add basic overlays
        self.page.overlay.extend([
            self.transaction_dialog, 
            self.conto_dialog,
            self.date_picker, 
            self.confirm_delete_dialog,
            self.error_dialog,
            self.spesa_fissa_dialog,
            self.immobile_dialog,
            self.prestito_dialogs.dialog_prestito,
            self.prestito_dialogs.dialog_paga_rata,
            self.portafoglio_dialogs.dialog_portafoglio,
            self.portafoglio_dialogs.dialog_operazione_asset,
            self.portafoglio_dialogs.dialog_aggiorna_prezzo,
            self.portafoglio_dialogs.dialog_modifica_asset,
            self.file_picker,
            self.file_picker_salva_excel,
            self.onboarding_dialog,
            # self.loading_overlay is dynamic
        ])

    def _carica_dashboard(self):
        """Override to load WebDashboardView"""
        self.page.views.clear()
        
        # Re-create to ensure fresh state
        self.dashboard_view = WebDashboardView(self)
        
        self.page.views.append(self.dashboard_view.build_view())
        
        self.page.update()
        self.hide_loading()

        # Restore settings
        saved_lang = self.page.client_storage.get("settings.language")
        if saved_lang: self.loc.set_language(saved_lang)
        
        # Load data
        self.update_all_views(is_initial_load=True)
        self.page.update()
        
        # Prova Onboarding
        self._check_onboarding()
