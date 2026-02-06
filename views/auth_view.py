import flet as ft
from db.gestione_db import (
    registra_utente, verifica_login, aggiungi_utente_a_famiglia, trova_utente_per_email,
    imposta_password_temporanea, cambia_password, hash_password, cambia_password_e_username,
    get_smtp_config
)
from utils.email_sender import send_email
from utils.logger import setup_logger
import os

logger = setup_logger("AuthView")


class AuthView:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc

        self.URL_BASE = os.environ.get("FLET_APP_URL", "http://localhost:8550")

        # Controlli per il Login
        self.txt_username = ft.TextField(autofocus=True, on_submit=self._login_cliccato)
        self.txt_password = ft.TextField(password=True, can_reveal_password=True, on_submit=self._login_cliccato)
        self.txt_errore_login = ft.Text(value="", color=ft.Colors.RED_500, visible=False)

        # Controlli per la Registrazione
        self.txt_reg_username = ft.TextField()
        self.txt_reg_email = ft.TextField()
        self.txt_reg_nome = ft.TextField()
        self.txt_reg_cognome = ft.TextField()
        self.txt_reg_password = ft.TextField(password=True, can_reveal_password=True)
        self.txt_reg_conferma_password = ft.TextField(password=True, can_reveal_password=True)
        self.txt_reg_data_nascita = ft.TextField(label="Data di Nascita (YYYY-MM-DD)")
        self.txt_reg_codice_fiscale = ft.TextField(label="Codice Fiscale")
        self.txt_reg_indirizzo = ft.TextField(label="Indirizzo")

        # Password Strength Indicator (v0.48)
        self.pwd_strength_bar = ft.ProgressBar(value=0, width=300, color=ft.Colors.RED, bgcolor=ft.Colors.GREY_200, visible=False)
        self.pwd_strength_text = ft.Text("", size=12, color=ft.Colors.GREY_600, visible=False)
        self.txt_reg_password.on_change = self._on_password_change

        # Cache complexities
        from db.gestione_db import get_password_complexity_config
        self.pwd_config = get_password_complexity_config()

        # Controlli per il Recupero Password
        self.txt_recovery_email = ft.TextField(autofocus=True)
        self.recovery_status_text = ft.Text(visible=False)

        # Controlli per il Reset Password
        self.txt_reset_username = ft.TextField(label="Nuovo Username")
        self.txt_reset_nome = ft.TextField(label="Nome")
        self.txt_reset_cognome = ft.TextField(label="Cognome")
        self.txt_reset_new_password = ft.TextField(password=True, can_reveal_password=True)
        self.txt_reset_confirm_password = ft.TextField(password=True, can_reveal_password=True)
        self.reset_status_text = ft.Text(visible=False)


    def get_login_view(self) -> ft.View:
        """Costruisce e restituisce la vista di Login."""
        loc = self.loc
        self.txt_username.label = loc.get("username_or_email")
        self.txt_password.label = "Password"
        self.txt_username.value = ""
        self.txt_password.value = ""
        self.txt_username.disabled = False
        self.txt_password.disabled = False
        self.txt_errore_login.visible = False

        return ft.View(
            "/",
            [
                ft.Column(
                    [
                        ft.Text("LOGIN", size=30, weight="bold"),
                        self.txt_username,
                        self.txt_password,
                        self.txt_errore_login,
                        ft.Container(height=10),
                        ft.ElevatedButton(
                            "Login",
                            icon="login",
                            on_click=self._login_cliccato,
                            width=300
                        ),
                        ft.TextButton(
                            loc.get("forgot_password"),
                            on_click=lambda _: self.page.go("/password-recovery")
                        ),
                        ft.Row(
                            [
                                ft.Text(loc.get("no_account_question")),
                                ft.TextButton(loc.get("register_now"), on_click=self._vai_a_registrazione)
                            ],
                            alignment=ft.MainAxisAlignment.CENTER
                        ),
                        ft.Container(height=20),
                        ft.Column([
                            ft.IconButton(
                                icon=ft.Icons.CALCULATE_OUTLINED,
                                icon_size=40,
                                icon_color=ft.Colors.GREEN,
                                tooltip="Divisore Pro (Free Tool)",
                                on_click=lambda _: self.page.go("/divisore")
                            ),
                            ft.Text("Divisore Pro", size=10, color=ft.Colors.GREEN),
                            ft.Container(height=10),
                            ft.TextButton(
                                "Informativa Privacy",
                                style=ft.ButtonStyle(color=ft.Colors.GREY_500),
                                on_click=lambda _: self.page.go("/privacy")
                            )
                        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
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

    def _vai_a_registrazione(self, e):
        """Naviga alla pagina di registrazione."""
        self.page.go("/registrazione")

    def get_registration_view(self) -> ft.View:
        """Costruisce e restituisce la vista di Registrazione."""
        loc = self.loc
        self.txt_reg_username.label = loc.get("username")
        self.txt_reg_email.label = loc.get("email")
        self.txt_reg_nome.label = loc.get("name")
        self.txt_reg_cognome.label = loc.get("Cognome")
        self.txt_reg_password.label = "Password"
        self.txt_reg_conferma_password.label = loc.get("confirm_new_password")

        # Reset dei campi
        for field in [self.txt_reg_username, self.txt_reg_email, self.txt_reg_nome, self.txt_reg_cognome,
                      self.txt_reg_password, self.txt_reg_conferma_password,
                      self.txt_reg_data_nascita, self.txt_reg_codice_fiscale, self.txt_reg_indirizzo]:
            field.value = ""
            field.error_text = None

        return ft.View(
            "/registrazione",
            [
                ft.Column(
                    [
                        ft.Text(loc.get("register_now"), size=30, weight="bold"),
                        self.txt_reg_username,
                        self.txt_reg_email,
                        self.txt_reg_nome,
                        self.txt_reg_cognome,
                        ft.Column([
                            self.txt_reg_password,
                            self.pwd_strength_bar,
                            self.pwd_strength_text
                        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        self.txt_reg_conferma_password,
                        ft.Container(height=10),
                        ft.ElevatedButton(
                            loc.get("register_now"),
                            icon="person_add",
                            on_click=self._registra_cliccato,
                            width=300
                        ),
                        ft.TextButton(loc.get("back_to_login"), on_click=lambda _: self.page.go("/")),
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

    def _login_cliccato(self, e):
        # Disable button to prevent double submission
        btn_login = e.control
        btn_login.disabled = True
        btn_login.update()

        username = self.txt_username.value.strip()
        password = self.txt_password.value
        
        logger.info("===== INIZIO SESSIONE LOGIN =====")
        logger.info(f"Tentativo di login per utente: {username}")

        if not username or not password:
            logger.warning("Login fallito: username o password mancante")
            self.txt_errore_login.value = "Inserisci username e password."
            self.txt_errore_login.visible = True
            btn_login.disabled = False
            self.page.update()
            return

        # Mostra spinner durante il login
        self.controller.show_loading("Accesso in corso...")
        
        try:
            from db.gestione_db import verifica_login
            utente, errore = verifica_login(username, password)
            
            if utente:
                logger.info(f"LOGIN RIUSCITO - Utente ID: {utente.get('id')}")
                logger.info(f"  - Forza cambio password: {utente.get('forza_cambio_password')}")
                logger.info(f"  - Master key presente: {'Si' if utente.get('master_key') else 'No'}")
                self.txt_errore_login.visible = False
                # Save temp password if user needs to change it (for re-encrypting family key)
                if utente.get("forza_cambio_password"):
                    self.page.session.set("_temp_password_for_reencrypt", password)
                self.controller.post_login_setup(utente)
            else:
                logger.warning(f"LOGIN FALLITO per {username}: {errore}")
                self.txt_errore_login.value = errore or "Username o password errati."
                self.txt_errore_login.visible = True
                btn_login.disabled = False
                self.page.update()
                self.controller.hide_loading()
        except Exception as ex:
            logger.error(f"Errore durante il login: {ex}", exc_info=True)
            btn_login.disabled = False
            self.controller.hide_loading()
            raise

    def _on_password_change(self, e):
        """Calcola la forza della password in tempo reale."""
        pwd = self.txt_reg_password.value
        if not pwd:
            self.pwd_strength_bar.visible = False
            self.pwd_strength_text.visible = False
            self.page.update()
            return
            
        self.pwd_strength_bar.visible = True
        self.pwd_strength_text.visible = True
        
        # Strength logic
        score = 0
        min_len = int(self.pwd_config.get("min_length", 8))
        if len(pwd) >= min_len: score += 1
        if any(c.isupper() for c in pwd): score += 1
        if any(c.isdigit() for c in pwd): score += 1
        if any(not c.isalnum() for c in pwd): score += 1
        
        colors = [ft.Colors.RED, ft.Colors.ORANGE, ft.Colors.YELLOW, ft.Colors.GREEN]
        labels = ["Molto Debole", "Debole", "Media", "Forte"]
        
        idx = min(score, 3)
        self.pwd_strength_bar.value = (idx + 1) / 4
        self.pwd_strength_bar.color = colors[idx]
        self.pwd_strength_text.value = f"Forza: {labels[idx]}"
        self.pwd_strength_text.color = colors[idx]
        self.page.update()

    def _check_password_complexity(self, password):
        """Verifica se la password rispetta i criteri Admin."""
        cfg = self.pwd_config
        errors = []
        if len(password) < int(cfg.get("min_length", 8)):
            errors.append(f"Almeno {cfg['min_length']} caratteri")
        if cfg.get("require_uppercase") and not any(c.isupper() for c in password):
            errors.append("Almeno una maiuscola")
        if cfg.get("require_digits") and not any(c.isdigit() for c in password):
            errors.append("Almeno un numero")
        if cfg.get("require_special") and not any(not c.isalnum() for c in password):
            errors.append("Almeno un carattere speciale")
        return errors

    def _registra_cliccato(self, e):
        # Disable button to prevent double submission
        btn_registra = e.control
        btn_registra.disabled = True
        btn_registra.update()

        username = self.txt_reg_username.value.strip()
        email = self.txt_reg_email.value.lower().strip()
        nome = self.txt_reg_nome.value.strip()
        cognome = self.txt_reg_cognome.value.strip()
        password = self.txt_reg_password.value
        conferma_password = self.txt_reg_conferma_password.value
        # Campi opzionali o rimossi nella v0.48
        data_nascita = None
        codice_fiscale = None
        indirizzo = None

        # Reset errori
        for field in [self.txt_reg_username, self.txt_reg_email, self.txt_reg_nome, self.txt_reg_cognome,
                      self.txt_reg_password, self.txt_reg_conferma_password,
                      self.txt_reg_data_nascita, self.txt_reg_codice_fiscale, self.txt_reg_indirizzo]:
            field.error_text = None

        # Validazione
        is_valid = True
        if not all([username, email, nome, cognome, password, conferma_password]):
            self.controller.show_snack_bar("Username, Email, Nome, Cognome e Password sono obbligatori.", success=False)
            is_valid = False
            
        # Check Complessità Password (v0.48)
        pwd_errors = self._check_password_complexity(password)
        if pwd_errors:
            self.txt_reg_password.error_text = "Requisiti: " + ", ".join(pwd_errors)
            is_valid = False
            
        if password != conferma_password:
            self.txt_reg_conferma_password.error_text = "Le password non coincidono."
            is_valid = False

        if not is_valid:
            btn_registra.disabled = False
            btn_registra.update()
            self.page.update()
            return

        logger.debug("Verifica disponibilità registrazione...")
        from db.gestione_db import check_registration_availability, generate_email_verification_code, verify_email_code
        
        if not check_registration_availability(username, email):
            self.txt_reg_username.error_text = "Username o Email già in uso."
            btn_registra.disabled = False
            btn_registra.update()
            self.page.update()
            return

        # --- EMAIL VERIFICATION FLOW (v0.48) ---
        verification_code = generate_email_verification_code(email)
        
        # Invia Email prima di creare l'utente
        from utils.email_sender import send_email
        subject = "Codice di Verifica BudgetAmico"
        body = f"<h1>Benvenuto su BudgetAmico!</h1><p>Il tuo codice di verifica è: <b>{verification_code}</b></p><p>Inseriscilo nell'app per completare la registrazione.</p>"
        
        self.controller.show_loading("Invio codice di verifica...")
        success_email, err_email = send_email(email, subject, body)
        self.controller.hide_loading()
        
        if not success_email:
             self.controller.show_snack_bar(f"Errore invio mail: {err_email}", success=False)
             btn_registra.disabled = False
             btn_registra.update()
             return

        def on_verify_code(e):
            code = txt_verification_code.value.strip()
            if verify_email_code(email, code):
                verify_dialog.open = False
                self.page.update()
                
                # ORA ESEGUE LA REGISTRAZIONE EFFETTIVA
                self.controller.show_loading("Creazione account in corso...")
                try:
                    result = registra_utente(nome, cognome, username, password, email, None, None, None)
                finally:
                    self.controller.hide_loading()

                if result:
                    id_nuovo_utente = result.get("id_utente")
                    recovery_key = result.get("recovery_key")
                    
                    invito_attivo = self.page.session.get("invito_attivo")
                    if invito_attivo:
                        from db.gestione_db import accetta_invito
                        master_key = result.get("master_key")
                        accetta_invito(id_nuovo_utente, invito_attivo['token'], master_key)
                        self.page.session.remove("invito_attivo")

                    self.controller.show_snack_bar("Email verificata e account creato!", success=True)
                    # Mostra recovery key dialog
                    self.page.overlay.append(dialog)
                    dialog.open = True
                    # Update parameters for the recovery dialog which is already defined below in the original code logic
                    # We need to make sure recovery_key is passed correctly. 
                    # Actually, the 'dialog' variable is defined below in the original scope.
                    # To avoid issues, let's redefine the dialog logic or ensure it's accessible.
                    
                    # Ricarichiamo il valore nella TextField del dialog
                    txt_recovery.value = recovery_key
                    self.page.update()
                else:
                    self.controller.show_snack_bar("Errore durante la registrazione finale.", success=False)
            else:
                txt_verification_code.error_text = "Codice non valido o scaduto."
                self.page.update()

        txt_verification_code = ft.TextField(label="Codice di Verifica", width=200, text_align=ft.TextAlign.CENTER)
        verify_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Verifica la tua Email"),
            content=ft.Column([
                ft.Text(f"Abbiamo inviato un codice di 6 cifre a {email}", size=14),
                txt_verification_code
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            actions=[
                ft.ElevatedButton("Verifica", on_click=on_verify_code)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.overlay.append(verify_dialog)
        verify_dialog.open = True

        # Show recovery key dialog definition (placeholders for late filling)
        def close_dialog(e):
            dialog.open = False
            self.page.update()
            self.controller.show_snack_bar("Registrazione completata! Effettua il login.", success=True)
            self.page.go("/")
        
        txt_recovery = ft.TextField(
            value="",
            read_only=True,
            multiline=True,
            text_size=12,
            border_color=ft.Colors.BLUE_400,
            text_style=ft.TextStyle(font_family="Courier New")
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ SALVA LA TUA CHIAVE DI RECUPERO", weight=ft.FontWeight.BOLD, size=18),
            content=ft.Column([
                ft.Text("Questa è la tua chiave di recupero. SALVALA IN UN POSTO SICURO!", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("Se perdi la password, questa chiave è l'UNICO modo per recuperare i tuoi dati.", size=12, color=ft.Colors.RED_400),
                ft.Container(height=10),
                txt_recovery,
                ft.Container(height=10),
                ft.Text("⚠️ Senza questa chiave, i dati criptati saranno PERSI per sempre!", size=11, italic=True, color=ft.Colors.ORANGE_400, weight=ft.FontWeight.BOLD)
            ], tight=True, scroll=ft.ScrollMode.AUTO, width=500),
            actions=[
                ft.TextButton("✅ Ho salvato la chiave", on_click=close_dialog, style=ft.ButtonStyle(color=ft.Colors.GREEN_400))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page.update()

    # --- VISTA E LOGICA RECUPERO PASSWORD ---

    def get_password_recovery_view(self) -> ft.View:
        """Costruisce la vista per richiedere il reset della password."""
        loc = self.loc
        self.txt_recovery_email.label = loc.get("email")
        self.txt_recovery_email.value = ""
        self.txt_recovery_email.error_text = None
        self.recovery_status_text.visible = False

        return ft.View(
            "/password-recovery",
            [
                ft.Column(
                    [
                        ft.Text(loc.get("password_recovery_title"), size=30, weight=ft.FontWeight.BOLD),
                        ft.Text(loc.get("password_recovery_desc")),
                        self.txt_recovery_email,
                        self.recovery_status_text,
                        ft.ElevatedButton(
                            loc.get("send_reset_link"),
                            icon=ft.Icons.EMAIL,
                            on_click=self._invia_link_reset,
                            width=300
                        ),
                        ft.TextButton(loc.get("back_to_login"), on_click=lambda _: self.page.go("/")),
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

    def _invia_link_reset(self, e):
        # Disable button to prevent double submission
        btn_invia = e.control
        btn_invia.disabled = True
        btn_invia.update()

        email = self.txt_recovery_email.value.lower().strip()
        self.txt_recovery_email.error_text = None

        if not email:
            self.txt_recovery_email.error_text = self.loc.get("email_is_required")
            btn_invia.disabled = False
            self.page.update()
            return

        # Mostra spinner durante l'invio
        self.controller.show_loading("Invio email in corso...")

        try:
            utente = trova_utente_per_email(email)

            if utente:
                # Genera una password temporanea
                import secrets
                temp_password = secrets.token_urlsafe(8)

                if imposta_password_temporanea(utente['id_utente'], temp_password):
                    body = f"""
                        <html><body>
                            <p>Ciao {utente['nome']},</p>
                            <p>La tua password temporanea è: <b>{temp_password}</b></p>
                            <p>Al prossimo accesso ti verrà chiesto di impostare una nuova password personale.</p>
                            <p><i>Nota: I tuoi dati sono stati recuperati con successo grazie al backup server.</i></p>
                        </body></html>
                        """
                    
                    # Recupera la configurazione SMTP della famiglia dell'utente
                    id_famiglia = utente.get('id_famiglia')
                    smtp_config = None
                    if id_famiglia:
                        smtp_config = get_smtp_config(id_famiglia=id_famiglia)
                        if not smtp_config or not smtp_config.get('server'):
                            smtp_config = get_smtp_config()
                    else:
                        smtp_config = get_smtp_config()
                    
                    success, error = send_email(email, "Password Temporanea - Budget Amico", body, smtp_config=smtp_config)
                    
                    if not success and "SMTP" in str(error):
                        self.controller.hide_loading()
                        self.recovery_status_text.value = f"Errore configurazione: {error}"
                        self.recovery_status_text.color = ft.Colors.RED
                        self.recovery_status_text.visible = True
                        btn_invia.disabled = False
                        self.page.update()
                        return
                else:
                    self.controller.hide_loading()
                    self.recovery_status_text.value = "Impossibile recuperare l'account (Chiave di backup non trovata)."
                    self.recovery_status_text.color = ft.Colors.RED
                    self.recovery_status_text.visible = True
                    btn_invia.disabled = False
                    self.page.update()
                    return

            # Mostra un messaggio generico per motivi di sicurezza
            self.controller.hide_loading()
            self.recovery_status_text.value = self.loc.get("reset_link_sent_confirmation")
            self.recovery_status_text.color = ft.Colors.GREEN
            self.recovery_status_text.visible = True
            btn_invia.disabled = False
            self.page.update()
        except Exception as ex:
            self.controller.hide_loading()
            self.recovery_status_text.value = f"Errore: {ex}"
            self.recovery_status_text.color = ft.Colors.RED
            self.recovery_status_text.visible = True
            btn_invia.disabled = False
            self.page.update()

    # --- VISTA E LOGICA RESET PASSWORD ---

    def get_force_change_password_view(self) -> ft.View:
        """Costruisce la vista per impostare la nuova password."""
        loc = self.loc
        self.txt_reset_new_password.label = loc.get("new_password")
        self.txt_reset_confirm_password.label = loc.get("confirm_new_password")
        self.txt_reset_new_password.value = ""
        self.txt_reset_confirm_password.value = ""
        self.reset_status_text.visible = False

        return ft.View(
            "/force-change-password",
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(loc.get("set_new_password_title"), size=30, weight=ft.FontWeight.BOLD),
                                ft.Container(height=10),
                                self.txt_reset_new_password,
                                self.txt_reset_confirm_password,
                                self.reset_status_text,
                                ft.ElevatedButton(loc.get("save_new_password"), icon=ft.Icons.SAVE,
                                                  on_click=self._salva_nuova_password),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            width=350,
                            spacing=15
                        )
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True
                )
            ]
        )

    def _salva_nuova_password(self, e):
        # Disable button to prevent double submission
        btn_salva = e.control
        btn_salva.disabled = True
        btn_salva.update()

        nuova_pass = self.txt_reset_new_password.value
        conferma_pass = self.txt_reset_confirm_password.value

        if not nuova_pass or nuova_pass != conferma_pass:
            self.reset_status_text.value = "Le password non coincidono o sono vuote."
            self.reset_status_text.color = ft.Colors.RED
            self.reset_status_text.visible = True
            btn_salva.disabled = False
            self.page.update()
            return

        id_utente = self.controller.get_user_id()
        if not id_utente:
            self.page.go("/")
            return

        # Mostra spinner durante il salvataggio
        self.controller.show_loading("Salvataggio in corso...")

        try:
            # Pass RAW password, not hash!
            # Get old password for re-encrypting family key
            vecchia_password = self.page.session.get("_temp_password_for_reencrypt")
            if vecchia_password:
                self.page.session.remove("_temp_password_for_reencrypt")
            result = cambia_password_e_username(id_utente, nuova_pass, vecchia_password=vecchia_password)

            self.controller.hide_loading()

            if result and result.get("success"):
                # Update session username and keys
                utente = self.page.session.get("utente_loggato")
                if utente:
                    utente['username'] = nuovo_username
                    if result.get("master_key"):
                         utente['master_key'] = result.get("master_key")
                         self.page.session.set("master_key", result.get("master_key"))
                    self.page.session.set("utente_loggato", utente)
                
                recovery_key = result.get("recovery_key")
                
                # Show recovery key dialog identical to registration
                def close_dialog(e):
                    dialog.open = False
                    if dialog in self.page.overlay:
                       self.page.overlay.remove(dialog)
                    self.page.update()
                    
                    self.controller.show_snack_bar("Profilo aggiornato con successo!", success=True)
                    # Ricarica la dashboard con la sessione valida e chiavi
                    self.page.go("/dashboard")

                dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("⚠️ SALVA LA TUA CHIAVE DI RECUPERO", weight=ft.FontWeight.BOLD, size=18),
                    content=ft.Column([
                        ft.Text("Password aggiornata! Ecco la tua chiave di recupero.", 
                               size=14, weight=ft.FontWeight.BOLD),
                        ft.Text("Questa chiave è essenziale per decriptare i tuoi dati se perdi la password.", 
                               size=12, color=ft.Colors.RED_400),
                        ft.Container(height=10),
                        ft.TextField(
                            value=recovery_key,
                            read_only=True,
                            multiline=True,
                            text_size=12,
                            border_color=ft.Colors.BLUE_400,
                            text_style=ft.TextStyle(font_family="Courier New")
                        ),
                    ], tight=True, scroll=ft.ScrollMode.AUTO, width=500),
                    actions=[
                        ft.TextButton("✅ Ho salvato e capito", on_click=close_dialog, 
                                     style=ft.ButtonStyle(color=ft.Colors.GREEN_400))
                    ],
                    actions_alignment=ft.MainAxisAlignment.END
                )
                
                self.page.overlay.append(dialog)
                dialog.open = True
                self.page.update()

            else:
                error_msg = result.get("error") if result else "Errore sconosciuto"
                self.reset_status_text.value = f"Errore aggiornamento: {error_msg}"
                self.reset_status_text.color = ft.Colors.RED
                self.reset_status_text.visible = True
                btn_salva.disabled = False
                self.page.update()
        except Exception as ex:
            self.controller.hide_loading()
            self.reset_status_text.value = f"Errore: {ex}"
            self.reset_status_text.color = ft.Colors.RED
            self.reset_status_text.visible = True
            btn_salva.disabled = False
            self.page.update()