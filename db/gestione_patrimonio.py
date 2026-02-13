"""
Funzioni patrimonio: prestiti, fondi pensione, immobili, piani ammortamento
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
from utils.logger import setup_logger
from utils.crypto_manager import CryptoManager
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
import os

logger = setup_logger(__name__)
import json

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code, _get_system_keys,
    HASH_SALT, SYSTEM_FERNET_KEY, SERVER_SECRET_KEY,
    crypto as _crypto_instance
)



# --- Funzioni Fondo Pensione ---
def aggiorna_valore_fondo_pensione(id_conto, nuovo_valore):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Conti SET valore_manuale = %s WHERE id_conto = %s AND tipo = 'Fondo Pensione'",
                        (nuovo_valore, id_conto))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante l'aggiornamento del valore del fondo pensione: {e}")
        return False

def esegui_operazione_fondo_pensione(id_fondo_pensione, tipo_operazione, importo, data, id_conto_collegato=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")

            if tipo_operazione == 'VERSAMENTO':
                descrizione = f"Versamento a fondo pensione (ID: {id_fondo_pensione})"
                # Transazione in uscita dal conto collegato
                cur.execute("INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (?, %s, %s, %s)",
                            (id_conto_collegato, data, descrizione, -abs(importo)))
                
                # Transazione in entrata nel fondo pensione (opzionale, ma utile per tracciamento)
                # Per ora manteniamo la logica originale che aggiorna solo il valore manuale, 
                # ma potremmo voler tracciare anche qui.
                # Se vogliamo tracciare l'entrata nel fondo pensione:
                # cur.execute("INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (?, %s, %s, %s)",
                #             (id_fondo_pensione, data, "Versamento da conto", abs(importo)))

            elif tipo_operazione == 'VERSAMENTO_ESTERNO':
                # Nuova logica: registriamo una transazione di entrata direttamente sul fondo pensione
                descrizione = "Versamento Esterno / Entrata"
                # Assicuriamoci di avere una categoria/sottocategoria appropriata o lasciamo NULL
                # Se vogliamo che sia un'entrata, l'importo deve essere positivo.
                cur.execute("""
                    INSERT INTO Transazioni (id_conto, data, descrizione, importo) 
                    VALUES (%s, %s, %s, %s)
                """, (id_fondo_pensione, data, descrizione, abs(importo)))

            elif tipo_operazione == 'PRELIEVO':
                descrizione = f"Prelievo da fondo pensione (ID: {id_fondo_pensione})"
                cur.execute("INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (?, %s, %s, %s)",
                            (id_conto_collegato, data, descrizione, abs(importo)))

            if tipo_operazione in ['VERSAMENTO', 'VERSAMENTO_ESTERNO']:
                cur.execute("UPDATE Conti SET valore_manuale = valore_manuale + %s WHERE id_conto = %s",
                            (abs(importo), id_fondo_pensione))
            elif tipo_operazione == 'PRELIEVO':
                cur.execute("UPDATE Conti SET valore_manuale = valore_manuale - %s WHERE id_conto = %s",
                            (abs(importo), id_fondo_pensione))

            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'esecuzione dell'operazione sul fondo pensione: {e}")
        if con: con.rollback()
        return False



# --- Funzioni Prestiti ---

def gestisci_quote_prestito(id_prestito, lista_quote):
    """
    Gestisce le quote di competenza di un prestito.
    lista_quote: lista di dizionari {'id_utente': int, 'percentuale': float}
    """
    if lista_quote is None:
        return True
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM QuotePrestiti WHERE id_prestito = %s", (id_prestito,))
            for quota in lista_quote:
                cur.execute("""
                    INSERT INTO QuotePrestiti (id_prestito, id_utente, percentuale)
                    VALUES (%s, %s, %s)
                """, (id_prestito, quota['id_utente'], quota['percentuale']))
            con.commit()
        return True
    except Exception as e:
        print(f"[ERRORE] Errore salvataggio quote prestito: {e}")
        return False

def ottieni_quote_prestito(id_prestito):
    try:
        with get_db_connection() as con:
             cur = con.cursor()
             cur.execute("SELECT id_utente, percentuale FROM QuotePrestiti WHERE id_prestito = %s", (id_prestito,))
             return [dict(row) for row in cur.fetchall()]
    except Exception:
        return []

def aggiungi_prestito(id_famiglia, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                      importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default=None,
                      id_conto_condiviso_default=None, id_sottocategoria_default=None, addebito_automatico=False,
                      master_key_b64=None, id_utente=None, lista_quote=None):
    
    # Encrypt sensitive data if keys available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                row = cur.fetchone()
                if row and row['chiave_famiglia_criptata']:
                    family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                    family_key = base64.b64decode(family_key_b64)
        except Exception:
            pass

    encrypted_nome = _encrypt_if_key(nome, family_key, crypto)
    encrypted_descrizione = _encrypt_if_key(descrizione, family_key, crypto)

    try:
        id_new = None
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        INSERT INTO Prestiti (id_famiglia, nome, tipo, descrizione, data_inizio, numero_mesi_totali,
                                              importo_finanziato, importo_interessi, importo_residuo, importo_rata,
                                              giorno_scadenza_rata, id_conto_pagamento_default,
                                              id_conto_condiviso_pagamento_default, id_sottocategoria_pagamento_default,
                                              addebito_automatico)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_prestito
                        """, (id_famiglia, encrypted_nome, tipo, encrypted_descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                              importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default,
                              id_conto_condiviso_default, id_sottocategoria_default, bool(addebito_automatico)))
            id_new = cur.fetchone()['id_prestito']
        
        # Effettuiamo la gestione quote DOPO il commit della transazione principale
        # altrimenti la nuova query in gestisci_quote_prestito (nuova connessione) non vedrebbe l'ID
        if id_new and lista_quote:
            gestisci_quote_prestito(id_new, lista_quote)
            
        return id_new
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiunta del prestito: {e}")
        return None


