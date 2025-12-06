import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_spese_fisse_famiglia,
    elimina_spesa_fissa,
    modifica_stato_spesa_fissa,
    aggiungi_transazione,
    aggiungi_transazione_condivisa
)
from utils.styles import AppStyles, AppColors, PageConstants
from datetime import datetime


class SpeseFisseTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.page = controller.page

        # Controlli UI
        self.dt_spese_fisse = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("..."))],
            rows=[],
            expand=True,
            heading_row_height=40,
            data_row_max_height=60,
            border_radius=10
        )
        
        self.no_data_view = ft.Container(
            content=AppStyles.body_text(self.controller.loc.get("no_fixed_expenses")),
            alignment=ft.alignment.center,
            expand=True,
            visible=False
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
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        self.content.controls = self.build_controls(theme)

        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return

        master_key_b64 = self.controller.page.session.get("master_key")
        current_user_id = self.controller.get_user_id()
        spese_fisse = ottieni_spese_fisse_famiglia(id_famiglia, master_key_b64, current_user_id)
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
                        ft.DataCell(ft.Text(spesa['nome'], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(self.controller.loc.format_currency(spesa['importo']))),
                        ft.DataCell(ft.Text(spesa['nome_conto'])),
                        ft.DataCell(ft.Text(str(spesa['giorno_addebito']))),
                        ft.DataCell(ft.Switch(value=bool(spesa['attiva']), data=spesa['id_spesa_fissa'], on_change=self._cambia_stato_attiva)),
                        ft.DataCell(ft.Row([
                            # Icona addebito automatico
                            ft.Icon(
                                name=ft.Icons.AUTO_MODE if spesa.get('addebito_automatico') else ft.Icons.BLOCK,
                                color=AppColors.SUCCESS if spesa.get('addebito_automatico') else ft.Colors.GREY_400,
                                size=20
                            ),
                            ft.IconButton(icon=ft.Icons.PAYMENT, tooltip="Paga", data=spesa,
                                          icon_color=AppColors.SUCCESS,
                                          on_click=self._paga_spesa_fissa),
                            ft.IconButton(icon=ft.Icons.EDIT, tooltip=self.controller.loc.get("edit"), data=spesa,
                                          icon_color=AppColors.PRIMARY,
                                          on_click=lambda e: self.controller.spesa_fissa_dialog.apri_dialog(e.control.data)),
                            ft.IconButton(icon=ft.Icons.DELETE, tooltip=self.controller.loc.get("delete"), icon_color=AppColors.ERROR,
                                          data=spesa['id_spesa_fissa'],
                                          on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.elimina_cliccato, e))),
                        ])),
                    ])
                )
        if self.page:
            self.page.update()

    def build_controls(self, theme):
        loc = self.controller.loc
        
        self.dt_spese_fisse.heading_row_color = AppColors.SURFACE_VARIANT
        self.dt_spese_fisse.data_row_color = {"hovered": ft.Colors.with_opacity(0.1, theme.primary)}
        self.dt_spese_fisse.border = ft.border.all(1, ft.Colors.OUTLINE_VARIANT)
        
        self.dt_spese_fisse.columns = [
            ft.DataColumn(ft.Text(loc.get("name"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(loc.get("amount"), weight=ft.FontWeight.BOLD), numeric=True),
            ft.DataColumn(ft.Text(loc.get("account"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(loc.get("debit_day"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(loc.get("active"), weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text(loc.get("actions"), weight=ft.FontWeight.BOLD)),
        ]

        return [
            AppStyles.section_header(
                loc.get("fixed_expenses_management"),
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    tooltip=loc.get("add_fixed_expense"),
                    icon_color=AppColors.PRIMARY,
                    on_click=lambda e: self.controller.spesa_fissa_dialog.apri_dialog()
                )
            ),
            AppStyles.page_divider(),
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

    def _paga_spesa_fissa(self, e):
        """Crea una transazione per pagare la spesa fissa."""
        spesa = e.control.data
        try:
            # Prepara i dati per la transazione
            data_oggi = datetime.now().strftime("%Y-%m-%d")
            descrizione = f"Pagamento: {spesa['nome']}"
            importo = -abs(spesa['importo'])  # Negativo perché è un'uscita
            id_sottocategoria = spesa.get('id_sottocategoria')
            
            # Determina se è un conto personale o condiviso
            success = False
            if spesa['id_conto_personale_addebito']:
                # Transazione su conto personale
                master_key_b64 = self.controller.page.session.get("master_key")
                success = aggiungi_transazione(
                    id_conto=spesa['id_conto_personale_addebito'],
                    data=data_oggi,
                    descrizione=descrizione,
                    importo=importo,
                    id_sottocategoria=id_sottocategoria,
                    master_key_b64=master_key_b64
                )
            elif spesa['id_conto_condiviso_addebito']:
                # Transazione su conto condiviso
                id_utente = self.controller.get_user_id()
                master_key_b64 = self.controller.page.session.get("master_key")
                success = aggiungi_transazione_condivisa(
                    id_utente_autore=id_utente,
                    id_conto_condiviso=spesa['id_conto_condiviso_addebito'],
                    data=data_oggi,
                    descrizione=descrizione,
                    importo=importo,
                    id_sottocategoria=id_sottocategoria,
                    master_key_b64=master_key_b64
                )
            
            if success:
                self.controller.show_snack_bar(f"✅ Pagamento registrato: {spesa['nome']}", success=True)
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("❌ Errore durante la registrazione del pagamento.", success=False)
                
        except Exception as ex:
            print(f"Errore pagamento spesa fissa: {ex}")
            self.controller.show_snack_bar(f"❌ Errore: {ex}", success=False)