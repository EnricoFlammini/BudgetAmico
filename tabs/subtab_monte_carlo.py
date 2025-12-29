import flet as ft
from typing import List, Dict
import asyncio
from utils.async_task import AsyncTask
from utils.monte_carlo import run_monte_carlo_simulation
from utils.styles import AppStyles, AppColors
from db.gestione_db import ottieni_dettagli_conti_utente, ottieni_portafoglio

class MonteCarloSubTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=10, expand=True)
        self.controller = controller
        self.page = controller.page
        
        # Stato
        self.portfolio_assets = []
        self.total_value = 0.0
        self.years = 10
        self.n_simulations = 1000
        self.is_simulating = False
        
        # UI Components - Configuration
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
        
        self.txt_valore_iniziale = ft.Text("€ 0,00", size=16, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY)
        
        self.btn_avvia = ft.ElevatedButton(
            "Avvia Simulazione",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._avvia_simulazione,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=AppColors.PRIMARY,
            )
        )
        
        # UI Components - Chart using matplotlib (static image for stability)
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
            alignment=ft.alignment.center
        )
        
        # UI Components - Results Cards
        self.card_pessimistic = self._build_result_card("Pessimistico (10%)", AppColors.ERROR, ft.Icons.TRENDING_DOWN)
        self.card_expected = self._build_result_card("Atteso (50%)", AppColors.PRIMARY, ft.Icons.TRENDING_FLAT)
        self.card_optimistic = self._build_result_card("Ottimistico (90%)", AppColors.SUCCESS, ft.Icons.TRENDING_UP)
        
        self._build_ui()
        
    def _build_result_card(self, title, color, icon):
        """Helper per creare le card dei risultati."""
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, color=color, size=20),
                    ft.Text(title, color=ft.Colors.GREY_700, size=12, weight=ft.FontWeight.BOLD)
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(height=5, color="transparent"),
                ft.Text("-", size=20, weight=ft.FontWeight.BOLD, color=color, text_align=ft.TextAlign.CENTER),
                ft.Text("-", size=10, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER)  # Subtext for clarification
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=15,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, color),
            border_radius=8,
            expand=True
        )

    def _build_ui(self):
        """Costruisce il layout."""
        
        # Config Panel (Left)
        config_panel = AppStyles.card_container(
            content=ft.Column([
                AppStyles.subheader_text("Parametri"),
                ft.Divider(height=10),
                
                ft.Text("Orizzonte Temporale", size=12, color=ft.Colors.GREY_600),
                ft.Row([self.slider_ani, self.txt_anni], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Text("Numero Simulazioni", size=12, color=ft.Colors.GREY_600),
                ft.Row([self.slider_sim, self.txt_sim], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Divider(height=20),
                ft.Text("Valore Iniziale", size=12, color=ft.Colors.GREY_600),
                self.txt_valore_iniziale,
                
                ft.Container(height=10),
                self.btn_avvia
            ], spacing=5),
            padding=20,
            width=300
        )
        
        # Results Row
        results_row = ft.Row([
            self.card_pessimistic,
            self.card_expected,
            self.card_optimistic
        ], spacing=10)
        
        # Main Layout
        self.content = ft.Row([
            # Left Column: Config
            ft.Column([config_panel], alignment=ft.MainAxisAlignment.START),
            
            # Right Column: Chart + Results
            ft.Column([
                self.chart_container, 
                results_row
            ], expand=True, spacing=10)
        ], expand=True, spacing=20)

    def update_view_data(self):
        """Carica dati portafoglio all'apertura."""
        utente_id = self.controller.get_user_id()
        if not utente_id: return
        
        master_key_b64 = self.controller.page.session.get("master_key")
        
        def fetch_data():
             # Qui replichiamo logica simile a tab_investimenti per ottenere TUTTI gli asset aggregati
             conti_utente = ottieni_dettagli_conti_utente(utente_id, master_key_b64=master_key_b64)
             conti_investimento = [c for c in conti_utente if c['tipo'] == 'Investimento']
             
             assets = []
             for conto in conti_investimento:
                 portafoglio = ottieni_portafoglio(conto['id_conto'], master_key_b64=master_key_b64)
                 for item in portafoglio:
                     assets.append({
                         'ticker': item['ticker'],
                         'quantita': item['quantita'],
                         'prezzo_attuale': item['prezzo_attuale_manuale']
                     })
             return assets

        # Esegui in background per non bloccare
        task = AsyncTask(
            target=fetch_data,
            args=(),
            callback=self._on_data_loaded,
            error_callback=lambda e: print(f"Errore caricamento dati MC: {e}")
        )
        task.start()

    def _on_data_loaded(self, result):
        self.portfolio_assets = result
        totale = sum([a['quantita'] * a['prezzo_attuale'] for a in self.portfolio_assets])
        self.total_value = totale
        
        self.txt_valore_iniziale.value = self.controller.loc.format_currency(totale)
        if self.page: self.page.update()

    def _on_params_change(self, e):
        self.years = int(self.slider_ani.value)
        self.n_simulations = int(self.slider_sim.value)
        
        self.txt_anni.value = f"{self.years} Anni"
        self.txt_sim.value = f"{self.n_simulations} Sim."
        if self.page: self.page.update()

    def _avvia_simulazione(self, e):
        if self.total_value <= 0:
            self.controller.show_snack_bar("Portafoglio vuoto o valore nullo.", success=False)
            return

        self.is_simulating = True
        self.btn_avvia.disabled = True
        self.chart_container.content = ft.Column([
            ft.ProgressRing(),
            ft.Text("Esecuzione Simulazione Monte Carlo...", color=AppColors.TEXT_SECONDARY)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER)
        if self.page: self.page.update()
        
        task = AsyncTask(
            target=run_monte_carlo_simulation,
            args=(self.portfolio_assets, self.years, self.n_simulations, self.total_value),
            callback=self._on_simulazione_completata,
            error_callback=self._on_errore_simulazione
        )
        task.start()

    def _on_simulazione_completata(self, results):
        self.is_simulating = False
        self.btn_avvia.disabled = False
        
        if "error" in results:
            self.controller.show_snack_bar(f"Errore: {results['error']}", success=False)
            self.chart_container.content = ft.Column([
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=AppColors.ERROR, size=48),
                ft.Text(results['error'], color=AppColors.ERROR)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER)
        else:
            # Update Cards
            finals = results['final_values']
            loc = self.controller.loc
            
            # Pessimistic
            self.card_pessimistic.content.controls[2].value = loc.format_currency(finals['p10'])
            self.card_pessimistic.content.controls[3].value = "Rendimento basso"
            
            # Expected
            self.card_expected.content.controls[2].value = loc.format_currency(finals['p50'])
            cagr = results.get('cagr_percent', 0)
            self.card_expected.content.controls[3].value = f"CAGR stimato: {cagr:.1f}%"
            
            # Optimistic 
            self.card_optimistic.content.controls[2].value = loc.format_currency(finals['p90'])
            self.card_optimistic.content.controls[3].value = "Rendimento alto"
            
            # Generate Chart Image
            img_base64 = self._generrate_chart_image(results)
            self.chart_container.content = ft.Image(src_base64=img_base64, fit=ft.ImageFit.CONTAIN, expand=True)
            
        if self.page: self.page.update()

    def _on_errore_simulazione(self, e):
        self.is_simulating = False
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
        
        # Create simpler index array for x-axis to avoid date parsing issues in matplotlib sometimes
        x = np.arange(len(dates))
        
        fig, ax = plt.subplots(figsize=(10, 6), facecolor='white')
        
        # Cone
        ax.fill_between(x, p10, p90, color='#1976D2', alpha=0.2, label='Confidenza 10-90%')
        
        # Lines
        ax.plot(x, p50, color='#1976D2', linewidth=2, label='Mediana')
        ax.plot(x, p90, color='#2E7D32', linestyle='--', linewidth=1, label='90° Percentile')
        ax.plot(x, p10, color='#C62828', linestyle='--', linewidth=1, label='10° Percentile')
        
        # Formatting
        ax.set_title("Proiezione Portafoglio", fontsize=14, pad=15)
        ax.grid(True, linestyle=':', alpha=0.6)
        
        # X Axis ticks reduction
        step = max(1, len(dates) // 10)
        ax.set_xticks(x[::step])
        ax.set_xticklabels([dates[i] for i in range(0, len(dates), step)], rotation=45)
        
        # Y Axis Currency Formatting
        def currency_formatter(x, p):
            return f"€{x:,.0f}"
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(currency_formatter))
        
        ax.legend(loc='upper left')
        
        # Save
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_str
