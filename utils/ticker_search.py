"""
Componente UI riutilizzabile per la ricerca ticker con autocomplete.
Usa un Dropdown che si popola con i risultati della ricerca.
"""
import flet as ft
from typing import Callable, Optional
import threading

from utils.styles import AppStyles, AppColors


class TickerSearchField(ft.Column):
    """
    Campo di ricerca ticker con autocomplete tramite Dropdown.
    
    Mostra risultati da Yahoo Finance con ticker, nome e borsa.
    """
    
    def __init__(
        self,
        on_select: Callable[[dict], None],
        controller=None,  # Controller per riferimento stabile a page
        label: str = "Cerca ticker",
        hint_text: str = "es. Apple, AAPL, ISIN (IT...)",
        width: int = 300,
        show_borsa: bool = True,
    ):
        super().__init__(spacing=5)
        
        self.on_select_callback = on_select
        self.show_borsa = show_borsa
        self._search_timer = None
        self._last_query = ""
        self._risultati_cache = {}  # {ticker: risultato dict}
        self._controller = controller  # Riferimento stabile
        
        # Campo di ricerca
        self.txt_search = ft.TextField(
            label=label,
            hint_text=hint_text,
            width=width,
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_change,
            on_submit=self._on_search_submit,
        )
        
        # Dropdown per i risultati
        self.dd_risultati = ft.Dropdown(
            label="Seleziona ticker",
            width=width,
            visible=False
        )
        self.dd_risultati.on_change = self._on_dropdown_change
        
        self.controls = [
            self.txt_search,
            self.dd_risultati,
        ]
    
    def _on_search_change(self, e):
        """Gestisce cambio testo con debounce."""
        query = e.control.value.strip()
        
        # Nascondi dropdown se query vuota
        if len(query) < 2:
            self.dd_risultati.visible = False
            self._safe_update()
            return
        
        # Debounce: aspetta 500ms prima di cercare
        if self._search_timer:
            self._search_timer.cancel()
        
        self._search_timer = threading.Timer(0.5, self._esegui_ricerca, [query])
        self._search_timer.start()
    
    def _on_search_submit(self, e):
        """Quando l'utente preme invio, cerca subito."""
        query = e.control.value.strip()
        if len(query) >= 2:
            self._esegui_ricerca(query)
    
    def _esegui_ricerca(self, query: str):
        """Esegue la ricerca in background."""
        try:
            from utils.yfinance_manager import cerca_ticker
            risultati = cerca_ticker(query, limit=10)
            
            # Aggiorna dropdown
            self._risultati_cache.clear()
            self.dd_risultati.options.clear()
            
            if risultati:
                for r in risultati:
                    ticker = r['ticker']
                    nome = r['nome']
                    borsa = r.get('borsa', '')
                    
                    # Salva in cache per recupero successivo
                    self._risultati_cache[ticker] = r
                    
                    # Crea opzione dropdown
                    if self.show_borsa and borsa:
                        label = f"{ticker} ({borsa}) - {nome[:30]}"
                    else:
                        label = f"{ticker} - {nome[:35]}"
                    
                    self.dd_risultati.options.append(
                        ft.dropdown.Option(key=ticker, text=label)
                    )
                
                self.dd_risultati.visible = True
                self.dd_risultati.value = None
            else:
                self.dd_risultati.options.append(
                    ft.dropdown.Option(key="", text="Nessun risultato")
                )
                self.dd_risultati.visible = True
            
            self._safe_update()
            
        except Exception as e:
            print(f"Errore ricerca ticker: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_dropdown_change(self, e):
        """Quando l'utente seleziona un ticker dal dropdown."""
        ticker = e.control.value
        if not ticker:
            return
        
        # Recupera dati dalla cache
        risultato = self._risultati_cache.get(ticker)
        if risultato:
            # Imposta il ticker nel campo di ricerca
            self.txt_search.value = ticker
            self.dd_risultati.visible = False
            self._safe_update()
            
            # Chiama callback
            if self.on_select_callback:
                self.on_select_callback(risultato)
    
    def _safe_update(self):
        """Aggiorna la UI in modo sicuro."""
        try:
            # Usa controller.page per riferimento stabile
            page = None
            if self._controller and hasattr(self._controller, 'page'):
                page = self._controller.page
            elif self.page:
                page = self.page
            
            if page:
                page.update()
        except:
            pass
    
    def reset(self):
        """Resetta il campo di ricerca."""
        self.txt_search.value = ""
        self.dd_risultati.visible = False
        self.dd_risultati.options.clear()
        self.dd_risultati.value = None
        self._risultati_cache.clear()
        self._safe_update()
    
    @property
    def value(self) -> str:
        """Restituisce il valore corrente del campo."""
        return self.txt_search.value or ""
    
    @value.setter
    def value(self, val: str):
        """Imposta il valore del campo."""
        self.txt_search.value = val
