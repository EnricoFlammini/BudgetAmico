import flet as ft
from db.gestione_db import (
    ottieni_riepilogo_patrimonio_famiglia_aggregato,
    ottieni_dettagli_famiglia,
    ottieni_totali_famiglia,
    ottieni_anni_mesi_storicizzati  # Per popolare il filtro
)
import datetime


class FamigliaTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)
        self.controller = controller
        self.page = controller.page

        # Controlli per i totali della famiglia
        self.txt_patrimonio_totale_famiglia = ft.Text(size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_300)
        self.txt_liquidita_totale_famiglia = ft.Text(size=16)
        self.txt_investimenti_totali_famiglia = ft.Text(size=16)

        # Filtro per mese
        self.dd_mese_filtro = ft.Dropdown(
            on_change=self._filtro_mese_cambiato
        )

        # DataTable per le transazioni
        self.dt_transazioni_famiglia = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("..."))],  # <-- CORREZIONE QUI
            rows=[],
            expand=True,
            heading_row_color=ft.Colors.BLUE_GREY_900,
            data_row_color={"hovered": ft.Colors.BLUE_GREY_800},
            border_radius=5,
            border=ft.border.all(1, ft.Colors.GREY_800),
        )

        # Contenitore principale della scheda
        self.main_content = ft.Column(
            [],
            expand=True,
            spacing=10
        )

        self.content = self.main_content

    def update_view_data(self, is_initial_load=False):
        # Ricostruisce l'interfaccia con le traduzioni corrette ogni volta
        self.main_content.controls = self.build_controls()

        if is_initial_load:
            self._popola_filtro_mese()

        utente_id = self.controller.get_user_id()
        famiglia_id = self.controller.get_family_id()
        ruolo = self.controller.get_user_role()

        if not utente_id:
            return

        if not famiglia_id:  # Se l'utente non è in una famiglia
            self.main_content.controls.append(
                ft.Column(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=50, color=ft.Colors.GREY_500),
                        ft.Text(self.controller.loc.get("not_in_family"), size=18)
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True
                )
            )
        elif ruolo == 'livello3':  # Livello 3 non ha accesso
            self.main_content.controls.append(
                ft.Column(
                    [
                        ft.Icon(ft.Icons.LOCK, size=50, color=ft.Colors.GREY_500),
                        ft.Text(self.controller.loc.get("no_family_access_permission"), size=18)
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True
                )
            )
        elif ruolo == 'livello2':  # Livello 2 vede solo i totali per membro
            self.main_content.controls.clear()  # Pulisce per mostrare solo i totali
            self.main_content.controls.append(
                ft.Text(self.controller.loc.get("wealth_by_member"), size=24, weight=ft.FontWeight.BOLD))
            self.main_content.controls.append(ft.Divider())
            totali = ottieni_totali_famiglia(famiglia_id)
            for m in totali:
                self.main_content.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(m['nome_visualizzato'], weight=ft.FontWeight.BOLD, size=16, expand=True),
                            ft.Text(self.controller.loc.format_currency(m['saldo_totale']), size=16,
                                    color=ft.Colors.GREEN_500 if m['saldo_totale'] >= 0 else ft.Colors.RED_500)
                        ]),
                        padding=10,
                        border=ft.border.all(1, ft.Colors.GREY_800),
                        border_radius=5
                    )
                )
        elif ruolo in ['admin', 'livello1']:  # Admin e Livello 1 vedono la nuova vista aggregata
            print(f"DEBUG (FamilyTab.update_view_data): id_famiglia = {famiglia_id}")

            anno, mese = self._get_anno_mese_selezionato()

            # Aggiorna i totali della famiglia
            riepilogo_famiglia = ottieni_riepilogo_patrimonio_famiglia_aggregato(famiglia_id, anno, mese)
            self.txt_patrimonio_totale_famiglia.value = self.controller.loc.format_currency(
                riepilogo_famiglia.get('patrimonio_netto', 0))
            self.txt_liquidita_totale_famiglia.value = self.controller.loc.format_currency(
                riepilogo_famiglia.get('liquidita', 0))
            self.txt_investimenti_totali_famiglia.value = self.controller.loc.format_currency(
                riepilogo_famiglia.get('investimenti', 0))
            self.txt_investimenti_totali_famiglia.visible = riepilogo_famiglia.get('investimenti', 0) > 0

            print(f"DEBUG (FamilyTab.update_view_data): Riepilogo famiglia per {anno}-{mese}: {riepilogo_famiglia}")

            # Aggiorna la lista delle transazioni
            transazioni = ottieni_dettagli_famiglia(famiglia_id, anno, mese)
            self.dt_transazioni_famiglia.rows.clear()
            if not transazioni:
                self.dt_transazioni_famiglia.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(self.controller.loc.get("no_transactions_found_family"),
                                                text_align=ft.TextAlign.CENTER)),
                            ft.DataCell(ft.Text("")), ft.DataCell(ft.Text("")), ft.DataCell(ft.Text("")),
                            ft.DataCell(ft.Text("")), ft.DataCell(ft.Text("")),
                        ]
                    )
                )
            else:
                for t in transazioni:
                    self.dt_transazioni_famiglia.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(t.get('utente_nome') or self.controller.loc.get("shared"))),
                            ft.DataCell(ft.Text(t.get('data') or "N/A")),
                            ft.DataCell(ft.Text(t.get('descrizione') or "N/A")),
                            ft.DataCell(ft.Text(t.get('nome_categoria') or "N/A")),
                            ft.DataCell(ft.Text(t.get('conto_nome') or "N/A")),
                            ft.DataCell(ft.Text(self.controller.loc.format_currency(t.get('importo', 0)),
                                                color=ft.Colors.GREEN_500 if t.get('importo',
                                                                                   0) >= 0 else ft.Colors.RED_500)),
                        ])
                    )
        else:
            self.main_content.controls.append(ft.Text("Ruolo non riconosciuto."))

        if self.page:
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        loc = self.controller.loc
        self.dd_mese_filtro.label = loc.get("filter_by_month")
        self.dt_transazioni_famiglia.columns = [
            ft.DataColumn(ft.Text(loc.get("user"))),
            ft.DataColumn(ft.Text(loc.get("date"))),
            ft.DataColumn(ft.Text(loc.get("description"))),
            ft.DataColumn(ft.Text(loc.get("category"))),
            ft.DataColumn(ft.Text(loc.get("account"))),
            ft.DataColumn(ft.Text(loc.get("amount")), numeric=True),
        ]

        # La visibilità dei controlli dipende dal ruolo, quindi la logica rimane in update_view_data
        # Qui restituiamo solo i controlli che sono sempre presenti per admin/livello1
        return [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column([
                            ft.Text(loc.get("total_family_wealth"), size=12, color=ft.Colors.GREY_500),
                            self.txt_patrimonio_totale_famiglia
                        ]),
                        ft.Column([
                            ft.Text(loc.get("total_liquidity"), size=12, color=ft.Colors.GREY_500),
                            self.txt_liquidita_totale_famiglia,
                            ft.Text(loc.get("total_investments"), size=12, color=ft.Colors.GREY_500,
                                    visible=self.txt_investimenti_totali_famiglia.visible),
                            self.txt_investimenti_totali_famiglia
                        ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.END)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ), padding=10, border=ft.border.all(1, ft.Colors.GREY_800), border_radius=5),
            self.dd_mese_filtro,
            ft.Divider(height=20),
            ft.Text(loc.get("all_family_transactions"), size=24, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Column([self.dt_transazioni_famiglia], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
        ]

    def _popola_filtro_mese(self):
        """Popola il dropdown con i mesi disponibili."""
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        periodi = ottieni_anni_mesi_storicizzati(id_famiglia)
        oggi = datetime.date.today()
        periodo_corrente = {'anno': oggi.year, 'mese': oggi.month}
        if periodo_corrente not in periodi:
            periodi.insert(0, periodo_corrente)

        self.dd_mese_filtro.options = [
            ft.dropdown.Option(
                key=f"{p['anno']}-{p['mese']}",
                text=datetime.date(p['anno'], p['mese'], 1).strftime("%B %Y")
            ) for p in periodi
        ]
        self.dd_mese_filtro.value = f"{oggi.year}-{oggi.month}"

    def _get_anno_mese_selezionato(self):
        if self.dd_mese_filtro.value:
            return map(int, self.dd_mese_filtro.value.split('-'))
        oggi = datetime.date.today()
        return oggi.year, oggi.month

    def _filtro_mese_cambiato(self, e):
        self.update_view_data()
        self.page.update()