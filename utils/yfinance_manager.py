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


def applica_suffisso_borsa(ticker: str, borsa_default: Optional[str]) -> str:
    """
    Applica il suffisso della borsa al ticker se non è già presente.
    
    Args:
        ticker: Il simbolo ticker dell'asset
        borsa_default: Il suffisso della borsa di default (es. ".MI") o None
        
    Returns:
        Il ticker eventualmente modificato con il suffisso
    """
    if not ticker:
        return ticker
        
    if borsa_default:
        if "." not in ticker:
            ticker += borsa_default
            
    return ticker


def ottieni_storico_asset(ticker: str, anni: int = 5) -> List[Dict]:
    """
    Recupera lo storico prezzi di un asset tramite Yahoo Finance API.
    
    Args:
        ticker: Il simbolo ticker dell'asset (es. "AAPL", "MSFT")
        anni: Numero di anni di storico da recuperare (default 5)
    
    Returns:
        Lista di dict con {data: 'YYYY-MM-DD', prezzo: float} ordinata per data crescente,
        o lista vuota se errore
    """
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        params = {
            'interval': '1d',
            'range': f'{anni}y'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        risultato = []
        
        if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
            result = data['chart']['result'][0]
            
            if 'timestamp' in result and 'indicators' in result:
                timestamps = result['timestamp']
                quotes = result['indicators']['quote'][0]
                closes = quotes.get('close', [])
                
                from datetime import datetime
                
                for i, ts in enumerate(timestamps):
                    if i < len(closes) and closes[i] is not None:
                        # Converti timestamp Unix in data
                        data_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                        risultato.append({
                            'data': data_str,
                            'prezzo': float(closes[i])
                        })
        
        return risultato
        
    except Exception as e:
        print(f"Errore nel recupero dello storico per {ticker}: {e}")
        return []


def cerca_ticker(query: str, limit: int = 10) -> List[Dict]:
    """
    Cerca ticker su Yahoo Finance per nome o simbolo.
    Supporta filtro per borsa: es. "Apple Milano" cerca Apple e filtra per Milano.
    
    Args:
        query: Testo da cercare (nome azienda o ticker parziale)
               Può includere nome borsa per filtrare: "Apple Milano", "Amazon XETRA"
        limit: Numero massimo di risultati (default 10)
    
    Returns:
        Lista di dizionari con: ticker, nome, borsa, tipo
    """
    if not query or len(query) < 2:
        return []
    
    # Mappa nomi borsa a codici e suffissi ticker
    borse_keywords = {
        'milano': ('MIL', '.MI'),
        'xetra': ('GER', '.DE'),
        'frankfurt': ('FRA', '.F'),
        'parigi': ('PAR', '.PA'),
        'londra': ('LON', '.L'),
        'amsterdam': ('AMS', '.AS'),
        'bruxelles': ('BRU', '.BR'),
        'madrid': ('MCE', '.MC'),
        'nasdaq': ('NMS', ''),
        'nyse': ('NYQ', ''),
        'usa': ('NMS', ''),
        'america': ('NMS', ''),
    }
    
    # Cerca se c'è un filtro borsa nella query
    filtro_borsa = None
    query_pulita = query
    query_lower = query.lower()
    
    for borsa_nome, (codice, suffisso) in borse_keywords.items():
        if borsa_nome in query_lower:
            filtro_borsa = codice
            # Rimuovi il nome borsa dalla query
            import re
            query_pulita = re.sub(rf'\b{borsa_nome}\b', '', query_lower, flags=re.IGNORECASE).strip()
            break
    
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Aumenta il limite se c'è un filtro (per avere più risultati da filtrare)
        params = {
            'q': query_pulita,
            'quotesCount': limit * 3 if filtro_borsa else limit,
            'newsCount': 0,
            'enableFuzzyQuery': True,
            'quotesQueryId': 'tss_match_phrase_query'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Mappa codici borsa a nomi leggibili
        borse_map = {
            'NMS': 'NASDAQ',
            'NYQ': 'NYSE',
            'GER': 'XETRA',
            'FRA': 'Frankfurt',
            'MIL': 'Milano',
            'PAR': 'Parigi',
            'LON': 'Londra',
            'AMS': 'Amsterdam',
            'ETR': 'XETRA',
            'BRU': 'Bruxelles',
            'MCE': 'Madrid',
        }
        
        risultati = []
        if 'quotes' in data:
            for quote in data['quotes']:
                # Estrai informazioni rilevanti
                ticker = quote.get('symbol', '')
                nome = quote.get('longname') or quote.get('shortname') or ticker
                borsa = quote.get('exchange', '')
                tipo = quote.get('quoteType', '')  # EQUITY, ETF, MUTUALFUND, etc.
                
                # Applica filtro borsa se specificato
                if filtro_borsa and borsa != filtro_borsa:
                    continue
                
                borsa_nome = borse_map.get(borsa, borsa)
                
                risultati.append({
                    'ticker': ticker,
                    'nome': nome,
                    'borsa': borsa_nome,
                    'tipo': tipo
                })
                
                # Limita risultati
                if len(risultati) >= limit:
                    break
        
        return risultati
        
    except Exception as e:
        print(f"Errore nella ricerca ticker per '{query}': {e}")
        return []