def modifica_prestito(id_prestito, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                      importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default=None,
                      id_conto_condiviso_default=None, id_sottocategoria_default=None, addebito_automatico=False,
                      master_key_b64=None, id_utente=None, lista_quote=None):
    
    # Encrypt sensitive data if keys available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                # Need id_famiglia to get key
                cur.execute("SELECT id_famiglia FROM Prestiti WHERE id_prestito = %s", (id_prestito,))
                p_row = cur.fetchone()
                if p_row:
                    id_famiglia = p_row['id_famiglia']
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
        except Exception:
            pass

    encrypted_nome = _encrypt_if_key(nome, family_key, crypto)
    encrypted_descrizione = _encrypt_if_key(descrizione, family_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        UPDATE Prestiti
                        SET nome                           = %s,
                            tipo                           = %s,
                            descrizione                    = %s,
                            data_inizio                    = %s,
                            numero_mesi_totali             = %s,
                            importo_finanziato             = %s,
                            importo_interessi              = %s,
                            importo_residuo                = %s,
                            importo_rata                   = %s,
                            giorno_scadenza_rata           = %s,
                            id_conto_pagamento_default     = %s,
                            id_conto_condiviso_pagamento_default = %s,
                            id_sottocategoria_pagamento_default = %s,
                            addebito_automatico            = %s
                        WHERE id_prestito = %s
                        """, (encrypted_nome, tipo, encrypted_descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                              importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default,
                              id_conto_condiviso_default, id_sottocategoria_default, bool(addebito_automatico), id_prestito))
        
        # Gestione Quote DOPO il commit della transazione principale
        if lista_quote is not None:
            gestisci_quote_prestito(id_prestito, lista_quote)
            
        return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica del prestito: {e}")
        return False


def elimina_prestito(id_prestito):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM Prestiti WHERE id_prestito = %s", (id_prestito,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione del prestito: {e}")
        return None


def _applica_override_piani_ammortamento(results, cur):
    """
    Helper interno per arricchire una lista di prestiti (o record collegati a prestiti)
    con i dati reali calcolati dal Piano Ammortamento.
    'results' deve essere una lista di dizionari (record della tabella Prestiti o Immobili).
    Modifica i dizionari in-place.
    """
    ids_prestiti = []
    for r in results:
        pid = r.get('id_prestito') or r.get('id_prestito_collegato')
        if pid:
            ids_prestiti.append(pid)
            
    if not ids_prestiti:
        return

    piano_map = {} # id_prestito -> { 'rate_pagate': 0, 'rate_totali': 0, ... }
    ids_unique = list(set(ids_prestiti))
    placeholders = ','.join(['%s'] * len(ids_unique))
    query_piano = f"""
        SELECT id_prestito, importo_rata, quota_capitale, quota_interessi, data_scadenza, stato 
        FROM PianoAmmortamento 
        WHERE id_prestito IN ({placeholders})
        ORDER BY data_scadenza ASC
    """
    cur.execute(query_piano, tuple(ids_unique))
    rows_piano = cur.fetchall()
    
    for r in rows_piano:
        pid = r['id_prestito']
        if pid not in piano_map:
            piano_map[pid] = {
                'rate_pagate': 0, 
                'rate_totali': 0, 
                'next_rata_found': False, 
                'next_rata_importo': 0.0,
                'residuo_totale': 0.0,
                'capitale_residuo': 0.0,
                'interessi_residui': 0.0
            }
        
        piano_map[pid]['rate_totali'] += 1
        
        if r['stato'] == 'pagata':
            piano_map[pid]['rate_pagate'] += 1
        elif r['stato'] == 'da_pagare':
            # Somma residuo
            piano_map[pid]['residuo_totale'] += float(r['importo_rata'])
            piano_map[pid]['capitale_residuo'] += float(r['quota_capitale'])
            piano_map[pid]['interessi_residui'] += float(r['quota_interessi'])
            
            if not piano_map[pid]['next_rata_found']:
                # La prima rata 'da_pagare' (ordinato data ASC) è quella corrente
                piano_map[pid]['next_rata_found'] = True
                piano_map[pid]['next_rata_importo'] = float(r['importo_rata'])
    
    # Applica override ai risultati
    for row in results:
        pid = row.get('id_prestito') or row.get('id_prestito_collegato')
        if pid in piano_map:
            pm = piano_map[pid]
            row['rate_pagate'] = pm['rate_pagate']
            if 'numero_mesi_totali' in row:
                row['numero_mesi_totali'] = pm['rate_totali']
            if 'importo_residuo' in row:
                row['importo_residuo'] = pm['residuo_totale']
            if 'valore_mutuo_residuo' in row:
                row['valore_mutuo_residuo'] = pm['residuo_totale']
            row['capitale_residuo'] = pm['capitale_residuo']
            row['interessi_residui'] = pm['interessi_residui']
            if pm['next_rata_found'] and 'importo_rata' in row:
               row['importo_rata'] = pm['next_rata_importo']

def ottieni_prestiti_famiglia(id_famiglia, master_key_b64=None, id_utente=None, forced_family_key_b64=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                        SELECT P.*, 
                               C.nome_categoria AS nome_categoria_default,
                               CASE 
                                   WHEN P.importo_rata > 0 THEN CAST((P.importo_finanziato + COALESCE(P.importo_interessi, 0) - P.importo_residuo) / P.importo_rata AS INTEGER)
                                   ELSE 0 
                               END as rate_pagate
                        FROM Prestiti P
                                 LEFT JOIN Categorie C ON P.id_categoria_pagamento_default = C.id_categoria
                        WHERE P.id_famiglia = %s
                        ORDER BY P.data_inizio DESC
                        """, (id_famiglia,))
            results = [dict(row) for row in cur.fetchall()]

            if not results:
                return []

            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            
            if forced_family_key_b64:
                family_key = base64.b64decode(forced_family_key_b64)
            elif master_key and id_utente:
                try:
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
                except Exception:
                    pass

            if family_key:
                for row in results:
                    row['nome'] = _decrypt_if_key(row['nome'], family_key, crypto, silent=True)
                    row['descrizione'] = _decrypt_if_key(row['descrizione'], family_key, crypto, silent=True)
            
            # --- Batch Quote Prestiti ---
            ids_prestiti = [r['id_prestito'] for r in results]
            quote_map = {}
            if ids_prestiti:
                placeholders = ','.join(['%s'] * len(ids_prestiti))
                query = f"SELECT id_prestito, id_utente, percentuale FROM QuotePrestiti WHERE id_prestito IN ({placeholders})"
                cur.execute(query, tuple(ids_prestiti))
                rows = cur.fetchall()
                for r in rows:
                    if r['id_prestito'] not in quote_map:
                        quote_map[r['id_prestito']] = []
                    quote_map[r['id_prestito']].append({'id_utente': r['id_utente'], 'percentuale': r['percentuale']})
            
            for row in results:
                row['lista_quote'] = quote_map.get(row['id_prestito'], [])

            # --- Override Piano Ammortamento ---
            _applica_override_piani_ammortamento(results, cur)
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero prestiti: {e}")
        return []

