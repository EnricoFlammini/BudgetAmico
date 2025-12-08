import flet as ft
from functools import partial
from db.gestione_db import ottieni_immobili_famiglia, elimina_immobile
from utils.styles import AppStyles, AppColors, PageConstants


class ImmobiliTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
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
        
        try:
            immobili = ottieni_immobili_famiglia(id_famiglia, master_key_b64, id_utente)
            
            # Calcolo Totali
            tot_acquisto = 0.0
            tot_attuale = 0.0
            tot_mutui = 0.0
            
            for imm in immobili:
                val_acq = imm.get('valore_acquisto') or 0.0
                val_att = imm.get('valore_attuale') or 0.0
                val_mut = imm.get('valore_mutuo_residuo') or 0.0
                
                tot_acquisto += val_acq
                tot_mutui += val_mut
                if not imm.get('nuda_proprieta'):
                    tot_attuale += val_att
            
            tot_netto = tot_attuale - tot_mutui

            self.lv_immobili.controls.clear()

            # Costruisco header con riepilogo
            header_controls = [
                AppStyles.section_header(
                    self.controller.loc.get("properties_management"),
                    ft.IconButton(
                        icon=ft.Icons.ADD_HOME,
                        tooltip=self.controller.loc.get("add_property"),
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self.controller.immobile_dialog.apri_dialog_immobile()
                    )
                ),
                AppStyles.page_divider(),
            ]

            # Card Riepilogo (se ci sono immobili)
            if immobili:
                loc = self.controller.loc
                summary_content = ft.Column([
                    AppStyles.subheader_text("Riepilogo Patrimonio Immobiliare"),
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    ft.Row([
                        self._crea_info_immobile(loc.get("current_value"), loc.format_currency(tot_attuale), theme, colore_valore=AppColors.SUCCESS),
                        self._crea_info_immobile(loc.get("residual_mortgage"), loc.format_currency(tot_mutui), theme, colore_valore=AppColors.ERROR),
                        self._crea_info_immobile("Valore Netto", loc.format_currency(tot_netto), theme, colore_valore=AppColors.PRIMARY),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ])
                header_controls.append(AppStyles.card_container(summary_content, padding=15))
                header_controls.append(ft.Container(height=10)) # Spaziatura
            
            self.lv_immobili.controls.extend(header_controls)

            if not immobili:
                self.lv_immobili.controls.append(AppStyles.body_text(self.controller.loc.get("no_properties")))
            else:
                for immobile in immobili:
                    self.lv_immobili.controls.append(self._crea_widget_immobile(immobile, theme))
        except Exception as e:
            print(f"Errore in ImmobiliTab.update_view_data: {e}")
            self.lv_immobili.controls.clear()
            self.lv_immobili.controls.append(AppStyles.body_text(f"Errore durante il caricamento: {e}", color=AppColors.ERROR))

        if self.page:
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        # Nota: I controlli vengono ora gestiti dinamicamente in update_view_data
        return [self.lv_immobili]

    def _crea_widget_immobile(self, immobile, theme):
        loc = self.controller.loc
        is_nuda = immobile.get('nuda_proprieta')
        
        val_acq = immobile.get('valore_acquisto') or 0.0
        val_att = immobile.get('valore_attuale') or 0.0
        val_mut = immobile.get('valore_mutuo_residuo') or 0.0
        
        valore_netto = val_att - val_mut
        
        colore_valore_attuale = AppColors.SUCCESS
        tooltip_valore = None
        
        header_row_controls = [AppStyles.subheader_text(immobile.get('nome', 'Senza Nome'))]
        if is_nuda:
            header_row_controls.append(
                ft.Container(
                    content=ft.Text("NUDA PROPRIETÀ", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    bgcolor=ft.Colors.ORANGE_700,
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    border_radius=4,
                    tooltip="Valore non conteggiato nei totali"
                )
            )
            colore_valore_attuale = AppColors.TEXT_SECONDARY
            tooltip_valore = "Escluso dai totali"
            
        content = ft.Column([
            ft.Row([
                ft.Row(header_row_controls, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                ft.Text(f"{immobile.get('via', '')}, {immobile.get('citta', '')}", size=12, italic=True,
                        color=AppColors.TEXT_SECONDARY)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
            ft.Row([
                self._crea_info_immobile(loc.get("purchase_value"),
                                         loc.format_currency(val_acq), theme),
                self._crea_info_immobile(loc.get("current_value"),
                                         loc.format_currency(val_att),
                                         theme, colore_valore=colore_valore_attuale),
            ]),
            ft.Row([
                self._crea_info_immobile(loc.get("residual_mortgage"),
                                         loc.format_currency(val_mut), theme),
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