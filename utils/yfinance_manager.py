"""
Modulo per recuperare i prezzi degli asset finanziari usando chiamate HTTP dirette.
Usa solo 'requests' per massima compatibilità con PyInstaller.
"""
from typing import Optional, Dict, List
import requests
import json


def ottieni_prezzo_asset(ticker: str) -> Optional[float]:
    """
    Recupera il prezzo corrente di un asset tramite Yahoo Finance API.
    
    Args:
        ticker: Il simbolo ticker dell'asset (es. "AAPL", "MSFT", "GOOGL")
    
    Returns:
        Il prezzo corrente dell'asset, o None se non trovato o in caso di errore
    """
    try:
        # URL dell'API Yahoo Finance (v8)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        params = {
            'interval': '1d',
            'range': '1d'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Estrai il prezzo corrente
        if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
            result = data['chart']['result'][0]
            
            # Prova a ottenere il prezzo corrente
            if 'meta' in result and 'regularMarketPrice' in result['meta']:
                return float(result['meta']['regularMarketPrice'])
            
            # Fallback: usa l'ultimo prezzo di chiusura
            if 'indicators' in result and 'quote' in result['indicators']:
                quotes = result['indicators']['quote'][0]
                if 'close' in quotes and quotes['close']:
                    # Prendi l'ultimo valore non-None
                    closes = [c for c in quotes['close'] if c is not None]
                    if closes:
                        return float(closes[-1])
        
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
        # URL per quote summary
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        params = {
            'interval': '1d',
            'range': '1d'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
            result = data['chart']['result'][0]
            meta = result.get('meta', {})
            
            return {
                'nome': meta.get('longName') or meta.get('shortName') or ticker,
                'prezzo_corrente': meta.get('regularMarketPrice'),
                'valuta': meta.get('currency'),
                'tipo': meta.get('instrumentType'),
                'cambio_percentuale': None,  # Non disponibile in questa API
            }
        
        return None
        
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
        prezzo = ottieni_prezzo_asset(ticker)
        return prezzo is not None and prezzo > 0
    except Exception:
        return False