def check_e_paga_rate_scadute(id_famiglia, master_key_b64=None, id_utente=None, forced_family_key_b64=None):
    oggi = datetime.date.today()
    pagamenti_eseguiti = 0
    try:
        prestiti_attivi = ottieni_prestiti_famiglia(id_famiglia, master_key_b64=master_key_b64, id_utente=id_utente, forced_family_key_b64=forced_family_key_b64)
        with get_db_connection() as con:
            cur = con.cursor()
            for p in prestiti_attivi:
                # 1. Verifica Addebito Automatico Attivo
                if not p.get('addebito_automatico'):
                    continue
                    
                # Validazione dati minimi
                id_conto_pers = p.get('id_conto_pagamento_default')
                id_conto_cond = p.get('id_conto_condiviso_pagamento_default')
                
                if p['importo_residuo'] <= 0 or (not id_conto_pers and not id_conto_cond):
                    continue

                pay_data = None # (amount, id_rata_schedule)

                # 2. Controllo Piano Ammortamento (Prioritario)
                cur.execute("""
                    SELECT id_rata, data_scadenza, importo_rata 
                    FROM PianoAmmortamento 
                    WHERE id_prestito = %s AND stato = 'da_pagare' 
                    ORDER BY data_scadenza ASC LIMIT 1
                """, (p['id_prestito'],))
                sched = cur.fetchone()

                from datetime import datetime as dt_class # Per parsing sicuro se non importato top-level

                if sched:
                    try:
                        # Parsing data scadenza (YYYY-MM-DD)
                        if isinstance(sched['data_scadenza'], str):
                             due_dt = dt_class.strptime(sched['data_scadenza'], '%Y-%m-%d').date()
                        else:
                             due_dt = sched['data_scadenza'] # Se driver restituisce date object
                        
                        if oggi >= due_dt:
                             pay_data = (float(sched['importo_rata']), sched['id_rata'])
                    except Exception as ed:
                        print(f"Errore parsing data rata id {sched['id_rata']}: {ed}")
                else:
                    # 3. Logica Legacy (Statico)
                    day = p.get('giorno_scadenza_rata')
                    if day and oggi.day >= day:
                        # Verifica importo
                        amount = min(float(p['importo_rata']), float(p['importo_residuo']))
                        pay_data = (amount, None)

                # 4. Esecuzione Pagamento
                if pay_data:
                    amount, sched_id = pay_data
                    
                    perform_payment = False
                    
                    if sched_id:
                        # Se da schedina, 'da_pagare' fa da lock (se paghiamo ora, settiamo 'pagata')
                        perform_payment = True
                    else:
                        # Se legacy, check Storico mensile per evitare doppi pagamenti
                        cur.execute("SELECT 1 FROM StoricoPagamentiRate WHERE id_prestito = %s AND anno = %s AND mese = %s", 
                                    (p['id_prestito'], oggi.year, oggi.month))
                        if not cur.fetchone():
                            perform_payment = True

                    if perform_payment:
                        # Usa categoria default o sottocategoria? Il vecchio codice usava id_categoria... 
                        # Controlliamo la firma di effettua_pagamento_rata -> args: id_sottocategoria
                        # Il vecchio codice passava id_categoria_pagamento_default... verifichiamo se p ha sottocategoria
                        cat_id = p.get('id_sottocategoria_pagamento_default') or p.get('id_categoria_pagamento_default')
                        
                        effettua_pagamento_rata(
                            p['id_prestito'], 
                            id_conto_pers, 
                            amount, 
                            oggi.strftime('%Y-%m-%d'), 
                            cat_id, 
                            p['nome'],
                            id_conto_condiviso=id_conto_cond,
                            id_utente_autore=id_utente
                        )
                        
                        if sched_id:
                            # Aggiorna lo stato nel piano
                            aggiorna_stato_rata_piano(sched_id, 'pagata')
                        
                        pagamenti_eseguiti += 1

        return pagamenti_eseguiti
    except Exception as e:
        print(f"[ERRORE] Errore critico durante il controllo delle rate scadute: {e}")
        return 0


