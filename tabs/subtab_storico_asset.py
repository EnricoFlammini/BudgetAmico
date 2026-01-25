"""
Sotto-tab per visualizzazione grafico storico asset.
"""
import flet as ft
import io
import base64
from datetime import datetime, timedelta
from functools import partial

from db.gestione_db import (
    ottieni_dettagli_conti_utente,
    ottieni_portafoglio,
    ottieni_storico_asset_globale,
    aggiorna_storico_asset_se_necessario
)
from utils.styles import AppStyles, AppColors, PageConstants
from utils.async_task import AsyncTask
from utils.ticker_search import TickerSearchField


class StoricoAssetSubTab(ft.Container):
    """Sotto-tab per visualizzazione grafico storico asset."""
    
    def __init__(self, controller):
        super().__init__(padding=10, expand=True)
        self.controller = controller
        self.controller.page = controller.page
        
        # Stato
        self.tutti_asset = []  # Lista di ticker disponibili
        self.tickers_selezionati = set()  # Ticker selezionati per il grafico
        self.periodo = "5y"  # Default 5 anni
        self.aggiornamento_in_corso = False
        
        # Cache in memoria per evitare query ripetute al DB
        self._cache_storico = {}  # {ticker: [{data, prezzo_chiusura}, ...]}
        
        # Ticker preferiti (non nel portafoglio) - con descrizione {ticker: nome}
        self.tickers_preferiti = {}  # {ticker: descrizione}
        # NON caricare qui - la page potrebbe non essere pronta
        
        # UI Components
        self.checkbox_container = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, spacing=5)
        self.grafico_container = ft.Container(
            content=ft.Column([
                ft.ProgressRing(),
                ft.Text("Seleziona asset e premi 'Genera Grafico'", color=AppColors.TEXT_SECONDARY)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment(0, 0),
            expand=True
        )
        self.periodo_dropdown = ft.Dropdown(
            label="Periodo",
            value="5y",
            options=[
                ft.dropdown.Option("1m", "1 Mese"),
                ft.dropdown.Option("6m", "6 Mesi"),
                ft.dropdown.Option("1y", "1 Anno"),
                ft.dropdown.Option("2y", "2 Anni"),
                ft.dropdown.Option("5y", "5 Anni"),
                ft.dropdown.Option("10y", "10 Anni"),
                ft.dropdown.Option("20y", "20 Anni"),
                ft.dropdown.Option("25y", "25 Anni (Max)"),
            ],
            width=150
        )
        self.periodo_dropdown.on_change = self._on_periodo_change
        self.btn_genera = ft.ElevatedButton(
            "Genera Grafico",
            icon=ft.Icons.SHOW_CHART,
            on_click=self._genera_grafico_click,
            disabled=True
        )
        self.btn_aggiorna = ft.ElevatedButton(
            "Aggiorna Dati",
            icon=ft.Icons.REFRESH,
            on_click=self._aggiorna_dati_click
        )
        
        # Campo ricerca ticker con autocomplete
        self.ticker_search = TickerSearchField(
            on_select=self._on_ticker_selezionato,
            controller=self.controller,  # Riferimento stabile per update
            label="Cerca ticker",
            hint_text="es. Apple, MSFT...",
            width=200,
            show_borsa=True
        )
        
        # Label ultimo aggiornamento
        self.txt_ultimo_aggiornamento = ft.Text(
            "",
            size=11,
            color=AppColors.TEXT_SECONDARY,
            italic=True
        )
        
        self._build_ui()
    
    def _build_ui(self):
        """Costruisce l'interfaccia utente."""
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        
        self.content = ft.Column([
            # Toolbar
            ft.Row([
                AppStyles.subheader_text("Andamento Storico"),
                ft.Row([
                    self.periodo_dropdown,
                    self.btn_genera,
                    self.btn_aggiorna,
                ], spacing=10)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Divider(color=ft.Colors.OUTLINE_VARIANT),
            
            # Main content: checkbox sinistra + grafico destra
            ft.ResponsiveRow([
                # Sidebar con checkbox asset e ricerca preferiti
                ft.Column([
                    AppStyles.card_container(
                        content=ft.Column([
                            AppStyles.caption_text("Asset Portafoglio"),
                            ft.Divider(height=1),
                            self.checkbox_container,
                            ft.Container(height=15),
                            AppStyles.caption_text("Aggiungi Preferito"),
                            ft.Divider(height=1),
                            self.ticker_search,
                        ], spacing=5),
                        padding=10,
                        # width=250  <-- Removed fixed width
                    )
                ], col={"xs": 12, "md": 3}), # 3/12 width on desktop, full on mobile
                
                # Grafico principale con info aggiornamento
                ft.Column([
                    ft.Container(
                        content=self.grafico_container,
                        # expand=True, <-- Removed expand, controlled by Column
                        height=500, # Give it a height so Image fit works well
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=8,
                        padding=10
                    ),
                    self.txt_ultimo_aggiornamento,
                ], col={"xs": 12, "md": 9}, spacing=5) # 9/12 width on desktop
            ])
        ], expand=True, scroll=ft.ScrollMode.AUTO) # Added scroll to main column if needed
    
    def update_view_data(self, is_initial_load=False):
        """Carica la lista degli asset disponibili."""
        utente_id = self.controller.get_user_id()
        if not utente_id:
            return
        
        master_key_b64 = self.controller.page.session.get("master_key")
        
        task = AsyncTask(
            target=self._fetch_asset_list,
            args=(utente_id, master_key_b64),
            callback=self._on_asset_list_loaded,
            error_callback=self._on_error
        )
        task.start()
    
    def _fetch_asset_list(self, utente_id, master_key_b64):
        """Recupera lista asset in background."""
        conti_utente = ottieni_dettagli_conti_utente(utente_id, master_key_b64=master_key_b64)
        conti_investimento = [c for c in conti_utente if c['tipo'] == 'Investimento']
        
        tutti_asset = []
        tickers_visti = set()
        
        for conto in conti_investimento:
            portafoglio = ottieni_portafoglio(conto['id_conto'], master_key_b64=master_key_b64)
            for asset in portafoglio:
                ticker = asset['ticker'].upper()
                if ticker not in tickers_visti:
                    tickers_visti.add(ticker)
                    tutti_asset.append({
                        'ticker': ticker,
                        'nome': asset['nome_asset']
                    })
        
        return tutti_asset
    
    def _on_asset_list_loaded(self, result):
        """Callback: popola checkbox con asset disponibili e genera grafico automaticamente."""
        self.tutti_asset = result
        self.checkbox_container.controls.clear()
        self.tickers_selezionati.clear()
        
        # Ricarica preferiti salvati (potrebbero essere cambiati)
        self._carica_preferiti_salvati()
        
        if not self.tutti_asset and not self.tickers_preferiti:
            self.checkbox_container.controls.append(
                AppStyles.body_text("Nessun asset nel portafoglio", color=AppColors.TEXT_SECONDARY)
            )
        else:
            # Seleziona TUTTI gli asset del portafoglio con descrizione su 2 righe
            for asset in self.tutti_asset:
                ticker = asset['ticker']
                nome = asset.get('nome', '')
                self.tickers_selezionati.add(ticker)  # Seleziona automaticamente
                
                # Crea checkbox con descrizione su riga separata
                checkbox_row = self._crea_checkbox_asset(ticker, nome, is_preferito=False)
                self.checkbox_container.controls.append(checkbox_row)
            
            # Aggiungi anche i preferiti salvati
            for ticker, descrizione in self.tickers_preferiti.items():
                self.tickers_selezionati.add(ticker)  # Seleziona automaticamente
                checkbox_row = self._crea_checkbox_asset(ticker, descrizione, is_preferito=True)
                self.checkbox_container.controls.append(checkbox_row)
        
        self._update_btn_state()
        if self.page:
            self.page.update()
        
        # Se ci sono asset (portafoglio o preferiti), aggiorna dati e genera grafico automaticamente
        if (self.tutti_asset or self.tickers_preferiti) and not self.aggiornamento_in_corso:
            self._aggiorna_e_genera_automatico()
    
    def _crea_checkbox_asset(self, ticker: str, descrizione: str, is_preferito: bool = False):
        """Crea un controllo checkbox con ticker e tooltip per descrizione completa."""
        # Prefisso per preferiti
        prefisso = "⭐ " if is_preferito else "✓ "
        
        # Checkbox principale
        cb = ft.Checkbox(
            value=True,
            data=ticker,
            on_change=self._on_checkbox_change
        )
        
        # Testo ticker (bold)
        txt_ticker = ft.Text(f"{prefisso}{ticker}", weight=ft.FontWeight.BOLD, size=13)
        
        # Pulsante elimina per preferiti
        btn_elimina = None
        if is_preferito:
            btn_elimina = ft.IconButton(
                icon=ft.Icons.CLOSE,
                icon_size=14,
                icon_color=AppColors.ERROR,
                tooltip="Rimuovi preferito",
                data=ticker,
                on_click=self._elimina_preferito
            )
        
        # Contenuto con tooltip per descrizione completa
        if descrizione and descrizione != ticker:
            # Descrizione troncata visibile
            desc_troncata = descrizione[:25] + "..." if len(descrizione) > 25 else descrizione
            txt_desc = ft.Text(desc_troncata, size=10, color=AppColors.TEXT_SECONDARY, italic=True)
            content = ft.Column([txt_ticker, txt_desc], spacing=0)
            
            if btn_elimina:
                row = ft.Row([cb, content, btn_elimina], spacing=5, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            else:
                row = ft.Row([cb, content], spacing=5)
            row.tooltip = descrizione
            return row
        else:
            if btn_elimina:
                return ft.Row([cb, txt_ticker, btn_elimina], spacing=5, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            return ft.Row([cb, txt_ticker], spacing=5)
    
    def _elimina_preferito(self, e):
        """Elimina un ticker dai preferiti."""
        ticker = e.control.data
        
        if ticker in self.tickers_preferiti:
            del self.tickers_preferiti[ticker]
            self._salva_preferiti()
        
        # Rimuovi dalla selezione
        self.tickers_selezionati.discard(ticker)
        
        # Ricostruisci la lista checkbox
        self._ricostruisci_lista_asset()
        
        self.controller.show_snack_bar(f"✓ {ticker} rimosso dai preferiti", success=True)
    
    def _ricostruisci_lista_asset(self):
        """Ricostruisce la lista degli asset/preferiti nella UI."""
        self.checkbox_container.controls.clear()
        
        # Aggiungi asset del portafoglio
        for asset in self.tutti_asset:
            ticker = asset['ticker']
            nome = asset.get('nome', '')
            if ticker in self.tickers_selezionati:
                pass  # Mantieni selezione esistente
            checkbox_row = self._crea_checkbox_asset(ticker, nome, is_preferito=False)
            self.checkbox_container.controls.append(checkbox_row)
        
        # Aggiungi preferiti
        for ticker, descrizione in self.tickers_preferiti.items():
            checkbox_row = self._crea_checkbox_asset(ticker, descrizione, is_preferito=True)
            self.checkbox_container.controls.append(checkbox_row)
        
        self._update_btn_state()
        if self.page:
            self.page.update()
    
    def _on_checkbox_change(self, e):
        """Gestisce selezione/deselezione asset."""
        ticker = e.control.data
        if e.control.value:
            self.tickers_selezionati.add(ticker)
        else:
            self.tickers_selezionati.discard(ticker)
        
        self._update_btn_state()
        if self.page:
            self.page.update()
    
    def _update_btn_state(self):
        """Abilita/disabilita pulsante genera in base alla selezione."""
        self.btn_genera.disabled = len(self.tickers_selezionati) == 0
    
    def _on_periodo_change(self, e):
        """Gestisce cambio periodo."""
        self.periodo = e.control.value
    
    def _on_ticker_selezionato(self, risultato: dict):
        """Callback quando un ticker viene selezionato dall'autocomplete."""
        ticker = risultato['ticker']
        nome = risultato['nome']
        borsa = risultato.get('borsa', '')
        
        # Controlla se già presente
        tickers_esistenti = [a['ticker'] for a in self.tutti_asset]
        if ticker in tickers_esistenti or ticker in self.tickers_preferiti:
            self.controller.show_snack_bar(f"{ticker} già presente", success=False)
            self.ticker_search.reset()
            return
        
        # Descrizione include borsa se disponibile
        descrizione = f"{nome} ({borsa})" if borsa else nome
        
        # Aggiungi ai preferiti con descrizione
        self.tickers_preferiti[ticker] = descrizione
        self._salva_preferiti()
        
        # Aggiungi checkbox con descrizione
        checkbox_row = self._crea_checkbox_asset(ticker, descrizione, is_preferito=True)
        self.checkbox_container.controls.append(checkbox_row)
        
        # Seleziona automaticamente
        self.tickers_selezionati.add(ticker)
        
        # Pulisci campo
        self.ticker_search.reset()
        
        self._update_btn_state()
        self.controller.show_snack_bar(f"✓ {ticker} aggiunto", success=True)
        
        if self.page:
            self.page.update()
    
    def _carica_preferiti_salvati(self):
        """Carica i ticker preferiti salvati da client_storage (per utente)."""
        try:
            if self.controller and self.controller.page:
                utente_id = self.controller.get_user_id()
                storage_key = f"storico_asset.preferiti.{utente_id}" if utente_id else "storico_asset.preferiti"
                salvati = self.controller.page.client_storage.get(storage_key)
                print(f"[DEBUG] Preferiti caricati per user {utente_id}: {salvati}")
                if salvati and isinstance(salvati, dict):
                    self.tickers_preferiti = salvati
                elif salvati and isinstance(salvati, str):
                    # Potrebbe essere serializzato come JSON string
                    import json
                    self.tickers_preferiti = json.loads(salvati)
        except Exception as e:
            print(f"[ERRORE] Caricamento preferiti: {e}")
    
    def _salva_preferiti(self):
        """Salva i ticker preferiti in client_storage (per utente)."""
        try:
            if self.controller and self.controller.page:
                utente_id = self.controller.get_user_id()
                storage_key = f"storico_asset.preferiti.{utente_id}" if utente_id else "storico_asset.preferiti"
                print(f"[DEBUG] Salvataggio preferiti per user {utente_id}: {self.tickers_preferiti}")
                self.controller.page.client_storage.set(storage_key, dict(self.tickers_preferiti))
        except Exception as e:
            print(f"[ERRORE] Salvataggio preferiti: {e}")
    
    def _aggiorna_label_ultimo_aggiornamento(self, tickers):
        """Aggiorna la label con la data dell'ultimo aggiornamento."""
        from db.gestione_db import ultimo_aggiornamento_storico
        
        date_aggiornamento = []
        for ticker in tickers:
            ultima = ultimo_aggiornamento_storico(ticker)
            if ultima:
                date_aggiornamento.append(f"{ticker}: {ultima}")
        
        if date_aggiornamento:
            self.txt_ultimo_aggiornamento.value = f"Ultimo dato: {', '.join(date_aggiornamento)}"
        else:
            self.txt_ultimo_aggiornamento.value = "Nessun dato storico disponibile"
    
    def _aggiorna_e_genera_automatico(self):
        """Aggiorna i dati storici e genera il grafico automaticamente all'apertura."""
        self.aggiornamento_in_corso = True
        self.btn_aggiorna.disabled = True
        
        # Mostra loading nel grafico
        self.grafico_container.content = ft.Column([
            ft.ProgressRing(),
            ft.Text("Caricamento dati storici (potrebbe richiedere qualche secondo)...", color=AppColors.TEXT_SECONDARY),
            ft.Text("Sto scaricando 25 anni di storico per analisi avanzate.", size=12, color=AppColors.TEXT_SECONDARY, italic=True)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        if self.page:
            self.page.update()
        
        # Aggiorna dati in background, poi genera grafico
        task = AsyncTask(
            target=self._aggiorna_dati_task,
            args=(list(self.tickers_selezionati),),
            callback=self._on_aggiornamento_automatico_completato,
            error_callback=self._on_aggiornamento_errore
        )
        task.start()
    
    def _on_aggiornamento_automatico_completato(self, result):
        """Dopo aggiornamento automatico, genera il grafico."""
        self.aggiornamento_in_corso = False
        self.btn_aggiorna.disabled = False
        
        # Genera grafico automaticamente (i dati sono ora in cache)
        self._genera_grafico_click(None)
    
    def _on_error(self, e):
        """Gestisce errori."""
        print(f"Errore in StoricoAssetSubTab: {e}")
        self.controller.show_snack_bar(f"Errore: {e}", success=False)
    
    def _genera_grafico_click(self, e):
        """Avvia generazione grafico."""
        if not self.tickers_selezionati:
            return
        
        self.grafico_container.content = ft.Column([
            ft.ProgressRing(),
            ft.Text("Generazione grafico in corso...", color=AppColors.TEXT_SECONDARY)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        if self.page:
            self.page.update()
        
        # Calcola data inizio in base al periodo
        oggi = datetime.now()
        if self.periodo == "1m":
            data_inizio = (oggi - timedelta(days=30)).strftime('%Y-%m-%d')
        elif self.periodo == "6m":
            data_inizio = (oggi - timedelta(days=180)).strftime('%Y-%m-%d')
        elif self.periodo == "1y":
            data_inizio = (oggi - timedelta(days=365)).strftime('%Y-%m-%d')
        elif self.periodo == "2y":
            data_inizio = (oggi - timedelta(days=730)).strftime('%Y-%m-%d')
        elif self.periodo == "5y":
            data_inizio = (oggi - timedelta(days=1825)).strftime('%Y-%m-%d')
        elif self.periodo == "10y":
             data_inizio = (oggi - timedelta(days=3650)).strftime('%Y-%m-%d')
        elif self.periodo == "20y":
             data_inizio = (oggi - timedelta(days=7300)).strftime('%Y-%m-%d')
        else:  # 25y or fallback
            data_inizio = (oggi - timedelta(days=9125)).strftime('%Y-%m-%d')
        
        task = AsyncTask(
            target=self._genera_grafico_task,
            args=(list(self.tickers_selezionati), data_inizio),
            callback=self._on_grafico_generato,
            error_callback=self._on_error
        )
        task.start()
    
    def _genera_grafico_task(self, tickers, data_inizio):
        """Genera il grafico in background."""
        import matplotlib
        matplotlib.use('Agg')  # Backend non-interattivo
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime as dt
        
        # Recupera dati storici per ogni ticker (usa cache se disponibile)
        dati_per_ticker = {}
        for ticker in tickers:
            # Controlla se i dati sono in cache
            if ticker in self._cache_storico:
                storico_completo = self._cache_storico[ticker]
            else:
                # Carica dal DB e metti in cache
                storico_completo = ottieni_storico_asset_globale(ticker)
                self._cache_storico[ticker] = storico_completo
            
            # Filtra per data_inizio
            storico = [d for d in storico_completo if d['data'] >= data_inizio]
            if storico:
                dati_per_ticker[ticker] = storico
        
        if not dati_per_ticker:
            return None
        
        # Crea figura con SFONDO CHIARO
        fig, ax = plt.subplots(figsize=(10, 6), facecolor='#ffffff')
        ax.set_facecolor('#f8f9fa')
        
        # Colori per le linee (più vivaci per sfondo chiaro)
        colori = ['#2563eb', '#16a34a', '#ea580c', '#dc2626', '#7c3aed', '#0891b2']
        
        for i, (ticker, dati) in enumerate(dati_per_ticker.items()):
            date = [dt.strptime(d['data'], '%Y-%m-%d') for d in dati]
            prezzi = [d['prezzo_chiusura'] for d in dati]
            
            colore = colori[i % len(colori)]
            ax.plot(date, prezzi, label=ticker, color=colore, linewidth=1.8)
        
        # Formattazione per sfondo chiaro
        ax.set_xlabel('Data', color='#374151')
        ax.set_ylabel('Prezzo (€)', color='#374151')
        ax.tick_params(colors='#374151')
        ax.legend(facecolor='#ffffff', edgecolor='#d1d5db', labelcolor='#374151')
        ax.grid(True, alpha=0.4, color='#d1d5db')
        
        # Formatta asse X
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate()
        
        # Bordi spine
        for spine in ax.spines.values():
            spine.set_color('#d1d5db')
        
        # Salva in buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#ffffff')
        buf.seek(0)
        plt.close(fig)
        
        # Converti in base64
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return img_base64
    
    def _on_grafico_generato(self, result):
        """Callback: mostra il grafico generato."""
        if result:
            self.grafico_container.content = ft.Image(
                src_base64=result,
                fit=ft.ImageFit.CONTAIN,
                expand=True
            )
            # Aggiorna label ultimo aggiornamento
            self._aggiorna_label_ultimo_aggiornamento(list(self.tickers_selezionati))
        else:
            self.grafico_container.content = ft.Column([
                ft.Icon(ft.Icons.WARNING_AMBER, color=AppColors.WARNING, size=48),
                ft.Text("Nessun dato storico disponibile.", color=AppColors.TEXT_SECONDARY),
                ft.Text("Premi 'Aggiorna Dati' per scaricare lo storico.", color=AppColors.TEXT_SECONDARY)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            self.txt_ultimo_aggiornamento.value = ""
        
        if self.page:
            self.page.update()
    
    def _aggiorna_dati_click(self, e):
        """Aggiorna i dati storici da yfinance."""
        if self.aggiornamento_in_corso:
            return
        
        if not self.tickers_selezionati:
            self.controller.show_snack_bar("Seleziona almeno un asset", success=False)
            return
        
        self.aggiornamento_in_corso = True
        self.btn_aggiorna.disabled = True
        
        # Mostra loading esplicito nel container del grafico
        self.grafico_container.content = ft.Column([
            ft.ProgressRing(),
            ft.Text("Aggiornamento dati in corso...", color=AppColors.TEXT_SECONDARY, weight=ft.FontWeight.BOLD),
            ft.Text("Download dello storico completo (fino a 25 anni). Attendere...", size=12, color=AppColors.TEXT_SECONDARY)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        if self.page:
            self.page.update()
        
        task = AsyncTask(
            target=self._aggiorna_dati_task,
            args=(list(self.tickers_selezionati),),
            callback=self._on_aggiornamento_completato,
            error_callback=self._on_aggiornamento_errore
        )
        task.start()
    
    def _aggiorna_dati_task(self, tickers):
        """Aggiorna dati in background."""
        aggiornati = 0
        for ticker in tickers:
            if aggiorna_storico_asset_se_necessario(ticker, anni=25):
                aggiornati += 1
                # Invalida la cache per questo ticker
                if ticker in self._cache_storico:
                    del self._cache_storico[ticker]
        return aggiornati
    
    def _on_aggiornamento_completato(self, result):
        """Callback: aggiornamento completato."""
        self.aggiornamento_in_corso = False
        self.btn_aggiorna.disabled = False
        
        if result > 0:
            self.controller.show_snack_bar(f"Aggiornati {result} asset", success=True)
            # Rigenera il grafico automaticamente
            self._genera_grafico_click(None)
        else:
            self.controller.show_snack_bar("Dati già aggiornati", success=True)
        
        if self.page:
            self.page.update()
    
    def _on_aggiornamento_errore(self, e):
        """Callback: errore aggiornamento."""
        self.aggiornamento_in_corso = False
        self.btn_aggiorna.disabled = False
        self.controller.show_snack_bar(f"Errore aggiornamento: {e}", success=False)
        
        if self.page:
            self.page.update()
