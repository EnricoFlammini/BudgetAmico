import flet as ft
# Importa solo le funzioni DB necessarie per QUESTA scheda
from db.gestione_db import (
    ottieni_membri_famiglia,
    rimuovi_utente_da_famiglia
)


class AdminSubTabMembri(ft.Column):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.controller.page = controller.page

        # --- Controlli della Scheda ---
        self.lv_membri_famiglia = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE
        )

        # --- Tabella Riferimento Livelli ---
        self.tabella_livelli = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Livello", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Accesso", weight=ft.FontWeight.BOLD)),
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text("Admin", weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text("Tutto + Gestione Admin"))
                ]),
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text("Livello 1")),
                    ft.DataCell(ft.Text("Tutto + Dettagli Famiglia"))
                ]),
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text("Livello 2")),
                    ft.DataCell(ft.Text("Patrimonio + Solo Totali Famiglia"))
                ]),
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text("Livello 3")),
                    ft.DataCell(ft.Text("Solo Dati Personali e Condivisi"))
                ]),
            ],
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=10,
            heading_row_color=ft.Colors.SURFACE_VARIANT,
            data_row_max_height=40,
        )

        # --- Layout della Scheda ---
        self.controls = [
            ft.Text("Membri Famiglia", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("I membri possono essere aggiunti o invitati tramite il pulsante 'Invita/Sblocca'.", size=12, color=ft.Colors.GREY_500),
            ft.Divider(),
            ft.Text("Riferimento Livelli", size=16, weight=ft.FontWeight.BOLD),
            self.tabella_livelli,
            ft.Divider(),
            self.lv_membri_famiglia
        ]

        self.expand = True
        self.spacing = 10

    def update_view_data(self, is_initial_load=False):
        """
        Questa funzione viene chiamata da AdminTab.
        Aggiorna i dati e chiama l'update sulla lista solo se non è il caricamento iniziale.
        """
        famiglia_id = self.controller.get_family_id()
        admin_id = self.controller.get_user_id()

        if not famiglia_id or not admin_id:
            return

        self.lv_membri_famiglia.controls.clear()

        try:
            membri = ottieni_membri_famiglia(famiglia_id)

            if not membri:
                self.lv_membri_famiglia.controls.append(ft.Text("Nessun membro trovato in questa famiglia."))

            for membro in membri:
                is_self = (membro['id_utente'] == admin_id)

                self.lv_membri_famiglia.controls.append(
                    ft.Row(
                        [
                            ft.Column([
                                ft.Text(membro['nome_visualizzato'], weight=ft.FontWeight.BOLD if is_self else ft.FontWeight.NORMAL),
                                ft.Text(f"Ruolo: {membro['ruolo']}", size=12, color=ft.Colors.GREY_500)
                            ], expand=True),
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                tooltip="Modifica Ruolo",
                                disabled=is_self,
                                data=membro,
                                on_click=self._on_edit_membro_click
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                tooltip="Rimuovi da famiglia",
                                icon_color=ft.Colors.RED_400,
                                disabled=is_self,
                                data=membro['id_utente'],
                                on_click=self._rimuovi_membro_cliccato
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        height=50
                    )
                )
        except Exception as e:
            self.lv_membri_famiglia.controls.append(ft.Text(f"Errore caricamento membri: {e}"))

        # L'aggiornamento UI è gestito dal controller globale

    def _rimuovi_membro_cliccato(self, e):
        id_utente = e.control.data
        famiglia_id = self.controller.get_family_id()
        admin_id = self.controller.get_user_id()

        if id_utente == admin_id:
            self.controller.show_snack_bar("Non puoi rimuovere te stesso.", success=False)
            return

        success = rimuovi_utente_da_famiglia(id_utente, famiglia_id)

        if success:
            self.controller.show_snack_bar("Membro rimosso dalla famiglia.", success=True)
            self.controller.update_all_views()
        else:
            self.controller.show_snack_bar("Errore durante la rimozione.", success=False)

    def _on_edit_membro_click(self, e):
        membro_data = e.control.data
        self.controller.admin_dialogs.apri_dialog_modifica_ruolo(
            membro_data['id_utente'],
            membro_data['nome_visualizzato'],
            membro_data['ruolo']
        )