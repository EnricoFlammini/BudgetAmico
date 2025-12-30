import flet as ft
from typing import List, Dict
import asyncio
from utils.async_task import AsyncTask
from utils.monte_carlo import run_monte_carlo_simulation
from utils.styles import AppStyles, AppColors
from db.gestione_db import ottieni_dettagli_conti_utente, ottieni_portafoglio
from utils.ticker_search import TickerSearchField # Imported for favorites search

class MonteCarloSubTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=10, expand=True)
        self.controller = controller
        self.controller.page = controller.page
        
        # Stato
        self.portfolio_assets = [] # Original data from DB: {ticker, nome, quantita, prezzo, is_favorite}
        self.favorites = {} # Dict {ticker: description}
        
        self.ui_asset_controls = {} # ticker -> {check: Checkbox, val: TextField, row: Row}
        self.pac_rows = [] # List of {ticker_dd, amount_tf, freq_dd, row_control}
        
        self.years = 10
        self.n_simulations = 1000
        self.is_simulating = False
        
        # --- UI Components ---
        
        # 1. Configurazione Parametri
        self.slider_ani = ft.Slider(
            min=1, max=30, value=10, divisions=29, 
            label="{value} Anni", 
            on_change=self._on_params_change
        )
        self.txt_anni = ft.Text("10 Anni", weight=ft.FontWeight.BOLD)
        
        self.slider_sim = ft.Slider(
            min=100, max=5000, value=1000, divisions=49, 
            label="{value} Sim.", 
            on_change=self._on_params_change
        )
        self.txt_sim = ft.Text("1000 Simulazioni", weight=ft.FontWeight.BOLD)
        
        # 2. Lista Asset & Ricerca
        self.asset_list_col = ft.Column(scroll=ft.ScrollMode.AUTO, height=200, spacing=5)
        self.txt_valore_simulato = ft.Text("Valore Iniziale: € 0,00", size=14, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY)

        # Search Field per aggiungere Asset
        self.ticker_search = TickerSearchField(
            on_select=self._on_ticker_found,
            controller=self.controller,
            label="Aggiungi Asset / Preferito",
            hint_text="Cerca es. AAPL, VWCE",
            width=250,
            show_borsa=True
        )
        
        # 3. Sezione PAC
        self.pac_list_col = ft.Column(spacing=5)
        self.btn_add_pac = ft.TextButton("Aggiungi PAC", icon=ft.Icons.ADD, on_click=self._add_pac_row)
        
        # Action Button
        self.btn_avvia = ft.ElevatedButton(
            "Avvia Simulazione",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._avvia_simulazione,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=AppColors.PRIMARY,
            ),
            width=200
        )
        
        # 4. Chart & Results
        self.chart_container = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.INSIGHTS, size=48, color=ft.Colors.GREY_400),
                ft.Text("Premi 'Avvia Simulazione' per vedere la proiezione", color=ft.Colors.GREY_500)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
            expand=True,
            bgcolor=ft.Colors.WHITE,
            border_radius=10,
            padding=10,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            alignment=ft.Alignment(0, 0)
        )
        
        self.card_pessimistic = self._build_result_card("Pessimistico (10%)", AppColors.ERROR, ft.Icons.TRENDING_DOWN)
        self.card_expected = self._build_result_card("Atteso (50%)", AppColors.PRIMARY, ft.Icons.TRENDING_FLAT)
        self.card_optimistic = self._build_result_card("Ottimistico (90%)", AppColors.SUCCESS, ft.Icons.TRENDING_UP)
        
        self.txt_info_storico = ft.Text("", size=11, color=ft.Colors.GREY_500, italic=True)
        
        self._build_ui()
        
    def _build_result_card(self, title, color, icon):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, color=color, size=20),
                    ft.Text(title, color=ft.Colors.GREY_700, size=12, weight=ft.FontWeight.BOLD)
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(height=5, color="transparent"),
                ft.Text("-", size=20, weight=ft.FontWeight.BOLD, color=color, text_align=ft.TextAlign.CENTER),
                ft.Text("-", size=10, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=15,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, color),
            border_radius=8,
            expand=True
        )

    def _build_ui(self):
        # Left Config Panel
        config_content = ft.Column([
            # Sezione Parametri
            ft.Text("Parametri Simulazione", weight=ft.FontWeight.BOLD, size=16),
            ft.Divider(height=10),
            ft.Text("Orizzonte Temporale", size=12, color=ft.Colors.GREY_600),
            ft.Row([self.slider_ani, self.txt_anni], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text("Numero Simulazioni", size=12, color=ft.Colors.GREY_600),
            ft.Row([self.slider_sim, self.txt_sim], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Divider(height=20),
            
            # Sezione Asset
            ft.Text("Asset Portafoglio", weight=ft.FontWeight.BOLD, size=16),
            ft.Text("Lista portafoglio + Preferiti. Imposta valore a 0 se non posseduto.", size=11, color=ft.Colors.GREY_500),
            
            # Search Bar Integration
            ft.Container(self.ticker_search, padding=ft.padding.only(bottom=10)),
            
            self.asset_list_col,
            self.txt_valore_simulato,
            
            ft.Divider(height=20),
            
            # Sezione PAC
            ft.Row([
                ft.Text("Piani di Accumulo (PAC)", weight=ft.FontWeight.BOLD, size=16),
                self.btn_add_pac
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.pac_list_col,
            
            ft.Container(height=20),
            ft.Row([self.btn_avvia], alignment=ft.MainAxisAlignment.CENTER)
            
        ], spacing=5, scroll=ft.ScrollMode.HIDDEN) 
        
        config_container = AppStyles.card_container(
            content=config_content,
            padding=20,
            width=380 
        )
        
        # Right Results Panel
        results_row = ft.Row([
            self.card_pessimistic,
            self.card_expected,
            self.card_optimistic
        ], spacing=10)
        
        right_col = ft.Column([
            self.chart_container,
            results_row,
            ft.Container(content=self.txt_info_storico, alignment=ft.Alignment(1, 0))
        ], expand=True, spacing=10)
        
        self.content = ft.Row([
            ft.Column([config_container], scroll=ft.ScrollMode.AUTO, height=800), 
            right_col
        ], expand=True, spacing=20)

    def update_view_data(self):
        """Carica dati portafoglio e inizializza lista asset."""
        utente_id = self.controller.get_user_id()
        print(f"[DEBUG] MonteCarloSubTab.update_view_data - User ID: {utente_id}")
        
        if not utente_id: return
        
        # Reset State Data explicitly
        self.portfolio_assets = []
        self.favorites = {}
        
        self.asset_list_col.controls.clear()
        self.asset_list_col.controls.append(ft.ProgressRing())
        
        # Reset State
        self.pac_rows = []
        self.pac_list_col.controls.clear()
        
        # Reset Chart & Results to default
        self.chart_container.content = ft.Column([
            ft.Icon(ft.Icons.INSIGHTS, size=48, color=ft.Colors.GREY_400),
            ft.Text("Premi 'Avvia Simulazione' per vedere la proiezione", color=ft.Colors.GREY_500)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER)
        
        self.card_pessimistic.content.controls[2].value = "-"
        self.card_expected.content.controls[2].value = "-"
        self.card_expected.content.controls[3].value = "-"
        self.card_optimistic.content.controls[2].value = "-"
        self.txt_info_storico.value = ""
        self.txt_valore_simulato.value = "Valore Iniziale: € 0,00"
        
        if self.controller.page: self.controller.page.update()
        
        # Load Favorites from Client Storage
        self._load_favorites()
        
        master_key_b64 = self.controller.page.session.get("master_key")
        
        def fetch_data():
             conti_utente = ottieni_dettagli_conti_utente(utente_id, master_key_b64=master_key_b64)
             conti_investimento = [c for c in conti_utente if c['tipo'] == 'Investimento']
             assets = []
             for conto in conti_investimento:
                 portafoglio = ottieni_portafoglio(conto['id_conto'], master_key_b64=master_key_b64)
                 for item in portafoglio:
                     found = next((a for a in assets if a['ticker'] == item['ticker']), None)
                     if found:
                         found['quantita'] += item['quantita']
                         # Average price? Keep last one for now or weighted avg
                     else:
                         assets.append({
                             'ticker': item['ticker'],
                             'nome': item.get('nome_asset', item['ticker']),
                             'quantita': item['quantita'],
                             'prezzo_attuale': item['prezzo_attuale_manuale'],
                             'is_favorite': False # Owned assets are not "favorites" in this context
                         })
             return assets

        task = AsyncTask(
            target=fetch_data,
            args=(),
            callback=self._on_data_loaded,
            error_callback=lambda e: print(f"Errore caricamento dati MC: {e}")
        )
        task.start()

    def _load_favorites(self):
        """Carica i preferiti dal local storage (condiviso con storico asset)."""
        try:
            if self.controller.page:
                utente_id = self.controller.get_user_id()
                # Chiave unificata con StoricoAssetSubTab
                key = f"storico_asset.preferiti.{utente_id}" if utente_id else "storico_asset.preferiti"
                
                print(f"[DEBUG] MonteCarlo loading favorites from key: {key}")
                saved = self.page.client_storage.get(key)
                print(f"[DEBUG] Raw saved data: {saved}")
                
                # Reset favorites before loading
                self.favorites = {}
                if saved:
                    if isinstance(saved, dict):
                         self.favorites = saved
                    elif isinstance(saved, list):
                        # Migrazione da lista a dict
                        for t in saved:
                            self.favorites[t] = t 
                    elif isinstance(saved, str):
                        try:
                            import json
                            self.favorites = json.loads(saved)
                        except:
                            print(f"[ERROR] Failed to parse favorites json: {saved}")
                            
                print(f"[DEBUG] Parsed favorites: {self.favorites}")
                        
        except Exception as e:
            print(f"Errore loading favorites: {e}")
            self.favorites = {}

    def _save_favorites(self):
        """Salva i preferiti (condiviso con storico asset)."""
        try:
             if self.page:
                utente_id = self.controller.get_user_id()
                key = f"storico_asset.preferiti.{utente_id}" if utente_id else "storico_asset.preferiti"
                self.page.client_storage.set(key, self.favorites)
        except Exception as e:
            print(f"Errore saving favorites: {e}")

    def _on_data_loaded(self, result):
        # Merge portfolio assets with favorites
        self.portfolio_assets = result
        
        # Add Favorites (only if not already in portfolio)
        existing_tickers = {a['ticker'] for a in self.portfolio_assets}
        for fav_ticker, fav_desc in self.favorites.items():
            if fav_ticker not in existing_tickers:
                self.portfolio_assets.append({
                    'ticker': fav_ticker,
                    'nome': fav_desc,
                    'quantita': 0.0,
                    'prezzo_attuale': 0.0,
                    'is_favorite': True
                })

        self._rebuild_asset_list()

    def _rebuild_asset_list(self):
        """Ricostruisce la lista asset nella UI."""
        self.asset_list_col.controls.clear()
        self.ui_asset_controls = {}
        
        if not self.portfolio_assets:
            self.asset_list_col.controls.append(ft.Text("Nessun asset. Inizia aggiungendone uno."))
        else:
            # Header
            self.asset_list_col.controls.append(
                ft.Row([
                    ft.Text("", width=30), 
                    ft.Text("Asset", expand=True, weight=ft.FontWeight.BOLD),
                    ft.Text("Valore Sim.", width=90, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT)
                ])
            )
            
            for asset in self.portfolio_assets:
                ticker = asset['ticker']
                nome = asset.get('nome', '')
                curr_val = asset['quantita'] * asset['prezzo_attuale']
                is_fav = asset.get('is_favorite', False)
                
                chk = ft.Checkbox(value=True, on_change=self._recalc_simulated_total)
                tf_val = ft.TextField(
                    value=f"{curr_val:.2f}", 
                    width=90, 
                    height=30, 
                    text_size=12,
                    content_padding=5,
                    text_align=ft.TextAlign.RIGHT,
                    on_change=self._recalc_simulated_total
                )
                
                # Ticker + Description Column
                if not nome or nome == ticker:
                    txt_col = ft.Text(ticker, weight=ft.FontWeight.BOLD, size=13)
                else:
                    txt_col = ft.Column([
                        ft.Text(ticker, weight=ft.FontWeight.BOLD, size=13),
                        ft.Text(nome[:25] + "..." if len(nome) > 25 else nome, size=10, color=ft.Colors.GREY_600, italic=True)
                    ], spacing=0)

                # Rows components
                comps = [
                    chk, 
                    ft.Container(content=txt_col, expand=True), 
                    tf_val
                ]
                
                # Delete button for favorites
                if is_fav:
                   btn_del = ft.IconButton(
                       icon=ft.Icons.DELETE_OUTLINE, 
                       icon_size=16, 
                       icon_color=ft.Colors.GREY_400,
                       on_click=lambda e, t=ticker: self._remove_favorite(t),
                       tooltip="Rimuovi dai preferiti"
                   )
                   comps.append(btn_del)
                else:
                    comps.append(ft.Container(width=40)) # Spacer

                row = ft.Row(comps, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=5)
                
                self.ui_asset_controls[ticker] = {'check': chk, 'val': tf_val}
                self.asset_list_col.controls.append(row)

        self._recalc_simulated_total(None)
        if self.page: self.page.update()

    def _remove_favorite(self, ticker):
        """Rimuove un asset dai preferiti."""
        if ticker in self.favorites:
            del self.favorites[ticker] # Remove key from dict
            self._save_favorites()
            
            # Remove from portfolio_assets list logic
            self.portfolio_assets = [a for a in self.portfolio_assets if a['ticker'] != ticker]
            self._rebuild_asset_list()
            self.controller.show_snack_bar(f"Rimosso {ticker}", success=True)

    def _on_ticker_found(self, result):
        """Callback del TickerSearchField."""
        ticker = result['ticker']
        nome = result.get('nome', ticker)
        borsa = result.get('borsa', '')
        descrizione = f"{nome} ({borsa})" if borsa else nome
        
        # Check if exists
        exists = any(a['ticker'] == ticker for a in self.portfolio_assets)
        if exists:
            self.controller.show_snack_bar(f"Asset {ticker} già presente in lista.", success=False)
            self.ticker_search.reset()
            return

        # Add to favorites
        self.favorites[ticker] = descrizione
        self._save_favorites()
        
        # Add to local list and rebuild
        self.portfolio_assets.append({
            'ticker': ticker,
            'nome': descrizione,
            'quantita': 0.0,
            'prezzo_attuale': 0.0,
            'is_favorite': True
        })
        self._rebuild_asset_list()
        
        self.ticker_search.reset()
        self.controller.show_snack_bar(f"Aggiunto {ticker}", success=True)

    def _recalc_simulated_total(self, e):
        total = 0.0
        for ticker, ctrls in self.ui_asset_controls.items():
            if ctrls['check'].value:
                try:
                    val = float(ctrls['val'].value.replace(',', '.')) 
                    total += val
                except ValueError:
                    pass
        
        self.txt_valore_simulato.value = f"Valore Iniziale: {self.controller.loc.format_currency(total)}"
        if self.page: self.page.update()

    def _add_pac_row(self, e):
        # Ticker List for Dropdown (include all visible assets)
        options = [ft.dropdown.Option(a['ticker']) for a in self.portfolio_assets]
        
        dd_ticker = ft.Dropdown(
            options=options, 
            width=100, 
            hint_text="Ticker", 
            text_size=12,
            content_padding=5,
        )
        if options: dd_ticker.value = options[0].key

        tf_amount = ft.TextField(
            value="100", 
            width=80, 
            height=30, 
            text_size=12, 
            content_padding=5,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        dd_freq = ft.Dropdown(
            options=[
                ft.dropdown.Option("Mensile"),
                ft.dropdown.Option("Trimestrale"),
                ft.dropdown.Option("Annuale"),
            ],
            width=110,
            value="Mensile",
            text_size=11,
            content_padding=5
        )
        
        def remove_row(e):
            self.pac_list_col.controls.remove(row_container)
            if row_data in self.pac_rows:
                self.pac_rows.remove(row_data)
            self.page.update()
            
        btn_rem = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE, 
            icon_color=ft.Colors.GREY_500, 
            icon_size=18,
            on_click=remove_row,
            width=30
        )
        
        row_content = ft.Row([dd_ticker, tf_amount, dd_freq, btn_rem], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=5)
        row_container = ft.Container(content=row_content, bgcolor=ft.Colors.GREY_50, padding=2, border_radius=5)
        
        row_data = {'ticker_dd': dd_ticker, 'amount_tf': tf_amount, 'freq_dd': dd_freq, 'container': row_container}
        self.pac_rows.append(row_data)
        
        self.pac_list_col.controls.append(row_container)
        self.page.update()

    def _on_params_change(self, e):
        self.years = int(self.slider_ani.value)
        self.n_simulations = int(self.slider_sim.value)
        self.txt_anni.value = f"{self.years} Anni"
        self.txt_sim.value = f"{self.n_simulations} Sim."
        if self.page: self.page.update()

    def _avvia_simulazione(self, e):
        # 1. Raccogli Asset Attivi e Valori
        sim_assets = []
        for ticker, ctrls in self.ui_asset_controls.items():
            if ctrls['check'].value:
                try:
                    val = float(ctrls['val'].value.replace(',', '.'))
                    sim_assets.append({'ticker': ticker, 'valore_simulato': val})
                except ValueError:
                    pass
        
        # 2. Raccogli PAC
        sim_pacs = []
        for row in self.pac_rows:
            try:
                amt = float(row['amount_tf'].value.replace(',', '.'))
                t = row['ticker_dd'].value
                f = row['freq_dd'].value
                if t and amt > 0:
                    sim_pacs.append({'ticker': t, 'importo': amt, 'frequenza': f})
            except ValueError:
                pass
                
        if not sim_assets and not sim_pacs:
             self.controller.show_snack_bar("Nessun asset o PAC configurato.", success=False)
             return

        self.btn_avvia.disabled = True
        self.chart_container.content = ft.Column([
            ft.ProgressRing(),
            ft.Text("Esecuzione Simulazione Monte Carlo...", color=AppColors.TEXT_SECONDARY)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER)
        if self.page: self.page.update()
        
        task = AsyncTask(
            target=run_monte_carlo_simulation,
            args=(sim_assets, self.years, self.n_simulations, 0.0, sim_pacs),
            callback=self._on_simulazione_completata,
            error_callback=self._on_errore_simulazione
        )
        task.start()

    def _on_simulazione_completata(self, results):
        self.btn_avvia.disabled = False
        
        if "error" in results:
            self.controller.show_snack_bar(f"Errore: {results['error']}", success=False)
            self.chart_container.content = ft.Column([
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=AppColors.ERROR, size=48),
                ft.Text(results['error'], color=AppColors.ERROR)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER)
        else:
            finals = results['final_values']
            loc = self.controller.loc
            
            # Cards
            self.card_pessimistic.content.controls[2].value = loc.format_currency(finals['p10'])
            self.card_expected.content.controls[2].value = loc.format_currency(finals['p50'])
            roi = results.get('roi_percent', 0)
            self.card_expected.content.controls[3].value = f"ROI totale: {roi:+.1f}%"
            self.card_optimistic.content.controls[2].value = loc.format_currency(finals['p90'])
            
            # Info Storico
            years_hist = results.get('history_years', 0)
            self.txt_info_storico.value = f"Analisi basata su {years_hist} anni di dati storici del mercato."
            
            # Chart
            img_base64 = self._generrate_chart_image(results)
            self.chart_container.content = ft.Image(src_base64=img_base64, fit=ft.ImageFit.CONTAIN, expand=True)
            
        if self.page: self.page.update()

    def _on_errore_simulazione(self, e):
        self.btn_avvia.disabled = False
        self.controller.show_error_dialog(f"Errore simulazione: {e}")
        if self.page: self.page.update()

    def _generrate_chart_image(self, results):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import io
        import base64
        import numpy as np
        
        dates = results['dates']
        p10 = results['p10']
        p50 = results['p50']
        p90 = results['p90']
        asset_trends = results.get('asset_trends', {})
        
        x = np.arange(len(dates))
        
        fig, ax = plt.subplots(figsize=(10, 6), facecolor='white')
        
        # Area Cone
        ax.fill_between(x, p10, p90, color='#1976D2', alpha=0.15, label='Confidenza 10-90%')
        
        # Main Lines
        ax.plot(x, p50, color='#1976D2', linewidth=2.5, label='Totale (Mediana)')
        ax.plot(x, p90, color='#2E7D32', linestyle=':', linewidth=1, label='90° Percentile')
        ax.plot(x, p10, color='#C62828', linestyle=':', linewidth=1, label='10° Percentile')
        
        # Individual Asset Trends (Dashed Lines)
        # Use a colormap for distinct lines
        colors = plt.cm.tab10(np.linspace(0, 1, len(asset_trends)))
        
        for i, (ticker, trend_values) in enumerate(asset_trends.items()):
            # Safe check length
            if len(trend_values) == len(x):
                ax.plot(x, trend_values, color=colors[i], linestyle='--', alpha=0.7, linewidth=1.2, label=f"{ticker}")
        
        ax.set_title("Proiezione Portafoglio & Asset", fontsize=14, pad=15)
        ax.grid(True, linestyle=':', alpha=0.6)
        
        step = max(1, len(dates) // 8)
        ax.set_xticks(x[::step])
        ax.set_xticklabels([dates[i] for i in range(0, len(dates), step)], rotation=45)
        
        def currency_formatter(x, p): return f"€{x:,.0f}"
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(currency_formatter))
        
        # Legend outside or bottom if too many assets
        if len(asset_trends) > 5:
             ax.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize='small')
             plt.subplots_adjust(right=0.8) # Make space for legend
        else:
             ax.legend(loc='upper left', fontsize='small')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_str
