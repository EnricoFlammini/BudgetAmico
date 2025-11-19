import flet as ft
from db.gestione_db import (
    registra_utente, verifica_login, aggiungi_utente_a_famiglia, trova_utente_per_email,
    imposta_password_temporanea, cambia_password, hash_password
)
from utils.gmail_sender import send_email_via_gmail_api
import os
import google_auth_manager


class AuthView:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc

        self.URL_BASE = os.environ.get("FLET_APP_URL", "http://localhost:8550")

        # Controlli per il Login
        self.txt_username = ft.TextField(autofocus=True)
        self.txt_password = ft.TextField(password=True, can_reveal_password=True)
        self.txt_errore_login = ft.Text(value="", color=ft.Colors.RED_500, visible=False)

        # Controlli per la Registrazione
        self.txt_reg_username = ft.TextField()
        self.txt_reg_email = ft.TextField()
        self.txt_reg_nome = ft.TextField()
        self.txt_reg_cognome = ft.TextField()
        self.txt_reg_password = ft.TextField(password=True, can_reveal_password=True)
        self.txt_reg_conferma_password = ft.TextField(password=True, can_reveal_password=True)

        # Controlli per il Recupero Password
        self.txt_recovery_email = ft.TextField(autofocus=True)
        self.recovery_status_text = ft.Text(visible=False)

        # Controlli per il Reset Password
        self.txt_reset_new_password = ft.TextField(password=True, can_reveal_password=True)
        self.txt_reset_confirm_password = ft.TextField(password=True, can_reveal_password=True)
        self.reset_status_text = ft.Text(visible=False)
        # self.reset_token = None # Non più necessario

    def login_google(self, e):
        """Avvia il flusso di autenticazione Google."""
        # Chiama la funzione authenticate dal modulo google_auth_manager
        google_auth_manager.authenticate(self.controller)

    def get_login_view(self) -> ft.View:
        """Costruisce e restituisce la vista di Login."""
        loc = self.loc
        self.txt_username.label = loc.get("username_or_email")
        self.txt_password.label = "Password"
        self.txt_username.value = ""
        self.txt_password.value = ""
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
                        )
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
                      self.txt_reg_password,
                      self.txt_reg_conferma_password]:
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
                        self.txt_reg_password,
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
        username = self.txt_username.value.strip()
        password = self.txt_password.value

        if not username or not password:
            self.txt_errore_login.value = "Inserisci username e password."
            self.txt_errore_login.visible = True
            self.page.update()
            return

        utente = verifica_login(username, password)
        if utente:
            self.txt_errore_login.visible = False
            self.controller.post_login_setup(utente)
        else:
            self.txt_errore_login.value = "Username o password non validi."
            self.txt_errore_login.visible = True
            self.page.update()

    def _registra_cliccato(self, e):
        username = self.txt_reg_username.value.strip()
        email = self.txt_reg_email.value.lower().strip()
        nome = self.txt_reg_nome.value.strip()
        cognome = self.txt_reg_cognome.value.strip()
        password = self.txt_reg_password.value
        conferma_password = self.txt_reg_conferma_password.value

        # Reset errori
        for field in [self.txt_reg_username, self.txt_reg_email, self.txt_reg_nome, self.txt_reg_cognome,
                      self.txt_reg_password,
                      self.txt_reg_conferma_password]:
            field.error_text = None

        # Validazione
        is_valid = True
        if not all([username, email, nome, cognome, password, conferma_password]):
            self.controller.show_snack_bar("Tutti i campi sono obbligatori.", success=False)
            is_valid = False
        if password != conferma_password:
            self.txt_reg_conferma_password.error_text = "Le password non coincidono."
            is_valid = False

        if not is_valid:
            self.page.update()
            return

        id_nuovo_utente = registra_utente(username, email, password, nome, cognome)

        if id_nuovo_utente:
            invito_attivo = self.page.session.get("invito_attivo")
            if invito_attivo:
                aggiungi_utente_a_famiglia(invito_attivo['id_famiglia'], id_nuovo_utente,
                                           invito_attivo['ruolo_assegnato'])
                self.page.session.remove("invito_attivo")

            self.controller.show_snack_bar("Registrazione completata! Effettua il login.", success=True)
            self.page.go("/")
        else:
            self.txt_reg_username.error_text = "Username o Email già in uso."
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
        email = self.txt_recovery_email.value.lower().strip()
        self.txt_recovery_email.error_text = None

        if not email:
            self.txt_recovery_email.error_text = self.loc.get("email_is_required")
            self.page.update()
            return

        utente = trova_utente_per_email(email)

        if utente:
            # Genera una password temporanea
            import secrets
            temp_password = secrets.token_urlsafe(8)
            temp_password_hash = hash_password(temp_password)

            if imposta_password_temporanea(utente['id_utente'], temp_password_hash):
                body = f"""
                    <html><body>
                        <p>Ciao {utente['nome']},</p>
                        <p>La tua password temporanea è: <b>{temp_password}</b></p>
                        <p>Al prossimo accesso ti verrà chiesto di impostare una nuova password personale.</p>
                    </body></html>
                    """
                send_email_via_gmail_api(email, "Password Temporanea - Budget Amico", body)

        # Mostra un messaggio generico per motivi di sicurezza
        self.recovery_status_text.value = self.loc.get("reset_link_sent_confirmation")
        self.recovery_status_text.color = ft.Colors.GREEN
        self.recovery_status_text.visible = True
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
                ft.Column(
                    [
                        ft.Text(loc.get("set_new_password_title"), size=30, weight=ft.FontWeight.BOLD),
                        self.txt_reset_new_password,
                        self.txt_reset_confirm_password,
                        self.reset_status_text,
                        ft.ElevatedButton(loc.get("save_new_password"), icon=ft.Icons.SAVE,
                                          on_click=self._salva_nuova_password),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True,
                    width=350
                )
            ]
        )

    def _salva_nuova_password(self, e):
        nuova_pass = self.txt_reset_new_password.value
        conferma_pass = self.txt_reset_confirm_password.value

        if not nuova_pass or nuova_pass != conferma_pass:
            self.reset_status_text.value = self.loc.get("passwords_do_not_match")
            self.reset_status_text.color = ft.Colors.RED
            self.reset_status_text.visible = True
            self.page.update()
            return

        id_utente = self.controller.get_user_id()
        if not id_utente:
            self.page.go("/")
            return

        success = cambia_password(id_utente, hash_password(nuova_pass))

        if success:
            self.controller.show_snack_bar(self.loc.get("password_updated_success"), success=True)
            # Ricarica la dashboard con la sessione valida
            self.page.go("/dashboard")
        else:
            self.reset_status_text.value = "Errore durante l'aggiornamento della password."
            self.reset_status_text.color = ft.Colors.RED
            self.reset_status_text.visible = True
            self.page.update()