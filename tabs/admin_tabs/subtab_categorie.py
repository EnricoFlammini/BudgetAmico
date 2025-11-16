import flet as ft
# Importa solo le funzioni DB necessarie per QUESTA scheda
from db.gestione_db import (
    ottieni_categorie,
    aggiungi_categoria,
    elimina_categoria
)


class AdminSubTabCategorie(ft.Column):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.page = controller.page

        # --- Controlli della Scheda ---
        self.txt_nuova_categoria = ft.TextField(label="Nome nuova categoria", expand=True)

        self.lv_categorie = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE
        )

        # --- Layout della Scheda ---
        self.controls = [
            ft.Text("Gestione Categorie", size=24, weight=ft.FontWeight.BOLD),
            ft.Row([
                self.txt_nuova_categoria,
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    on_click=self._aggiungi_categoria_cliccato,
                    tooltip="Aggiungi"
                )
            ]),
            ft.Divider(),
            self.lv_categorie
        ]

        self.expand = True
        self.spacing = 10

    def update_view_data(self, is_initial_load=False):
        """ Questa funzione viene chiamata da AdminTab """
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            return

        self.lv_categorie.controls.clear()

        try:
            categorie = ottieni_categorie(famiglia_id)
            if not categorie:
                self.lv_categorie.controls.append(ft.Text("Nessuna categoria creata."))

            for cat in categorie:
                cat_nome_upper = cat['nome_categoria'].upper()
                self.lv_categorie.controls.append(
                    ft.Row(
                        [
                            ft.Text(cat_nome_upper, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                tooltip="Rinomina",
                                data=cat,
                                on_click=self._on_edit_categoria_click
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                tooltip="Elimina",
                                icon_color=ft.Colors.RED_400,
                                data=cat['id_categoria'],
                                on_click=self._elimina_categoria_cliccato
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        height=48
                    )
                )
        except Exception as e:
            self.lv_categorie.controls.append(ft.Text(f"Errore caricamento categorie: {e}"))

        # L'aggiornamento UI è gestito dal controller globale

    def _aggiungi_categoria_cliccato(self, e):
        nome_cat = self.txt_nuova_categoria.value
        famiglia_id = self.controller.get_family_id()
        if not nome_cat or not famiglia_id:
            self.controller.show_snack_bar("Errore: Inserire un nome valido.", success=False)
            return

        new_id = aggiungi_categoria(famiglia_id, nome_cat)

        if new_id:
            self.controller.show_snack_bar("Categoria aggiunta!", success=True)
            self.txt_nuova_categoria.value = ""
            self.controller.update_all_views()
        else:
            self.controller.show_snack_bar("Errore: Categoria già esistente.", success=False)
            self.txt_nuova_categoria.update()

    def _elimina_categoria_cliccato(self, e):
        id_cat = e.control.data
        success = elimina_categoria(id_cat)

        if success:
            self.controller.show_snack_bar("Categoria eliminata.", success=True)
            self.controller.update_all_views()
        else:
            self.controller.show_snack_bar("Errore durante l'eliminazione.", success=False)

    def _on_edit_categoria_click(self, e):
        cat_data = e.control.data
        self.controller.admin_dialogs.apri_dialog_modifica_cat(
            cat_data['id_categoria'],
            cat_data['nome_categoria']
        )