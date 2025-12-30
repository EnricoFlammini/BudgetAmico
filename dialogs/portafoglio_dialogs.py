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
from utils.yfinance_manager import applica_suffisso_borsa
from utils.ticker_search import TickerSearchField


class PortafoglioDialogs:
    def __init__(self, controller):
        self.controller = controller
        # self.page = controller.page # Removed for Flet 0.80 compatibility
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
                ft.ElevatedButton(icon=ft.Icons.ADD_BOX, text=self.loc.get("add_existing_asset"), on_click=self._apri_dialog_asset_esistente),
                ft.ElevatedButton(icon=ft.Icons.ADD, text=self.loc.get("add_operation"), on_click=self._apri_dialog_operazione)
            ]
        )

        # --- Dialogo per operazione (compra/vendi) ---
        self.dd_asset_esistenti = ft.Dropdown(on_change=self._on_asset_selezionato)
        self.dd_conto_transazione = ft.Dropdown()
        
        # Campo ricerca ticker con autocomplete
        self.ticker_search = TickerSearchField(
            on_select=self._on_ticker_autocomplete_select,
            controller=controller,  # Riferimento stabile per update
            label="Cerca ticker",
            hint_text="es. Apple Milano, AAPL...",
            width=380,
            show_borsa=True
        )
        self.txt_ticker = ft.TextField()  # Nascosto, usato solo per valore
        self.txt_nome_asset = ft.TextField()  # Nascosto, usato solo per valore
        self.txt_quantita = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_prezzo_unitario = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.radio_operazione = ft.RadioGroup(content=ft.Row())
        self.dialog_operazione_asset = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([
                self.dd_asset_esistenti,
                self.ticker_search,  # Autocomplete + nome automatico
                self.txt_quantita,
                self.txt_prezzo_unitario,
                self.dd_conto_transazione,
                self.radio_operazione
            ], tight=True, spacing=10, height=450, width=420),
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
        # Campo ricerca per modifica ticker
        self.ticker_search_modifica = TickerSearchField(
            on_select=self._on_ticker_modifica_select,
            controller=controller,
            label="Cerca nuovo ticker",
            hint_text="es. Apple, MSFT...",
            width=380,
            show_borsa=True
        )
        self.txt_modifica_ticker = ft.TextField()  # Nascosto, usato per valore
        self.txt_modifica_nome = ft.TextField()  # Nascosto, usato per valore
        self.asset_da_modificare = None
        self.dialog_modifica_asset = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([self.ticker_search_modifica], tight=True, width=400),
            actions=[
                ft.TextButton(on_click=self._chiudi_dialog_modifica_asset),
                ft.TextButton(on_click=self._salva_modifica_asset)
            ]
        )

        # --- Dialogo per aggiungere asset esistente ---
        # Campo ricerca per asset esistente
        self.ticker_search_esistente = TickerSearchField(
            on_select=self._on_ticker_esistente_select,
            controller=controller,
            label="Cerca ticker",
            hint_text="es. Apple, MSFT...",
            width=380,
            show_borsa=True
        )
        self.txt_ticker_esistente = ft.TextField()  # Nascosto, usato per valore
        self.txt_nome_asset_esistente = ft.TextField()  # Nascosto, usato per valore
        self.txt_quantita_esistente = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_prezzo_medio_acquisto = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_valore_attuale_unitario = ft.TextField(keyboard_type=ft.KeyboardType.NUMBER)
        self.dialog_asset_esistente = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column([
                self.ticker_search_esistente,  # Autocomplete invece di txt
                self.txt_quantita_esistente,
                self.txt_prezzo_medio_acquisto,
                self.txt_valore_attuale_unitario
            ], tight=True, spacing=10, height=450, width=420),
            actions=[
                ft.TextButton(on_click=self._chiudi_dialog_asset_esistente),
                ft.TextButton(on_click=self._salva_asset_esistente)
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
        self.dialog_portafoglio.actions[1].text = loc.get("add_existing_asset")
        self.dialog_portafoglio.actions[2].text = loc.get("add_operation")
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

        # Dialogo Aggiungi Asset Esistente (potrebbe essere un BottomSheet senza title)
        if hasattr(self.dialog_asset_esistente, 'title'):
            self.dialog_asset_esistente.title.value = loc.get("add_existing_asset")
        self.txt_ticker_esistente.label = loc.get("ticker")
        self.txt_nome_asset_esistente.label = loc.get("asset_name")
        self.txt_quantita_esistente.label = loc.get("quantity")
        self.txt_prezzo_medio_acquisto.label = loc.get("avg_purchase_price")
        self.txt_valore_attuale_unitario.label = loc.get("current_unit_price")
        if hasattr(self.dialog_asset_esistente, 'actions'):
            self.dialog_asset_esistente.actions[0].text = loc.get("cancel")
            self.dialog_asset_esistente.actions[1].text = loc.get("save")

    def apri_dialog_portafoglio(self, e, conto_data):
        self._update_texts()
        self.conto_selezionato = conto_data
        self.dialog_portafoglio.title.value = f"{self.loc.get('manage_portfolio_dialog')}: {conto_data['nome_conto']}"
        self._aggiorna_tabella_portafoglio()
        self.controller.page.open(self.dialog_portafoglio)
        self.controller.page.update()

    def _chiudi_dialog_portafoglio(self, e):
        try:
            self.controller.page.close(self.dialog_portafoglio)
            self.controller.page.update()
        except Exception as ex:
            print(f"Errore chiusura dialog portafoglio: {ex}")
            import traceback
            traceback.print_exc()

    def _aggiorna_tabella_portafoglio(self):
        loc = self.loc
        master_key_b64 = self.page.session.get("master_key")
        portafoglio = ottieni_portafoglio(self.conto_selezionato['id_conto'], master_key_b64=master_key_b64)
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
        # RIPRISTINA IL CONTENUTO ORIGINALE (perché potrebbe essere stato alterato da _apri_dialog_asset_esistente)
        self.dialog_operazione_asset.content = ft.Column([
            self.dd_asset_esistenti,
            self.ticker_search,  # Autocomplete + nome automatico
            self.txt_quantita,
            self.txt_prezzo_unitario,
            self.dd_conto_transazione,
            self.radio_operazione
        ], tight=True, spacing=10, height=450, width=420)
        
        self.dialog_operazione_asset.actions = [
            ft.TextButton(on_click=self._chiudi_dialog_operazione),
            ft.TextButton(on_click=self._salva_operazione)
        ]

        self._update_texts()
        # Reset dei campi
        self.txt_ticker.value = ""
        self.txt_nome_asset.value = ""
        self.ticker_search.reset()
        self.txt_quantita.value = ""
        self.txt_prezzo_unitario.value = ""
        self.radio_operazione.value = "COMPRA"

        master_key_b64 = self.page.session.get("master_key")

        # Popola il dropdown degli asset esistenti
        portafoglio_attuale = ottieni_portafoglio(self.conto_selezionato['id_conto'], master_key_b64=master_key_b64)
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
        tutti_conti = ottieni_tutti_i_conti_utente(id_utente, master_key_b64=master_key_b64)
        
        # Filtra solo conti non di investimento
        conti_disponibili = [c for c in tutti_conti if c['tipo'] not in ['Investimento', 'Fondo Pensione']]
        
        self.dd_conto_transazione.options = [
            ft.dropdown.Option(key="CASHBACK", text="🎁 Cashback (no addebito)")
        ] + [
            ft.dropdown.Option(
                key=f"{'C' if c.get('is_condiviso') else 'P'}_{c['id_conto']}",
                text=f"{c['nome_conto']} ({c['tipo']})" + (" - Condiviso" if c.get('is_condiviso') else "")
            ) for c in conti_disponibili
        ]
        self.dd_conto_transazione.value = None

        self.controller.page.open(self.dialog_operazione_asset)
        self.controller.page.update()

    def _chiudi_dialog_operazione(self, e):
        try:
            self.controller.page.close(self.dialog_operazione_asset)
            self.controller.page.update()
        except Exception as ex:
            print(f"Errore chiusura dialog operazione: {ex}")
            import traceback
            traceback.print_exc()

    def _on_asset_selezionato(self, e):
        """Chiamato quando un asset viene selezionato dal dropdown."""
        selected_value = str(e.control.value) if e.control.value is not None else None
        selected_option = next((opt for opt in self.dd_asset_esistenti.options if str(opt.key) == selected_value), None)
        
        if selected_option and selected_option.data:
            asset_data = selected_option.data
            self.txt_ticker.value = asset_data['ticker']
            self.ticker_search.value = asset_data['ticker']
            self.txt_nome_asset.value = asset_data['nome_asset']
            self.txt_nome_asset.read_only = True
            self.ticker_search.txt_search.read_only = True
        else:
            self.txt_ticker.value = ""
            self.ticker_search.reset()
            self.txt_nome_asset.value = ""
            self.txt_nome_asset.read_only = False
            self.ticker_search.txt_search.read_only = False

        if self.dialog_operazione_asset.open:
            self.dialog_operazione_asset.update()
    
    def _on_ticker_autocomplete_select(self, risultato: dict):
        """Callback quando un ticker viene selezionato dall'autocomplete."""
        ticker = risultato['ticker']
        nome = risultato['nome']
        
        # Imposta valori nei campi
        self.txt_ticker.value = ticker
        self.txt_nome_asset.value = nome
        self.txt_nome_asset.read_only = False  # L'utente può modificare il nome
        
        if self.dialog_operazione_asset.open:
            self.dialog_operazione_asset.update()
    
    def _on_ticker_esistente_select(self, risultato: dict):
        """Callback per autocomplete nel dialog Aggiungi Asset Esistente."""
        ticker = risultato['ticker']
        nome = risultato['nome']
        
        self.txt_ticker_esistente.value = ticker
        self.txt_nome_asset_esistente.value = nome
        
        if self.dialog_operazione_asset.open:
            self.dialog_operazione_asset.update()
    
    def _on_ticker_modifica_select(self, risultato: dict):
        """Callback per autocomplete nel dialog Modifica Asset."""
        ticker = risultato['ticker']
        nome = risultato['nome']
        
        self.txt_modifica_ticker.value = ticker
        self.txt_modifica_nome.value = nome
        
        if self.dialog_modifica_asset.open:
            self.dialog_modifica_asset.update()

    def _salva_operazione(self, e):
        try:
            tipo_op = self.radio_operazione.value
            quantita = float(self.txt_quantita.value.replace(",", "."))
            prezzo = float(self.txt_prezzo_unitario.value.replace(",", "."))
            # Usa txt_ticker se settato (da autocomplete), altrimenti dal campo search
            ticker = self.txt_ticker.value.strip().upper() or self.ticker_search.value.strip().upper()
            
            # Aggiungi suffisso borsa default se presente e se il ticker non ha già un suffisso
            borsa_default = None
            if self.conto_selezionato and 'borsa_default' in self.conto_selezionato:
                borsa_default = self.conto_selezionato['borsa_default']
            
            ticker = applica_suffisso_borsa(ticker, borsa_default)

            nome_asset = self.txt_nome_asset.value.strip()
            conto_selezionato_key = self.dd_conto_transazione.value

            # Validate that operation type is selected
            if not tipo_op:
                self.controller.show_snack_bar(self.loc.get("fill_all_fields"), success=False)
                return

            if not all([ticker, nome_asset, quantita > 0, prezzo > 0, conto_selezionato_key]):
                self.controller.show_snack_bar(self.loc.get("fill_all_fields"), success=False)
                return

            # Controlla se è un acquisto Cashback (no addebito)
            is_cashback = (conto_selezionato_key == "CASHBACK")
            
            # Per vendita, non permettere cashback
            if tipo_op == "VENDI" and is_cashback:
                self.controller.show_snack_bar("Non puoi vendere con Cashback. Seleziona un conto.", success=False)
                return

            # Calcola l'importo totale della transazione
            importo_totale = quantita * prezzo
            data_oggi = datetime.date.today().strftime('%Y-%m-%d')
            master_key_b64 = self.page.session.get("master_key")

            if tipo_op == "COMPRA":
                # Acquisto: sottrai denaro dal conto (se non è cashback)
                descrizione = f"{'Cashback: ' if is_cashback else 'Acquisto '}{quantita} {ticker} @ {prezzo}"
                
                # Compra l'asset
                compra_asset(self.conto_selezionato['id_conto'], ticker, nome_asset, quantita, prezzo, master_key_b64=master_key_b64)
                
                # Crea transazione SOLO se non è cashback
                if not is_cashback:
                    tipo_conto, id_conto_str = conto_selezionato_key.split("_")
                    id_conto_transazione = int(id_conto_str)
                    is_conto_condiviso = (tipo_conto == "C")
                    importo_transazione = -abs(importo_totale)
                    
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
                
            elif tipo_op == "VENDI":
                # Vendita: aggiungi denaro al conto
                tipo_conto, id_conto_str = conto_selezionato_key.split("_")
                id_conto_transazione = int(id_conto_str)
                is_conto_condiviso = (tipo_conto == "C")
                descrizione = f"Vendita {quantita} {ticker} @ {prezzo}"
                importo_transazione = abs(importo_totale)
                
                # Vendi l'asset
                vendi_asset(self.conto_selezionato['id_conto'], ticker, quantita, prezzo, master_key_b64=master_key_b64)
                
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
            else:
                self.controller.show_snack_bar(self.loc.get("fill_all_fields"), success=False)
                return

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
        self.controller.page.open(self.dialog_aggiorna_prezzo)
        self.controller.page.update()

    def _chiudi_dialog_aggiorna_prezzo(self, e):
        try:
            self.controller.page.close(self.dialog_aggiorna_prezzo)
            self.controller.page.update()
        except Exception as ex:
            print(f"Errore chiusura dialog aggiorna prezzo: {ex}")
            import traceback
            traceback.print_exc()

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
        # Setta valori correnti
        self.txt_modifica_ticker.value = self.asset_da_modificare['ticker']
        self.txt_modifica_nome.value = self.asset_da_modificare['nome_asset']
        # Mostra ticker corrente nel campo search
        self.ticker_search_modifica.txt_search.value = self.asset_da_modificare['ticker']
        self.ticker_search_modifica.dd_risultati.visible = False
        
        self.dialog_modifica_asset.title.value = f"{self.loc.get('edit_asset_details')}: {self.asset_da_modificare['ticker']}"
        self.controller.page.open(self.dialog_modifica_asset)
        self.controller.page.update()

    def _chiudi_dialog_modifica_asset(self, e):
        try:
            self.controller.page.close(self.dialog_modifica_asset)
            self.controller.page.update()
        except Exception as ex:
            print(f"Errore chiusura dialog modifica asset: {ex}")
            import traceback
            traceback.print_exc()

    def _salva_modifica_asset(self, e):
        # Usa txt se settato (da autocomplete), altrimenti dal campo search
        nuovo_ticker = self.txt_modifica_ticker.value.strip().upper() or self.ticker_search_modifica.value.strip().upper()
        nuovo_nome = self.txt_modifica_nome.value.strip() or nuovo_ticker  # Se nome non settato, usa ticker
        master_key_b64 = self.page.session.get("master_key")
        
        if nuovo_ticker and nuovo_nome:
            modifica_asset_dettagli(self.asset_da_modificare['id_asset'], nuovo_ticker, nuovo_nome, master_key_b64=master_key_b64)
            self.controller.db_write_operation()
            self._aggiorna_tabella_portafoglio()
            self._chiudi_dialog_modifica_asset(e)

    def _apri_dialog_asset_esistente(self, e):
        self._update_texts()
        
        # Reset dei campi
        self.txt_ticker_esistente.value = ""
        self.txt_nome_asset_esistente.value = ""
        self.ticker_search_esistente.reset()
        self.txt_quantita_esistente.value = ""
        self.txt_prezzo_medio_acquisto.value = ""
        self.txt_valore_attuale_unitario.value = ""
        
        # RIUSO IL DIALOGO OPERAZIONE (che sappiamo funzionare)
        # Sostituisco il contenuto con i campi per l'asset esistente
        self.dialog_operazione_asset.title.value = self.loc.get("add_existing_asset")
        self.dialog_operazione_asset.content = ft.Column([
            self.ticker_search_esistente,  # Autocomplete
            self.txt_quantita_esistente,
            self.txt_prezzo_medio_acquisto,
            self.txt_valore_attuale_unitario
        ], tight=True, spacing=10, height=450, width=420)
        
        # Sostituisco le azioni
        self.dialog_operazione_asset.actions = [
            ft.TextButton(self.loc.get("cancel"), on_click=self._chiudi_dialog_asset_esistente),
            ft.TextButton(self.loc.get("save"), on_click=self._salva_asset_esistente)
        ]
        
        if self.dialog_operazione_asset not in self.controller.page.overlay:
            self.controller.page.overlay.append(self.dialog_operazione_asset)
        self.dialog_operazione_asset.open = True
        self.controller.page.update()

    def _chiudi_dialog_asset_esistente(self, e):
        try:
            self.controller.page.close(self.dialog_operazione_asset)
            self.controller.page.update()
        except Exception as ex:
            print(f"Errore chiusura dialog asset esistente: {ex}")
            import traceback
            traceback.print_exc()

    def _salva_asset_esistente(self, e):
        try:
            # Usa txt se settato (da autocomplete), altrimenti dal campo search
            ticker = self.txt_ticker_esistente.value.strip().upper() or self.ticker_search_esistente.value.strip().upper()
            nome_asset = self.txt_nome_asset_esistente.value.strip() or ticker  # Se nome non settato, usa ticker
            quantita = float(self.txt_quantita_esistente.value.replace(",", "."))
            prezzo_medio = float(self.txt_prezzo_medio_acquisto.value.replace(",", "."))
            valore_attuale = float(self.txt_valore_attuale_unitario.value.replace(",", "."))

            if not all([ticker, nome_asset, quantita > 0, prezzo_medio >= 0, valore_attuale >= 0]):
                self.controller.show_snack_bar(self.loc.get("fill_all_fields"), success=False)
                return

            # Aggiungi suffisso borsa default se necessario
            borsa_default = None
            if self.conto_selezionato and 'borsa_default' in self.conto_selezionato:
                borsa_default = self.conto_selezionato['borsa_default']
            
            ticker = applica_suffisso_borsa(ticker, borsa_default)
            
            # Prima chiudo il dialog
            self._chiudi_dialog_asset_esistente(e)
            
            # Poi mostro lo spinner
            self.controller.show_loading("Attendere...")
            
            try:
                master_key_b64 = self.page.session.get("master_key")

                # Usa compra_asset per aggiungere l'asset con il costo storico e il valore attuale
                compra_asset(
                    self.conto_selezionato['id_conto'], 
                    ticker, 
                    nome_asset, 
                    quantita, 
                    prezzo_medio, # Questo diventa il costo_iniziale_unitario
                    tipo_mov="APERTURA", # O altro identificativo per saldo iniziale
                    prezzo_attuale_override=valore_attuale, # Questo imposta il prezzo attuale manuale
                    master_key_b64=master_key_b64
                )

                self.controller.db_write_operation()
                self._aggiorna_tabella_portafoglio()
                self.controller.show_snack_bar("Asset aggiunto con successo", success=True)
            finally:
                self.controller.hide_loading()

        except (ValueError, TypeError):
            self.controller.show_snack_bar(self.loc.get("invalid_amount"), success=False)