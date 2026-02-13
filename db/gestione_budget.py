"""
Funzioni budget: limiti, storico, analisi mensile/annuale
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
from utils.logger import setup_logger
from utils.crypto_manager import CryptoManager
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
import os

logger = setup_logger(__name__)
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse as parse_date
import json

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code, _get_system_keys,
    HASH_SALT, SYSTEM_FERNET_KEY, SERVER_SECRET_KEY,
    crypto as _crypto_instance
)


def get_impostazioni_budget_famiglia(id_famiglia: str, anno: int = None, mese: int = None) -> Dict[str, Union[float, str]]:
    """
    Recupera le impostazioni del budget famiglia.
    Se anno e mese sono forniti, recupera dallo storico.
    """
    import datetime
    today = datetime.date.today()
    is_current = (anno is None or (anno == today.year and mese == today.month))
    
    if is_current:
        return {
            'entrate_mensili': float(get_configurazione('budget_entrate_mensili', id_famiglia) or 0),
            'risparmio_tipo': get_configurazione('budget_risparmio_tipo', id_famiglia) or 'percentuale',
            'risparmio_valore': float(get_configurazione('budget_risparmio_valore', id_famiglia) or 0)
        }
    else:
        chiave_base = f"budget_storico_{anno}_{mese:02d}"
        return {
            'entrate_mensili': float(get_configurazione(f"{chiave_base}_entrate", id_famiglia) or 0),
            'risparmio_tipo': get_configurazione(f"{chiave_base}_risparmio_tipo", id_famiglia) or 'percentuale',
            'risparmio_valore': float(get_configurazione(f"{chiave_base}_risparmio_valore", id_famiglia) or 0)
        }

def set_impostazioni_budget_famiglia(id_famiglia: str, entrate_mensili: float, risparmio_tipo: str, risparmio_valore: float, anno: int = None, mese: int = None) -> bool:
    """
    Salva le impostazioni del budget famiglia.
    Se anno e mese sono forniti, salva nello storico.
    """
    try:
        import datetime
        today = datetime.date.today()
        is_current = (anno is None or (anno == today.year and mese == today.month))
        
        if is_current:
            set_configurazione('budget_entrate_mensili', str(entrate_mensili), id_famiglia)
            set_configurazione('budget_risparmio_tipo', risparmio_tipo, id_famiglia)
            set_configurazione('budget_risparmio_valore', str(risparmio_valore), id_famiglia)
        else:
            chiave_base = f"budget_storico_{anno}_{mese:02d}"
            set_configurazione(f"{chiave_base}_entrate", str(entrate_mensili), id_famiglia)
            set_configurazione(f"{chiave_base}_risparmio_tipo", risparmio_tipo, id_famiglia)
            set_configurazione(f"{chiave_base}_risparmio_valore", str(risparmio_valore), id_famiglia)
        return True
    except Exception as e:
        logger.error(f"Errore salvataggio impostazioni budget: {e}")
        return False

        return False

def calcola_entrate_mensili_famiglia(id_famiglia: str, anno: int, mese: int, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> float:
    """
    Calcola la somma delle transazioni categorizzate come "Entrate" 
    per tutti i membri della famiglia nel mese specificato.
    Cerca la categoria con nome contenente "Entrat" (case insensitive).
    """
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Prima troviamo le categorie "Entrate" della famiglia
            # Le categorie potrebbero essere criptate, quindi le recuperiamo tutte
            cur.execute("""
                SELECT id_categoria, nome_categoria 
                FROM Categorie 
                WHERE id_famiglia = %s
            """, (id_famiglia,))
            categorie = cur.fetchall()
            
            # Decrypt e cerca "Entrat" nel nome
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            id_categorie_entrate = []
            for cat in categorie:
                nome = cat['nome_categoria']
                if family_key:
                    nome = _decrypt_if_key(nome, family_key, crypto)
                if nome and 'entrat' in nome.lower():
                    id_categorie_entrate.append(cat['id_categoria'])
            
            if not id_categorie_entrate:
                return 0.0
            
            # Ottieni le sottocategorie di queste categorie
            placeholders = ','.join(['%s'] * len(id_categorie_entrate))
            cur.execute(f"""
                SELECT id_sottocategoria 
                FROM Sottocategorie 
                WHERE id_categoria IN ({placeholders})
            """, tuple(id_categorie_entrate))
            id_sottocategorie = [row['id_sottocategoria'] for row in cur.fetchall()]
            
            if not id_sottocategorie:
                return 0.0
            
            # Somma le transazioni personali con queste sottocategorie, ESCLUDENDO i Fondi Pensione
            placeholders_sub = ','.join(['%s'] * len(id_sottocategorie))
            cur.execute(f"""
                SELECT COALESCE(SUM(T.importo), 0.0) as totale
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND T.id_sottocategoria IN ({placeholders_sub})
                  AND T.data BETWEEN %s AND %s
                  AND C.tipo != 'Fondo Pensione'
            """, (id_famiglia, *id_sottocategorie, data_inizio, data_fine))
            totale_personali = cur.fetchone()['totale'] or 0.0
            
            # Somma le transazioni condivise con queste sottocategorie
            cur.execute(f"""
                SELECT COALESCE(SUM(TC.importo), 0.0) as totale
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND TC.id_sottocategoria IN ({placeholders_sub})
                  AND TC.data BETWEEN %s AND %s
            """, (id_famiglia, *id_sottocategorie, data_inizio, data_fine))
            totale_condivise = cur.fetchone()['totale'] or 0.0
            
            return totale_personali + totale_condivise
    except Exception as e:
        logger.error(f"Errore calcola_entrate_mensili_famiglia: {e}")
        return 0.0

def ottieni_totale_budget_allocato(id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> float:
    """
    Ritorna il totale dei budget assegnati alle sottocategorie (escluse Entrate).
    """
    try:
        budget_list = ottieni_budget_famiglia(id_famiglia, master_key_b64, id_utente)
        # Escludiamo esplicitamente le categorie di entrata dal totale budget
        return sum(b.get('importo_limite', 0) for b in budget_list if "ENTRAT" not in (b.get('nome_categoria') or "").upper())
    except Exception as e:
        logger.error(f"Errore calcolo totale budget allocato: {e}")
        return 0.0

def ottieni_totale_budget_storico(id_famiglia: str, anno: int, mese: int, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> float:
    """
    Ritorna il totale dei budget assegnati per un mese specifico dallo storico.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        key_to_use = family_key if family_key else master_key

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT BS.importo_limite, C.nome_categoria 
                FROM Budget_Storico BS
                JOIN Sottocategorie S ON BS.id_sottocategoria = S.id_sottocategoria
                JOIN Categorie C ON S.id_categoria = C.id_categoria
                WHERE BS.id_famiglia = %s AND BS.anno = %s AND BS.mese = %s
            """, (id_famiglia, anno, mese))
            
            rows = cur.fetchall()
            if not rows:
                return 0.0
                
            totale = 0.0
            for row in rows:
                enc_limite = row['importo_limite']
                nome_cat = row['nome_categoria']
                
                # Decripta nome categoria per controllo esclusione
                if family_key:
                    try:
                        nome_cat = _decrypt_if_key(nome_cat, family_key, crypto, silent=True)
                    except: pass
                
                if nome_cat and "ENTRAT" in nome_cat.upper():
                    continue

                try:
                    limite_str = _decrypt_if_key(enc_limite, key_to_use, crypto)
                    totale += float(limite_str)
                except Exception as e:
                    pass
            return totale
            
    except Exception as e:
        logger.error(f"Errore calcolo totale budget storico: {e}")
        return 0.0

def salva_impostazioni_budget_storico(id_famiglia: str, anno: int, mese: int, entrate_mensili: float, risparmio_tipo: str, risparmio_valore: float) -> bool:
    """
    Salva le impostazioni budget nello storico per un mese specifico.
    Usa la tabella Configurazioni con chiavi contenenti anno e mese.
    """
    try:
        chiave_base = f"budget_storico_{anno}_{mese:02d}"
        set_configurazione(f"{chiave_base}_entrate", str(entrate_mensili), id_famiglia)
        set_configurazione(f"{chiave_base}_risparmio_tipo", risparmio_tipo, id_famiglia)
        set_configurazione(f"{chiave_base}_risparmio_valore", str(risparmio_valore), id_famiglia)
        return True
    except Exception as e:
        logger.error(f"Errore salvataggio storico impostazioni budget: {e}")
        return False

def ottieni_impostazioni_budget_storico(id_famiglia: str, anno: int, mese: int) -> Optional[Dict[str, Union[float, str]]]:
    """
    Recupera le impostazioni budget dallo storico per un mese specifico.
    Se non esistono, ritorna None.
    """
    chiave_base = f"budget_storico_{anno}_{mese:02d}"
    entrate = get_configurazione(f"{chiave_base}_entrate", id_famiglia)
    
    if entrate is None:
        return None  # Non esiste storico per questo mese
    
    return {
        'entrate_mensili': float(entrate or 0),
        'risparmio_tipo': get_configurazione(f"{chiave_base}_risparmio_tipo", id_famiglia) or 'percentuale',
        'risparmio_valore': float(get_configurazione(f"{chiave_base}_risparmio_valore", id_famiglia) or 0)
    }

def ottieni_dati_analisi_mensile(id_famiglia: str, anno: int, mese: int, master_key_b64: str, id_utente: str) -> Optional[Dict[str, Any]]:
    """
    Recupera i dati completi per l'analisi mensile del budget.
    Include entrate, spese totali, budget totale, risparmio, delta e ripartizione categorie.
    """
    try:
        # 1. Recupera Entrate REALI (somma transazioni categoria Entrate)
        entrate = calcola_entrate_mensili_famiglia(id_famiglia, anno, mese, master_key_b64, id_utente)
        
        # 1b. Recupera Impostazioni (per risparmio)
        impostazioni_storico = ottieni_impostazioni_budget_storico(id_famiglia, anno, mese)
        if not impostazioni_storico:
            impostazioni_storico = get_impostazioni_budget_famiglia(id_famiglia)
        
        entrate_stimate = impostazioni_storico['entrate_mensili']

        # 2. Calcola Spese Totali e Spese per Categoria (con decriptazione)
        data_inizio = f"{anno}-{mese:02d}-01"
        ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
        data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"
        
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        spese_per_categoria = []
        spese_totali = 0.0

        with get_db_connection() as con:
            cur = con.cursor()
            
            # Query UNICA per spese personali raggruppate per sottocategoria
            # Esclude i giroconti (transazioni senza sottocategoria)
            cur.execute("""
                SELECT T.id_sottocategoria, SUM(T.importo) as totale
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND T.data BETWEEN %s AND %s
                  AND T.importo < 0
                  AND T.id_sottocategoria IS NOT NULL
                GROUP BY T.id_sottocategoria
            """, (id_famiglia, data_inizio, data_fine))
            spese_personali = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}

            # Query UNICA per spese condivise raggruppate per sottocategoria
            # Esclude i giroconti (transazioni senza sottocategoria)
            cur.execute("""
                SELECT TC.id_sottocategoria, SUM(TC.importo) as totale
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND TC.data BETWEEN %s AND %s
                  AND TC.importo < 0
                  AND TC.id_sottocategoria IS NOT NULL
                GROUP BY TC.id_sottocategoria
            """, (id_famiglia, data_inizio, data_fine))
            spese_condivise = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}

            # Uniamo le spese
            tutte_spese_map = spese_personali.copy()
            for id_sub, importo in spese_condivise.items():
                tutte_spese_map[id_sub] = tutte_spese_map.get(id_sub, 0.0) + importo
            
            # spese_totali = sum(tutte_spese_map.values()) # OLD LOGIC: Included everything, even Income corrections or Orphans

            spese_totali = 0.0

            # Ora aggreghiamo per Categoria e decriptiamo i nomi
            cur.execute("SELECT id_categoria, nome_categoria FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
            raw_categorie = cur.fetchall()
            
            for raw_cat in raw_categorie:
                cat_id = raw_cat['id_categoria']
                nome_crip = raw_cat['nome_categoria']
                nome_chiaro = nome_crip
                if family_key:
                    nome_chiaro = _decrypt_if_key(nome_crip, family_key, crypto)
                
                # Cerca sottocategorie per questa categoria
                cur.execute("SELECT id_sottocategoria FROM Sottocategorie WHERE id_categoria = %s", (cat_id,))
                subs = [row['id_sottocategoria'] for row in cur.fetchall()]
                
                tot_cat = sum(tutte_spese_map.get(sub_id, 0.0) for sub_id in subs)
                
                if tot_cat > 0:
                    # FIX: Escludi categorie "Entrate" (che contengono storni/correzioni) dal totale SPESE
                    # ed escludile dalla lista per coerenza (già fatto dalla UI, ma lo facciamo anche qui)
                    if "entrat" not in nome_chiaro.lower():
                        spese_totali += tot_cat
                        spese_per_categoria.append({
                            'nome_categoria': nome_chiaro,
                            'importo': tot_cat
                        })

        # Calcola percentuali
        for item in spese_per_categoria:
            item['percentuale'] = (item['importo'] / spese_totali * 100) if spese_totali > 0 else 0

        # 3. Budget Totale
        today = datetime.date.today()
        # Se stiamo guardando il mese corrente o futuro, prendiamo il budget allocato ATTUALE
        if anno > today.year or (anno == today.year and mese >= today.month):
             budget_totale = ottieni_totale_budget_allocato(id_famiglia, master_key_b64, id_utente)
        else:
             # Per i mesi passati, prendiamo lo storico
             budget_totale = ottieni_totale_budget_storico(id_famiglia, anno, mese, master_key_b64, id_utente)
             
             # Fallback opzionale: se lo storico è vuoto (es. non ancora salvato), proviamo a prendere quello corrente?
             # Per ora lasciamo 0 o quello che trova, per coerenza storica.
             if budget_totale == 0 and anno == today.year and mese == today.month:
                 # Caso limite: siamo nel mese corrente ma lo storico non c'è ancora.
                 budget_totale = ottieni_totale_budget_allocato(id_famiglia, master_key_b64, id_utente)

        risparmio = entrate - spese_totali
        delta = budget_totale - spese_totali
        
        # 4. Recupera dati annuali per confronto
        dati_annuali = ottieni_dati_analisi_annuale(id_famiglia, anno, master_key_b64, id_utente, include_prev_year=False)

        return {
            'entrate': entrate,
            'entrate_stimate': entrate_stimate,
            'spese_totali': spese_totali,
            'budget_totale': budget_totale,
            'risparmio': entrate - spese_totali,
            'delta_budget_spese': budget_totale - spese_totali,
            'spese_per_categoria': sorted(spese_per_categoria, key=lambda x: x['importo'], reverse=True),
            'dati_confronto': dati_annuali
        }

    except Exception as e:
        logger.error(f"ottieni_dati_analisi_mensile: {e}")
        return None


def ottieni_dati_analisi_annuale(id_famiglia: str, anno: int, master_key_b64: str, id_utente: str, include_prev_year: bool = True) -> Optional[Dict[str, Any]]:
    """
    Recupera i dati completi per l'analisi annuale.
    Media spese, media budget, media differenza, spese categorie annuali.
    """
    try:
        # Prepara range date
        data_inizio_anno = f"{anno}-01-01"
        data_fine_anno = f"{anno}-12-31"

        # Recupera tutte le spese dell'anno per calcolare totali e medie
        totale_spese_annuali = 0.0
        spese_per_categoria_annuali = []
        
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            
            # --- SPESE ---
            # Personali (esclude giroconti)
            cur.execute("""
                SELECT T.id_sottocategoria, SUM(T.importo) as totale
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND T.data BETWEEN %s AND %s
                  AND T.importo < 0
                  AND T.id_sottocategoria IS NOT NULL
                GROUP BY T.id_sottocategoria
            """, (id_famiglia, data_inizio_anno, data_fine_anno))
            spese_personali = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}
            
            # Condivise (esclude giroconti)
            cur.execute("""
                SELECT TC.id_sottocategoria, SUM(TC.importo) as totale
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND TC.data BETWEEN %s AND %s
                  AND TC.importo < 0
                  AND TC.id_sottocategoria IS NOT NULL
                GROUP BY TC.id_sottocategoria
            """, (id_famiglia, data_inizio_anno, data_fine_anno))
            spese_condivise = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}
            
            # Unione
            tutte_spese_map = spese_personali.copy()
            for id_sub, importo in spese_condivise.items():
                tutte_spese_map[id_sub] = tutte_spese_map.get(id_sub, 0.0) + importo
            
            totale_spese_annuali = sum(tutte_spese_map.values())
            
            # Aggregazione Categorie
            cur.execute("SELECT id_categoria, nome_categoria FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
            raw_categorie = cur.fetchall()
            
            for raw_cat in raw_categorie:
                cat_id = raw_cat['id_categoria']
                nome_crip = raw_cat['nome_categoria']
                nome_chiaro = nome_crip
                if family_key:
                    nome_chiaro = _decrypt_if_key(nome_crip, family_key, crypto)
                
                cur.execute("SELECT id_sottocategoria FROM Sottocategorie WHERE id_categoria = %s", (cat_id,))
                subs = [row['id_sottocategoria'] for row in cur.fetchall()]
                
                tot_cat = sum(tutte_spese_map.get(sub_id, 0.0) for sub_id in subs)
                if tot_cat > 0:
                    spese_per_categoria_annuali.append({
                        'nome_categoria': nome_chiaro,
                        'importo': tot_cat
                    })

        # Percentuali
        for item in spese_per_categoria_annuali:
            item['percentuale'] = (item['importo'] / totale_spese_annuali * 100) if totale_spese_annuali > 0 else 0

        # --- MEDIE E BUDGET ---
        # Determina i mesi attivi (quelli con spese registrate)
        mesi_attivi = set()
        
        # Mesi da spese personali
        cur.execute("""
            SELECT DISTINCT EXTRACT(MONTH FROM T.data::DATE) as mese
            FROM Transazioni T
            JOIN Conti C ON T.id_conto = C.id_conto
            JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
            WHERE AF.id_famiglia = %s
              AND T.data BETWEEN %s AND %s
              AND T.importo < 0
        """, (id_famiglia, data_inizio_anno, data_fine_anno))
        for row in cur.fetchall():
            mesi_attivi.add(int(row['mese']))

        # Mesi da spese condivise
        cur.execute("""
            SELECT DISTINCT EXTRACT(MONTH FROM TC.data::DATE) as mese
            FROM TransazioniCondivise TC
            JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
            WHERE CC.id_famiglia = %s
              AND TC.data BETWEEN %s AND %s
              AND TC.importo < 0
        """, (id_famiglia, data_inizio_anno, data_fine_anno))
        for row in cur.fetchall():
            mesi_attivi.add(int(row['mese']))
            
        numero_mesi_attivi = len(mesi_attivi)
        
        # Se non ci sono mesi attivi, usiamo 12 come standard per evitare divisioni per zero o dati vuoti
        # Oppure mostriamo tutto a 0? Meglio standard per vedere il budget annuale teorico.
        # User request: "se ho compilato...". Se 0, non ho compilato.
        use_active_months = numero_mesi_attivi > 0
        divisor = numero_mesi_attivi if use_active_months else 12

        budget_mensile_corrente = ottieni_totale_budget_allocato(id_famiglia, master_key_b64, id_utente)
        
        entrate_totali_periodo = 0.0
        budget_totale_periodo = 0.0 
        
        imps_correnti = get_impostazioni_budget_famiglia(id_famiglia)
        entrate_std = imps_correnti['entrate_mensili']

        # Se usiamo i mesi attivi, sommiamo budget ed entrate SOLO per quei mesi.
        # Altrimenti (fallback), sommiamo per tutto l'anno (1-12)
        mesi_da_considerare = mesi_attivi if use_active_months else range(1, 13)

        for m in mesi_da_considerare:
            imp_storico = ottieni_impostazioni_budget_storico(id_famiglia, anno, m)
            if imp_storico:
                entrate_totali_periodo += imp_storico['entrate_mensili']
            else:
                entrate_totali_periodo += entrate_std
            
            # BUDGET: Use historical if available
            today = datetime.date.today()
            if anno > today.year or (anno == today.year and m > today.month):
                 # Future: use current
                 budget_totale_periodo += budget_mensile_corrente
            elif anno == today.year and m == today.month:
                 # Current month: try historical, else current
                 b_storico = ottieni_totale_budget_storico(id_famiglia, anno, m, master_key_b64, id_utente)
                 if b_storico == 0:
                     b_storico = budget_mensile_corrente
                 budget_totale_periodo += b_storico
            else:
                 # Past month: use historical
                 budget_totale_periodo += ottieni_totale_budget_storico(id_famiglia, anno, m, master_key_b64, id_utente) 

        media_spese_mensili = totale_spese_annuali / divisor
        media_budget_mensile = budget_totale_periodo / divisor
        media_entrate_mensili = entrate_totali_periodo / divisor

        # --- RISPARMIO e DELTA ---
        media_risparmio = media_entrate_mensili - media_spese_mensili
        media_delta = media_budget_mensile - media_spese_mensili

        for item in spese_per_categoria_annuali:
            # Calcola la media mensile per ogni categoria
            item['importo_media'] = item['importo'] / divisor
            item['percentuale'] = (item['importo_media'] / media_spese_mensili * 100) if media_spese_mensili > 0 else 0

        # Ordina per importo medio decrescente
        spese_per_categoria_annuali = sorted(spese_per_categoria_annuali, key=lambda x: x['importo_media'], reverse=True)

        dati_anno_precedente = None
        if include_prev_year:
            dati_anno_precedente = ottieni_dati_analisi_annuale(
                id_famiglia, anno - 1, master_key_b64, id_utente, include_prev_year=False
            )
            # Se l'anno precedente non ha mesi attivi (nessuna spesa), non considerarlo valido per il confronto
            if dati_anno_precedente and dati_anno_precedente.get('numero_mesi_attivi', 0) == 0:
                 dati_anno_precedente = None

        return {
            'media_entrate_mensili': media_entrate_mensili,
            'media_spese_mensili': media_spese_mensili,
            'media_budget_mensile': media_budget_mensile,
            'media_differenza_entrate_spese': media_risparmio,
            'media_delta_budget_spese': media_delta,
            'spese_per_categoria_annuali': spese_per_categoria_annuali,
            'numero_mesi_attivi': numero_mesi_attivi,
            'dati_confronto': dati_anno_precedente
        }

    except Exception as e:
        print(f"[ERRORE] ottieni_dati_analisi_annuale: {e}")
        return None



# --- Funzioni Budget ---
def imposta_budget(id_famiglia, id_sottocategoria, importo_limite, master_key_b64=None, id_utente=None, anno=None, mese=None):
    try:
        import datetime
        today = datetime.date.today()
        is_current = (anno is None or (anno == today.year and mese == today.month))

        # Encrypt importo_limite with family_key
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        family_key = None
        if master_key and id_utente:
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        key_to_use = family_key if family_key else master_key
        encrypted_importo = _encrypt_if_key(str(importo_limite), key_to_use, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            if is_current:
                cur.execute("""
                            INSERT INTO Budget (id_famiglia, id_sottocategoria, importo_limite, periodo)
                            VALUES (%s, %s, %s, 'Mensile') ON CONFLICT(id_famiglia, id_sottocategoria, periodo) DO
                            UPDATE SET importo_limite = excluded.importo_limite
                            """, (id_famiglia, id_sottocategoria, encrypted_importo))
                
                # Auto-update history for current month
                try:
                    now = datetime.datetime.now()
                    trigger_budget_history_update(id_famiglia, now, master_key_b64, id_utente, cursor=cur)
                except Exception as e:
                    print(f"[WARN] Failed auto-update in imposta_budget: {e}")
            else:
                # Recupera nome sottocategoria per lo storico (se possibile)
                cur.execute("SELECT nome_sottocategoria FROM Sottocategorie WHERE id_sottocategoria = %s", (id_sottocategoria,))
                row_sub = cur.fetchone()
                nome_sub = row_sub['nome_sottocategoria'] if row_sub else "Sconosciuta"

                cur.execute("""
                            INSERT INTO Budget_Storico (id_famiglia, id_sottocategoria, nome_sottocategoria, anno, mese,
                                                        importo_limite, importo_speso)
                            VALUES (%s, %s, %s, %s, %s, %s, '0.0') ON CONFLICT(id_famiglia, id_sottocategoria, anno, mese) DO
                            UPDATE SET importo_limite = excluded.importo_limite
                            """, (id_famiglia, id_sottocategoria, nome_sub, anno, mese, encrypted_importo))

            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'impostazione del budget: {e}")
        return False

def ottieni_budget_famiglia(id_famiglia, master_key_b64=None, id_utente=None, anno=None, mese=None):
    try:
        import datetime
        today = datetime.date.today()
        is_current = (anno is None or (anno == today.year and mese == today.month))

        with get_db_connection() as con:
            cur = con.cursor()
            if is_current:
                cur.execute("""
                            SELECT B.id_budget, B.id_sottocategoria, C.nome_categoria, S.nome_sottocategoria, B.importo_limite
                            FROM Budget B
                                     JOIN Sottocategorie S ON B.id_sottocategoria = S.id_sottocategoria
                                     JOIN Categorie C ON S.id_categoria = C.id_categoria
                            WHERE B.id_famiglia = %s
                              AND B.periodo = 'Mensile'
                            """, (id_famiglia,))
            else:
                cur.execute("""
                            SELECT BS.id_storico as id_budget, BS.id_sottocategoria, C.nome_categoria, BS.nome_sottocategoria, BS.importo_limite
                            FROM Budget_Storico BS
                                     JOIN Sottocategorie S ON BS.id_sottocategoria = S.id_sottocategoria
                                     JOIN Categorie C ON S.id_categoria = C.id_categoria
                            WHERE BS.id_famiglia = %s AND BS.anno = %s AND BS.mese = %s
                            """, (id_famiglia, anno, mese))
            
            rows = [dict(row) for row in cur.fetchall()]
            
            # Decrypt
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            for row in rows:
                key_to_use = family_key if family_key else master_key
                decrypted = _decrypt_if_key(row['importo_limite'], key_to_use, crypto, silent=True)
                
                try:
                    row['importo_limite'] = float(decrypted)
                except (ValueError, TypeError):
                    row['importo_limite'] = 0.0
                
                # Decrypt category and subcategory names (if encrypted)
                if family_key:
                    row['nome_categoria'] = _decrypt_if_key(row['nome_categoria'], family_key, crypto)
                    row['nome_sottocategoria'] = _decrypt_if_key(row['nome_sottocategoria'], family_key, crypto)
            
            rows.sort(key=lambda x: (x['nome_categoria'] or "", x['nome_sottocategoria'] or ""))
            return rows
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero budget: {e}")
        return []


def ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese, master_key_b64=None, id_utente=None):
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                SELECT
                    C.id_categoria,
                    C.nome_categoria,
                    S.id_sottocategoria,
                    S.nome_sottocategoria,
                    COALESCE(BS.importo_limite, B.importo_limite, '0.0') as importo_limite,
                    COALESCE(T_SPESE.spesa_totale, 0.0) as spesa_totale
                FROM Categorie C
                JOIN Sottocategorie S ON C.id_categoria = S.id_categoria
                LEFT JOIN Budget_Storico BS ON S.id_sottocategoria = BS.id_sottocategoria 
                    AND BS.id_famiglia = C.id_famiglia 
                    AND BS.anno = %s 
                    AND BS.mese = %s
                LEFT JOIN Budget B ON S.id_sottocategoria = B.id_sottocategoria 
                    AND B.id_famiglia = C.id_famiglia 
                    AND B.periodo = 'Mensile'
                LEFT JOIN (
                    SELECT id_sottocategoria, SUM(spesa_totale) as spesa_totale
                    FROM (
                        SELECT
                            T.id_sottocategoria,
                            SUM(T.importo) as spesa_totale
                        FROM Transazioni T
                        JOIN Conti CO ON T.id_conto = CO.id_conto
                        JOIN Appartenenza_Famiglia AF ON CO.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s AND T.data BETWEEN %s AND %s
                          AND T.id_sottocategoria IS NOT NULL
                        GROUP BY T.id_sottocategoria
                        UNION ALL
                        SELECT
                            TC.id_sottocategoria,
                            SUM(TC.importo) as spesa_totale
                        FROM TransazioniCondivise TC
                        JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                        WHERE CC.id_famiglia = %s AND TC.data BETWEEN %s AND %s
                          AND TC.id_sottocategoria IS NOT NULL
                        GROUP BY TC.id_sottocategoria
                    ) AS U
                    GROUP BY id_sottocategoria
                ) AS T_SPESE ON S.id_sottocategoria = T_SPESE.id_sottocategoria
                WHERE C.id_famiglia = %s
                ORDER BY C.nome_categoria, S.nome_sottocategoria;
            """, (anno, mese, id_famiglia, data_inizio, data_fine, id_famiglia, data_inizio, data_fine, id_famiglia))
            
            riepilogo = {}
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            for row in cur.fetchall():
                cat_id = row['id_categoria']
                if cat_id not in riepilogo:
                    # Decrypt category name
                    cat_name = row['nome_categoria']
                    if family_key:
                        cat_name = _decrypt_if_key(cat_name, family_key, crypto)
                        
                    riepilogo[cat_id] = {
                        'nome_categoria': cat_name,
                        'importo_limite_totale': 0,
                        'spesa_totale_categoria': 0,
                        'sottocategorie': []
                    }
                
                spesa = -row['spesa_totale']
                
                # Decrypt importo_limite (Try Family Key, then Master Key)
                if family_key:
                    decrypted_limite = _decrypt_if_key(row['importo_limite'], family_key, crypto, silent=True)
                    # If decryption failed (returns [ENCRYPTED]) and it looks encrypted, try master_key
                    if decrypted_limite == "[ENCRYPTED]" and isinstance(row['importo_limite'], str) and row['importo_limite'].startswith("gAAAAA"):
                         decrypted_limite = _decrypt_if_key(row['importo_limite'], master_key, crypto, silent=True)
                else:
                    decrypted_limite = row['importo_limite'] # Cannot decrypt without family key
                try:
                    limite = float(decrypted_limite)
                except (ValueError, TypeError):
                    limite = 0.0

                riepilogo[cat_id]['importo_limite_totale'] += limite
                riepilogo[cat_id]['spesa_totale_categoria'] += spesa
                
                # Decrypt subcategory name
                sub_name = row['nome_sottocategoria']
                if family_key:
                    sub_name = _decrypt_if_key(sub_name, family_key, crypto, silent=True)

                riepilogo[cat_id]['sottocategorie'].append({
                    'id_sottocategoria': row['id_sottocategoria'],
                    'nome_sottocategoria': sub_name,
                    'importo_limite': limite,
                    'spesa_totale': spesa,
                    'rimanente': limite - spesa
                })
            
            # Calcola il rimanente totale per categoria
            for cat_id in riepilogo:
                riepilogo[cat_id]['rimanente_totale'] = riepilogo[cat_id]['importo_limite_totale'] - riepilogo[cat_id]['spesa_totale_categoria']
            
            # Sort categories and subcategories in Python
            # Convert dict to list of values for sorting, but we return a dict keyed by cat_id.
            # Actually, the caller expects a dict. But we can't sort a dict in place reliably across versions (though 3.7+ preserves insertion order).
            # Let's sort the subcategories list within each category.
            for cat_id in riepilogo:
                riepilogo[cat_id]['sottocategorie'].sort(key=lambda x: x['nome_sottocategoria'] or "")
            
            # To sort categories, we might need to return a sorted dict or list.
            # The current implementation returns a dict. The caller iterates over values.
            # Let's return a dict with sorted keys (insertion order).
            sorted_riepilogo = dict(sorted(riepilogo.items(), key=lambda item: item[1]['nome_categoria'] or ""))

            return sorted_riepilogo

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero riepilogo budget: {e}")
        return {}


