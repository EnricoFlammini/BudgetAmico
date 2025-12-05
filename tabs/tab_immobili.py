import flet as ft
from functools import partial
from db.gestione_db import ottieni_immobili_famiglia, elimina_immobile
from utils.styles import AppStyles, AppColors


class ImmobiliTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page

        self.lv_immobili = ft.Column(
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
            spacing=10
        )
        self.content = ft.Column(expand=True, spacing=10)

    def update_view_data(self, is_initial_load=False):
        theme = self.page.theme.color_scheme if self.page and self.page.theme else ft.ColorScheme()
        self.content.controls = self.build_controls()

        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        master_key_b64 = self.controller.page.session.get("master_key")
        id_utente = self.controller.get_user_id()
        immobili = ottieni_immobili_famiglia(id_famiglia, master_key_b64, id_utente)
        self.lv_immobili.controls.clear()

        if not immobili:
            self.lv_immobili.controls.append(AppStyles.body_text(self.controller.loc.get("no_properties")))
        else:
            for immobile in immobili:
                self.lv_immobili.controls.append(self._crea_widget_immobile(immobile, theme))

        if self.page:
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        loc = self.controller.loc
        return [
            ft.Row(
                [
                    AppStyles.header_text(loc.get("properties_management")),
                    ft.IconButton(
                        icon=ft.Icons.ADD_HOME,
                        tooltip=loc.get("add_property"),
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self.controller.immobile_dialog.apri_dialog_immobile()
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            AppStyles.body_text(loc.get("properties_description")),
            ft.Divider(color=ft.Colors.OUTLINE_VARIANT),
            self.lv_immobili
        ]

    def _crea_widget_immobile(self, immobile, theme):
        loc = self.controller.loc
        valore_netto = immobile['valore_attuale'] - (immobile.get('valore_mutuo_residuo') or 0)

        content = ft.Column([
            ft.Row([
                AppStyles.subheader_text(immobile['nome']),
                ft.Text(f"{immobile['via']}, {immobile['citta']}", size=12, italic=True,
                        color=AppColors.TEXT_SECONDARY)
            ]),
            ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
            ft.Row([
                self._crea_info_immobile(loc.get("purchase_value"),
                                         loc.format_currency(immobile['valore_acquisto']), theme),
                self._crea_info_immobile(loc.get("current_value"),
                                         loc.format_currency(immobile['valore_attuale']),
                                         theme, colore_valore=AppColors.SUCCESS),
            ]),
            ft.Row([
                self._crea_info_immobile(loc.get("residual_mortgage"),
                                         loc.format_currency(immobile.get('valore_mutuo_residuo') or 0), theme),
                self._crea_info_immobile("Valore Netto", loc.format_currency(valore_netto), theme, colore_valore=AppColors.PRIMARY),
            ]),
            ft.Row([
                ft.IconButton(icon=ft.Icons.EDIT, tooltip=loc.get("edit"), data=immobile,
                              icon_color=AppColors.PRIMARY,
                              on_click=lambda e: self.controller.immobile_dialog.apri_dialog_immobile(
                                  e.control.data)),
                ft.IconButton(icon=ft.Icons.DELETE, tooltip=loc.get("delete"), icon_color=AppColors.ERROR,
                              data=immobile['id_immobile'],
                              on_click=lambda e: self.controller.open_confirm_delete_dialog(
                                  partial(self.elimina_cliccato, e))),
            ], alignment=ft.MainAxisAlignment.END)
        ])
        
        return AppStyles.card_container(content, padding=15)

    def _crea_info_immobile(self, etichetta, valore, theme, colore_valore=None):
        return ft.Column([
            AppStyles.caption_text(etichetta),
            ft.Text(str(valore), size=16, weight=ft.FontWeight.BOLD, color=colore_valore)
        ], horizontal_alignment=ft.CrossAxisAlignment.START)

    def elimina_cliccato(self, e):
        id_immobile = e.control.data
        success = elimina_immobile(id_immobile)
        if success:
            self.controller.show_snack_bar("Immobile eliminato con successo.", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore durante l'eliminazione dell'immobile.", success=False)