import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from db.gestione_db import ottieni_storico_asset_globale

def run_monte_carlo_simulation(
    portfolio_assets: List[Dict],
    years: int = 10,
    n_simulations: int = 1000,
    initial_portfolio_value: float = 0.0, # Kept for compatibility but calculated from assets if 0
    pac_list: List[Dict] = None # List of {ticker, amount, frequency}
) -> Dict:
    """
    Esegue una simulazione Monte Carlo multi-asset con supporto ai PAC.

    Args:
        portfolio_assets: Lista di {'ticker': str, 'quantita': float, 'prezzo_attuale': float, 'valore_simulato': float (opt)}
        years: Numero di anni di proiezione
        n_simulations: Numero di simulazioni
        initial_portfolio_value: (Ignorato se portfolio_assets ha valori)
        pac_list: Lista di {'ticker': str, 'importo': float, 'frequenza': str ('Mensile', 'Trimestrale', 'Annuale')}

    Returns:
        Dizionario risultati
    """
    if not portfolio_assets and not pac_list:
        return {"error": "Portafoglio vuoto e nessun PAC configurato."}
    
    # --- 1. Preparazione Asset e Pesi Iniziali ---
    # Normalizziamo input: usiamo 'valore_simulato' se presente (override utente), altrimenti quantita * prezzo
    
    # Asset che sono nel portafoglio iniziale
    active_assets = {} # ticker -> valore_iniziale
    
    for asset in portfolio_assets:
        ticker = asset.get('ticker').upper()
        if asset.get('valore_simulato') is not None:
             val = float(asset['valore_simulato'])
        else:
             val = float(asset['quantita']) * float(asset['prezzo_attuale'])
        
        if val > 0:
            active_assets[ticker] = val
            
    # Asset che sono SOLO nei PAC (potrebbero non essere nel portafoglio iniziale)
    pac_tickers = set()
    if pac_list:
        for pac in pac_list:
            t = pac.get('ticker', '').upper()
            if t: pac_tickers.add(t)
            
    all_tickers = list(set(active_assets.keys()) | pac_tickers)
    
    if not all_tickers:
        return {"error": "Nessun ticker valido identificato."}

    # Valore iniziale totale per report
    total_start_value = sum(active_assets.values())

    # --- 2. Recupero Dati Storici ---
    data_frames = {}
    
    # Cerchiamo almeno 3-5 anni di storico comune. Se asset è molto giovane, prendiamo quello che c'è.
    # L'intersezione determinerà la profondità effettiva.
    start_date_limit = (datetime.now() - timedelta(days=365*25)).strftime('%Y-%m-%d') # Chiediamo 25 anni

    for ticker in all_tickers:
        storico = ottieni_storico_asset_globale(ticker, data_inizio=start_date_limit)
        if not storico:
            # Se un asset non ha storico, non possiamo simularlo. 
            # Se è vitale per il portafoglio, è un errore. Se è un PAC marginale, potremmo ignorarlo?
            # Per sicurezza, ritorniamo errore.
            return {"error": f"Nessun dato storico per {ticker}. Impossibile simulare."}
            
        df = pd.DataFrame(storico)
        df['data'] = pd.to_datetime(df['data'])
        df.set_index('data', inplace=True)
        # Resample mensile, tenendo l'ultimo prezzo del mese
        df_monthly = df['prezzo_chiusura'].resample('ME').last().ffill()
        data_frames[ticker] = df_monthly

    # Unisci dati
    price_data = pd.concat(data_frames.values(), axis=1, keys=data_frames.keys()).dropna()
    
    # Check profondità storica
    months_history = len(price_data)
    years_history = months_history / 12.0
    
    if months_history < 12:
        return {"error": "Dati storici insufficienti o non sovrapposti per gli asset selezionati (minimo 1 anno comune)."}
    
    # --- 3. Calcolo Parametri Simulazione (Log-Returns Mensili) ---
    log_returns = np.log(price_data / price_data.shift(1)).dropna()
    mean_returns = log_returns.mean()
    cov_matrix = log_returns.cov()
    
    try:
        L = np.linalg.cholesky(cov_matrix)
    except np.linalg.LinAlgError:
        # Tenta correzione per matrici non positive-definite (aggiunta piccolo epsilon alla diagonale)
        epsilon = 1e-6
        cov_matrix_fixed = cov_matrix + np.eye(cov_matrix.shape[0]) * epsilon
        try:
            L = np.linalg.cholesky(cov_matrix_fixed)
        except np.linalg.LinAlgError:
             return {"error": "Errore matematico nella matrice di covarianza (dati colineari o insufficienti)."}

    # --- 4. Setup Simulazione ---
    months_per_year = 12
    total_steps = years * months_per_year
    n_assets = len(all_tickers)
    asset_mapping = {t: i for i, t in enumerate(all_tickers)} # ticker -> index

    # Generiamo TUTTI gli shock casuali in una volta sola: (steps, sims, assets)
    # Z ~ N(0, 1)
    Z = np.random.normal(0.0, 1.0, (total_steps, n_simulations, n_assets))
    
    # Correla gli shock: R_sim = mu + L * Z
    # mean_returns.values è (n_assets,)
    # Z è (steps, sims, n_assets)
    # L è (n_assets, n_assets)
    # Vogliamo R: (steps, sims, n_assets)
    
    # Espansione media per broadcasting
    mu = mean_returns.values[np.newaxis, np.newaxis, :] 
    
    # Prodotto tensoriale Z * L.T
    # Z[t, s, :] è un vettore 1xN per una sim s al tempo t
    # Correlated = Z @ L.T
    correlated_shocks = np.einsum('ijk,lk->ijl', Z, L)
    
    sim_log_returns = mu + correlated_shocks
    # Converti log returns in moltiplicatori aritmetici: exp(r) = P_t / P_{t-1}
    sim_returns_mult = np.exp(sim_log_returns) 
    
    # --- 5. Esecuzione Step-by-Step con PAC ---
    # Inizializziamo valori correnti degli asset per ogni simulazione
    # current_values shape: (sims, n_assets)
    current_values = np.zeros((n_simulations, n_assets))
    
    # Array per salvare la storia MEDIA di ogni asset (per i trend individuali)
    # asset_history_sum: (steps + 1, n_assets) - Accumuliamo la somma per calcolare la media alla fine
    # Usiamo la media (o mediana) per il trend visuale. La media è più facile da accumulare live.
    asset_trends_history = np.zeros((total_steps + 1, n_assets))
    
    # Imposta valori iniziali
    for ticker, val in active_assets.items():
        idx = asset_mapping[ticker]
        current_values[:, idx] = val
        
    # Set initial values in history
    asset_trends_history[0, :] = current_values.mean(axis=0)
        
    # Prepare PAC instructions pre-mapped to indices
    # pacs_optimized: list of (index, amount, frequency_mod)
    pacs_optimized = []
    if pac_list:
        for pac in pac_list:
            t = pac.get('ticker', '').upper()
            if t in asset_mapping:
                idx = asset_mapping[t]
                amount = float(pac.get('importo', 0))
                freq_str = pac.get('frequenza', 'Mensile')
                
                mod = 1 # Mensile
                if freq_str == 'Trimestrale': mod = 3
                elif freq_str == 'Annuale': mod = 12
                
                if amount > 0:
                    pacs_optimized.append((idx, amount, mod))

    # Array per salvare la storia del PORTAFOGLIO TOTALE (non singoli asset per risparmiare RAM)
    # portfolio_history: (steps + 1, sims)
    portfolio_history = np.zeros((total_steps + 1, n_simulations))
    portfolio_history[0, :] = current_values.sum(axis=1) # Step 0
    
    # Loop Temporale
    for t in range(total_steps):
        # 1. Applica rendimento di mercato (Molt)
        # sim_returns_mult[t] è (sims, n_assets)
        current_values *= sim_returns_mult[t]
        
        # 2. Applica PAC Inflows (Fine mese)
        # t va da 0 a total_steps - 1.
        # Mese simulato corrente = t + 1
        current_month_idx = t + 1
        
        for p_idx, p_amount, p_mod in pacs_optimized:
             if current_month_idx % p_mod == 0:
                 current_values[:, p_idx] += p_amount
                 
        # 3. Salva totale
        portfolio_history[t+1, :] = current_values.sum(axis=1)
        
        # 4. Salva trend asset (Media dello step t+1)
        asset_trends_history[t+1, :] = current_values.mean(axis=0)
        
    # --- 6. Aggregazione Risultati ---
    # Percentili finali e trend
    percentiles = [10, 50, 90]
    results_per_step = np.percentile(portfolio_history, percentiles, axis=1) # (3, steps+1)
    
    # Sampling date per grafico
    step_size = max(1, total_steps // 50) 
    indices = np.arange(0, total_steps + 1, step_size)
    if indices[-1] != total_steps:
        indices = np.append(indices, total_steps)
        
    current_month = datetime.now().replace(day=1)
    dates_str = []
    for i in indices:
        d = current_month + pd.DateOffset(months=int(i))
        dates_str.append(d.strftime('%Y-%m'))
        
    p10 = results_per_step[0, indices]
    p50 = results_per_step[1, indices]
    p90 = results_per_step[2, indices]
    
    # Extract asset trends for selected indices
    # asset_trends dict: {ticker: [values_at_indices]}
    asset_trends = {}
    for ticker, idx in asset_mapping.items():
        # Export only if final value > 0 important? Or always?
        # Let's export always so users see even flat lines if they added a ticker with 0 val.
        trend_series = asset_trends_history[indices, idx]
        # Filter out assets that are 0 flat? 
        if trend_series[-1] > 1.0: # Arbitrary small threshold
            asset_trends[ticker] = trend_series.tolist()

    final_values_dict = {
        "p10": float(results_per_step[0, -1]),
        "p50": float(results_per_step[1, -1]),
        "p90": float(results_per_step[2, -1])
    }
    
    # CAGR Calcolo (Adjusted for PAC? No, simple CAGR on total outcome vs total input is tricky with PAC)
    # Usiamo Money-Weighted Return (MWRR) approssimato o semplicemente il ritorno totale sul capitale investito?
    # Per semplicità nel grafico mostriamo CAGR "come se fosse interesse composto equivalente", ma con i PAC è fuorviante.
    # Meglio mostrare rendimento assoluto e % totale.
    
    # Calcolo Totale Investito (Capitale)
    total_invested = total_start_value
    if pac_list:
        for pac in pac_list:
             amount = float(pac.get('importo', 0))
             freq_str = pac.get('frequenza', 'Mensile')
             if freq_str == 'Mensile': n_vers = total_steps
             elif freq_str == 'Trimestrale': n_vers = total_steps // 3
             elif freq_str == 'Annuale': n_vers = total_steps // 12
             else: n_vers = 0
             total_invested += (amount * n_vers)
             
    net_profit_p50 = final_values_dict["p50"] - total_invested
    roi_percent = (net_profit_p50 / total_invested * 100) if total_invested > 0 else 0

    return {
        "dates": dates_str,
        "p10": p10.tolist(),
        "p50": p50.tolist(),
        "p90": p90.tolist(),
        "asset_trends": asset_trends, # New: Individual asset trends
        "final_values": final_values_dict,
        "initial_value": total_start_value, # Nota: questo è SOLO quello iniziale, non include i PAC
        "total_invested": total_invested, # Capitale totale versato
        "roi_percent": roi_percent,
        "years": years,
        "simulations": n_simulations,
        "history_years": round(years_history, 1)
    }

