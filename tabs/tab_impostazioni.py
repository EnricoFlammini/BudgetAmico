import flet as ft
import datetime
from utils.styles import AppColors, AppStyles, PageConstants
from db.gestione_db import (
    imposta_conto_default_utente, aggiorna_profilo_utente, cambia_password, hash_password,
    ottieni_tutti_i_conti_utente, ottieni_conto_default_utente, ottieni_dettagli_utente, ottieni_carte_utente
)
from utils.async_task import AsyncTask
from utils.logger import setup_logger

logger = setup_logger("ImpostazioniTab")

class ImpostazioniTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page
        self.loc = controller.loc
        
        # Cache complexities
        from db.gestione_db import get_password_complexity_config
        self.pwd_config = get_password_complexity_config()

        self.content = ft.Column(
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
            spacing=15,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

    def _lingua_cambiata(self, e):
        """Callback per il cambio lingua."""
        lang_code = e.control.value
        self.controller.loc.set_language(lang_code)
        self.controller.page.client_storage.set("settings.language", lang_code)
        self.controller.update_all_views(is_initial_load=True)

    def _valuta_cambiata(self, e):
        """Callback per il cambio valuta."""
        currency_code = e.control.value
        self.controller.loc.set_currency(currency_code)
        self.controller.page.client_storage.set("settings.currency", currency_code)
        self.controller.update_all_views()

    def _salva_conto_default_cliccato(self, e):
        """Salva il conto di default selezionato."""
        selected_key = self.dd_conto_default.value
        if not selected_key:
            return

        id_utente = self.controller.get_user_id()
        tipo_conto = selected_key[0]
        id_conto = int(selected_key[1:])

        if tipo_conto == 'P':
            imposta_conto_default_utente(id_utente, id_conto_personale=id_conto)
        elif tipo_conto == 'C':
            imposta_conto_default_utente(id_utente, id_conto_condiviso=id_conto)
        elif tipo_conto == 'K':
            imposta_conto_default_utente(id_utente, id_carta_default=id_conto)

        self.controller.show_snack_bar("Conto predefinito salvato con successo!", success=True)

    def _salva_profilo_cliccato(self, e):
        """Salva le modifiche al profilo utente."""
        loc = self.loc
        id_utente = self.controller.get_user_id()

        # Aggiorna dati profilo
        dati_profilo = {
            "username": self.txt_username.value,
            "email": self.txt_email.value,
            "nome": self.txt_nome.value,
            "cognome": self.txt_cognome.value,
            "data_nascita": self.txt_data_nascita.value,
            "codice_fiscale": self.txt_codice_fiscale.value,
            "indirizzo": self.txt_indirizzo.value,
        }
        
        master_key_b64 = self.controller.page.session.get("master_key")
        
        successo_profilo = aggiorna_profilo_utente(id_utente, dati_profilo, master_key_b64)

        # Aggiorna password se inserita
        nuova_password = self.txt_nuova_password.value
        conferma_password = self.txt_conferma_password.value
        successo_password = True

        if nuova_password:
            # Check Complessità (v0.48)
            pwd_errors = self._check_password_complexity(nuova_password)
            if pwd_errors:
                self.txt_nuova_password.error_text = "Requisiti: " + ", ".join(pwd_errors)
                successo_password = False
                self.page.update()
            elif nuova_password == conferma_password:
                successo_password = cambia_password(id_utente, hash_password(nuova_password))
                if not successo_password:
                    self.controller.show_error_dialog("Errore durante il cambio password.")
            else:
                self.txt_conferma_password.error_text = loc.get("passwords_do_not_match")
                successo_password = False
        
        # Mostra messaggio di conferma o errore
        logger.debug(f"_salva_profilo_cliccato: successo_profilo={successo_profilo}, successo_password={successo_password}")
        if successo_profilo and successo_password:
            self.controller.show_snack_bar("Profilo aggiornato con successo!", success=True)
            # Pulisci i campi password dopo il salvataggio
            self.txt_nuova_password.value = ""
            self.txt_conferma_password.value = ""
            self.txt_conferma_password.error_text = None
            if self.controller.page:
                self.controller.page.update()
        elif not successo_profilo:
            self.controller.show_snack_bar("Errore durante l'aggiornamento del profilo.", success=False)

    def build_controls(self):
        loc = self.loc
        
        self.dd_lingua = ft.Dropdown(
            label=loc.get("language"),
            options=[
                ft.dropdown.Option("it", "Italiano"),
                ft.dropdown.Option("en", "English"),
                ft.dropdown.Option("es", "Español"),
                ft.dropdown.Option("de", "Deutsch"),
            ],
            value=self.controller.loc.language,
            on_change=self._lingua_cambiata,
            border_color=ft.Colors.OUTLINE
        )
        
        self.dd_valuta = ft.Dropdown(
            label=loc.get("currency"),
            options=[ft.dropdown.Option(key, f"{key} ({info['symbol']})") for key, info in
                     self.controller.loc.currencies.items()],
            value=self.controller.loc.currency,
            on_change=self._valuta_cambiata,
            border_color=ft.Colors.OUTLINE
        )

        self.dd_conto_default = ft.Dropdown(label=loc.get("account"), border_color=ft.Colors.OUTLINE)
        
        self.btn_salva_conto_default = ft.ElevatedButton(
            loc.get("save_default_account"),
            icon=ft.Icons.SAVE,
            on_click=self._salva_conto_default_cliccato,
            bgcolor=AppColors.PRIMARY,
            color=AppColors.ON_PRIMARY
        )

        self.txt_username = ft.TextField(label=loc.get("username"), border_color=ft.Colors.OUTLINE)
        self.txt_email = ft.TextField(label=loc.get("email"), border_color=ft.Colors.OUTLINE)
        self.txt_nome = ft.TextField(label=loc.get("name"), border_color=ft.Colors.OUTLINE)
        self.txt_cognome = ft.TextField(label=loc.get("surname"), border_color=ft.Colors.OUTLINE)
        
        # Data di Nascita con DatePicker
        def on_date_change(e):
            if e.control.value:
                self.txt_data_nascita.value = e.control.value.strftime("%Y-%m-%d")
            self.date_picker.open = False
            self.page.update()

        def on_dismiss(e):
            self.date_picker.open = False
            self.page.update()

        self.date_picker = ft.DatePicker(
            on_change=on_date_change,
            on_dismiss=on_dismiss,
            first_date=datetime.datetime(1900, 1, 1),
            last_date=datetime.datetime.now(),
        )
        
        self.txt_data_nascita = ft.TextField(
            label=loc.get("date_of_birth"), 
            border_color=ft.Colors.OUTLINE,
            suffix_icon=ft.Icons.CALENDAR_MONTH,
            on_focus=lambda _: self.page.open(self.date_picker),
            read_only=True
        )
        
        self.txt_codice_fiscale = ft.TextField(label=loc.get("tax_code"), border_color=ft.Colors.OUTLINE, visible=False)
        self.txt_indirizzo = ft.TextField(label=loc.get("address"), border_color=ft.Colors.OUTLINE, visible=False)
        
        # Password Strength (v0.48)
        self.pwd_strength_bar = ft.ProgressBar(value=0, width=300, color=ft.Colors.RED, bgcolor=ft.Colors.GREY_200, visible=False)
        self.pwd_strength_text = ft.Text("", size=12, color=ft.Colors.GREY_600, visible=False)
        
        self.txt_nuova_password = ft.TextField(
            label=loc.get("new_password"), 
            password=True, 
            can_reveal_password=True, 
            border_color=ft.Colors.OUTLINE,
            on_change=self._on_password_change
        )
        self.txt_conferma_password = ft.TextField(label=loc.get("confirm_new_password"), password=True, can_reveal_password=True, border_color=ft.Colors.OUTLINE)
        
        # Toggle per campi opzionali
        def toggle_extra_fields(e):
            self.txt_codice_fiscale.visible = not self.txt_codice_fiscale.visible
            self.txt_indirizzo.visible = not self.txt_indirizzo.visible
            btn_extra.icon = ft.Icons.KEYBOARD_ARROW_UP if self.txt_codice_fiscale.visible else ft.Icons.KEYBOARD_ARROW_DOWN
            self.page.update()
            
        btn_extra = ft.TextButton("Dati Aggiuntivi (CF, Indirizzo)", icon=ft.Icons.KEYBOARD_ARROW_DOWN, on_click=toggle_extra_fields)
        
        self.btn_salva_profilo = ft.ElevatedButton(
            loc.get("save_profile"),
            icon=ft.Icons.SAVE,
            on_click=self._salva_profilo_cliccato,
            bgcolor=AppColors.PRIMARY,
            color=AppColors.ON_PRIMARY
        )

        return [
            # Titolo Pagina
            AppStyles.title_text(loc.get("settings")),
            
            # Sezione Lingua e Valuta
            AppStyles.section_header(loc.get("language_and_currency")),
            AppStyles.page_divider(),
            ft.ResponsiveRow([
                ft.Column([self.dd_lingua], col={"xs": 12, "sm": 6}),
                ft.Column([self.dd_valuta], col={"xs": 12, "sm": 6}),
            ]),

            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),

            # Sezione Conto Predefinito
            AppStyles.section_header(loc.get("default_account")),
            AppStyles.page_divider(),
            ft.ResponsiveRow([
                ft.Column([self.dd_conto_default], col={"xs": 12, "sm": 8}),
                ft.Column([self.btn_salva_conto_default], col={"xs": 12, "sm": 4}),
            ]),
            
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),

            # Sezione Profilo Utente
            AppStyles.section_header(loc.get("user_profile")),
            AppStyles.page_divider(),
            
            ft.ResponsiveRow([
                ft.Column([self.txt_username], col={"xs": 12, "sm": 6}),
                ft.Column([self.txt_email], col={"xs": 12, "sm": 6}),
            ]),
            
            ft.ResponsiveRow([
                ft.Column([self.txt_nome], col={"xs": 12, "sm": 6}),
                ft.Column([self.txt_cognome], col={"xs": 12, "sm": 6}),
            ]),
            
            ft.ResponsiveRow([
                ft.Column([self.txt_data_nascita], col={"xs": 12, "sm": 6}),
                ft.Column([btn_extra], col={"xs": 12, "sm": 6}, horizontal_alignment=ft.CrossAxisAlignment.END),
            ]),
            
            ft.ResponsiveRow([
                ft.Column([self.txt_codice_fiscale], col={"xs": 12, "sm": 6}),
                ft.Column([self.txt_indirizzo], col={"xs": 12, "sm": 6}),
            ]),

            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            AppStyles.subheader_text(loc.get("change_password")),
            
            ft.ResponsiveRow([
                ft.Column([
                    self.txt_nuova_password,
                    self.pwd_strength_bar,
                    self.pwd_strength_text
                ], col={"xs": 12, "sm": 6}),
                ft.Column([self.txt_conferma_password], col={"xs": 12, "sm": 6}),
            ]),
            
            ft.Row([self.btn_salva_profilo], alignment=ft.MainAxisAlignment.END),
            
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
            
            # Sezione Backup
            AppStyles.section_header(loc.get("backup_and_restore")),
            AppStyles.page_divider(),
            ft.ResponsiveRow(
                [
                    ft.Column([
                        ft.ElevatedButton(
                            loc.get("create_backup"),
                            icon=ft.Icons.SAVE,
                            on_click=lambda e: self.controller.backup_dati_clicked(),
                            bgcolor=AppColors.PRIMARY, color=AppColors.ON_PRIMARY,
                            width=1000 # Fill column width
                        )
                    ], col={"xs": 12, "sm": 6}),
                    
                    ft.Column([
                        ft.ElevatedButton(
                            loc.get("restore_from_backup"), 
                            icon=ft.Icons.RESTORE,
                            on_click=lambda e: self.controller.ripristina_dati_clicked(),
                            width=1000 # Fill column width
                        )
                    ], col={"xs": 12, "sm": 6}),
                ]
            ),
            ft.Row([
                ft.TextButton(
                    "Informativa Privacy",
                    icon=ft.Icons.PRIVACY_TIP,
                    on_click=lambda _: self.page.go("/privacy")
                )
            ], alignment=ft.MainAxisAlignment.CENTER),
            # Padding in fondo
            ft.Container(height=80)
        ]

    def update_view_data(self, is_initial_load=False):
        # Mostra loading locale
        self.content.controls.clear()
        self.content.controls.append(
            ft.Container(
                content=ft.ProgressRing(color=AppColors.PRIMARY),
                alignment=ft.Alignment(0, 0),
                padding=50
            )
        )
        if self.controller.page:
            self.controller.page.update()

        utente_id = self.controller.get_user_id()
        master_key_b64 = self.controller.page.session.get("master_key")

        # Avvia Task
        task = AsyncTask(
            target=self._fetch_data,
            args=(utente_id, master_key_b64),
            callback=self._on_data_loaded,
            error_callback=self._on_error
        )
        task.start()

    def _fetch_data(self, utente_id, master_key_b64):
        data = {}
        if utente_id:
            # 1. Conti utente per dropdown
            tutti_i_conti = ottieni_tutti_i_conti_utente(utente_id, master_key_b64=master_key_b64)
            data['conti_filtrati'] = [c for c in tutti_i_conti if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
            
            # 2. Conto Default
            data['conto_default_info'] = ottieni_conto_default_utente(utente_id)
            
            # 3. Carte
            data['carte'] = ottieni_carte_utente(utente_id, master_key_b64)
            
            # 4. Dati Profilo
            data['dati_utente'] = ottieni_dettagli_utente(utente_id, master_key_b64)
        return data

    def _on_data_loaded(self, result):
        try:
            self.content.controls = self.build_controls()
            
            # Popola Dropdown Conto Default
            conti_filtrati = result.get('conti_filtrati', [])
            opzioni_conto = []
            for c in conti_filtrati:
                prefix = "C" if c['is_condiviso'] else "P"
                opzioni_conto.append(ft.dropdown.Option(key=f"{prefix}{c['id_conto']}", text=c['nome_conto']))
            
            # Aggiungi Carte
            carte = result.get('carte', [])
            if carte:
                opzioni_conto.append(ft.dropdown.Option(key="DIVIDER", text="-- Carte --", disabled=True))
                for c in carte:
                    opzioni_conto.append(ft.dropdown.Option(key=f"K{c['id_carta']}", text=f"💳 {c['nome_carta']}"))

            self.dd_conto_default.options = opzioni_conto

            # Imposta valore Default
            conto_default_info = result.get('conto_default_info')
            if conto_default_info:
                tipo = conto_default_info['tipo']
                if tipo == 'personale':
                    val = f"P{conto_default_info['id']}"
                elif tipo == 'condiviso':
                    val = f"C{conto_default_info['id']}"
                elif tipo == 'carta':
                    val = f"K{conto_default_info['id']}"
                else:
                    val = None
                
                if val:
                    # Verifica che il valore esista nelle opzioni (potrebbe essere stato cancellato)
                    if any(opt.key == val for opt in opzioni_conto):
                        self.dd_conto_default.value = val

            # Popola Profilo
            dati_utente = result.get('dati_utente')
            if dati_utente:
                self.txt_username.value = dati_utente.get("username", "")
                self.txt_email.value = dati_utente.get("email", "")
                self.txt_nome.value = dati_utente.get("nome", "")
                self.txt_cognome.value = dati_utente.get("cognome", "")
                self.txt_data_nascita.value = dati_utente.get("data_nascita", "")
                self.txt_codice_fiscale.value = dati_utente.get("codice_fiscale", "")
                self.txt_indirizzo.value = dati_utente.get("indirizzo", "")

            if self.controller.page:
                self.controller.page.update()
        except Exception as e:
            self._on_error(e)

    def _on_password_change(self, e):
        """Calcola la forza della password in tempo reale."""
        pwd = self.txt_nuova_password.value
        if not pwd:
            self.pwd_strength_bar.visible = False
            self.pwd_strength_text.visible = False
            self.page.update()
            return
            
        self.pwd_strength_bar.visible = True
        self.pwd_strength_text.visible = True
        
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

    def _on_error(self, e):
        print(f"Errore ImpostazioniTab: {e}")
        try:
            self.content.controls.clear()
            self.content.controls.append(AppStyles.body_text(f"Errore durante il caricamento: {e}", color=AppColors.ERROR))
            if self.controller.page:
                self.controller.page.update()
        except:
            pass