import flet as ft
from db.gestione_db import (
    aggiungi_categoria,
    modifica_categoria,
    elimina_categoria,
    modifica_ruolo_utente,
    # ottieni_categorie, # Non più necessario qui
    ottieni_categorie_e_sottocategorie, # Usiamo questo
    imposta_budget,
    aggiungi_sottocategoria,
    modifica_sottocategoria
)


class AdminDialogs:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page
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
        self.txt_username_o_email = ft.TextField(label=self.loc.get("username_or_email"))
        self.dd_ruolo = ft.Dropdown(
            label=self.loc.get("role"),
            options=[
                ft.dropdown.Option("livello1", "Livello 1 (Accesso Completo)"),
                ft.dropdown.Option("livello2", "Livello 2 (Solo Totali Famiglia)"),
                ft.dropdown.Option("livello3", "Livello 3 (Nessun Accesso Famiglia)"),
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
                ft.dropdown.Option("admin", "Admin"),
                ft.dropdown.Option("livello1", "Livello 1"),
                ft.dropdown.Option("livello2", "Livello 2"),
                ft.dropdown.Option("livello3", "Livello 3"),
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

        self.page.dialog = self.dialog_modifica_cat
        self.dialog_modifica_cat.open = True
        self.page.update()

    def _chiudi_dialog_categoria(self, e):
        self.dialog_modifica_cat.open = False
        self.page.update()

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
            self.dialog_modifica_cat.open = False
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

        self.page.dialog = self.dialog_sottocategoria
        self.dialog_sottocategoria.open = True
        self.page.update()

    def _chiudi_dialog_sottocategoria(self, e):
        self.dialog_sottocategoria.open = False
        self.page.update()

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
            self.dialog_sottocategoria.open = False
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

    # --- Metodi Gestione Membri ---
    def apri_dialog_invito(self):
        self.txt_username_o_email.value = ""
        self.txt_username_o_email.error_text = None
        self.page.dialog = self.dialog_invito_membri
        self.dialog_invito_membri.open = True
        self.page.update()

    def _chiudi_dialog_invito(self, e):
        self.dialog_invito_membri.open = False
        self.page.update()

    def _invita_membro_cliccato(self, e):
        input_val = self.txt_username_o_email.value
        ruolo = self.dd_ruolo.value
        if not input_val:
            self.txt_username_o_email.error_text = self.loc.get("fill_all_fields")
            self.dialog_invito_membri.update()
            return

        messaggio, success = self.controller.gestisci_invito_o_sblocco(input_val, ruolo)
        self.controller.show_snack_bar(messaggio, success=success)
        if success:
            self.dialog_invito_membri.open = False
            self.controller.db_write_operation()

    def apri_dialog_modifica_ruolo(self, membro_data):
        self.membro_in_modifica = membro_data
        self.dialog_modifica_ruolo.title.value = f"{self.loc.get('edit')} {self.loc.get('role')} - {membro_data['nome_visualizzato']}"
        self.dd_modifica_ruolo.value = membro_data['ruolo']
        self.page.dialog = self.dialog_modifica_ruolo
        self.dialog_modifica_ruolo.open = True
        self.page.update()

    def _chiudi_dialog_modifica_ruolo(self, e):
        self.dialog_modifica_ruolo.open = False
        self.page.update()

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

        if success:
            self.controller.show_snack_bar("Ruolo aggiornato!", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore durante l'aggiornamento del ruolo.", success=False)

        self._chiudi_dialog_modifica_ruolo(e)

    # --- NUOVI METODI PER GESTIONE BUDGET ---
    def apri_dialog_imposta_budget(self):
        loc = self.loc
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        # Popola il dropdown con le sottocategorie
        categorie_con_sottocategorie = ottieni_categorie_e_sottocategorie(id_famiglia)
        opzioni = []
        for cat_id, cat_data in categorie_con_sottocategorie.items():
            if cat_data['sottocategorie']:
                opzioni.append(ft.dropdown.Option(key=f"cat_{cat_id}", text=cat_data['nome_categoria'], disabled=True))
                for sub in cat_data['sottocategorie']:
                    opzioni.append(ft.dropdown.Option(key=sub['id_sottocategoria'], text=f"  - {sub['nome_sottocategoria']}"))

        self.dd_budget_sottocategorie.options = opzioni
        self.dd_budget_sottocategorie.value = None
        self.txt_budget_limite.value = ""
        self.txt_budget_limite.error_text = None

        # Aggiorna prefisso valuta se è cambiato
        self.txt_budget_limite.prefix_text = loc.currencies[loc.currency]['symbol']

        self.page.dialog = self.dialog_imposta_budget
        self.dialog_imposta_budget.open = True
        self.page.update()

    def _chiudi_dialog_imposta_budget(self, e):
        self.dialog_imposta_budget.open = False
        self.page.update()

    def _salva_budget_cliccato(self, e):
        loc = self.loc
        id_famiglia = self.controller.get_family_id()
        id_sottocategoria = self.dd_budget_sottocategorie.value
        limite_str = self.txt_budget_limite.value

        if id_sottocategoria and limite_str:
            try:
                limite = float(limite_str.replace(",", "."))
                imposta_budget(id_famiglia, id_sottocategoria, limite)

                self.dialog_imposta_budget.open = False
                self.controller.show_snack_bar(loc.get("budget_saved"), success=True)

                # Aggiorna tutte le viste (così la scheda Budget si aggiorna)
                self.controller.update_all_views()

            except ValueError:
                self.txt_budget_limite.error_text = loc.get("invalid_amount")
                self.dialog_imposta_budget.update()
        else:
            self.controller.show_snack_bar(loc.get("fill_all_fields"), success=False)
    # --- FINE NUOVI METODI ---