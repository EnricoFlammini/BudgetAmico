import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_conti_condivisi_utente,
    elimina_conto_condiviso
)
from utils.styles import AppStyles, AppColors, PageConstants


class ContiCondivisiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.page = controller.page

        self.lv_conti_condivisi = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE,
            spacing=10
        )

        self.content = ft.Column(expand=True, spacing=10)

    def update_view_data(self, is_initial_load=False):
        utente_id = self.controller.get_user_id()
        if not utente_id:
            return

        print("Aggiornamento Scheda Conti Condivisi...")
        
        master_key_b64 = self.controller.page.session.get("master_key")
        conti_condivisi = ottieni_conti_condivisi_utente(utente_id, master_key_b64=master_key_b64)
        
        loc = self.controller.loc
        
        self.content.controls = [
            AppStyles.section_header(
                loc.get("shared_accounts"),
                ft.IconButton(
                    icon=ft.Icons.GROUP_ADD,
                    tooltip=loc.get("manage_shared_account"),
                    icon_color=AppColors.PRIMARY,
                    on_click=lambda e: self.controller.conto_condiviso_dialog.apri_dialog()
                )
            ),
            AppStyles.page_divider(),
            self.lv_conti_condivisi
        ]
        
        self.lv_conti_condivisi.controls.clear()
        if not conti_condivisi:
            self.lv_conti_condivisi.controls.append(AppStyles.body_text(loc.get("no_shared_accounts")))
        else:
            for conto in conti_condivisi:
                tipo_condivisione_text = loc.get(
                    "shared_type_family") if conto['tipo_condivisione'] == 'famiglia' else loc.get(
                    "shared_type_users")
                
                content = ft.Row(
                    [
                        ft.Column([
                            AppStyles.subheader_text(conto['nome_conto']),
                            AppStyles.caption_text(f"{conto['tipo']} ({tipo_condivisione_text})")
                        ], expand=True),
                        ft.Column([
                            AppStyles.caption_text(loc.get("current_balance")),
                            AppStyles.currency_text(loc.format_currency(conto['saldo_calcolato']),
                                    color=AppColors.SUCCESS if conto['saldo_calcolato'] >= 0 else AppColors.ERROR)
                        ], horizontal_alignment=ft.CrossAxisAlignment.END),
                        ft.IconButton(icon=ft.Icons.EDIT_NOTE, tooltip="Rettifica Saldo (Admin)", data=conto,
                                      on_click=lambda e: self.controller.conto_dialog.apri_dialog_rettifica_saldo(
                                          e.control.data, is_condiviso=True),
                                      visible=(self.controller.get_user_role() == 'admin' and 
                                               conto['tipo'] in ['Corrente', 'Risparmio', 'Contanti'])),
                        ft.IconButton(icon=ft.Icons.EDIT, tooltip="Gestisci Conto Condiviso", data=conto,
                                      icon_color=AppColors.PRIMARY,
                                      on_click=lambda e: self.controller.conto_condiviso_dialog.apri_dialog(
                                          e.control.data)),
                        ft.IconButton(icon=ft.Icons.DELETE,
                                      tooltip=loc.get("delete_account"),
                                      icon_color=AppColors.ERROR, data=conto['id_conto'],
                                      on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(
                                          self.elimina_conto_condiviso_cliccato,
                                          e))
                                      )
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
                
                self.lv_conti_condivisi.controls.append(
                    AppStyles.card_container(content, padding=10)
                )

        if self.page:
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        return [
            AppStyles.section_header(
                self.controller.loc.get("shared_accounts"),
                ft.IconButton(
                    icon=ft.Icons.GROUP_ADD,
                    tooltip=self.controller.loc.get("manage_shared_account"),
                    icon_color=AppColors.PRIMARY,
                    on_click=lambda e: self.controller.conto_condiviso_dialog.apri_dialog()
                )
            ),
            AppStyles.page_divider(),
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