def effettua_pagamento_rata(id_prestito, id_conto_pagamento, importo_pagato, data_pagamento, id_sottocategoria,
                            nome_prestito="", id_conto_condiviso=None, id_utente_autore=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")
            cur.execute("UPDATE Prestiti SET importo_residuo = importo_residuo - %s WHERE id_prestito = %s",
                        (importo_pagato, id_prestito))
            
            # --- Aggiornamento Piano Ammortamento (se presente) ---
            cur.execute("SELECT id_rata FROM PianoAmmortamento WHERE id_prestito = %s AND stato = 'da_pagare' ORDER BY numero_rata ASC LIMIT 1", (id_prestito,))
            rata_row = cur.fetchone()
            if rata_row:
                cur.execute("UPDATE PianoAmmortamento SET stato = 'pagata' WHERE id_rata = %s", (rata_row['id_rata'],))
            # ------------------------------------------------------
            descrizione = f"Pagamento rata {nome_prestito} (Prestito ID: {id_prestito})"
            
            if id_conto_condiviso:
                # Transazione condivisa
                if not id_utente_autore:
                    # Fallback on some admin ID or safe default if automated
                    # Better to print warning, but let's try to proceed if possible or error?
                    # Automated tasks pass id_utente now.
                    print("[WARNING] effettua_pagamento_rata called for shared account without id_utente_autore")
                    pass 
                
                # Per le transazioni condivise, l'autore deve essere specificato. 
                # Se è null, potrebbe fallire constraint NOT NULL su id_utente_autore.
                cur.execute(
                    "INSERT INTO TransazioniCondivise (id_conto_condiviso, id_utente_autore, id_sottocategoria, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s, %s)",
                    (id_conto_condiviso, id_utente_autore, id_sottocategoria, data_pagamento, descrizione, -abs(importo_pagato)))
            
            elif id_conto_pagamento:
                # Transazione personale standard
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s)",
                    (id_conto_pagamento, id_sottocategoria, data_pagamento, descrizione, -abs(importo_pagato)))
            else:
                 print(f"[ERRORE] effettua_pagamento_rata: Nessun conto specificato per il pagamento.")
                 con.rollback()
                 return False

            data_dt = parse_date(data_pagamento)
            cur.execute(
                "INSERT INTO StoricoPagamentiRate (id_prestito, anno, mese, data_pagamento, importo_pagato) VALUES (%s, %s, %s, %s, %s) ON CONFLICT(id_prestito, anno, mese) DO NOTHING",
                (id_prestito, data_dt.year, data_dt.month, data_pagamento, importo_pagato))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'esecuzione del pagamento rata: {e}")
        if con: con.rollback()
        return False


