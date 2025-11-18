import flet as ft
from functools import partial
from db.gestione_db import (
    modifica_categoria,
    aggiungi_categoria,
    elimina_categoria,
    ottieni_categorie_e_sottocategorie,
    imposta_budget,
    modifica_ruolo_utente,
    aggiungi_sottocategoria,
    modifica_sottocategoria,
    elimina_sottocategoria
)


class AdminDialogs:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc

        # Dialogo Categoria
        self.txt_nome_cat = ft.TextField()
        self.id_cat_in_modifica = None
        self.dialog_modifica_cat = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=self.txt_nome_cat,
            actions=[
                ft.TextButton(on_click=self.chiudi_dialog_categoria),
                ft.TextButton(on_click=self.salva_categoria_cliccato)
            ]
        )
        
        # Dialogo Sottocategoria
        self.txt_nome_sottocat = ft.TextField()
        self.id_sottocat_in_modifica = None
        self.id_cat_padre = None
        self.dialog_sottocategoria = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=self.txt_nome_sottocat,
            actions=[
                ft.TextButton(on_click=self.chiudi_dialog_sottocategoria),
                ft.TextButton(on_click=self.salva_sottocategoria_cliccato)
            ]
        )

        # Dialogo Imposta Budget
        self.dd_sottocategoria_budget = ft.Dropdown()
        self.txt_importo_budget = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dialog_imposta_budget = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([self.dd_sottocategoria_budget, self.txt_importo_budget], tight=True),
            actions=[
                ft.TextButton(on_click=self.chiudi_dialog_budget),
                ft.TextButton(on_click=self.salva_budget_cliccato)
            ]
        )

        # Dialogo Invito Membri
        self.txt_username_invito = ft.TextField()
        self.dd_ruolo_invito = ft.Dropdown()
        self.dialog_invito_membri = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([self.txt_username_invito, self.dd_ruolo_invito], tight=True),
            actions=[
                ft.TextButton(on_click=self.chiudi_dialog_invito),
                ft.TextButton(on_click=self.invia_invito_cliccato)
            ]
        )

        # Dialogo Modifica Ruolo
        self.dd_modifica_ruolo = ft.Dropdown()
        self.membro_in_modifica = None
        self.dialog_modifica_ruolo = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=self.dd_modifica_ruolo,
            actions=[
                ft.TextButton(on_click=self.chiudi_dialog_modifica_ruolo),
                ft.TextButton(on_click=self.salva_ruolo_cliccato)
            ]
        )

    # --- Gestione Categoria ---
    def apri_dialog_categoria(self, cat_data=None):
        loc = self.loc
        if cat_data:
            self.dialog_modifica_cat.title.value = loc.get("edit_category")
            self.txt_nome_cat.value = cat_data['nome_categoria']
            self.id_cat_in_modifica = cat_data['id_categoria']
        else:
            self.dialog_modifica_cat.title.value = loc.get("add_category")
            self.txt_nome_cat.value = ""
            self.id_cat_in_modifica = None
        
        self.dialog_modifica_cat.actions[0].text = loc.get("cancel")
        self.dialog_modifica_cat.actions[1].text = loc.get("save")
        self.txt_nome_cat.label = loc.get("category_name")
        
        self.page.dialog = self.dialog_modifica_cat
        self.dialog_modifica_cat.open = True
        self.page.update()

    def chiudi_dialog_categoria(self, e):
        self.dialog_modifica_cat.open = False
        self.page.update()

    def salva_categoria_cliccato(self, e):
        nome_cat = self.txt_nome_cat.value
        if not nome_cat:
            self.txt_nome_cat.error_text = self.loc.get("name_required")
            self.page.update()
            return

        if self.id_cat_in_modifica:
            success = modifica_categoria(self.id_cat_in_modifica, nome_cat)
        else:
            id_famiglia = self.controller.get_family_id()
            success = aggiungi_categoria(id_famiglia, nome_cat)

        if success:
            self.controller.show_snack_bar(self.loc.get("category_saved_successfully"), success=True)
            self.dialog_modifica_cat.open = False
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar(self.loc.get("category_save_error"), success=False)
        self.page.update()

    def elimina_categoria_cliccato(self, e):
        id_cat = e.control.data
        if elimina_categoria(id_cat):
            self.controller.show_snack_bar(self.loc.get("category_deleted_successfully"), success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar(self.loc.get("category_delete_error"), success=False)
    
    # --- Gestione Sottocategoria ---
    def apri_dialog_sottocategoria(self, sub_cat_data=None, id_categoria=None):
        loc = self.loc
        if sub_cat_data:
            self.dialog_sottocategoria.title.value = loc.get("edit_subcategory")
            self.txt_nome_sottocat.value = sub_cat_data['nome_sottocategoria']
            self.id_sottocat_in_modifica = sub_cat_data['id_sottocategoria']
            self.id_cat_padre = sub_cat_data['id_categoria']
        else:
            self.dialog_sottocategoria.title.value = loc.get("add_subcategory")
            self.txt_nome_sottocat.value = ""
            self.id_sottocat_in_modifica = None
            self.id_cat_padre = id_categoria

        self.dialog_sottocategoria.actions[0].text = loc.get("cancel")
        self.dialog_sottocategoria.actions[1].text = loc.get("save")
        self.txt_nome_sottocat.label = loc.get("subcategory_name")

        self.page.dialog = self.dialog_sottocategoria
        self.dialog_sottocategoria.open = True
        self.page.update()

    def chiudi_dialog_sottocategoria(self, e):
        self.dialog_sottocategoria.open = False
        self.page.update()

    def salva_sottocategoria_cliccato(self, e):
        nome_sottocat = self.txt_nome_sottocat.value
        if not nome_sottocat:
            self.txt_nome_sottocat.error_text = self.loc.get("name_required")
            self.page.update()
            return

        if self.id_sottocat_in_modifica:
            success = modifica_sottocategoria(self.id_sottocat_in_modifica, nome_sottocat)
        else:
            success = aggiungi_sottocategoria(self.id_cat_padre, nome_sottocat)

        if success:
            self.controller.show_snack_bar(self.loc.get("subcategory_saved_successfully"), success=True)
            self.dialog_sottocategoria.open = False
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar(self.loc.get("subcategory_save_error"), success=False)
        self.page.update()

    def elimina_sottocategoria_cliccato(self, e):
        id_sottocat = e.control.data
        if elimina_sottocategoria(id_sottocat):
            self.controller.show_snack_bar(self.loc.get("subcategory_deleted_successfully"), success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar(self.loc.get("subcategory_delete_error"), success=False)


    # --- Gestione Budget ---
    def apri_dialog_imposta_budget(self):
        loc = self.loc
        self.dialog_imposta_budget.title.value = loc.get("set_budget")
        self.dd_sottocategoria_budget.label = loc.get("subcategory")
        self.txt_importo_budget.label = loc.get("budget_amount")
        self.dialog_imposta_budget.actions[0].text = loc.get("cancel")
        self.dialog_imposta_budget.actions[1].text = loc.get("save")

        id_famiglia = self.controller.get_family_id()
        self.dd_sottocategoria_budget.options = []
        categorie = ottieni_categorie_e_sottocategorie(id_famiglia)
        for cat_id, cat_data in categorie.items():
            for sub_cat in cat_data['sottocategorie']:
                self.dd_sottocategoria_budget.options.append(
                    ft.dropdown.Option(key=sub_cat['id_sottocategoria'], text=f"{cat_data['nome_categoria']} - {sub_cat['nome_sottocategoria']}")
                )

        self.page.dialog = self.dialog_imposta_budget
        self.dialog_imposta_budget.open = True
        self.page.update()

    def chiudi_dialog_budget(self, e):
        self.dialog_imposta_budget.open = False
        self.page.update()

    def salva_budget_cliccato(self, e):
        id_sottocat = self.dd_sottocategoria_budget.value
        importo = self.txt_importo_budget.value
        if not id_sottocat or not importo:
            # Aggiungi logica di errore se necessario
            return

        try:
            importo_float = float(importo.replace(",", "."))
            id_famiglia = self.controller.get_family_id()
            if imposta_budget(id_famiglia, id_sottocat, importo_float):
                self.controller.show_snack_bar(self.loc.get("budget_set_successfully"), success=True)
                self.dialog_imposta_budget.open = False
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar(self.loc.get("budget_set_error"), success=False)
        except ValueError:
            self.txt_importo_budget.error_text = self.loc.get("invalid_amount")
        
        self.page.update()

    # --- Gestione Membri ---
    def apri_dialog_invito(self):
        loc = self.loc
        self.dialog_invito_membri.title.value = loc.get("invite_member")
        self.txt_username_invito.label = loc.get("username_or_email")
        self.dd_ruolo_invito.label = loc.get("role")
        self.dd_ruolo_invito.options = [
            ft.dropdown.Option("livello1"),
            ft.dropdown.Option("livello2"),
            ft.dropdown.Option("livello3"),
        ]
        self.dd_ruolo_invito.value = "livello2"
        self.dialog_invito_membri.actions[0].text = loc.get("cancel")
        self.dialog_invito_membri.actions[1].text = loc.get("send_invite")
        
        self.page.dialog = self.dialog_invito_membri
        self.dialog_invito_membri.open = True
        self.page.update()

    def chiudi_dialog_invito(self, e):
        self.dialog_invito_membri.open = False
        self.page.update()

    def invia_invito_cliccato(self, e):
        username_or_email = self.txt_username_invito.value
        ruolo = self.dd_ruolo_invito.value
        if not username_or_email or not ruolo:
            return

        messaggio, success = self.controller.gestisci_invito_o_sblocco(username_or_email, ruolo)
        self.controller.show_snack_bar(messaggio, success=success)
        if success:
            self.dialog_invito_membri.open = False
            self.controller.db_write_operation()
        self.page.update()

    def apri_dialog_modifica_ruolo(self, membro_data):
        loc = self.loc
        self.membro_in_modifica = membro_data
        self.dialog_modifica_ruolo.title.value = f"{loc.get('edit_role_for')} {membro_data['nome_visualizzato']}"
        self.dd_modifica_ruolo.label = loc.get("role")
        self.dd_modifica_ruolo.options = [
            ft.dropdown.Option("admin"),
            ft.dropdown.Option("livello1"),
            ft.dropdown.Option("livello2"),
            ft.dropdown.Option("livello3"),
        ]
        self.dd_modifica_ruolo.value = membro_data['ruolo']
        self.dialog_modifica_ruolo.actions[0].text = loc.get("cancel")
        self.dialog_modifica_ruolo.actions[1].text = loc.get("save")

        self.page.dialog = self.dialog_modifica_ruolo
        self.dialog_modifica_ruolo.open = True
        self.page.update()

    def chiudi_dialog_modifica_ruolo(self, e):
        self.dialog_modifica_ruolo.open = False
        self.page.update()

    def salva_ruolo_cliccato(self, e):
        nuovo_ruolo = self.dd_modifica_ruolo.value
        id_famiglia = self.controller.get_family_id()
        if not nuovo_ruolo or not self.membro_in_modifica:
            return

        success = modifica_ruolo_utente(self.membro_in_modifica['id_utente'], id_famiglia, nuovo_ruolo)
        if success:
            self.controller.show_snack_bar(self.loc.get("role_updated_successfully"), success=True)
            self.dialog_modifica_ruolo.open = False
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar(self.loc.get("role_update_error"), success=False)
        self.page.update()