import flet as ft
from db.gestione_db import (
    ottieni_riepilogo_patrimonio_famiglia_aggregato,
    ottieni_dettagli_famiglia,
    ottieni_totali_famiglia,
    ottieni_anni_mesi_storicizzati
)
import datetime


class FamigliaTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page

        # Controlli UI
        self.txt_patrimonio_totale_famiglia = ft.Text(size=22, weight=ft.FontWeight.BOLD)
        self.txt_liquidita_totale_famiglia = ft.Text(size=16)
        self.txt_investimenti_totali_famiglia = ft.Text(size=16)
        self.dd_mese_filtro = ft.Dropdown(on_change=self._filtro_mese_cambiato)
        self.dt_transazioni_famiglia = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("..."))],
            rows=[],
            expand=True,
            border_radius=5
        )
        
        self.no_data_view = ft.Container(
            content=ft.Text(self.controller.loc.get("no_transactions_found_family"), text_align=ft.TextAlign.CENTER),
            alignment=ft.alignment.center,
            expand=True,
            visible=False
        )

        self.data_stack = ft.Stack(
            controls=[
                ft.Column([self.dt_transazioni_famiglia], scroll=ft.ScrollMode.ADAPTIVE, expand=True),
                self.no_data_view
            ],
            expand=True
        )
        
        self.main_content = ft.Column([], expand=True, spacing=10)
        self.content = self.main_content

    def update_view_data(self, is_initial_load=False):
        theme = self.page.theme.color_scheme if self.page and self.page.theme else ft.ColorScheme()
        
        self.main_content.controls = self.build_controls(theme)
        
        self.txt_patrimonio_totale_famiglia.color = theme.primary
        self.dt_transazioni_famiglia.heading_row_color = theme.primary_container # This might need to be a string color
        self.dt_transazioni_famiglia.data_row_color = {"hovered": theme.secondary_container}
        self.dt_transazioni_famiglia.border = ft.border.all(1, theme.outline)

        if is_initial_load:
            self._popola_filtro_mese()

        famiglia_id = self.controller.get_family_id()
        ruolo = self.controller.get_user_role()

        self._aggiorna_contenuto_per_ruolo(famiglia_id, ruolo, theme)
        
        if self.page:
            self.page.update()

    def _aggiorna_contenuto_per_ruolo(self, famiglia_id, ruolo, theme):
        if not famiglia_id:
            self.main_content.controls = [ft.Column(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=50, color=theme.on_surface_variant),
                    ft.Text(self.controller.loc.get("not_in_family"), size=18)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, expand=True
            )]
            return

        if ruolo == 'livello3':
            self.main_content.controls = [ft.Column(
                [
                    ft.Icon(ft.Icons.LOCK, size=50, color=theme.on_surface_variant),
                    ft.Text(self.controller.loc.get("no_family_access_permission"), size=18)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, expand=True
            )]
            return
            
        if ruolo == 'livello2':
            self.main_content.controls.clear()
            self.main_content.controls.extend([
                ft.Text(self.controller.loc.get("wealth_by_member"), size=24, weight=ft.FontWeight.BOLD),
                ft.Divider()
            ])
            totali = ottieni_totali_famiglia(famiglia_id)
            for m in totali:
                self.main_content.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(m['nome_visualizzato'], weight=ft.FontWeight.BOLD, size=16, expand=True),
                            ft.Text(self.controller.loc.format_currency(m['saldo_totale']), size=16,
                                    color=theme.primary if m['saldo_totale'] >= 0 else theme.error)
                        ]),
                        padding=10, border=ft.border.all(1, theme.outline), border_radius=5
                    )
                )
            return

        if ruolo in ['admin', 'livello1']:
            anno, mese = self._get_anno_mese_selezionato()
            riepilogo = ottieni_riepilogo_patrimonio_famiglia_aggregato(famiglia_id, anno, mese)
            self.txt_patrimonio_totale_famiglia.value = self.controller.loc.format_currency(riepilogo.get('patrimonio_netto', 0))
            self.txt_liquidita_totale_famiglia.value = self.controller.loc.format_currency(riepilogo.get('liquidita', 0))
            self.txt_investimenti_totali_famiglia.value = self.controller.loc.format_currency(riepilogo.get('investimenti', 0))
            self.txt_investimenti_totali_famiglia.visible = riepilogo.get('investimenti', 0) > 0

            transazioni = ottieni_dettagli_famiglia(famiglia_id, anno, mese)
            self.dt_transazioni_famiglia.rows.clear()
            if not transazioni:
                self.dt_transazioni_famiglia.visible = False
                self.no_data_view.visible = True
            else:
                self.dt_transazioni_famiglia.visible = True
                self.no_data_view.visible = False
                for t in transazioni:
                    self.dt_transazioni_famiglia.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(t.get('utente_nome') or self.controller.loc.get("shared"))),
                            ft.DataCell(ft.Text(t.get('data') or "N/A")),
                            ft.DataCell(ft.Text(t.get('descrizione') or "N/A")),
                            ft.DataCell(ft.Text(t.get('nome_categoria') or "N/A")),
                            ft.DataCell(ft.Text(t.get('conto_nome') or "N/A")),
                            ft.DataCell(ft.Text(self.controller.loc.format_currency(t.get('importo', 0)),
                                                color=theme.primary if t.get('importo', 0) >= 0 else theme.error)),
                        ])
                    )

    def build_controls(self, theme):
        loc = self.controller.loc
        on_surface_variant = theme.on_surface_variant
        outline = theme.outline

        self.dd_mese_filtro.label = loc.get("filter_by_month")
        self.dt_transazioni_famiglia.columns = [
            ft.DataColumn(ft.Text(loc.get("user"))), ft.DataColumn(ft.Text(loc.get("date"))),
            ft.DataColumn(ft.Text(loc.get("description"))), ft.DataColumn(ft.Text(loc.get("category"))),
            ft.DataColumn(ft.Text(loc.get("account"))), ft.DataColumn(ft.Text(loc.get("amount")), numeric=True),
        ]

        return [
            ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(loc.get("total_family_wealth"), size=12, color=on_surface_variant),
                        self.txt_patrimonio_totale_famiglia
                    ]),
                    ft.Column([
                        ft.Text(loc.get("total_liquidity"), size=12, color=on_surface_variant),
                        self.txt_liquidita_totale_famiglia,
                        ft.Text(loc.get("total_investments"), size=12, color=on_surface_variant,
                                visible=self.txt_investimenti_totali_famiglia.visible),
                        self.txt_investimenti_totali_famiglia
                    ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.END)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=10, border=ft.border.all(1, outline), border_radius=5
            ),
            self.dd_mese_filtro,
            ft.Divider(height=20),
            ft.Text(loc.get("all_family_transactions"), size=24, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            self.data_stack
        ]

    def _popola_filtro_mese(self):
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return

        periodi = ottieni_anni_mesi_storicizzati(id_famiglia)
        oggi = datetime.date.today()
        periodo_corrente = {'anno': oggi.year, 'mese': oggi.month}
        if periodo_corrente not in periodi:
            periodi.insert(0, periodo_corrente)

        self.dd_mese_filtro.options = [
            ft.dropdown.Option(key=f"{p['anno']}-{p['mese']}", text=datetime.date(p['anno'], p['mese'], 1).strftime("%B %Y"))
            for p in periodi
        ]
        self.dd_mese_filtro.value = f"{oggi.year}-{oggi.month}"

    def _get_anno_mese_selezionato(self):
        if self.dd_mese_filtro.value:
            return map(int, self.dd_mese_filtro.value.split('-'))
        oggi = datetime.date.today()
        return oggi.year, oggi.month

    def _filtro_mese_cambiato(self, e):
        self.update_view_data()