# --- Funzioni Immobili ---

def gestisci_quote_immobile(id_immobile, lista_quote):
    """
    Gestisce le quote di proprietà di un immobile.
    lista_quote: lista di dizionari {'id_utente': int, 'percentuale': float}
    """
    if lista_quote is None:
        return True
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Rimuovi quote esistenti
            cur.execute("DELETE FROM QuoteImmobili WHERE id_immobile = %s", (id_immobile,))
            
            # Inserisci nuove quote
            for quota in lista_quote:
                cur.execute("""
                    INSERT INTO QuoteImmobili (id_immobile, id_utente, percentuale)
                    VALUES (%s, %s, %s)
                """, (id_immobile, quota['id_utente'], quota['percentuale']))
            con.commit()
        return True
    except Exception as e:
        print(f"[ERRORE] Errore salvataggio quote immobile: {e}")
        return False

def ottieni_quote_immobile(id_immobile):
    try:
        with get_db_connection() as con:
             cur = con.cursor()
             cur.execute("SELECT id_utente, percentuale FROM QuoteImmobili WHERE id_immobile = %s", (id_immobile,))
             return [dict(row) for row in cur.fetchall()]
    except Exception:
        return []

def aggiungi_immobile(id_famiglia, nome, via, citta, valore_acquisto, valore_attuale, nuda_proprieta,
                      id_prestito_collegato=None, master_key_b64=None, id_utente=None, lista_quote=None):
    # Converti il valore del dropdown in int se necessario
    db_id_prestito = None
    if id_prestito_collegato is not None and id_prestito_collegato != "None":
        try:
            db_id_prestito = int(id_prestito_collegato)
        except (ValueError, TypeError):
            db_id_prestito = None
            
    # Encrypt sensitive data if keys available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                row = cur.fetchone()
                if row and row['chiave_famiglia_criptata']:
                    family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                    family_key = base64.b64decode(family_key_b64)
        except Exception:
            pass

    encrypted_nome = _encrypt_if_key(nome, family_key, crypto)
    encrypted_via = _encrypt_if_key(via, family_key, crypto)
    encrypted_citta = _encrypt_if_key(citta, family_key, crypto)

    id_new = None
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        INSERT INTO Immobili (id_famiglia, nome, via, citta, valore_acquisto, valore_attuale,
                                              nuda_proprieta, id_prestito_collegato)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_immobile
                        """,
                        (id_famiglia, encrypted_nome, encrypted_via, encrypted_citta, valore_acquisto, valore_attuale, bool(nuda_proprieta),
                         db_id_prestito))
            id_new = cur.fetchone()['id_immobile']
        
        # Gestione Quote DOPO il commit della transazione principale
        if id_new and lista_quote:
            gestisci_quote_immobile(id_new, lista_quote)
                
            return id_new
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiunta dell'immobile: {e}")
        return None


def modifica_immobile(id_immobile, nome, via, citta, valore_acquisto, valore_attuale, nuda_proprieta,
                      id_prestito_collegato=None, master_key_b64=None, id_utente=None, lista_quote=None):
    # Converti il valore del dropdown in int se necessario
    db_id_prestito = None
    if id_prestito_collegato is not None and id_prestito_collegato != "None":
        try:
            db_id_prestito = int(id_prestito_collegato)
        except (ValueError, TypeError):
            db_id_prestito = None
            
    # Encrypt sensitive data if keys available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                # Need id_famiglia to get key
                cur.execute("SELECT id_famiglia FROM Immobili WHERE id_immobile = %s", (id_immobile,))
                i_row = cur.fetchone()
                if i_row:
                    id_famiglia = i_row['id_famiglia']
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
        except Exception:
            pass

    encrypted_nome = _encrypt_if_key(nome, family_key, crypto)
    encrypted_via = _encrypt_if_key(via, family_key, crypto)
    encrypted_citta = _encrypt_if_key(citta, family_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        UPDATE Immobili
                        SET nome                  = %s,
                            via                   = %s,
                            citta                 = %s,
                            valore_acquisto       = %s,
                            valore_attuale        = %s,
                            nuda_proprieta        = %s,
                            id_prestito_collegato = %s
                        WHERE id_immobile = %s
                        """,
                        (encrypted_nome, encrypted_via, encrypted_citta, valore_acquisto, valore_attuale, bool(nuda_proprieta), db_id_prestito,
                         id_immobile))
        
        # Gestione Quote DOPO il commit della transazione principale
        if lista_quote is not None:
            gestisci_quote_immobile(id_immobile, lista_quote)

        return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica dell'immobile: {e}")
        return False


