import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_spese_fisse_famiglia,
    elimina_spesa_fissa,
    modifica_stato_spesa_fissa
)


class SpeseFisseTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page

        # Crea la DataTable qui, CON colonne iniziali (placeholder) per evitare l'AssertionError
        self.dt_spese_fisse = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Placeholder")), # Verrà aggiornato in build_controls
                ft.DataColumn(ft.Text("Placeholder"), numeric=True), # Verrà aggiornato in build_controls
                ft.DataColumn(ft.Text("Placeholder")), # Verrà aggiornato in build_controls
                ft.DataColumn(ft.Text("Placeholder")), # Verrà aggiornato in build_controls
                ft.DataColumn(ft.Text("Placeholder")), # Verrà aggiornato in build_controls
                ft.DataColumn(ft.Text("Placeholder")), # Verrà aggiornato in build_controls
            ],
            rows=[],
            expand=True,
            heading_row_color=ft.Colors.BLUE_GREY_900,
        )

        self.content = ft.Column(expand=True, spacing=10)

    def elimina_cliccato(self, e):
        id_spesa = e.control.data
        success = elimina_spesa_fissa(id_spesa)
        if success:
            self.controller.show_snack_bar("Spesa fissa eliminata.", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("❌ Errore durante l'eliminazione.", success=False)

    def _cambia_stato_attiva(self, e):
        id_spesa = e.control.data
        nuovo_stato = e.control.value
        success = modifica_stato_spesa_fissa(id_spesa, nuovo_stato)
        if success:
            self.controller.show_snack_bar("Stato aggiornato.", success=True)
        else:
            self.controller.show_snack_bar("❌ Errore durante l'aggiornamento dello stato.", success=False)
            # Ripristina lo stato visivo in caso di fallimento
            e.control.value = not nuovo_stato
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        loc = self.controller.loc
        # Ricrea completamente la lista delle colonne con le traduzioni corrette
        self.dt_spese_fisse.columns = [
            ft.DataColumn(ft.Text(loc.get("name"))),
            ft.DataColumn(ft.Text(loc.get("amount")), numeric=True),
            ft.DataColumn(ft.Text(loc.get("account"))),
            ft.DataColumn(ft.Text(loc.get("debit_day"))), # Usa la chiave tradotta per "Giorno"
            ft.DataColumn(ft.Text(loc.get("active"))),
            ft.DataColumn(ft.Text(loc.get("actions"))),
        ]

        return [
            ft.Row(
                [
                    ft.Text(loc.get("fixed_expenses_management"), size=24, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip=loc.get("add_fixed_expense"),
                        on_click=lambda e: self.controller.spesa_fissa_dialog.apri_dialog()
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            ft.Text(loc.get("fixed_expenses_description")),
            ft.Divider(),
            ft.Column([self.dt_spese_fisse], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
        ]

    def update_view_data(self, is_initial_load=False):
        self.content.controls = self.build_controls()

        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        spese_fisse = ottieni_spese_fisse_famiglia(id_famiglia)
        self.dt_spese_fisse.rows.clear()

        if not spese_fisse:
            self.dt_spese_fisse.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(self.controller.loc.get("no_fixed_expenses"), text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                    ]
                )
            )
        else:
            for spesa in spese_fisse:
                self.dt_spese_fisse.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(spesa['nome'])),
                            ft.DataCell(ft.Text(self.controller.loc.format_currency(spesa['importo']))),
                            ft.DataCell(ft.Text(spesa['nome_conto'])),
                            ft.DataCell(ft.Text(spesa['giorno_addebito'])),
                            ft.DataCell(
                                ft.Switch(
                                    value=bool(spesa['attiva']),
                                    data=spesa['id_spesa_fissa'],
                                    on_change=self._cambia_stato_attiva
                                )
                            ),
                            ft.DataCell(
                                ft.Row([
                                    ft.IconButton(icon=ft.Icons.EDIT,
                                                  tooltip=self.controller.loc.get("edit"),
                                                  data=spesa,
                                                  on_click=lambda e: self.controller.spesa_fissa_dialog.apri_dialog(
                                                      e.control.data)
                                                  ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE,
                                        tooltip=self.controller.loc.get("delete"),
                                        icon_color=ft.Colors.RED,
                                        data=spesa['id_spesa_fissa'],
                                        on_click=lambda e: self.controller.open_confirm_delete_dialog(
                                            partial(self.elimina_cliccato, e)
                                        )
                                    ),
                                ])
                            ),
                        ]
                    )
                )

        if self.page:
            self.page.update()