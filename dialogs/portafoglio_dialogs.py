import flet as ft
import datetime
from db.gestione_db import (
    ottieni_portafoglio,
    compra_asset,
    vendi_asset,
    aggiorna_prezzo_manuale_asset,
    modifica_asset_dettagli,
    ottieni_tutti_i_conti_utente,
    aggiungi_transazione,
    aggiungi_transazione_condivisa
)


class PortafoglioDialogs:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page
        self.loc = controller.loc
        self.conto_selezionato = None

        # --- Dialogo principale del portafoglio ---
        self.dt_portafoglio = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("..."))],
            rows=[],
            expand=True
        )
        self.txt_valore_totale = ft.Text(weight="bold", size=16)
        self.txt_gain_loss_totale = ft.Text(weight="bold", size=16)
        self.dialog_portafoglio = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([
                ft.Row([
                    ft.Text(weight="bold"),
                    self.txt_valore_totale,
                    ft.Text(weight="bold"),
                    self.txt_gain_loss_totale
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                ft.Divider(),
                ft.Column([self.dt_portafoglio], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
            ], width=800, height=500),
            actions=[
                ft.TextButton(on_click=self._chiudi_dialog_portafoglio),
                ft.ElevatedButton(icon=ft.Icons.ADD, on_click=self._apri_dialog_operazione)
            ]
        )

        # --- Dialogo per operazione (compra/vendi) ---
        self.dd_asset_esistenti = ft.Dropdown(on_change=self._on_asset_selezionato)
        self.dd_conto_transazione = ft.Dropdown()
        self.txt_ticker = ft.TextField()
        self.txt_nome_asset = ft.TextField()
        self.txt_quantita = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_prezzo_unitario = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.radio_operazione = ft.RadioGroup(content=ft.Row())
        self.dialog_operazione_asset = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([
                self.dd_asset_esistenti,
                self.txt_ticker,
                self.txt_nome_asset,
                self.txt_quantita,
                self.txt_prezzo_unitario,
                self.dd_conto_transazione,
                self.radio_operazione
            ], tight=True, spacing=10, height=550, width=400),
            actions=[
                ft.TextButton(on_click=self._chiudi_dialog_operazione),
                ft.TextButton(on_click=self._salva_operazione)
            ]
        )

        # --- Dialogo per aggiornare il prezzo ---
        self.txt_nuovo_prezzo = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.asset_da_aggiornare = None
        self.dialog_aggiorna_prezzo = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=self.txt_nuovo_prezzo,
            actions=[
                ft.TextButton(on_click=self._chiudi_dialog_aggiorna_prezzo),
                ft.TextButton(on_click=self._salva_nuovo_prezzo)
            ]
        )

        # --- Dialogo per modificare dettagli asset ---
        self.txt_modifica_ticker = ft.TextField()
        self.txt_modifica_nome = ft.TextField()
        self.asset_da_modificare = None
        self.dialog_modifica_asset = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([self.txt_modifica_ticker, self.txt_modifica_nome], tight=True),
            actions=[
                ft.TextButton(on_click=self._chiudi_dialog_modifica_asset),
                ft.TextButton(on_click=self._salva_modifica_asset)
            ]
        )

    def _update_texts(self):
        """Aggiorna i testi di tutti i dialoghi."""
        loc = self.loc
        # Dialogo Portafoglio
        self.dialog_portafoglio.title.value = loc.get("manage_portfolio_dialog")
        self.dialog_portafoglio.content.controls[0].controls[0].value = loc.get("total_portfolio_value") + ":"
        self.dialog_portafoglio.content.controls[0].controls[2].value = loc.get("total_gain_loss") + ":"
        self.dialog_portafoglio.actions[0].text = loc.get("close")
        self.dialog_portafoglio.actions[1].text = loc.get("add_operation")
        self.dt_portafoglio.columns = [
            ft.DataColumn(ft.Text(loc.get("ticker"))),
            ft.DataColumn(ft.Text(loc.get("asset_name"))),
            ft.DataColumn(ft.Text(loc.get("quantity")), numeric=True),
            ft.DataColumn(ft.Text(loc.get("current_unit_price")), numeric=True),
            ft.DataColumn(ft.Text("G/L " + loc.get("unit_price")), numeric=True),
            ft.DataColumn(ft.Text("G/L Totale"), numeric=True),
            ft.DataColumn(ft.Text(loc.get("actions"))),
        ]

        # Dialogo Operazione
        self.dialog_operazione_asset.title.value = loc.get("add_operation")
        self.dd_asset_esistenti.label = loc.get("select_existing_asset_optional")
        self.dd_conto_transazione.label = "Conto per transazione"
        self.txt_ticker.label = loc.get("ticker")
        self.txt_nome_asset.label = loc.get("asset_name")
        self.txt_quantita.label = loc.get("quantity")
        self.txt_prezzo_unitario.label = loc.get("unit_price")
        self.txt_prezzo_unitario.prefix_text = loc.currencies[loc.currency]['symbol']
        self.radio_operazione.content.controls = [
            ft.Radio(value="COMPRA", label=loc.get("buy")),
            ft.Radio(value="VENDI", label=loc.get("sell")),
        ]
        self.dialog_operazione_asset.actions[0].text = loc.get("cancel")
        self.dialog_operazione_asset.actions[1].text = loc.get("save")

        # Dialogo Aggiorna Prezzo
        self.dialog_aggiorna_prezzo.title.value = loc.get("update_price")
        self.txt_nuovo_prezzo.label = loc.get("new_price")
        self.txt_nuovo_prezzo.prefix_text = loc.currencies[loc.currency]['symbol']
        self.dialog_aggiorna_prezzo.actions[0].text = loc.get("cancel")
        self.dialog_aggiorna_prezzo.actions[1].text = loc.get("save")

        # Dialogo Modifica Asset
        self.dialog_modifica_asset.title.value = loc.get("edit_asset_details")
        self.txt_modifica_ticker.label = loc.get("ticker")
        self.txt_modifica_nome.label = loc.get("asset_name")
        self.dialog_modifica_asset.actions[0].text = loc.get("cancel")
        self.dialog_modifica_asset.actions[1].text = loc.get("save")

    def apri_dialog_portafoglio(self, e, conto_data):
        self._update_texts()
        self.conto_selezionato = conto_data
        self.dialog_portafoglio.title.value = f"{self.loc.get('manage_portfolio_dialog')}: {conto_data['nome_conto']}"
        self._aggiorna_tabella_portafoglio()
        self.page.dialog = self.dialog_portafoglio
        self.dialog_portafoglio.open = True
        self.page.update()

    def _chiudi_dialog_portafoglio(self, e):
        self.dialog_portafoglio.open = False
        self.page.update()

    def _aggiorna_tabella_portafoglio(self):
        loc = self.loc
        portafoglio = ottieni_portafoglio(self.conto_selezionato['id_conto'])
        self.dt_portafoglio.rows.clear()
        valore_totale = 0
        gain_loss_totale = 0

        for asset in portafoglio:
            valore_totale += asset['quantita'] * asset['prezzo_attuale_manuale']
            gain_loss_totale += asset['gain_loss_totale']
            self.dt_portafoglio.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(asset['ticker'])),
                    ft.DataCell(ft.Text(asset['nome_asset'])),
                    ft.DataCell(ft.Text(f"{asset['quantita']:.4f}")),
                    ft.DataCell(ft.Text(loc.format_currency(asset['prezzo_attuale_manuale']))),
                    ft.DataCell(ft.Text(loc.format_currency(asset['gain_loss_unitario']),
                                        color=ft.Colors.GREEN if asset['gain_loss_unitario'] >= 0 else ft.Colors.RED)),
                    ft.DataCell(ft.Text(loc.format_currency(asset['gain_loss_totale']),
                                        color=ft.Colors.GREEN if asset['gain_loss_totale'] >= 0 else ft.Colors.RED)),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.Icons.EDIT, tooltip=loc.get("edit"), data=asset,
                                      on_click=self._apri_dialog_modifica_asset),
                        ft.IconButton(icon=ft.Icons.PRICE_CHANGE, tooltip=loc.get("update_price"), data=asset,
                                      on_click=self._apri_dialog_aggiorna_prezzo)
                    ]))
                ])
            )
        self.txt_valore_totale.value = loc.format_currency(valore_totale)
        self.txt_gain_loss_totale.value = loc.format_currency(gain_loss_totale)
        self.txt_gain_loss_totale.color = ft.Colors.GREEN if gain_loss_totale >= 0 else ft.Colors.RED

        if self.dialog_portafoglio.open:
            self.dialog_portafoglio.update()

    def _apri_dialog_operazione(self, e):
        self._update_texts()
        # Reset dei campi
        self.txt_ticker.value = ""
        self.txt_nome_asset.value = ""
        self.txt_quantita.value = ""
        self.txt_prezzo_unitario.value = ""
        self.radio_operazione.value = "COMPRA"
        self.txt_ticker.read_only = False
        self.txt_nome_asset.read_only = False

        # Popola il dropdown degli asset esistenti
        portafoglio_attuale = ottieni_portafoglio(self.conto_selezionato['id_conto'])
        self.dd_asset_esistenti.options = [
            ft.dropdown.Option(
                key=str(asset['id_asset']),
                text=f"{asset['ticker']} - {asset['nome_asset']}",
                data=asset
            ) for asset in portafoglio_attuale
        ]
        self.dd_asset_esistenti.value = None

        # Popola il dropdown dei conti (personali e condivisi, esclusi investimenti)
        id_utente = self.controller.get_user_id()
        tutti_conti = ottieni_tutti_i_conti_utente(id_utente)
        
        # Filtra solo conti non di investimento
        conti_disponibili = [c for c in tutti_conti if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        
        self.dd_conto_transazione.options = [
            ft.dropdown.Option(
                key=f"{'C' if c.get('is_condiviso') else 'P'}_{c['id_conto']}",
                text=f"{c['nome_conto']} ({c['tipo']})" + (" - Condiviso" if c.get('is_condiviso') else "")
            ) for c in conti_disponibili
        ]
        self.dd_conto_transazione.value = None

        self.page.dialog = self.dialog_operazione_asset
        self.dialog_operazione_asset.open = True
        self.page.update()

    def _chiudi_dialog_operazione(self, e):
        self.dialog_operazione_asset.open = False
        self.page.dialog = self.dialog_portafoglio
        self.page.update()

    def _on_asset_selezionato(self, e):
        """Chiamato quando un asset viene selezionato dal dropdown."""
        selected_value = str(e.control.value) if e.control.value is not None else None
        selected_option = next((opt for opt in self.dd_asset_esistenti.options if str(opt.key) == selected_value), None)
        
        if selected_option and selected_option.data:
            asset_data = selected_option.data
            self.txt_ticker.value = asset_data['ticker']
            self.txt_nome_asset.value = asset_data['nome_asset']
            self.txt_ticker.read_only = True
            self.txt_nome_asset.read_only = True
        else:
            self.txt_ticker.value = ""
            self.txt_nome_asset.value = ""
            self.txt_ticker.read_only = False
            self.txt_nome_asset.read_only = False

        if self.dialog_operazione_asset.open:
            self.dialog_operazione_asset.update()

    def _salva_operazione(self, e):
        try:
            tipo_op = self.radio_operazione.value
            quantita = float(self.txt_quantita.value.replace(",", "."))
            prezzo = float(self.txt_prezzo_unitario.value.replace(",", "."))
            ticker = self.txt_ticker.value.strip().upper()
            nome_asset = self.txt_nome_asset.value.strip()
            conto_selezionato_key = self.dd_conto_transazione.value

            # Validate that operation type is selected
            if not tipo_op:
                self.controller.show_snack_bar(self.loc.get("fill_all_fields"), success=False)
                return

            if not all([ticker, nome_asset, quantita > 0, prezzo > 0, conto_selezionato_key]):
                self.controller.show_snack_bar(self.loc.get("fill_all_fields"), success=False)
                return

            # Parse il conto selezionato (formato: "P_123" o "C_456")
            tipo_conto, id_conto_str = conto_selezionato_key.split("_")
            id_conto_transazione = int(id_conto_str)
            is_conto_condiviso = (tipo_conto == "C")

            # Calcola l'importo totale della transazione
            importo_totale = quantita * prezzo
            data_oggi = datetime.date.today().strftime('%Y-%m-%d')

            if tipo_op == "COMPRA":
                # Acquisto: sottrai denaro dal conto
                descrizione = f"Acquisto {quantita} {ticker} @ {prezzo}"
                importo_transazione = -abs(importo_totale)
                
                # Compra l'asset
                compra_asset(self.conto_selezionato['id_conto'], ticker, nome_asset, quantita, prezzo)
                
            elif tipo_op == "VENDI":
                # Vendita: aggiungi denaro al conto
                descrizione = f"Vendita {quantita} {ticker} @ {prezzo}"
                importo_transazione = abs(importo_totale)
                
                # Vendi l'asset
                vendi_asset(self.conto_selezionato['id_conto'], ticker, quantita, prezzo)
            else:
                self.controller.show_snack_bar(self.loc.get("fill_all_fields"), success=False)
                return

            # Crea la transazione sul conto selezionato
            if is_conto_condiviso:
                id_utente = self.controller.get_user_id()
                aggiungi_transazione_condivisa(
                    id_utente, 
                    id_conto_transazione, 
                    data_oggi, 
                    descrizione, 
                    importo_transazione
                )
            else:
                aggiungi_transazione(
                    id_conto_transazione, 
                    data_oggi, 
                    descrizione, 
                    importo_transazione
                )

            self.controller.db_write_operation()
            self._aggiorna_tabella_portafoglio()
            self._chiudi_dialog_operazione(e)
            self.controller.show_snack_bar("Operazione completata con successo", success=True)
            
        except (ValueError, TypeError) as ex:
            print(f"Errore durante il salvataggio: {ex}")
            self.controller.show_snack_bar(self.loc.get("invalid_amount_or_quantity"), success=False)

    def _apri_dialog_aggiorna_prezzo(self, e):
        self.asset_da_aggiornare = e.control.data
        self.txt_nuovo_prezzo.value = str(self.asset_da_aggiornare['prezzo_attuale_manuale'])
        self.dialog_aggiorna_prezzo.title.value = f"{self.loc.get('update_price')}: {self.asset_da_aggiornare['ticker']}"
        self.page.dialog = self.dialog_aggiorna_prezzo
        self.dialog_aggiorna_prezzo.open = True
        self.page.update()

    def _chiudi_dialog_aggiorna_prezzo(self, e):
        self.dialog_aggiorna_prezzo.open = False
        self.page.dialog = self.dialog_portafoglio
        self.page.update()

    def _salva_nuovo_prezzo(self, e):
        try:
            nuovo_prezzo = float(self.txt_nuovo_prezzo.value.replace(",", "."))
            aggiorna_prezzo_manuale_asset(self.asset_da_aggiornare['id_asset'], nuovo_prezzo)
            self.controller.db_write_operation()
            self._aggiorna_tabella_portafoglio()
            self._chiudi_dialog_aggiorna_prezzo(e)
        except (ValueError, TypeError):
            self.controller.show_snack_bar(self.loc.get("invalid_amount"), success=False)

    def _apri_dialog_modifica_asset(self, e):
        self.asset_da_modificare = e.control.data
        self.txt_modifica_ticker.value = self.asset_da_modificare['ticker']
        self.txt_modifica_nome.value = self.asset_da_modificare['nome_asset']
        self.dialog_modifica_asset.title.value = f"{self.loc.get('edit_asset_details')}: {self.asset_da_modificare['ticker']}"
        self.page.dialog = self.dialog_modifica_asset
        self.dialog_modifica_asset.open = True
        self.page.update()

    def _chiudi_dialog_modifica_asset(self, e):
        self.dialog_modifica_asset.open = False
        self.page.dialog = self.dialog_portafoglio
        self.page.update()

    def _salva_modifica_asset(self, e):
        nuovo_ticker = self.txt_modifica_ticker.value.strip().upper()
        nuovo_nome = self.txt_modifica_nome.value.strip()
        if nuovo_ticker and nuovo_nome:
            modifica_asset_dettagli(self.asset_da_modificare['id_asset'], nuovo_ticker, nuovo_nome)
            self.controller.db_write_operation()
            self._aggiorna_tabella_portafoglio()
            self._chiudi_dialog_modifica_asset(e)