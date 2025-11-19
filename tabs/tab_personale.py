import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_transazioni_utente,
    elimina_transazione,
    elimina_transazione_condivisa,
    ottieni_riepilogo_patrimonio_utente,
    ottieni_anni_mesi_storicizzati  # Per popolare il filtro
)
import datetime


class PersonaleTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=ft.padding.only(left=10, top=10, right=10, bottom=80), expand=True)

        self.controller = controller
        self.page = controller.page

        self.txt_bentornato = ft.Text(size=16)
        self.txt_patrimonio = ft.Text(size=24, weight=ft.FontWeight.BOLD)
        self.txt_liquidita = ft.Text(size=14, color=ft.Colors.GREY_500)

        # Filtro per mese
        self.dd_mese_filtro = ft.Dropdown(
            on_change=self._filtro_mese_cambiato
        )

        self.lista_transazioni = ft.Column(
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
            spacing=10
        )

        self.content = ft.Column(expand=True)

    def update_view_data(self, is_initial_load=False):
        # Ricostruisce l'interfaccia con le traduzioni corrette ogni volta
        self.content.controls = self.build_controls()

        # Popola il filtro solo al primo caricamento per evitare refresh continui
        if is_initial_load:
            self._popola_filtro_mese()

        utente_id = self.controller.get_user_id()
        if not utente_id:
            return

        utente = self.controller.page.session.get("utente_loggato")
        if not utente:
            print("ERRORE in PersonaleTab: utente non trovato in sessione.")
            return

        # Ottieni anno e mese dal dropdown, o usa il mese corrente come default
        anno, mese = self._get_anno_mese_selezionato()

        # --- Aggiorna i totali usando la funzione centralizzata ---
        riepilogo_patrimonio = ottieni_riepilogo_patrimonio_utente(utente_id, anno, mese)
        patrimonio_totale = riepilogo_patrimonio.get('patrimonio_netto', 0.0)
        liquidita_totale = riepilogo_patrimonio.get('liquidita', 0.0)

        self.txt_bentornato.value = self.controller.loc.get("welcome_back", utente['nome'])
        self.txt_patrimonio.value = f"{self.controller.loc.get('total_wealth')}: {self.controller.loc.format_currency(patrimonio_totale)}"

        data_formattata = datetime.date(anno, mese, 1).strftime('%d/%m/%Y')
        self.txt_liquidita.value = self.controller.loc.get("liquidity_details",
                                                           self.controller.loc.format_currency(liquidita_totale),
                                                           data_formattata)

        # --- Aggiorna la lista delle transazioni ---
        transazioni = ottieni_transazioni_utente(utente_id, anno, mese)

        self.lista_transazioni.controls.clear()
        for t in transazioni:
            descrizione_transazione = t.get('descrizione', '').upper()
            if descrizione_transazione.startswith("SALDO INIZIALE"):
                continue

            azioni = ft.Row([
                ft.IconButton(icon=ft.Icons.EDIT, tooltip=self.controller.loc.get("edit"), data=t,
                              on_click=lambda e: self.controller.transaction_dialog.apri_dialog_modifica_transazione(
                                  e.control.data),
                              icon_color=ft.Colors.BLUE_400, icon_size=16),
                ft.IconButton(icon=ft.Icons.DELETE, tooltip=self.controller.loc.get("delete"), data=t,
                              on_click=lambda e: self.controller.open_confirm_delete_dialog(
                                  partial(self.elimina_cliccato, e)),
                              icon_color=ft.Colors.RED_400, icon_size=16)
            ], spacing=0)

            self.lista_transazioni.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column([
                                ft.Text(t['descrizione'], weight=ft.FontWeight.BOLD),
                                ft.Text(f"{t['data']} - {t['nome_conto']}", size=10, color=ft.Colors.GREY_500),
                            ], expand=True),
                            ft.Column([
                                ft.Text(self.controller.loc.format_currency(t['importo']), size=14,
                                        color=ft.Colors.GREEN_500 if t['importo'] > 0 else ft.Colors.RED_500),
                                ft.Text(t.get('nome_sottocategoria') or self.controller.loc.get("no_category"),
                                        size=10, color=ft.Colors.GREY_500)
                            ], horizontal_alignment=ft.CrossAxisAlignment.END),
                            azioni
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.GREY_800),
                    border_radius=5
                )
            )

        if self.page:
            self.page.update()

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        self.dd_mese_filtro.label = self.controller.loc.get("filter_by_month")

        return [
            self.txt_bentornato,
            self.txt_patrimonio,
            self.txt_liquidita,
            self.dd_mese_filtro,
            ft.Divider(),
            ft.Text(self.controller.loc.get("latest_transactions"), size=20),
            self.lista_transazioni
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

    def elimina_cliccato(self, e):
        transazione_data = e.control.data
        id_transazione = transazione_data.get('id_transazione')
        id_transazione_condivisa = transazione_data.get('id_transazione_condivisa')

        success = False
        if id_transazione and id_transazione > 0:
            success = elimina_transazione(id_transazione)
        elif id_transazione_condivisa and id_transazione_condivisa > 0:
            success = elimina_transazione_condivisa(id_transazione_condivisa)

        messaggio = "eliminata" if success else "errore nell'eliminazione"

        if success:
            self.controller.show_snack_bar(f"Transazione {messaggio}.", success=True)
            self.controller.db_write_operation()  # Esegue update e sync
        else:
            self.controller.show_snack_bar(f"Errore: {messaggio}.", success=False)