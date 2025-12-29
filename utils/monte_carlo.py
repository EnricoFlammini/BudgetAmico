import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from db.gestione_db import ottieni_storico_asset_globale

def run_monte_carlo_simulation(
    portfolio_assets: List[Dict],
    years: int = 10,
    n_simulations: int = 1000,
    initial_portfolio_value: float = 0.0
) -> Dict:
    """
    Esegue una simulazione Monte Carlo sul portafoglio fornito.

    Args:
        portfolio_assets: Lista di dizionari {'ticker': str, 'quantita': float, 'prezzo_attuale': float}
        years: Numero di anni di proiezione
        n_simulations: Numero di simulazioni da eseguire
        initial_portfolio_value: Valore iniziale totale (opzionale, se 0 calcolato dagli asset)

    Returns:
        Dizionario con i risultati della simulazione (percentili, date, statistiche finali)
    """
    if not portfolio_assets:
        return {"error": "Il portafoglio è vuoto."}

    # 1. Preparazione Dati
    tickers = [asset['ticker'] for asset in portfolio_assets]
    
    # Calcola pesi portafoglio
    values = np.array([asset['quantita'] * asset['prezzo_attuale'] for asset in portfolio_assets])
    total_value = np.sum(values)
    
    if initial_portfolio_value > 0:
        # Se fornito valore esplicito (es. cached), usalo come base, ma mantieni pesi relativi
        simulation_start_value = initial_portfolio_value
    else:
        simulation_start_value = total_value

    if total_value == 0:
        weights = np.ones(len(tickers)) / len(tickers) # Fallback pesi uguali se valore 0
    else:
        weights = values / total_value

    # 2. Recupero Storico e Calcolo Rendimenti
    data_frames = {}
    min_date = None
    
    # Cerchiamo di avere almeno 1-2 anni di dati comuni
    start_date_limit = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')

    for ticker in tickers:
        storico = ottieni_storico_asset_globale(ticker, data_inizio=start_date_limit)
        if not storico:
            continue
            
        df = pd.DataFrame(storico)
        df['data'] = pd.to_datetime(df['data'])
        df.set_index('data', inplace=True)
        df.sort_index(inplace=True)
        
        # Rinomina la colonna prezzi col ticker
        data_frames[ticker] = df['prezzo_chiusura']

    if not data_frames:
        return {"error": "Nessun dato storico disponibile per gli asset selezionati."}

    # Combina in un unico DataFrame allineato per data
    price_data = pd.concat(data_frames.values(), axis=1, keys=data_frames.keys()).dropna()
    
    if price_data.empty or len(price_data) < 30: # Almeno un mese di dati comuni
        return {"error": "Dati storici insufficienti o non sovrapposti per gli asset selezionati."}

    # Filtra pesi solo per asset con dati disponibili
    available_tickers = price_data.columns.tolist()
    available_indices = [tickers.index(t) for t in available_tickers]
    available_weights = weights[available_indices]
    
    # Rinormalizza pesi
    if np.sum(available_weights) > 0:
        available_weights = available_weights / np.sum(available_weights)
    else:
        available_weights = np.ones(len(available_tickers)) / len(available_tickers)

    # 2. b) Resampling Mensile per coerenza storica (25 anni vs 5 anni)
    # Poiché abbiamo dati misti (mensili vecchi, giornalieri nuovi), normalizziamo tutto a MENSILE.
    # Questo evita di calcolare volatilità errate mischiando periodi diversi.
    price_data = price_data.resample('ME').last().ffill().dropna()
    
    if price_data.empty or len(price_data) < 12: # Almeno un anno
        return {"error": "Dati storici insufficienti dopo il ricampionamento mensile."}

    # 3. Calcolo Statistiche Log-Rendimenti (Mensili)
    log_returns = np.log(price_data / price_data.shift(1)).dropna()
    
    if log_returns.empty:
         return {"error": "Impossibile calcolare i rendimenti (dati insufficienti)."}

    # Media e Covarianza (Mensili)
    mean_monthly_returns = log_returns.mean()
    cov_matrix = log_returns.cov()

    # 4. Simulazione Monte Carlo (Passi Mensili)
    months_per_year = 12
    total_steps = years * months_per_year
    
    # Genera rendimenti casuali normali
    # L = Cholesky decomposition della matrice di covarianza mensile
    try:
        L = np.linalg.cholesky(cov_matrix)
    except np.linalg.LinAlgError:
        # Fallback per matrici non positive definite (raro ma possibile con pochi dati)
        return {"error": "Errore matematico nella matrice di covarianza (dati insufficienti o colineari)."}

    # Random shocks: (steps, simulations, num_assets)
    Z = np.random.normal(0.0, 1.0, (total_steps, n_simulations, len(available_tickers)))
    
    # Correlated monthly returns
    monthly_returns_sim = mean_monthly_returns.values[np.newaxis, np.newaxis, :] + np.einsum('ijk,lk->ijl', Z, L)

    # 5. Calcolo Percorsi Portafoglio
    # portfolio_sim_returns shape: (steps, simulations)
    portfolio_sim_returns = np.dot(monthly_returns_sim, available_weights)
    
    # Cumulative returns
    cum_returns = np.exp(np.cumsum(portfolio_sim_returns, axis=0))
    
    # Portfolio paths
    portfolio_paths = simulation_start_value * np.vstack([np.ones((1, n_simulations)), cum_returns])
    
    # 6. Estrazione Percentili
    percentiles = [10, 50, 90]
    results_per_step = np.percentile(portfolio_paths, percentiles, axis=1)
    
    # Date per il grafico (Mensili)
    # indices va da 0 a total_steps
    step_size = max(1, total_steps // 50) 
    indices = np.arange(0, total_steps + 1, step_size)
    
    current_month = datetime.now().replace(day=1)
    dates = []
    for i in indices:
        # Aggiungi i mesi alla data corrente
        future_date = current_month + pd.DateOffset(months=int(i))
        dates.append(future_date)
        
    dates_str = [d.strftime('%Y-%m') for d in dates]
    
    p10 = results_per_step[0, indices]
    p50 = results_per_step[1, indices]
    p90 = results_per_step[2, indices]

    final_values = {
        "p10": float(results_per_step[0, -1]),
        "p50": float(results_per_step[1, -1]),
        "p90": float(results_per_step[2, -1])
    }
    
    # Calcolo CAGR atteso (Geometric Mean Return)
    total_return = final_values["p50"] / simulation_start_value
    cagr = (total_return ** (1/years)) - 1 if years > 0 else 0

    return {
        "dates": dates_str,
        "p10": p10.tolist(),
        "p50": p50.tolist(),
        "p90": p90.tolist(),
        "final_values": final_values,
        "initial_value": simulation_start_value,
        "cagr_percent": cagr * 100,
        "years": years,
        "simulations": n_simulations
    }
