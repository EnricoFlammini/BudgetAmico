import flet as ft
from db.gestione_db import (ottieni_tutti_i_conti_utente, imposta_conto_default_utente, ottieni_conto_default_utente,
                          ottieni_dettagli_utente, aggiorna_profilo_utente, cambia_password, hash_password)


class ImpostazioniTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc

        # I controlli verranno creati dinamicamente per supportare il multilingue
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
        self.page.client_storage.set("settings.language", lang_code)
        self.controller.update_all_views(is_initial_load=True)

    def _valuta_cambiata(self, e):
        """Callback per il cambio valuta."""
        currency_code = e.control.value
        self.controller.loc.set_currency(currency_code)
        self.page.client_storage.set("settings.currency", currency_code)
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
        successo_profilo = aggiorna_profilo_utente(id_utente, dati_profilo)

        # Aggiorna password se inserita
        nuova_password = self.txt_nuova_password.value
        conferma_password = self.txt_conferma_password.value
        successo_password = True

        if nuova_password:
            if nuova_password == conferma_password:
                successo_password = cambia_password(id_utente, hash_password(nuova_password))
                if not successo_password:
                    self.controller.show_error_dialog("Errore durante il cambio password.")
            else:
                self.txt_conferma_password.error_text = loc.get("passwords_do_not_match")
                self.content.update()
                return

        if successo_profilo and successo_password:
            self.controller.show_snack_bar(loc.get("profile_saved_success"), success=True)
            self.controller.update_all_views() # Ricarica tutto per riflettere i cambiamenti
        elif not successo_profilo:
            self.controller.show_error_dialog("Errore salvataggio profilo. Username o Email potrebbero essere già in uso.")


    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        loc = self.controller.loc

        # Controlli Lingua e Valuta
        self.dd_lingua = ft.Dropdown(
            label=loc.get("language"),
            options=[
                ft.dropdown.Option("it", "Italiano"),
                ft.dropdown.Option("en", "English"),
                ft.dropdown.Option("es", "Español"),
                ft.dropdown.Option("de", "Deutsch"),
            ],
            value=self.controller.loc.language,
            on_change=self._lingua_cambiata
        )
        self.dd_valuta = ft.Dropdown(
            label=loc.get("currency"),
            options=[ft.dropdown.Option(key, f"{key} ({info['symbol']})") for key, info in
                     self.controller.loc.currencies.items()],
            value=self.controller.loc.currency,
            on_change=self._valuta_cambiata
        )

        # Controlli Conto Predefinito
        self.dd_conto_default = ft.Dropdown(label=loc.get("account"))
        self.btn_salva_conto_default = ft.ElevatedButton(
            loc.get("save_default_account"),
            icon=ft.Icons.SAVE,
            on_click=self._salva_conto_default_cliccato
        )

        # --- NUOVI CONTROLLI PROFILO UTENTE ---
        self.txt_username = ft.TextField(label=loc.get("username"))
        self.txt_email = ft.TextField(label=loc.get("email"))
        self.txt_nome = ft.TextField(label=loc.get("name"))
        self.txt_cognome = ft.TextField(label="Cognome")
        self.txt_data_nascita = ft.TextField(label=loc.get("date_of_birth"))
        self.txt_codice_fiscale = ft.TextField(label=loc.get("tax_code"))
        self.txt_indirizzo = ft.TextField(label=loc.get("address"))
        self.txt_nuova_password = ft.TextField(label=loc.get("new_password"), password=True, can_reveal_password=True)
        self.txt_conferma_password = ft.TextField(label=loc.get("confirm_new_password"), password=True, can_reveal_password=True)
        self.btn_salva_profilo = ft.ElevatedButton(
            loc.get("save_profile"),
            icon=ft.Icons.SAVE,
            on_click=self._salva_profilo_cliccato
        )
        # --- FINE NUOVI CONTROLLI ---

        return [
            ft.Text(loc.get("language_and_currency"), size=24, weight=ft.FontWeight.BOLD),
            ft.Text(loc.get("language_and_currency_desc")),
            ft.Divider(),
            ft.Row([
                self.dd_lingua,
                self.dd_valuta,
            ], spacing=10),

            ft.Divider(height=30),

            ft.Text(loc.get("default_account"), size=24, weight=ft.FontWeight.BOLD),
            ft.Text(loc.get("default_account_desc")),
            ft.Divider(),
            ft.Row([
                self.dd_conto_default,
                self.btn_salva_conto_default
            ], spacing=10),

            ft.Divider(height=30),

            ft.Text(loc.get("user_profile"), size=24, weight=ft.FontWeight.BOLD),
            ft.Text(loc.get("user_profile_desc")),
            ft.Divider(),
            ft.Row([self.txt_username, self.txt_email], spacing=10),
            ft.Row([self.txt_nome, self.txt_cognome], spacing=10),
            ft.Row([self.txt_data_nascita, self.txt_codice_fiscale], spacing=10),
            self.txt_indirizzo,
            ft.Divider(height=20),
            ft.Text(loc.get("change_password"), weight=ft.FontWeight.BOLD),
            self.txt_nuova_password,
            self.txt_conferma_password,
            ft.Row(
                [self.btn_salva_profilo],
                alignment=ft.MainAxisAlignment.END
            ),

            ft.Divider(height=30),

            ft.Text(loc.get("backup_and_restore"), size=24, weight=ft.FontWeight.BOLD),
            ft.Text(loc.get("backup_and_restore_desc")),
            ft.Divider(),
            ft.Row(
                [
                    ft.ElevatedButton(
                        loc.get("create_backup"),
                        icon=ft.Icons.SAVE,
                        on_click=lambda e: self.controller.backup_dati_clicked(),
                        bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE
                    ),
                    ft.ElevatedButton(loc.get("restore_from_backup"), icon=ft.Icons.RESTORE,
                                      on_click=lambda e: self.controller.ripristina_dati_clicked()),
                ]
            )
        ]

    def update_view_data(self, is_initial_load=False):
        self.content.controls = self.build_controls()

        # Popola e imposta il conto di default
        utente_id = self.controller.get_user_id()
        if utente_id:
            tutti_i_conti = ottieni_tutti_i_conti_utente(utente_id)
            conti_filtrati = [c for c in tutti_i_conti if c['tipo'] not in ['Investimento', 'Fondo Pensione']]

            opzioni_conto = []
            for c in conti_filtrati:
                prefix = "C" if c['is_condiviso'] else "P"
                opzioni_conto.append(ft.dropdown.Option(key=f"{prefix}{c['id_conto']}", text=c['nome_conto']))
            self.dd_conto_default.options = opzioni_conto

            conto_default_info = ottieni_conto_default_utente(utente_id)
            if conto_default_info:
                self.dd_conto_default.value = f"{conto_default_info['tipo'][0].upper()}{conto_default_info['id']}"

            # Popola i campi del profilo utente
            dati_utente = ottieni_dettagli_utente(utente_id)
            if dati_utente:
                self.txt_username.value = dati_utente.get("username", "")
                self.txt_email.value = dati_utente.get("email", "")
                self.txt_nome.value = dati_utente.get("nome", "")
                self.txt_cognome.value = dati_utente.get("cognome", "")
                self.txt_data_nascita.value = dati_utente.get("data_nascita", "")
                self.txt_codice_fiscale.value = dati_utente.get("codice_fiscale", "")
                self.txt_indirizzo.value = dati_utente.get("indirizzo", "")

        if self.page:
            self.page.update()