def salva_budget_mese_corrente(id_famiglia, anno, mese, master_key_b64=None, id_utente=None):
    try:
        riepilogo_corrente = ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese, master_key_b64, id_utente)
        if not riepilogo_corrente:
            return False
            
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            dati_da_salvare = []
            # Salva per ogni sottocategoria
            for cat_id, cat_data in riepilogo_corrente.items():
                for sub_data in cat_data['sottocategorie']:
                    # Encrypt amounts
                    key_to_use = family_key if family_key else master_key
                    enc_limite = _encrypt_if_key(str(sub_data['importo_limite']), key_to_use, crypto)
                    enc_speso = _encrypt_if_key(str(abs(sub_data['spesa_totale'])), key_to_use, crypto)
                    
                    # Encrypt subcategory name (for history snapshot)
                    enc_sub_name = sub_data['nome_sottocategoria']
                    if family_key: # Re-encrypt if it was decrypted
                         enc_sub_name = _encrypt_if_key(sub_data['nome_sottocategoria'], family_key, crypto)

                    dati_da_salvare.append((
                        id_famiglia, sub_data['id_sottocategoria'], enc_sub_name,
                        anno, mese, enc_limite, enc_speso
                    ))
            
            cur.executemany("""
                            INSERT INTO Budget_Storico (id_famiglia, id_sottocategoria, nome_sottocategoria, anno, mese,
                                                        importo_limite, importo_speso)
                            VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT(id_famiglia, id_sottocategoria, anno, mese) DO
                            UPDATE SET importo_limite = excluded.importo_limite, importo_speso = excluded.importo_speso, nome_sottocategoria = excluded.nome_sottocategoria
                            """, dati_da_salvare)
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la storicizzazione del budget: {e}")
        return False


