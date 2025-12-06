import flet as ft
from functools import partial
from db.gestione_db import ottieni_prestiti_famiglia, elimina_prestito
from utils.styles import AppStyles, AppColors, PageConstants


class PrestitiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.page = controller.page

        self.lv_prestiti = ft.Column(
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
        prestiti = ottieni_prestiti_famiglia(id_famiglia, master_key_b64, id_utente)
        self.lv_prestiti.controls.clear()

        if not prestiti:
            self.lv_prestiti.controls.append(AppStyles.body_text(self.controller.loc.get("no_loans")))
        else:
            for prestito in prestiti:
                self.lv_prestiti.controls.append(self._crea_widget_prestito(prestito, theme))

        if self.page:
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        loc = self.controller.loc
        return [
            AppStyles.section_header(
                loc.get("loans_management"),
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    tooltip=loc.get("add_loan"),
                    icon_color=AppColors.PRIMARY,
                    on_click=lambda e: self.controller.prestito_dialogs.apri_dialog_prestito()
                )
            ),
            AppStyles.page_divider(),
            self.lv_prestiti
        ]

    def _crea_widget_prestito(self, prestito, theme):
        loc = self.controller.loc
        
        # Calcolo progresso
        mesi_totali = prestito['numero_mesi_totali']
        rate_pagate = prestito.get('rate_pagate', 0)
        progresso = rate_pagate / mesi_totali if mesi_totali > 0 else 0
        # Clamp progresso between 0 and 1 to avoid errors
        progresso = max(0.0, min(1.0, progresso))
        mesi_rimanenti = mesi_totali - rate_pagate

        progress_bar = ft.ProgressBar(value=progresso, width=200, color=AppColors.PRIMARY, bgcolor=AppColors.SURFACE_VARIANT)
        
        content = ft.Column([
            ft.Row([
                AppStyles.subheader_text(prestito['nome']),
                ft.Text(prestito['tipo'], size=12, italic=True, color=AppColors.TEXT_SECONDARY)
            ]),
            ft.Text(prestito['descrizione'] if prestito['descrizione'] else "", size=14),
            ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
            ft.Row([
                self._crea_info_prestito(loc.get("financed_amount"),
                                         loc.format_currency(prestito['importo_finanziato']), theme),
                self._crea_info_prestito(loc.get("remaining_amount"),
                                         loc.format_currency(prestito['importo_residuo']),
                                         theme, colore_valore=AppColors.ERROR),
            ]),
            ft.Row([
                self._crea_info_prestito(loc.get("monthly_installment"),
                                         loc.format_currency(prestito['importo_rata']), theme),
                self._crea_info_prestito(loc.get("total_installments"), mesi_totali, theme),
            ]),
            ft.Column([
                ft.Row([
                    ft.Text(f"{loc.get('paid_installments')}: {rate_pagate}/{mesi_totali}", size=12),
                    ft.Text(f"{loc.get('remaining_installments')}: {mesi_rimanenti}", size=12)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                progress_bar
            ], spacing=5),
            ft.Row([
                ft.ElevatedButton(loc.get("pay_installment"), icon=ft.Icons.PAYMENT,
                                  on_click=lambda e, p=prestito: self.controller.prestito_dialogs.apri_dialog_paga_rata(
                                      p),
                                  disabled=prestito['importo_residuo'] <= 0),
                ft.IconButton(icon=ft.Icons.EDIT, tooltip=loc.get("edit"), data=prestito,
                              icon_color=AppColors.PRIMARY,
                              on_click=lambda e: self.controller.prestito_dialogs.apri_dialog_prestito(
                                  e.control.data)),
                ft.IconButton(icon=ft.Icons.DELETE, tooltip=loc.get("delete"), icon_color=AppColors.ERROR,
                              data=prestito['id_prestito'],
                              on_click=lambda e: self.controller.open_confirm_delete_dialog(
                                  partial(self.elimina_cliccato, e))),
            ], alignment=ft.MainAxisAlignment.END)
        ])
        
        return AppStyles.card_container(content, padding=15)

    def _crea_info_prestito(self, etichetta, valore, theme, colore_valore=None):
        return ft.Column([
            AppStyles.caption_text(etichetta),
            ft.Text(str(valore), size=16, weight=ft.FontWeight.BOLD, color=colore_valore)
        ], horizontal_alignment=ft.CrossAxisAlignment.START)

    def elimina_cliccato(self, e):
        id_prestito = e.control.data
        success = elimina_prestito(id_prestito)
        if success:
            self.controller.show_snack_bar("Prestito eliminato con successo.", success=True)
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore durante l'eliminazione del prestito.", success=False)