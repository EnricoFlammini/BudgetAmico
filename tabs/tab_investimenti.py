import flet as ft
from functools import partial
from db.gestione_db import (
    ottieni_dettagli_conti_utente,
    ottieni_portafoglio,
    aggiorna_prezzo_manuale_asset,
    elimina_conto
)
from utils.styles import AppStyles, AppColors, PageConstants
from utils.yfinance_manager import ottieni_prezzo_asset, ottieni_prezzi_multipli
from dialogs.investimento_dialog import InvestimentoDialog
from utils.async_task import AsyncTask
from tabs.subtab_storico_asset import StoricoAssetSubTab
from tabs.subtab_monte_carlo import MonteCarloSubTab
import datetime


class InvestimentiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page

        # Controlli UI Portafoglio
        self.txt_valore_totale = AppStyles.header_text("")
        self.txt_gain_loss_totale = AppStyles.body_text("")
        self.lv_portafogli = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE, spacing=15)
        
        # Sotto-tab
        self.storico_subtab = StoricoAssetSubTab(controller)
        self.monte_carlo_subtab = MonteCarloSubTab(controller)
        
        # Container per contenuto portafoglio
        self.portafoglio_content = ft.Column(expand=True, spacing=10)
        
        # Tabs principali
        # Tabs principali
        t_port = ft.Tab(
            text="Portafoglio",
            icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
            content=ft.Container(content=self.portafoglio_content, padding=10, expand=True)
        )
        
        t_storico = ft.Tab(
            text="Andamento Storico",
            icon=ft.Icons.SHOW_CHART,
            content=ft.Container(content=self.storico_subtab, padding=10, expand=True)
        )
        
        t_mc = ft.Tab(
            text="Analisi Monte Carlo",
            icon=ft.Icons.INSIGHTS,
            content=ft.Container(content=self.monte_carlo_subtab, padding=10, expand=True)
        )

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[t_port, t_storico, t_mc],
            expand=True,
            on_change=self._on_tab_change
        )
        
        self.content = self.tabs
        
        # Stato per sincronizzazione
        self.sincronizzazione_in_corso = False
    
    def _on_tab_change(self, e):
        """Gestisce cambio sotto-tab."""
        if e.control.selected_index == 1:
            # Carica dati storico quando si passa alla tab
            self.storico_subtab.update_view_data()
        elif e.control.selected_index == 2:
            # Carica dati Monte Carlo
            self.monte_carlo_subtab.update_view_data()

    def update_view_data(self, is_initial_load=False):
        """
        Avvia il caricamento asincrono dei dati.
        """
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        self.portafoglio_content.controls = self.build_controls(theme)
        
        # 1. Mostra Loading State dentro la lista portafogli
        self.lv_portafogli.controls.clear()
        self.lv_portafogli.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.ProgressRing(color=AppColors.PRIMARY),
                    ft.Text("Caricamento portafoglio...", color=AppColors.TEXT_SECONDARY)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.Alignment(0, 0),
                padding=50
            )
        )
        if self.controller.page:
            self.controller.page.update()

        utente_id = self.controller.get_user_id()
        if not utente_id:
            return

        master_key_b64 = self.controller.page.session.get("master_key")
        
        # 2. Avvia Task Asincrono
        task = AsyncTask(
            target=self._fetch_data,
            args=(utente_id, master_key_b64),
            callback=self._on_data_loaded,
            error_callback=self._on_error
        )
        task.start()

    def _fetch_data(self, utente_id, master_key_b64):
        """
        Recupera conti e portafogli in background.
        """
        conti_utente = ottieni_dettagli_conti_utente(utente_id, master_key_b64=master_key_b64)
        conti_investimento = [c for c in conti_utente if c['tipo'] == 'Investimento']
        
        dati_portafogli = []
        for conto in conti_investimento:
            portafoglio = ottieni_portafoglio(conto['id_conto'], master_key_b64=master_key_b64)
            dati_portafogli.append({
                'conto': conto,
                'portafoglio': portafoglio
            })
            
        return dati_portafogli

    def _on_data_loaded(self, result):
        """
        Callback UI.
        """
        dati_portafogli = result
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        
        try:
            self.lv_portafogli.controls.clear()

            valore_totale = 0
            gain_loss_totale = 0

            if not dati_portafogli:
                self.lv_portafogli.controls.append(
                    AppStyles.body_text(self.controller.loc.get("no_investment_accounts"))
                )
            else:
                for item in dati_portafogli:
                    conto = item['conto']
                    portafoglio = item['portafoglio']
                    
                    # Calcola valore e gain/loss per questo portafoglio
                    valore_portafoglio = 0
                    gain_loss_portafoglio = 0
                    
                    for asset in portafoglio:
                        valore_portafoglio += asset['quantita'] * asset['prezzo_attuale_manuale']
                        gain_loss_portafoglio += asset['gain_loss_totale']
                    
                    valore_totale += valore_portafoglio
                    gain_loss_totale += gain_loss_portafoglio
                    
                    # Crea widget per questo portafoglio
                    self.lv_portafogli.controls.append(
                        self._crea_widget_portafoglio(conto, portafoglio, valore_portafoglio, gain_loss_portafoglio, theme)
                    )

            # Aggiorna i totali
            self.txt_valore_totale.value = self.controller.loc.format_currency(valore_totale)
            self.txt_valore_totale.color = theme.primary
            
            self.txt_gain_loss_totale.value = f"{self.controller.loc.get('total_gain_loss')}: {self.controller.loc.format_currency(gain_loss_totale)}"
            self.txt_gain_loss_totale.color = AppColors.SUCCESS if gain_loss_totale >= 0 else AppColors.ERROR

            if self.controller.page:
                self.controller.page.update()

        except Exception as e:
            self._on_error(e)

    def _on_error(self, e):
        print(f"Errore in InvestimentiTab._on_error: {e}")
        try:
            self.lv_portafogli.controls.clear()
            self.lv_portafogli.controls.append(AppStyles.body_text(f"Errore caricamento: {e}", color=AppColors.ERROR))
            if self.controller.page:
                self.controller.page.update()
        except:
            pass

    def build_controls(self, theme):
        loc = self.controller.loc
        return [
            # Header con statistiche totali
            AppStyles.card_container(
                content=ft.Column([
                    ft.Row([
                        ft.Column([
                            AppStyles.caption_text(loc.get("total_portfolio_value")),
                            self.txt_valore_totale
                        ], expand=True),
                        ft.Column([
                            self.txt_gain_loss_totale
                        ], horizontal_alignment=ft.CrossAxisAlignment.END)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], spacing=5),
                padding=15
            ),
            
            # Toolbar
            ft.Row([
                AppStyles.subheader_text(loc.get("investments")),
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ADD_CARD,
                        tooltip=loc.get("add_investment_account"),
                        icon_color=theme.primary,
                        on_click=self._aggiungi_conto_investimento
                    ),

                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip=loc.get("sync_prices"),
                        icon_color=theme.primary,
                        on_click=self._sincronizza_tutti_prezzi,
                        disabled=self.sincronizzazione_in_corso
                    )
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Divider(color=ft.Colors.OUTLINE_VARIANT),
            
            # Lista portafogli
            ft.Container(content=self.lv_portafogli, expand=True)
        ]

    def _crea_widget_portafoglio(self, conto, portafoglio, valore_totale, gain_loss_totale, theme):
        loc = self.controller.loc
        
        # Header del portafoglio
        header = ft.Row([
            ft.Column([
                AppStyles.subheader_text(conto['nome_conto']),
                AppStyles.caption_text(f"{loc.get('value')}: {loc.format_currency(valore_totale)}")
            ], expand=True),
            ft.Column([
                ft.Text(
                    f"G/L: {loc.format_currency(gain_loss_totale)}",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=AppColors.SUCCESS if gain_loss_totale >= 0 else AppColors.ERROR
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.END)
        ])
        
        # Tabella asset
        if not portafoglio:
            asset_list = ft.Column([
                AppStyles.body_text(loc.get("no_assets_in_portfolio"))
            ], spacing=5)
        else:
            asset_list = ft.Column(
                [self._crea_widget_asset(asset, conto, theme) for asset in portafoglio],
                spacing=5
            )
        
        # Pulsanti per gestire conto e portafoglio
        btn_row = ft.Row([
            ft.ElevatedButton(
                loc.get("manage_portfolio"),
                icon=ft.Icons.INSIGHTS,
                on_click=lambda e, c=conto: self.controller.portafoglio_dialogs.apri_dialog_portafoglio(e, c)
            ),
            ft.IconButton(
                icon=ft.Icons.EDIT,
                tooltip=loc.get("edit_account"),
                icon_color=AppColors.INFO,
                data=conto,
                on_click=self._modifica_conto_investimento
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE,
                tooltip=loc.get("delete_account"),
                icon_color=AppColors.ERROR,
                data=conto['id_conto'],
                on_click=lambda e: self.controller.open_confirm_delete_dialog(
                    partial(self._elimina_conto_investimento, e)
                )
            )
        ], alignment=ft.MainAxisAlignment.END)
        
        return AppStyles.card_container(
            content=ft.Column([
                header,
                ft.Divider(height=10),
                asset_list,
                ft.Container(height=10),
                btn_row
            ], spacing=5),
            padding=15
        )

    def _crea_widget_asset(self, asset, conto, theme):
        loc = self.controller.loc
        
        valore_totale = asset['quantita'] * asset['prezzo_attuale_manuale']
        
        return ft.Container(
            content=ft.Row([
                # Info asset
                ft.Column([
                    ft.Text(f"{asset['ticker']} - {asset['nome_asset']}", 
                           size=14, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{loc.get('quantity')}: {asset['quantita']:.4f}", 
                           size=12, color=AppColors.TEXT_SECONDARY)
                ], expand=True),
                
                # Prezzo e valore
                ft.Column([
                    ft.Text(f"{loc.format_currency(asset['prezzo_attuale_manuale'])}", 
                           size=13),
                    ft.Text(f"{loc.get('value')}: {loc.format_currency(valore_totale)}", 
                           size=12, color=AppColors.TEXT_SECONDARY),
                    ft.Text(f"Agg: {asset['data_aggiornamento']}" if asset['data_aggiornamento'] else "",
                            size=10, color=ft.Colors.GREY_500)
                ], horizontal_alignment=ft.CrossAxisAlignment.END),
                
                # Gain/Loss
                ft.Column([
                    ft.Text(
                        f"{loc.format_currency(asset['gain_loss_totale'])}",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=AppColors.SUCCESS if asset['gain_loss_totale'] >= 0 else AppColors.ERROR
                    ),
                    ft.Text(
                        f"{loc.format_currency(asset['gain_loss_unitario'])}/u",
                        size=11,
                        color=AppColors.SUCCESS if asset['gain_loss_unitario'] >= 0 else AppColors.ERROR
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
                
                # Pulsante sincronizza prezzo
                ft.IconButton(
                    icon=ft.Icons.SYNC,
                    tooltip=loc.get("sync_prices"),
                    icon_size=18,
                    data={'asset': asset, 'conto': conto},
                    on_click=self._sincronizza_prezzo_asset
                )
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=10,
            bgcolor=theme.surface_variant,
            border_radius=8
        )

    def _sincronizza_prezzo_asset(self, e):
        """Sincronizza il prezzo di un singolo asset tramite yfinance."""
        asset = e.control.data['asset']
        ticker = asset['ticker']
        
        # Mostra indicatore di caricamento
        self.controller.show_snack_bar(f"Recupero prezzo per {ticker}...", success=True)
        
        # Ottieni prezzo da yfinance - Questo è bloccante, ma essendo su azione utente potrebbe essere OK o andrebbe reso async
        # Per ora lo lascio sincrono per non complicare troppo, ma ideally should be async
        nuovo_prezzo = ottieni_prezzo_asset(ticker)
        
        if nuovo_prezzo:
            # Aggiorna nel database
            aggiorna_prezzo_manuale_asset(asset['id_asset'], nuovo_prezzo)
            self.controller.show_snack_bar(
                f"{ticker}: {self.controller.loc.format_currency(nuovo_prezzo)}",
                success=True
            )
            # Ricarica asincrono
            self.update_view_data() 
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar(
                f"{self.controller.loc.get('error_fetching_price')} per {ticker}",
                success=False
            )

    def _sincronizza_tutti_prezzi(self, e):
        """Sincronizza i prezzi di tutti gli asset nei portafogli."""
        self.sincronizzazione_in_corso = True
        self.controller.show_snack_bar(
            self.controller.loc.get("sync_prices") + "...",
            success=True
        )
        
        utente_id = self.controller.get_user_id()
        if not utente_id:
            self.sincronizzazione_in_corso = False
            return
            
        # Potremmo usare un AsyncTask anche qui per la sync pesante
        master_key_b64 = self.controller.page.session.get("master_key")
        
        task = AsyncTask(
            target=self._run_sync_tutti,
            args=(utente_id, master_key_b64),
            callback=self._on_sync_complete,
            error_callback=self._on_sync_error
        )
        task.start()

    def _run_sync_tutti(self, utente_id, master_key_b64):
        # Ottieni tutti i conti di investimento
        conti_utente = ottieni_dettagli_conti_utente(utente_id, master_key_b64=master_key_b64)
        conti_investimento = [c for c in conti_utente if c['tipo'] == 'Investimento']
        
        # Raccogli tutti i ticker unici
        tutti_asset = []
        for conto in conti_investimento:
            portafoglio = ottieni_portafoglio(conto['id_conto'], master_key_b64=master_key_b64)
            tutti_asset.extend(portafoglio)
        
        if not tutti_asset:
            return 0
        
        # Ottieni prezzi per tutti i ticker
        tickers = list(set([asset['ticker'] for asset in tutti_asset]))
        prezzi = ottieni_prezzi_multipli(tickers)
        
        # Aggiorna i prezzi nel database
        aggiornati = 0
        for asset in tutti_asset:
            ticker = asset['ticker']
            if ticker in prezzi and prezzi[ticker] is not None:
                aggiorna_prezzo_manuale_asset(asset['id_asset'], prezzi[ticker])
                aggiornati += 1
                
        return aggiornati

    def _on_sync_complete(self, aggiornati):
        self.sincronizzazione_in_corso = False
        if aggiornati > 0:
            self.controller.show_snack_bar(
                f"{aggiornati} {self.controller.loc.get('price_updated_successfully')}",
                success=True
            )
            # Ricarica vista
            self.update_view_data()
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar(
                self.controller.loc.get("no_assets_in_portfolio") if aggiornati == 0 else self.controller.loc.get("error_fetching_price"),
                success=False
            )

    def _on_sync_error(self, e):
        self.sincronizzazione_in_corso = False
        self.controller.show_snack_bar(f"Errore sync: {e}", success=False)


    def _aggiungi_conto_investimento(self, e):
        """Apre il dialogo per creare un nuovo conto di investimento."""
        print("Tentativo di apertura dialogo investimento...")
        try:
            def on_save():
                self.controller.db_write_operation()
                
            dialog = InvestimentoDialog(self.controller.page, on_save)
            
            if hasattr(self.controller.page, "open"):
                self.controller.page.open(dialog)
            else:
                if dialog not in self.controller.page.overlay:
                    self.controller.page.overlay.append(dialog)
                dialog.open = True
                self.controller.page.update()
            print("Dialogo aperto con successo.")
        except Exception as ex:
            print(f"Errore nell'apertura del dialogo: {ex}")
            import traceback
            traceback.print_exc()
            self.controller.show_error_dialog(f"Errore apertura dialogo: {ex}")

    def _modifica_conto_investimento(self, e):
        """Apre il dialogo per modificare un conto di investimento."""
        print("Tentativo di apertura dialogo modifica investimento...")
        try:
            conto_data = e.control.data
            
            def on_save():
                self.controller.db_write_operation()
                
            dialog = InvestimentoDialog(self.controller.page, on_save, conto_da_modificare=conto_data)
            
            if hasattr(self.controller.page, "open"):
                self.controller.page.open(dialog)
            else:
                if dialog not in self.controller.page.overlay:
                    self.controller.page.overlay.append(dialog)
                dialog.open = True
                self.controller.page.update()
            print("Dialogo modifica aperto con successo.")
        except Exception as ex:
            print(f"Errore nell'apertura del dialogo modifica: {ex}")
            import traceback
            traceback.print_exc()
            self.controller.show_error_dialog(f"Errore apertura dialogo: {ex}")

    def _elimina_conto_investimento(self, e):
        """Elimina un conto di investimento."""
        id_conto = e.control.data
        utente_id = self.controller.get_user_id()
        risultato = elimina_conto(id_conto, utente_id)

        if risultato is True:
            self.controller.show_snack_bar("Conto di investimento eliminato.", success=True)
            self.controller.db_write_operation()
        elif risultato == "NASCOSTO":
            self.controller.show_snack_bar("✅ Conto nascosto. Gli asset storici sono stati mantenuti.", success=True)
            self.controller.db_write_operation()
        elif risultato == "SALDO_NON_ZERO":
            self.controller.show_snack_bar("❌ Errore: Il valore del conto non è 0.", success=False)
        elif isinstance(risultato, tuple) and not risultato[0]:
            self.controller.show_error_dialog(risultato[1])
        else:
            self.controller.show_error_dialog("Si è verificato un errore sconosciuto durante l'eliminazione del conto.")