# --- Helper per Automazione Storico ---
def _get_famiglia_and_utente_from_conto(id_conto):
    try:
        with get_db_connection() as con:
             cur = con.cursor()
             # Get user and family from account
             cur.execute("""
                SELECT U.id_utente, AF.id_famiglia 
                FROM Conti C
                JOIN Utenti U ON C.id_utente = U.id_utente
                JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                WHERE C.id_conto = %s
             """, (id_conto,))
             res = cur.fetchone()
             if res:
                 return res['id_famiglia'], res['id_utente']
             return None, None
    except Exception as e:
        print(f"[ERRORE] _get_famiglia_and_utente_from_conto: {e}")
        return None, None

def trigger_budget_history_update(id_famiglia, date_obj, master_key_b64, id_utente):
    """Updates budget history for a specific month only if family and user are identified."""
    if not id_famiglia or not id_utente or not date_obj:
        return
    try:
        # Check if it looks like a date/datetime object
        if hasattr(date_obj, 'year') and hasattr(date_obj, 'month'):
            pass # It is already a valid date-like object
        else:
            # Assume it's a string or convertible to string
            date_str = str(date_obj)
            try:
                # Try standard format first
                parsed_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                try:
                    # Fallback to dateutil
                    parsed_date = parse_date(date_str)
                except Exception:
                    # Last resort: try today if parsing fails completely (shouldn't happen but prevents crash)
                    print(f"[WARN] Failed to parse date: '{date_str}', using today.")
                    parsed_date = datetime.date.today()
            date_obj = parsed_date
        
        # Now safely access .year and .month
        salva_budget_mese_corrente(id_famiglia, date_obj.year, date_obj.month, master_key_b64, id_utente)
    except Exception as e:
        print(f"[WARN] Failed to auto-update budget history. Data type: {type(date_obj)}. Error: {e}")



