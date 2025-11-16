import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_conti_condivisi_utente,
    elimina_conto_condiviso
)


class ContiCondivisiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page

        self.lv_conti_condivisi = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE,
            spacing=10
        )

        self.content = ft.Column(expand=True, spacing=10)

    def update_view_data(self, is_initial_load=False):
        self.content.controls = self.build_controls()

        utente_id = self.controller.get_user_id()
        if not utente_id:
            return

        print("Aggiornamento Scheda Conti Condivisi...")
        self.lv_conti_condivisi.controls.clear()

        conti_condivisi = ottieni_conti_condivisi_utente(utente_id)
        if not conti_condivisi:
            self.lv_conti_condivisi.controls.append(ft.Text(self.controller.loc.get("no_shared_accounts")))
        else:
            for conto in conti_condivisi:
                tipo_condivisione_text = self.controller.loc.get(
                    "shared_type_family") if conto['tipo_condivisione'] == 'famiglia' else self.controller.loc.get(
                    "shared_type_users")
                self.lv_conti_condivisi.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column([
                                    ft.Text(conto['nome_conto'], weight=ft.FontWeight.BOLD, size=18),
                                    ft.Text(f"{conto['tipo']} ({tipo_condivisione_text})", size=12,
                                            color=ft.Colors.GREY_500)
                                ], expand=True),
                                ft.Column([
                                    ft.Text(self.controller.loc.get("current_balance"), size=10,
                                            color=ft.Colors.GREY_500),
                                    ft.Text(self.controller.loc.format_currency(conto['saldo_calcolato']), size=16,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.GREEN_500 if conto[
                                                                              'saldo_calcolato'] >= 0 else ft.Colors.RED_500)
                                ], horizontal_alignment=ft.CrossAxisAlignment.END),
                                ft.IconButton(icon=ft.Icons.EDIT, tooltip="Gestisci Conto Condiviso", data=conto,
                                              on_click=lambda e: self.controller.conto_condiviso_dialog.apri_dialog(
                                                  e.control.data)),
                                ft.IconButton(icon=ft.Icons.DELETE,
                                              tooltip=self.controller.loc.get("delete_account"),
                                              icon_color=ft.Colors.RED_400, data=conto['id_conto'],
                                              on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(
                                                  self.elimina_conto_condiviso_cliccato,
                                                  e))
                                              )
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=10, border_radius=5, border=ft.border.all(1, ft.Colors.GREY_800)
                    )
                )

        if self.page:
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        return [
            ft.Row(
                [
                    ft.Text(self.controller.loc.get("shared_accounts"), size=24, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.Icons.GROUP_ADD,
                        tooltip=self.controller.loc.get("manage_shared_account"),
                        on_click=lambda e: self.controller.conto_condiviso_dialog.apri_dialog()
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            ft.Divider(),
            self.lv_conti_condivisi
        ]

    def elimina_conto_condiviso_cliccato(self, e):
        id_conto_condiviso = e.control.data
        success = elimina_conto_condiviso(id_conto_condiviso)
        if success:
            self.controller.show_snack_bar("Conto condiviso e dati collegati eliminati.", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("❌ Errore durante l'eliminazione del conto condiviso.", success=False)