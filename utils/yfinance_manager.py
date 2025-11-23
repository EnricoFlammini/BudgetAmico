"""
Modulo per l'integrazione con yfinance per ottenere i prezzi degli asset finanziari.
"""
import yfinance as yf
from typing import Optional, Dict, List
import datetime


def ottieni_prezzo_asset(ticker: str) -> Optional[float]:
    """
    Recupera il prezzo corrente di un asset tramite yfinance.
    
    Args:
        ticker: Il simbolo ticker dell'asset (es. "AAPL", "MSFT", "GOOGL")
    
    Returns:
        Il prezzo corrente dell'asset, o None se non trovato o in caso di errore
    """
    try:
        asset = yf.Ticker(ticker)
        info = asset.info
        
        # Prova diversi campi per ottenere il prezzo
        prezzo = (
            info.get('currentPrice') or 
            info.get('regularMarketPrice') or 
            info.get('previousClose')
        )
        
        if prezzo and prezzo > 0:
            return float(prezzo)
        
        # Se info non funziona, prova con history
        hist = asset.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
            
        return None
        
    except Exception as e:
        print(f"Errore nel recupero del prezzo per {ticker}: {e}")
        return None


def ottieni_prezzi_multipli(tickers: List[str]) -> Dict[str, Optional[float]]:
    """
    Recupera i prezzi correnti di più asset contemporaneamente.
    
    Args:
        tickers: Lista di simboli ticker
    
    Returns:
        Dizionario con ticker come chiave e prezzo come valore
    """
    risultati = {}
    
    for ticker in tickers:
        risultati[ticker] = ottieni_prezzo_asset(ticker)
    
    return risultati


def ottieni_info_asset(ticker: str) -> Optional[Dict]:
    """
    Recupera informazioni dettagliate su un asset.
    
    Args:
        ticker: Il simbolo ticker dell'asset
    
    Returns:
        Dizionario con informazioni sull'asset, o None se non trovato
    """
    try:
        asset = yf.Ticker(ticker)
        info = asset.info
        
        return {
            'nome': info.get('longName') or info.get('shortName'),
            'prezzo_corrente': (
                info.get('currentPrice') or 
                info.get('regularMarketPrice') or 
                info.get('previousClose')
            ),
            'valuta': info.get('currency'),
            'tipo': info.get('quoteType'),
            'cambio_percentuale': info.get('regularMarketChangePercent'),
        }
        
    except Exception as e:
        print(f"Errore nel recupero delle info per {ticker}: {e}")
        return None


def verifica_ticker_valido(ticker: str) -> bool:
    """
    Verifica se un ticker è valido e restituisce dati.
    
    Args:
        ticker: Il simbolo ticker da verificare
    
    Returns:
        True se il ticker è valido, False altrimenti
    """
    try:
        asset = yf.Ticker(ticker)
        info = asset.info
        
        # Verifica che ci siano dati significativi
        return bool(info.get('regularMarketPrice') or info.get('currentPrice'))
        
    except Exception:
        return False