def storicizza_budget_retroattivo(id_famiglia, master_key_b64=None):
    """
    Storicizza automaticamente i budget per tutti i mesi passati con transazioni.
    Usa i limiti correnti dalla tabella Budget come baseline per i mesi storici.
    Questa funzione dovrebbe essere chiamata una sola volta per popolare Budget_Storico.
    """
    try:
        oggi = datetime.date.today()
        
        # Ottieni tutti i mesi con transazioni
        periodi = ottieni_anni_mesi_storicizzati(id_famiglia)
        if not periodi:
            print("Nessun periodo storico trovato.")
            return True
        
        mesi_storicizzati = 0
        mesi_saltati = 0
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            for periodo in periodi:
                anno = periodo['anno']
                mese = periodo['mese']
                
                # Salta il mese corrente (verrà storicizzato normalmente)
                if anno == oggi.year and mese == oggi.month:
                    continue
                
                # Salta i mesi futuri
                if anno > oggi.year or (anno == oggi.year and mese > oggi.month):
                    continue
                
                # Controlla se il mese è già storicizzato
                cur.execute("""
                    SELECT COUNT(*) as count FROM Budget_Storico 
                    WHERE id_famiglia = %s AND anno = %s AND mese = %s
                """, (id_famiglia, anno, mese))
                
                if cur.fetchone()['count'] > 0:
                    mesi_saltati += 1
                    continue
                
                # Storicizza il mese usando i limiti correnti
                if salva_budget_mese_corrente(id_famiglia, anno, mese, master_key_b64):
                    mesi_storicizzati += 1
                    print(f"  Storicizzato {anno}-{mese:02d}")
                else:
                    print(f"  Errore storicizzando {anno}-{mese:02d}")
        
        print(f"\nStoricizzazione retroattiva completata:")
        print(f"  - Mesi storicizzati: {mesi_storicizzati}")
        print(f"  - Mesi già presenti: {mesi_saltati}")
        return True
        
    except Exception as e:
        print(f"Errore durante la storicizzazione retroattiva: {e}")
        return False



