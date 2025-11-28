import re

# Read the file
with open('views/auth_view.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Patch 1: Update _login_cliccato to store master_key
old_login = '''    def _login_cliccato(self, e):
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
            self.page.update()'''

new_login = '''    def _login_cliccato(self, e):
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
            # Store master_key in session for encryption/decryption
            if utente.get("master_key"):
                self.page.session.set("master_key", utente["master_key"])
            self.controller.post_login_setup(utente)
        else:
            self.txt_errore_login.value = "Username o password non validi."
            self.txt_errore_login.visible = True
            self.page.update()'''

content = content.replace(old_login, new_login)

# Patch 2: Update _registra_cliccato to show recovery key
old_reg = '''        result = registra_utente(nome, cognome, username, password, email, data_nascita, codice_fiscale, indirizzo)

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
            self.page.update()'''

new_reg = '''        result = registra_utente(nome, cognome, username, password, email, data_nascita, codice_fiscale, indirizzo)

        if result:
            id_nuovo_utente = result.get("id_utente")
            recovery_key = result.get("recovery_key")
            
            invito_attivo = self.page.session.get("invito_attivo")
            if invito_attivo:
                aggiungi_utente_a_famiglia(invito_attivo['id_famiglia'], id_nuovo_utente,
                                           invito_attivo['ruolo_assegnato'])
                self.page.session.remove("invito_attivo")

            # Show recovery key dialog
            def close_dialog(e):
                dialog.open = False
                self.page.update()
                self.page.go("/")
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("⚠️ SALVA LA TUA CHIAVE DI RECUPERO", weight=ft.FontWeight.BOLD),
                content=ft.Column([
                    ft.Text("Questa è la tua chiave di recupero. SALVALA IN UN POSTO SICURO!", size=14),
                    ft.Text("Se perdi la password, questa chiave è l'UNICO modo per recuperare i tuoi dati.", 
                           size=12, color=ft.Colors.RED_400),
                    ft.Container(height=10),
                    ft.TextField(
                        value=recovery_key,
                        read_only=True,
                        multiline=True,
                        text_size=12,
                        border_color=ft.Colors.BLUE_400
                    ),
                    ft.Container(height=10),
                    ft.Text("⚠️ Senza questa chiave, i dati criptati saranno PERSI per sempre!", 
                           size=11, italic=True, color=ft.Colors.ORANGE_400)
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                actions=[
                    ft.TextButton("Ho salvato la chiave", on_click=close_dialog)
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()
        else:
            self.txt_reg_username.error_text = "Username o Email già in uso."
            self.page.update()'''

content = content.replace(old_reg, new_reg)

# Write back
with open('views/auth_view.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched auth_view.py successfully")
