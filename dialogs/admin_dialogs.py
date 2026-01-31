import flet as ft
from db.gestione_db import (
    aggiungi_categoria,
    modifica_categoria,
    elimina_categoria,
    elimina_sottocategoria,
    modifica_ruolo_utente,
    ottieni_categorie_e_sottocategorie,
    imposta_budget,
    aggiungi_sottocategoria,
    modifica_sottocategoria,
    crea_utente_invitato,
    ottieni_utente_da_email,
    aggiungi_utente_a_famiglia,
    get_smtp_config
)
from utils.email_sender import send_email


class AdminDialogs:
    def __init__(self, controller):
        self.controller = controller
        # self.controller.page = controller.page # Removed for Flet 0.80 compatibility
        self.loc = controller.loc

        # --- Dialogo Gestione Categoria ---
        self.txt_nome_categoria = ft.TextField(label=self.loc.get("category_name"))
        self.id_categoria_in_modifica = None
        self.dialog_modifica_cat = ft.AlertDialog(
            modal=True,
            title=ft.Text(),  # Verrà impostato dinamicamente
            content=self.txt_nome_categoria,
            actions=[
                ft.TextButton(self.loc.get("cancel"), on_click=self._chiudi_dialog_categoria),
                ft.TextButton(self.loc.get("save"), on_click=self._salva_categoria_cliccato),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # --- Dialogo Gestione Sottocategoria ---
        self.txt_nome_sottocategoria = ft.TextField(label=self.loc.get("subcategory_name"))
        self.id_sottocategoria_in_modifica = None
        self.id_categoria_padre = None
        self.dialog_sottocategoria = ft.AlertDialog(
            modal=True,
            title=ft.Text(),  # Verrà impostato dinamicamente
            content=self.txt_nome_sottocategoria,
            actions=[
                ft.TextButton(self.loc.get("cancel"), on_click=self._chiudi_dialog_sottocategoria),
                ft.TextButton(self.loc.get("save"), on_click=self._salva_sottocategoria_cliccato),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # --- Dialogo Gestione Membri ---
        self.txt_username_o_email = ft.TextField(label="Email Utente")
        self.dd_ruolo = ft.Dropdown(
            label=self.loc.get("role"),
            options=[
                ft.dropdown.Option("livello1", "Livello 1 (Dettagli Famiglia)"),
                ft.dropdown.Option("livello2", "Livello 2 (Patrimonio + Totali Famiglia)"),
                ft.dropdown.Option("livello3", "Livello 3 (Solo Dati Personali)"),
            ],
            value="livello1"
        )
        
        self.dialog_invito_membri = ft.AlertDialog(
            modal=True,
            title=ft.Text(self.loc.get("invite_member")),
            content=ft.Column([self.txt_username_o_email, self.dd_ruolo], tight=True),
            actions=[
                ft.TextButton(self.loc.get("cancel"), on_click=self._chiudi_dialog_invito),
                ft.TextButton(self.loc.get("invite"), on_click=self._invita_membro_cliccato),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # --- Dialogo Modifica Ruolo ---
        self.membro_in_modifica = None
        self.dd_modifica_ruolo = ft.Dropdown(
            label=self.loc.get("role"),
            options=[
                ft.dropdown.Option("admin", "Admin (Gestione Completa)"),
                ft.dropdown.Option("livello1", "Livello 1 (Dettagli Famiglia)"),
                ft.dropdown.Option("livello2", "Livello 2 (Patrimonio + Totali Famiglia)"),
                ft.dropdown.Option("livello3", "Livello 3 (Solo Dati Personali)"),
            ]
        )
        self.dialog_modifica_ruolo = ft.AlertDialog(
            modal=True,
            title=ft.Text(),  # Dinamico
            content=self.dd_modifica_ruolo,
            actions=[
                ft.TextButton(self.loc.get("cancel"), on_click=self._chiudi_dialog_modifica_ruolo),
                ft.TextButton(self.loc.get("save"), on_click=self._salva_ruolo_cliccato),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # --- NUOVO DIALOGO: IMPOSTA BUDGET ---
        self.dd_budget_sottocategorie = ft.Dropdown(label=self.loc.get("subcategory"))
        self.txt_budget_limite = ft.TextField(label=self.loc.get("limit_amount"),
                                              prefix=self.loc.currencies[self.loc.currency]['symbol'])

        self.dialog_imposta_budget = ft.AlertDialog(
            modal=True,
            title=ft.Text(self.loc.get("set_monthly_budget")),
            content=ft.Column([self.dd_budget_sottocategorie, self.txt_budget_limite], tight=True),
            actions=[
                ft.TextButton(self.loc.get("cancel"), on_click=self._chiudi_dialog_imposta_budget),
                ft.TextButton(self.loc.get("save"), on_click=self._salva_budget_cliccato),
            ]
        )
        # --- FINE NUOVO DIALOGO ---

    # --- Metodi Gestione Categoria ---
    def apri_dialog_categoria(self, categoria_data=None):
        self.txt_nome_categoria.error_text = None
        if categoria_data:
            self.dialog_modifica_cat.title.value = self.loc.get("edit") + " " + self.loc.get("category")
            self.txt_nome_categoria.value = categoria_data['nome_categoria']
            self.id_categoria_in_modifica = categoria_data['id_categoria']
        else:
            self.dialog_modifica_cat.title.value = self.loc.get("add_category")
            self.txt_nome_categoria.value = ""
            self.id_categoria_in_modifica = None

        self.controller.page.open(self.dialog_modifica_cat)
        self.controller.page.update()

    def _chiudi_dialog_categoria(self, e):
        self.controller.page.close(self.dialog_modifica_cat)
        self.controller.page.update()

    def _salva_categoria_cliccato(self, e):
        nome_cat = self.txt_nome_categoria.value
        if not nome_cat:
            self.txt_nome_categoria.error_text = self.loc.get("fill_all_fields")
            self.dialog_modifica_cat.update()
            return

        id_famiglia = self.controller.get_family_id()
        success = False
        if self.id_categoria_in_modifica:
            success = modifica_categoria(self.id_categoria_in_modifica, nome_cat)
        else:
            success = aggiungi_categoria(id_famiglia, nome_cat)

        if success:
            self.controller.show_snack_bar("Categoria salvata con successo!", success=True)
            self.controller.page.close(self.dialog_modifica_cat)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore: Categoria già esistente o errore DB.", success=False)

    # --- Metodi Gestione Sottocategoria ---
    def apri_dialog_sottocategoria(self, sub_cat_data=None, id_categoria=None):
        self.txt_nome_sottocategoria.error_text = None
        if sub_cat_data:
            # Modalità modifica
            self.dialog_sottocategoria.title.value = self.loc.get("edit") + " " + self.loc.get("subcategory")
            self.txt_nome_sottocategoria.value = sub_cat_data['nome_sottocategoria']
            self.id_sottocategoria_in_modifica = sub_cat_data['id_sottocategoria']
            self.id_categoria_padre = sub_cat_data['id_categoria']
        elif id_categoria:
            # Modalità aggiunta
            self.dialog_sottocategoria.title.value = self.loc.get("add_subcategory")
            self.txt_nome_sottocategoria.value = ""
            self.id_sottocategoria_in_modifica = None
            self.id_categoria_padre = id_categoria
        else:
            return # Non fare nulla se non ci sono dati sufficienti

        self.controller.page.open(self.dialog_sottocategoria)
        self.controller.page.update()

    def _chiudi_dialog_sottocategoria(self, e):
        self.controller.page.close(self.dialog_sottocategoria)
        self.controller.page.update()

    def _salva_sottocategoria_cliccato(self, e):
        nome_sottocat = self.txt_nome_sottocategoria.value
        if not nome_sottocat:
            self.txt_nome_sottocategoria.error_text = self.loc.get("fill_all_fields")
            self.dialog_sottocategoria.update()
            return

        if self.id_sottocategoria_in_modifica:
            success = modifica_sottocategoria(self.id_sottocategoria_in_modifica, nome_sottocat)
        else:
            success = aggiungi_sottocategoria(self.id_categoria_padre, nome_sottocat)

        if success:
            self.controller.show_snack_bar("Sottocategoria salvata con successo!", success=True)
            self.controller.page.close(self.dialog_sottocategoria)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore: Sottocategoria già esistente o errore DB.", success=False)

    def elimina_categoria_cliccato(self, e):
        id_categoria = e.control.data
        success = elimina_categoria(id_categoria)
        if success:
            self.controller.show_snack_bar("Categoria eliminata.", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore durante l'eliminazione della categoria.", success=False)

    def elimina_sottocategoria_cliccato(self, e):
        id_sottocategoria = e.control.data
        success = elimina_sottocategoria(id_sottocategoria)
        if success:
            self.controller.show_snack_bar("Sottocategoria eliminata.", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore durante l'eliminazione della sottocategoria.", success=False)

    # --- Metodi Gestione Membri ---
    def apri_dialog_invito(self):
        self.txt_username_o_email.value = ""
        self.txt_username_o_email.error_text = None
        
        # Usa page.open() per gestire correttamente il dialog
        self.controller.page.open(self.dialog_invito_membri)
        self.controller.page.update()

    def _chiudi_dialog_invito(self, e=None):
        # Usa page.close() per chiudere correttamente il dialog
        self.controller.page.close(self.dialog_invito_membri)
        self.controller.page.update()

    def _invita_membro_cliccato(self, e):
        email = self.txt_username_o_email.value
        ruolo = self.dd_ruolo.value
        if not email:
            self.txt_username_o_email.error_text = self.loc.get("fill_all_fields")
            self.dialog_invito_membri.update()
            return

        id_famiglia = self.controller.get_family_id()
        
        # 1. Check if user exists
        existing_user = ottieni_utente_da_email(email)
        
        if existing_user:
            # Add to family
            success = aggiungi_utente_a_famiglia(id_famiglia, existing_user['id_utente'], ruolo)
            # Chiudi il dialog prima del feedback
            self._chiudi_dialog_invito(e)
            if success:
                self.controller.show_snack_bar(f"Utente {email} aggiunto alla famiglia!", success=True)
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("Errore durante l'aggiunta dell'utente.", success=False)
        else:
            # Create new user and invite - pass admin credentials to share family key
            master_key_b64 = self.controller.page.session.get("master_key")
            current_user_id = self.controller.get_user_id()
            credenziali = crea_utente_invitato(email, ruolo, id_famiglia, id_admin=current_user_id, master_key_b64=master_key_b64)
            if credenziali:
                # Chiudi il dialog SUBITO (prima dell'invio email)
                self._chiudi_dialog_invito(e)
                self.controller.db_write_operation()
                self.controller.show_snack_bar(f"Utente creato. Invio email in corso...", success=True)
                
                # Recupera Configurazione SMTP decriptata
                smtp_config = get_smtp_config(id_famiglia, master_key_b64, current_user_id)
                
                # Invia email in modo asincrono
                from utils.async_task import AsyncTask
                
                def _send_invite_email():
                    return send_email(
                        to_email=email,
                        subject="Benvenuto in Budget Amico - Credenziali di Accesso",
                        body=f"Sei stato invitato nella famiglia!\n\nEcco le tue credenziali temporanee:\nEmail: {email}\nUsername: {credenziali['username']}\nPassword: {credenziali['password']}\n\nAccedi e completa il tuo profilo.",
                        smtp_config=smtp_config
                    )
                
                def _on_email_sent(result):
                    success, error = result
                    if success:
                        self.controller.show_snack_bar(f"Email inviata a {email}!", success=True)
                    else:
                        self.controller.show_snack_bar(f"Errore invio email: {error}", success=False)
                
                def _on_email_error(err):
                    self.controller.show_snack_bar(f"Errore invio email: {err}", success=False)
                
                task = AsyncTask(
                    target=_send_invite_email,
                    callback=_on_email_sent,
                    error_callback=_on_email_error
                )
                task.start()
            else:
                # Chiudi il dialog anche in caso di errore
                self._chiudi_dialog_invito(e)
                self.controller.show_snack_bar("Errore durante la creazione dell'utente.", success=False)

    def apri_dialog_modifica_ruolo(self, membro_data):
        self.membro_in_modifica = membro_data
        self.dialog_modifica_ruolo.title.value = f"{self.loc.get('edit')} {self.loc.get('role')} - {membro_data['nome_visualizzato']}"
        self.dd_modifica_ruolo.value = membro_data['ruolo']
        if self.dialog_modifica_ruolo not in self.controller.page.overlay:
            self.controller.page.overlay.append(self.dialog_modifica_ruolo)
        self.dialog_modifica_ruolo.open = True
        self.controller.page.update()

    def _chiudi_dialog_modifica_ruolo(self, e):
        self.dialog_modifica_ruolo.open = False
        self.controller.page.update()
        if self.dialog_modifica_ruolo in self.controller.page.overlay:
            self.controller.page.overlay.remove(self.dialog_modifica_ruolo)
        self.controller.page.update()

    def _salva_ruolo_cliccato(self, e):
        if not self.membro_in_modifica:
            return

        id_utente = self.membro_in_modifica['id_utente']
        nuovo_ruolo = self.dd_modifica_ruolo.value
        id_famiglia = self.controller.get_family_id()

        if not all([id_utente, nuovo_ruolo, id_famiglia]):
            self.controller.show_snack_bar("Errore: Dati mancanti.", success=False)
            return

        success = modifica_ruolo_utente(id_utente, id_famiglia, nuovo_ruolo)

        # Prima chiudi il dialog, poi aggiorna i dati
        self._chiudi_dialog_modifica_ruolo(e)

        if success:
            self.controller.show_snack_bar("Ruolo aggiornato!", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore durante l'aggiornamento del ruolo.", success=False)

    # --- NUOVI METODI PER GESTIONE BUDGET ---
    def apri_dialog_imposta_budget(self):
        loc = self.loc
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        # Popola il dropdown con le sottocategorie
        categorie_con_sottocategorie = ottieni_categorie_e_sottocategorie(id_famiglia)
        opzioni = []
        for cat_data in categorie_con_sottocategorie:
            if cat_data['sottocategorie']:
                opzioni.append(ft.dropdown.Option(key=f"cat_{cat_data['id_categoria']}", text=cat_data['nome_categoria'], disabled=True))
                for sub in cat_data['sottocategorie']:
                    opzioni.append(ft.dropdown.Option(key=sub['id_sottocategoria'], text=f"  - {sub['nome_sottocategoria']}"))

        self.dd_budget_sottocategorie.options = opzioni
        self.dd_budget_sottocategorie.value = None
        self.txt_budget_limite.value = ""
        self.txt_budget_limite.error_text = None

        # Aggiorna prefisso valuta se è cambiato
        self.txt_budget_limite.prefix_text = loc.currencies[loc.currency]['symbol']

        # Use page.open instead of overlay manipulation
        self.controller.page.open(self.dialog_imposta_budget)
        self.controller.page.update()

    def _chiudi_dialog_imposta_budget(self, e):
        # Use page.close
        self.controller.page.close(self.dialog_imposta_budget)
        self.controller.page.update()

    def _salva_budget_cliccato(self, e):
        loc = self.loc
        id_famiglia = self.controller.get_family_id()
        id_sottocategoria = self.dd_budget_sottocategorie.value
        limite_str = self.txt_budget_limite.value

        if id_sottocategoria and limite_str:
            try:
                limite = float(limite_str.replace(",", "."))
                
                # Pass master_key_b64 and id_utente
                master_key_b64 = self.controller.page.session.get("master_key")
                id_utente = self.controller.get_user_id()
                
                imposta_budget(id_famiglia, id_sottocategoria, limite, master_key_b64, id_utente)

                self.controller.page.close(self.dialog_imposta_budget)
                self.controller.show_snack_bar(loc.get("budget_saved"), success=True)

                # Aggiorna tutte le viste (così la scheda Budget si aggiorna)
                self.controller.update_all_views()

            except ValueError:
                self.txt_budget_limite.error_text = loc.get("invalid_amount")
                self.dialog_imposta_budget.update()
        else:
            self.controller.show_snack_bar(loc.get("fill_all_fields"), success=False)