def ottieni_anni_mesi_storicizzati(id_famiglia):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            # Query aggiornata per leggere i mesi da TUTTE le transazioni (personali e condivise)
            cur.execute("""
                SELECT DISTINCT anno, mese FROM (
                    -- Mesi da transazioni personali
                    SELECT
                        CAST(EXTRACT(YEAR FROM CAST(T.data AS DATE)) AS INTEGER) as anno,
                        CAST(EXTRACT(MONTH FROM CAST(T.data AS DATE)) AS INTEGER) as mese
                    FROM Transazioni T
                    JOIN Conti C ON T.id_conto = C.id_conto
                    JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                    WHERE AF.id_famiglia = %s

                    UNION

                    -- Mesi da transazioni condivise
                    SELECT
                        CAST(EXTRACT(YEAR FROM CAST(TC.data AS DATE)) AS INTEGER) as anno,
                        CAST(EXTRACT(MONTH FROM CAST(TC.data AS DATE)) AS INTEGER) as mese
                    FROM TransazioniCondivise TC
                    JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                    WHERE CC.id_famiglia = %s
                ) ORDER BY anno DESC, mese DESC
            """, (id_famiglia, id_famiglia))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero periodi storici: {e}")
        return []


def ottieni_periodi_budget_disponibili(id_famiglia) -> List[Dict[str, int]]:
    """
    Ritorna la lista di anni e mesi in cui è presente una configurazione budget (impostazioni o limiti).
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # 1. Da Budget_Storico e Configurazioni
            cur.execute("""
                SELECT DISTINCT anno, mese FROM (
                    SELECT anno, mese FROM Budget_Storico WHERE id_famiglia = %s
                    UNION
                    SELECT 
                        CAST(SPLIT_PART(chiave, '_', 3) AS INTEGER) as anno,
                        CAST(SPLIT_PART(chiave, '_', 4) AS INTEGER) as mese
                    FROM Configurazioni 
                    WHERE id_famiglia = %s AND chiave LIKE 'budget_storico_%%_entrate'
                ) AS periods 
                ORDER BY anno DESC, mese DESC
            """, (id_famiglia, id_famiglia))
            
            res = cur.fetchall()
            periodi = [dict(row) for row in res]
            
            # Aggiungiamo il mese corrente se non c'è già
            oggi = datetime.date.today()
            if not any(p['anno'] == oggi.year and p['mese'] == oggi.month for p in periodi):
                periodi.insert(0, {'anno': oggi.year, 'mese': oggi.month})
            
            return periodi
    except Exception as e:
        logger.error(f"Errore ottieni_periodi_budget_disponibili: {e}")
        return []


def ottieni_storico_budget_per_export(id_famiglia, lista_periodi, master_key_b64=None, id_utente=None):
    if not lista_periodi: return []
    placeholders = " OR ".join(["(anno = %s AND mese = %s)"] * len(lista_periodi))
    params = [id_famiglia] + [item for sublist in lista_periodi for item in sublist]
    
    # Decryption setup
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Budget_Storico has 'nome_sottocategoria'
            # Fetch raw values, decrypt and calculate in Python
            query = f"""
                SELECT anno, mese, nome_sottocategoria, importo_limite, importo_speso
                FROM Budget_Storico
                WHERE id_famiglia = %s AND ({placeholders})
                ORDER BY anno, mese, nome_sottocategoria
            """
            cur.execute(query, tuple(params))
            results = [dict(row) for row in cur.fetchall()]
            
            for row in results:
                # Decrypt subcategory name if needed
                if row.get('nome_sottocategoria'):
                     decrypted = _decrypt_if_key(row['nome_sottocategoria'], family_key, crypto, silent=True)
                     if not decrypted and family_key != master_key:
                         decrypted = _decrypt_if_key(row['nome_sottocategoria'], master_key, crypto, silent=True)
                     row['nome_sottocategoria'] = decrypted or row['nome_sottocategoria']

                # Decrypt and process amounts
                limit = row.get('importo_limite')
                spent = row.get('importo_speso')
                
                # Decrypt limit
                if isinstance(limit, str) and not limit.replace('.', '', 1).isdigit(): # Simple check if likely encrypted
                     dec_limit = _decrypt_if_key(limit, family_key, crypto, silent=True)
                     if not dec_limit and family_key != master_key:
                         dec_limit = _decrypt_if_key(limit, master_key, crypto, silent=True)
                     limit = float(dec_limit) if dec_limit else 0.0
                else:
                    limit = float(limit) if limit is not None else 0.0
                
                # Decrypt spent
                if isinstance(spent, str) and not spent.replace('.', '', 1).isdigit():
                     dec_spent = _decrypt_if_key(spent, family_key, crypto, silent=True)
                     if not dec_spent and family_key != master_key:
                         dec_spent = _decrypt_if_key(spent, master_key, crypto, silent=True)
                     spent = float(dec_spent) if dec_spent else 0.0
                else:
                     spent = float(spent) if spent is not None else 0.0
                
                row['importo_limite'] = limit
                row['importo_speso'] = spent
                row['rimanente'] = limit - spent

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero storico per export: {e}")
        return []




# --- Funzioni Budget History Helpers ---

def trigger_budget_history_update(id_famiglia, data_riferimento, master_key_b64=None, id_utente=None, cursor=None, forced_family_key_b64=None):
    """
    Allinea la tabella Budget_Storico con la tabella Budget per il mese/anno corrente.
    Itera sui budget definiti, cripta nome e spesa (0), ed esegue UPSERT.
    
    Se forced_family_key_b64 è fornito, viene usato direttamente senza tentare la decifratura 
    (utile per le chiamate dal background_service che hanno già la chiave decifrata).
    """
    anno = data_riferimento.year
    mese = data_riferimento.month
    
    # 1. Recupera chiavi per crittografia
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    
    # Se è stata fornita la family_key già decifrata, usala direttamente
    if forced_family_key_b64:
        family_key = base64.b64decode(forced_family_key_b64)
    elif master_key and id_utente:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    
    if not family_key:
        print(f"[WARN] trigger_budget_history_update: Cannot encrypt without family_key. id_utente={id_utente}")
        return False

    # 2. Definisci logica di update (inner function per riuso con/senza cursor esterno)
    def _perform_update(cur):
        # Fetch budget correnti con nomi in chiaro
        sql_fetch = """
        SELECT B.id_sottocategoria, B.importo_limite, S.nome_sottocategoria 
        FROM Budget B
        JOIN Sottocategorie S ON B.id_sottocategoria = S.id_sottocategoria
        WHERE B.id_famiglia = %s AND B.periodo = 'Mensile'
        """
        cur.execute(sql_fetch, (id_famiglia,))
        rows = cur.fetchall()
        
        # Prepare encrypted zero for new rows
        zero_enc = _encrypt_if_key("0.0", family_key, crypto)
        
        for row in rows:
            # Encrypt name
            nome_enc = _encrypt_if_key(row['nome_sottocategoria'], family_key, crypto)
            limit_val = row['importo_limite'] # Already encrypted in Budget table
            
            # Upsert
            # ON CONFLICT: Update ONLY LIMIT. Preserve existing imported_speso and names.
            sql_upsert = """
            INSERT INTO Budget_Storico (id_famiglia, id_sottocategoria, anno, mese, importo_limite, nome_sottocategoria, importo_speso)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_famiglia, id_sottocategoria, anno, mese)
            DO UPDATE SET importo_limite = EXCLUDED.importo_limite;
            """
            cur.execute(sql_upsert, (
                id_famiglia, 
                row['id_sottocategoria'], 
                anno, 
                mese, 
                limit_val, 
                nome_enc, 
                zero_enc
            ))

    if cursor:
        try:
            _perform_update(cursor)
            return True
        except Exception as e:
             print(f"[ERRORE] Errore trigger_budget_history_update (shared cursor): {e}")
             return False

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            _perform_update(cur)
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore trigger_budget_history_update: {e}")
        return False

