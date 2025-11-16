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

        # Controlli UI
        self.dt_spese_fisse = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("..."))],
            rows=[],
            expand=True
        )
        
        self.no_data_view = ft.Container(
            content=ft.Text(self.controller.loc.get("no_fixed_expenses"), text_align=ft.TextAlign.CENTER),
            alignment=ft.alignment.center,
            expand=True,
            visible=False  # Nascosto di default
        )

        # Stack per alternare tra tabella e messaggio "nessun dato"
        self.data_stack = ft.Stack(
            controls=[
                ft.Column([self.dt_spese_fisse], scroll=ft.ScrollMode.ADAPTIVE, expand=True),
                self.no_data_view
            ],
            expand=True
        )
        
        self.content = ft.Column(expand=True, spacing=10)

    def update_view_data(self, is_initial_load=False):
        theme = self.page.theme.color_scheme if self.page and self.page.theme else ft.ColorScheme()
        self.content.controls = self.build_controls(theme)

        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return

        spese_fisse = ottieni_spese_fisse_famiglia(id_famiglia)
        self.dt_spese_fisse.rows.clear()

        if not spese_fisse:
            self.dt_spese_fisse.visible = False
            self.no_data_view.visible = True
        else:
            self.dt_spese_fisse.visible = True
            self.no_data_view.visible = False
            for spesa in spese_fisse:
                self.dt_spese_fisse.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(spesa['nome'])),
                        ft.DataCell(ft.Text(self.controller.loc.format_currency(spesa['importo']))),
                        ft.DataCell(ft.Text(spesa['nome_conto'])),
                        ft.DataCell(ft.Text(spesa['giorno_addebito'])),
                        ft.DataCell(ft.Switch(value=bool(spesa['attiva']), data=spesa['id_spesa_fissa'], on_change=self._cambia_stato_attiva)),
                        ft.DataCell(ft.Row([
                            ft.IconButton(icon=ft.Icons.EDIT, tooltip=self.controller.loc.get("edit"), data=spesa,
                                          on_click=lambda e: self.controller.spesa_fissa_dialog.apri_dialog(e.control.data)),
                            ft.IconButton(icon=ft.Icons.DELETE, tooltip=self.controller.loc.get("delete"), icon_color=theme.error,
                                          data=spesa['id_spesa_fissa'],
                                          on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.elimina_cliccato, e))),
                        ])),
                    ])
                )
        if self.page:
            self.page.update()

    def build_controls(self, theme):
        loc = self.controller.loc
        
        self.dt_spese_fisse.heading_row_color = theme.primary_container
        self.dt_spese_fisse.columns = [
            ft.DataColumn(ft.Text(loc.get("name"))),
            ft.DataColumn(ft.Text(loc.get("amount")), numeric=True),
            ft.DataColumn(ft.Text(loc.get("account"))),
            ft.DataColumn(ft.Text(loc.get("debit_day"))),
            ft.DataColumn(ft.Text(loc.get("active"))),
            ft.DataColumn(ft.Text(loc.get("actions"))),
        ]

        return [
            ft.Row([
                ft.Text(loc.get("fixed_expenses_management"), size=24, weight=ft.FontWeight.BOLD),
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    tooltip=loc.get("add_fixed_expense"),
                    on_click=lambda e: self.controller.spesa_fissa_dialog.apri_dialog()
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(loc.get("fixed_expenses_description")),
            ft.Divider(),
            self.data_stack
        ]

    def elimina_cliccato(self, e):
        id_spesa = e.control.data
        if elimina_spesa_fissa(id_spesa):
            self.controller.show_snack_bar("Spesa fissa eliminata.", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("❌ Errore durante l'eliminazione.", success=False)

    def _cambia_stato_attiva(self, e):
        id_spesa = e.control.data
        nuovo_stato = e.control.value
        if modifica_stato_spesa_fissa(id_spesa, nuovo_stato):
            self.controller.show_snack_bar("Stato aggiornato.", success=True)
        else:
            self.controller.show_snack_bar("❌ Errore durante l'aggiornamento dello stato.", success=False)
            e.control.value = not nuovo_stato
            if self.page:
                self.page.update()