def elimina_immobile(id_immobile):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM Immobili WHERE id_immobile = %s", (id_immobile,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione dell'immobile: {e}")
        return None


def ottieni_immobili_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT I.*, P.importo_residuo AS valore_mutuo_residuo, P.nome AS nome_mutuo
                        FROM Immobili I
                                 LEFT JOIN Prestiti P ON I.id_prestito_collegato = P.id_prestito
                        WHERE I.id_famiglia = %s
                        ORDER BY I.nome
                        """, (id_famiglia,))
            results = [dict(row) for row in cur.fetchall()]

            if not results:
                return []
            
            # --- Override Piano Ammortamento per Mutui collegati ---
            _applica_override_piani_ammortamento(results, cur)
            
            # Decrypt sensitive data if keys available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                try:
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
                except Exception:
                    pass

            if family_key:
                for row in results:
                    row['nome'] = _decrypt_if_key(row['nome'], family_key, crypto, silent=True)
                    row['via'] = _decrypt_if_key(row['via'], family_key, crypto, silent=True)
                    row['citta'] = _decrypt_if_key(row['citta'], family_key, crypto, silent=True)
                    # Also decrypt linked loan name if present
                    if row.get('nome_mutuo'):
                        row['nome_mutuo'] = _decrypt_if_key(row['nome_mutuo'], family_key, crypto, silent=True)
            
            # --- OTTIMIZZAZIONE INIZIO: Batch Fetching delle Quote ---
            ids_immobili = [r['id_immobile'] for r in results]
            ids_prestiti = [r['id_prestito_collegato'] for r in results if r.get('id_prestito_collegato')]
            
            # Batch fetch Quote Immobili
            quote_immobili_map = {} # id_immobile -> list[dict]
            if ids_immobili:
                placeholders = ','.join(['%s'] * len(ids_immobili))
                query_qi = f"SELECT id_immobile, id_utente, percentuale FROM QuoteImmobili WHERE id_immobile IN ({placeholders})"
                cur.execute(query_qi, tuple(ids_immobili))
                rows_qi = cur.fetchall()
                for r in rows_qi:
                    if r['id_immobile'] not in quote_immobili_map:
                        quote_immobili_map[r['id_immobile']] = []
                    quote_immobili_map[r['id_immobile']].append({'id_utente': r['id_utente'], 'percentuale': r['percentuale']})
            
            # Batch fetch Quote Prestiti
            quote_prestiti_map = {} # id_prestito -> list[dict]
            if ids_prestiti:
                ids_prestiti_unique = list(set(ids_prestiti))
                placeholders_p = ','.join(['%s'] * len(ids_prestiti_unique))
                query_qp = f"SELECT id_prestito, id_utente, percentuale FROM QuotePrestiti WHERE id_prestito IN ({placeholders_p})"
                cur.execute(query_qp, tuple(ids_prestiti_unique))
                rows_qp = cur.fetchall()
                for r in rows_qp:
                    if r['id_prestito'] not in quote_prestiti_map:
                        quote_prestiti_map[r['id_prestito']] = []
                    quote_prestiti_map[r['id_prestito']].append({'id_utente': r['id_utente'], 'percentuale': r['percentuale']})

            # Assegna i risultati in memoria
            for row in results:
                row['lista_quote'] = quote_immobili_map.get(row['id_immobile'], [])
                if row.get('id_prestito_collegato'):
                    row['lista_quote_prestito'] = quote_prestiti_map.get(row.get('id_prestito_collegato'), [])
                else:
                    row['lista_quote_prestito'] = []
            # --- OTTIMIZZAZIONE FINE ---

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero immobili: {e}")
        return []

# --- GESTIONE PIANO AMMORTAMENTO ---

def aggiungi_rata_piano_ammortamento(id_prestito, numero_rata, data_scadenza, importo_rata, quota_capitale, quota_interessi, spese_fisse=0, stato='da_pagare'):
    """
    Aggiunge una rata al piano di ammortamento di un prestito.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO PianoAmmortamento 
                (id_prestito, numero_rata, data_scadenza, importo_rata, quota_capitale, quota_interessi, spese_fisse, stato)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (id_prestito, numero_rata, data_scadenza, importo_rata, quota_capitale, quota_interessi, spese_fisse, stato))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta rata piano ammortamento: {e}")
        return False

def ottieni_piano_ammortamento(id_prestito):
    """
    Recupera il piano di ammortamento completo per un prestito, ordinato per numero rata.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT * FROM PianoAmmortamento 
                WHERE id_prestito = %s 
                ORDER BY numero_rata ASC
            """, (id_prestito,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore recupero piano ammortamento: {e}")
        return []

def elimina_piano_ammortamento(id_prestito):
    """
    Elimina tutte le rate del piano di ammortamento per un prestito.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM PianoAmmortamento WHERE id_prestito = %s", (id_prestito,))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione piano ammortamento: {e}")
        return False

def aggiorna_stato_rata_piano(id_rata, nuovo_stato):
    """
    Aggiorna lo stato di una rata e ricalcola il residuo statico del prestito.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # 1. Recupera id_prestito
            cur.execute("SELECT id_prestito FROM PianoAmmortamento WHERE id_rata = %s", (id_rata,))
            row = cur.fetchone()
            if not row: return False
            id_prestito = row['id_prestito']
            
            # 2. Aggiorna stato rata
            cur.execute("UPDATE PianoAmmortamento SET stato = %s WHERE id_rata = %s", (nuovo_stato, id_rata))
            
            # 3. Ricalcola residuo totale (somma rate 'da_pagare')
            cur.execute("SELECT SUM(importo_rata) as residuo FROM PianoAmmortamento WHERE id_prestito = %s AND stato = 'da_pagare'", (id_prestito,))
            res_row = cur.fetchone()
            nuovo_residuo = float(res_row['residuo'] or 0)
            
            # 4. Aggiorna tabella Prestiti (valore statico)
            cur.execute("UPDATE Prestiti SET importo_residuo = %s WHERE id_prestito = %s", (nuovo_residuo, id_prestito))
            
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiornamento stato rata e residuo: {e}")
        return False

