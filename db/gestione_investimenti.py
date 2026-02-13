"""
Funzioni investimenti: asset, portafoglio, storico prezzi
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
import base64

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code, _get_system_keys,
    HASH_SALT, SYSTEM_FERNET_KEY, SERVER_SECRET_KEY,
    crypto as _crypto_instance
)



# --- Funzioni Asset ---
def compra_asset(id_conto_investimento, ticker, nome_asset, quantita, costo_unitario_nuovo, tipo_mov='COMPRA',
                 prezzo_attuale_override=None, master_key_b64=None, id_utente=None):
    ticker_upper = ticker.upper()
    nome_asset_upper = nome_asset.upper()
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Determine Keys for Duplicate Check
    keys_to_try = []
    family_key = None
    
    if id_utente:
         id_famiglia = ottieni_prima_famiglia_utente(id_utente)
         if id_famiglia and master_key:
              family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    
    if master_key: keys_to_try.append(master_key)
    if family_key: keys_to_try.append(family_key)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Fetch matching asset directly if exists
            cur.execute(
                "SELECT id_asset, ticker, quantita, costo_iniziale_unitario, nome_asset FROM Asset WHERE id_conto = %s AND ticker = %s",
                (id_conto_investimento, ticker_upper))
            risultato = cur.fetchone()
            
            # Determine encryption key for NEW write
            # Use Family Key if available (shared logic preference), else Master Key
            write_key = family_key if family_key else master_key
            
            cur.execute(
                "INSERT INTO Storico_Asset (id_conto, ticker, data, tipo_movimento, quantita, prezzo_unitario_movimento) VALUES (%s, %s, %s, %s, %s, %s)",
                (id_conto_investimento, ticker_upper, datetime.date.today().strftime('%Y-%m-%d'), tipo_mov, quantita,
                 costo_unitario_nuovo))
                 
            if risultato:
                id_asset_aggiornato = risultato['id_asset']
                vecchia_quantita = float(risultato['quantita'])
                vecchio_costo_medio = float(risultato['costo_iniziale_unitario'])
                
                nuova_quantita_totale = vecchia_quantita + quantita
                nuovo_costo_medio = (
                                                vecchia_quantita * vecchio_costo_medio + quantita * costo_unitario_nuovo) / nuova_quantita_totale
                
                # Keep existing name if not explicitly changed, or update? 
                # Strategy: If found, we update Quantita and Costo Medio. 
                # Should we re-encrypt Name and Ticker with new key? 
                # Better to keep existing keys for consistency unless we want to migrate.
                # Let's just update numerics to be safe, OR re-encrypt everything if we want to unify keys.
                # Re-encrypting ensures latest key is used.
                
                cur.execute(
                    "UPDATE Asset SET quantita = %s, costo_iniziale_unitario = %s WHERE id_asset = %s",
                    (nuova_quantita_totale, nuovo_costo_medio, id_asset_aggiornato))
            else:
                prezzo_attuale = prezzo_attuale_override if prezzo_attuale_override is not None else costo_unitario_nuovo
                cur.execute(
                    "INSERT INTO Asset (id_conto, ticker, nome_asset, quantita, costo_iniziale_unitario, prezzo_attuale_manuale) VALUES (%s, %s, %s, %s, %s, %s)",
                    (id_conto_investimento, ticker_upper, nome_asset_upper, quantita, costo_unitario_nuovo,
                     prezzo_attuale))
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'acquisto asset: {e}")
        return False


def vendi_asset(id_conto_investimento, ticker, quantita_da_vendere, prezzo_di_vendita_unitario, master_key_b64=None):
    ticker_upper = ticker.upper()
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    # Determine correct key (Family Key if applicable)
    encryption_key = _get_key_for_transaction(id_conto_investimento, master_key, crypto)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            
            # Fetch matching asset directly
            cur.execute("SELECT id_asset, ticker, quantita FROM Asset WHERE id_conto = %s AND ticker = %s",
                        (id_conto_investimento, ticker_upper))
            risultato = cur.fetchone()
            
            if not risultato: return False
            
            id_asset = risultato['id_asset']
            quantita_attuale = risultato['quantita']
            
            if quantita_da_vendere > quantita_attuale and abs(
                quantita_da_vendere - quantita_attuale) > 1e-9: return False

            nuova_quantita = quantita_attuale - quantita_da_vendere
            
            cur.execute(
                "INSERT INTO Storico_Asset (id_conto, ticker, data, tipo_movimento, quantita, prezzo_unitario_movimento) VALUES (%s, %s, %s, %s, %s, %s)",
                (id_conto_investimento, ticker_upper, datetime.date.today().strftime('%Y-%m-%d'), 'VENDI',
                 quantita_da_vendere, prezzo_di_vendita_unitario))
                 
            if nuova_quantita < 1e-9:
                cur.execute("DELETE FROM Asset WHERE id_asset = %s", (id_asset,))
            else:
                cur.execute("UPDATE Asset SET quantita = %s WHERE id_asset = %s", (nuova_quantita, id_asset))
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la vendita asset: {e}")
        return False


def ottieni_portafoglio(id_conto_investimento, master_key_b64=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT id_asset,
                               ticker,
                               nome_asset,
                               quantita,
                               prezzo_attuale_manuale,
                               costo_iniziale_unitario,
                               data_aggiornamento,
                               (prezzo_attuale_manuale - costo_iniziale_unitario)              AS gain_loss_unitario,
                               (quantita * (prezzo_attuale_manuale - costo_iniziale_unitario)) AS gain_loss_totale
                        FROM Asset
                        WHERE id_conto = %s
                        ORDER BY ticker
                        """, (id_conto_investimento,))
            results = [dict(row) for row in cur.fetchall()]
            
            # Plaintext results
            return results
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero portafoglio: {e}")
        return []


def aggiorna_prezzo_manuale_asset(id_asset, nuovo_prezzo):
    # No encryption needed for price
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            adesso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("UPDATE Asset SET prezzo_attuale_manuale = %s, data_aggiornamento = %s WHERE id_asset = %s", (nuovo_prezzo, adesso, id_asset))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiornamento prezzo: {e}")
        return False


def modifica_asset_dettagli(id_asset, nuovo_ticker, nuovo_nome, nuova_quantita=None, nuovo_costo_medio=None, master_key_b64=None):
    nuovo_ticker_upper = nuovo_ticker.upper()
    nuovo_nome_upper = nuovo_nome.upper()
    
    # Fetch id_conto to determine key
    id_conto = None
    try:
         with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_conto FROM Asset WHERE id_asset = %s", (id_asset,))
            res = cur.fetchone()
            if res:
                id_conto = res['id_conto']
    except Exception as e:
        print(f"[ERRORE] Errore recupero conto per modifica dettagli asset: {e}")

    # Names are now plaintext
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Costruisci query dinamica
            query = "UPDATE Asset SET ticker = %s, nome_asset = %s"
            params = [nuovo_ticker_upper, nuovo_nome_upper]
            
            if nuova_quantita is not None:
                query += ", quantita = %s"
                params.append(nuova_quantita)
            
            if nuovo_costo_medio is not None:
                query += ", costo_iniziale_unitario = %s"
                params.append(nuovo_costo_medio)
                
            query += " WHERE id_asset = %s"
            params.append(id_asset)
            
            cur.execute(query, tuple(params))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiornamento dettagli asset: {e}")
        return False

def elimina_asset(id_asset):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Elimina lo storico associato (opzionale, ma consigliato per pulizia)
            # ATTENZIONE: Se eliminiamo storico, perdiamo traccia dei movimenti?
            # Se l'utente elimina l'asset, forse vuole cancellare tutto.
            # Per ora cancelliamo solo l'asset dalla tabella Asset.
            # Lo storico rimane "orfano" ma non crea problemi logici immediati.
            cur.execute("DELETE FROM Asset WHERE id_asset = %s", (id_asset,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione asset: {e}")
        return False




# --- Funzioni Investimenti ---
def aggiungi_investimento(id_conto, ticker, nome_asset, quantita, costo_unitario, data_acquisto, master_key_b64=None):
    # Plaintext
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO Asset (id_conto, ticker, nome_asset, quantita, costo_iniziale_unitario, data_acquisto, prezzo_attuale_manuale) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_asset",
                (id_conto, ticker.upper(), nome_asset, quantita, costo_unitario, data_acquisto, costo_unitario))
            return cur.fetchone()['id_asset']
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta investimento: {e}")
        return None

def modifica_investimento(id_asset, ticker, nome_asset, quantita, costo_unitario, data_acquisto, master_key_b64=None):
    # Fetch id_conto to determine key
    id_conto = None
    try:
         with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_conto FROM Asset WHERE id_asset = %s", (id_asset,))
            res = cur.fetchone()
            if res:
                id_conto = res['id_conto']
    except Exception as e:
        print(f"[ERRORE] Errore recupero conto per modifica asset: {e}")

    # Plaintext
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(
                "UPDATE Asset SET ticker = %s, nome_asset = %s, quantita = %s, costo_iniziale_unitario = %s, data_acquisto = %s WHERE id_asset = %s",
                (ticker.upper(), nome_asset, quantita, costo_unitario, data_acquisto, id_asset))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore modifica investimento: {e}")
        return False

def elimina_investimento(id_asset):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM Asset WHERE id_asset = %s", (id_asset,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione investimento: {e}")
        return False

def ottieni_investimenti(id_conto, master_key_b64=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Asset WHERE id_conto = %s", (id_conto,))
            assets = [dict(row) for row in cur.fetchall()]
            
            # Plaintext
            return assets
            
            return assets
    except Exception as e:
        print(f"[ERRORE] Errore recupero investimenti: {e}")
        return []

def ottieni_dettaglio_asset(id_asset, master_key_b64=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Asset WHERE id_asset = %s", (id_asset,))
            res = cur.fetchone()
            if not res: return None
            
            # Plaintext
            return asset
            
            return asset
    except Exception as e:
        print(f"[ERRORE] Errore recupero dettaglio asset: {e}")
        return None

def aggiorna_prezzo_asset(id_asset, nuovo_prezzo):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Asset SET prezzo_attuale_manuale = %s, data_ultimo_aggiornamento = CURRENT_TIMESTAMP WHERE id_asset = %s",
                        (nuovo_prezzo, id_asset))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore aggiornamento prezzo asset: {e}")
        return False


def _determina_conti_spesa(spesa):
    """
    Determina i conti effettivi di addebito (personale o condiviso) per una spesa fissa,
    considerando anche le carte e i loro conti di appoggio.
    Ritorna: (id_conto_personale, id_conto_condiviso) - uno dei due sarà valorizzato.
    """
    id_conto_personale = spesa.get('id_conto_personale_addebito')
    id_conto_condiviso = spesa.get('id_conto_condiviso_addebito')
    id_carta = spesa.get('id_carta')
    
    if id_carta:
         # Priorità 1: Conto Contabile della Carta (es. Credito)
         if spesa.get('id_conto_carta_pers'):
             return spesa.get('id_conto_carta_pers'), None
         elif spesa.get('id_conto_carta_cond'):
             return None, spesa.get('id_conto_carta_cond')
         
         # Priorità 2: Conto di Riferimento della Carta (es. Debito fallback)
         elif spesa.get('id_carta_rif_pers'):
             return spesa.get('id_carta_rif_pers'), None
         elif spesa.get('id_carta_rif_cond'):
             return None, spesa.get('id_carta_rif_cond')
    
    return id_conto_personale, id_conto_condiviso

def _esegui_spesa_fissa(spesa, descrizione_custom=None, data_esecuzione=None, master_key_b64=None):
    """Esegue una singola spesa fissa creando la transazione."""
    today = datetime.date.today()
    try:
        id_conto_personale, id_conto_condiviso = _determina_conti_spesa(spesa)
        id_carta = spesa.get('id_carta')

        
        # Se nome è criptato e non abbiamo chiave qui (job automatico), lo passiamo criptato o cerchiamo di decriptare?
        # Il job automatico spesso non ha chiavi utente in memoria se gira in background.
        # Ma controlla_scadenze viene chiamato spesso con utente loggato.
        # Assumiamo che descrizione sia già il nome (potrebbe essere criptato).
        
        # Usa valori custom se passati, altrimenti default
        descrizione_finale = descrizione_custom if descrizione_custom else f"{spesa['nome']} (Automatico)"
        data_finale = data_esecuzione if data_esecuzione else today.strftime('%Y-%m-%d')
        
        if id_conto_personale:
            res = aggiungi_transazione(
                id_conto=id_conto_personale,
                data=data_finale,
                descrizione=descrizione_finale,
                importo=-abs(spesa['importo']),
                id_sottocategoria=spesa['id_sottocategoria'],
                master_key_b64=master_key_b64, # Use passed key (could be family key)
                id_carta=id_carta
            )
        elif id_conto_condiviso:
            id_autore = _trova_admin_famiglia(spesa['id_famiglia'])
            if not id_autore: return False
            
            res = aggiungi_transazione_condivisa(
                id_utente_autore=id_autore,
                id_conto_condiviso=id_conto_condiviso,
                data=data_finale,
                descrizione=descrizione_finale,
                importo=-abs(spesa['importo']),
                id_sottocategoria=spesa['id_sottocategoria'],
                master_key_b64=master_key_b64, # Use passed key
                id_carta=id_carta
            )
        else:
            return False
            
        # -- GESTIONE GIROCONTO (NUOVO) --
        if res and spesa.get('is_giroconto'):
             importo_accredito = abs(spesa['importo'])
             descrizione_accredito = f"Giroconto da: {spesa['nome']} (Automatico)"
             
             # Destinazione Personale
             if spesa.get('id_conto_personale_beneficiario'):
                 aggiungi_transazione(
                    id_conto=spesa['id_conto_personale_beneficiario'],
                    data=data_finale,
                    descrizione=descrizione_accredito,
                    importo=importo_accredito,
                    id_sottocategoria=spesa['id_sottocategoria'], # Same category/subcategory? Usually "Giroconti" or "Transfer"
                    master_key_b64=master_key_b64
                 )
             # Destinazione Condivisa
             elif spesa.get('id_conto_condiviso_beneficiario'):
                 id_autore_ben = _trova_admin_famiglia(spesa['id_famiglia'])
                 if id_autore_ben:
                     aggiungi_transazione_condivisa(
                        id_utente_autore=id_autore_ben,
                        id_conto_condiviso=spesa['id_conto_condiviso_beneficiario'],
                        data=data_finale,
                        descrizione=descrizione_accredito,
                        importo=importo_accredito,
                        id_sottocategoria=spesa['id_sottocategoria'],
                        master_key_b64=master_key_b64
                     )

        return res is not None

    except Exception as e:
        print(f"[ERRORE] Errore esecuzione spesa fissa: {e}")
        return False


def check_e_processa_spese_fisse(id_famiglia, master_key_b64=None, id_utente=None, forced_family_key_b64=None):
    oggi = datetime.date.today()
    spese_eseguite = 0
    try:
        spese_da_processare = ottieni_spese_fisse_famiglia(id_famiglia, master_key_b64=master_key_b64, id_utente=id_utente, forced_family_key_b64=forced_family_key_b64)
        
        # Use forced key if available, otherwise user's master key
        key_to_use = forced_family_key_b64 if forced_family_key_b64 else master_key_b64
        
        with get_db_connection() as con:
            cur = con.cursor()
            for spesa in spese_da_processare:
                try:
                    # -----------------------------------------------------------
                    # ROW LOCKING PER EVITARE RACE CONDITIONS
                    # -----------------------------------------------------------
                    # Acquisisce un lock esclusivo sulla riga della spesa fissa.
                    # Qualsiasi altro processo che tenta di processare la stessa spesa
                    # attenderà qui finché questa transazione non viene committata o rollbacked.
                    cur.execute("SELECT 1 FROM SpeseFisse WHERE id_spesa_fissa = %s FOR UPDATE", (spesa['id_spesa_fissa'],))
                    
                    if not spesa['attiva']:
                        continue
                    
                    # Processa solo le spese con addebito automatico abilitato
                    if not spesa.get('addebito_automatico'):
                        continue

                    # Suffisso univoco per identificare la spesa
                    suffisso_id = f"[SF-{spesa['id_spesa_fissa']}]"
                    
                    # Risolvi conti effettivi per il controllo
                    conto_pers_check, conto_cond_check = _determina_conti_spesa(spesa)

                    # Controlla se la spesa è già stata eseguita questo mese
                    already_paid = False
                    
                    # Controllo duplicati Python-side (necessario per descrizioni criptate)
                    already_paid = False
                    
                    # Prepare crypto helper
                    crypto_chk, mk_chk = _get_crypto_and_key(key_to_use)
                    family_key_chk = None
                    try:
                        if id_utente and mk_chk and spesa.get('id_famiglia'):
                             family_key_chk = _get_family_key_for_user(spesa['id_famiglia'], id_utente, mk_chk, crypto_chk)
                    except: pass
                    
                    def _is_dup_desc(desc_enc):
                        # 1. Try with Master Key (Personal) or provided key
                        d = _decrypt_if_key(desc_enc, mk_chk, crypto_chk, silent=True)
                        if suffisso_id in d: return True
                        # 2. Try with Family Key (Shared)
                        if family_key_chk:
                            d2 = _decrypt_if_key(desc_enc, family_key_chk, crypto_chk, silent=True)
                            if suffisso_id in d2: return True
                        # 3. Try plaintext?
                        if suffisso_id in desc_enc: return True
                        return False

                    # Check personal account
                    if conto_pers_check:
                        cur.execute("""
                            SELECT descrizione FROM Transazioni
                            WHERE id_conto = %s
                            AND TO_CHAR(data::date, 'YYYY-MM') = %s
                        """, (conto_pers_check, oggi.strftime('%Y-%m')))
                        for row in cur.fetchall():
                             if _is_dup_desc(row['descrizione']): 
                                 already_paid = True
                                 break
                    
                    # Check shared account
                    if not already_paid and conto_cond_check:
                        cur.execute("""
                            SELECT descrizione FROM TransazioniCondivise
                            WHERE id_conto_condiviso = %s
                            AND TO_CHAR(data::date, 'YYYY-MM') = %s
                        """, (conto_cond_check, oggi.strftime('%Y-%m')))
                        for row in cur.fetchall():
                             if _is_dup_desc(row['descrizione']):
                                 already_paid = True
                                 break

                    if already_paid:
                        continue

                    # Se il giorno di addebito è passato, esegui la transazione
                    if oggi.day >= spesa['giorno_addebito']:
                        # Usa il giorno configurato per la data di esecuzione, non la data odierna
                        data_esecuzione = datetime.date(oggi.year, oggi.month, spesa['giorno_addebito']).strftime('%Y-%m-%d')
                        # Aggiungi suffisso ID alla descrizione per tracciabilità e controllo duplicati
                        descrizione = f"Spesa Fissa: {spesa['nome']} {suffisso_id}"
                        importo = -abs(spesa['importo'])

                        # NOTA: _esegui_spesa_fissa userà una sua connessione per eseguire l'insert.
                        # Dato che siamo in READ COMMITTED, l'insert sarà visibile agli altri solo dopo che loro acquisiranno il lock.
                        if _esegui_spesa_fissa(spesa, descrizione_custom=descrizione, data_esecuzione=data_esecuzione, master_key_b64=key_to_use):
                            spese_eseguite += 1
                
                except Exception as e:
                    logger.error(f"Errore processamento singola spesa {spesa.get('id_spesa_fissa')}: {e}")
                    # Continua con la prossima spesa, non rompere tutto il ciclo
                    continue

            # Commit finale: rilascia TUTTI i lock acquisiti nel loop
            if spese_eseguite > 0:
                con.commit()
            else:
                con.commit() # Commit comunque necessario per rilasciare i lock anche se non abbiamo fatto insert
                
        return spese_eseguite
    except Exception as e:
        logger.error(f"Errore critico durante il processamento delle spese fisse: {e}")
        return 0


# --- FUNZIONI STORICO ASSET GLOBALE (cross-famiglia) ---

_TABELLA_STORICO_CREATA = False
_LAST_UPDATE_CHECK_CACHE = {}  # Cache per throttling aggiornamenti (ticker -> datetime)

def _crea_tabella_storico_asset_globale():
    """Crea la tabella StoricoAssetGlobale se non esiste."""
    global _TABELLA_STORICO_CREATA
    if _TABELLA_STORICO_CREATA:
        return True
        
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Crea la tabella se non esiste
            cur.execute("""
                CREATE TABLE IF NOT EXISTS StoricoAssetGlobale (
                    id SERIAL PRIMARY KEY,
                    ticker VARCHAR(30) NOT NULL,
                    data DATE NOT NULL,
                    prezzo_chiusura DECIMAL(18, 6) NOT NULL,
                    data_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 2. Migrazione: verifica esistenza UNIQUE constraint (necessario per ON CONFLICT)
            cur.execute("""
                SELECT count(*) as conteggio
                FROM pg_indexes 
                WHERE tablename = 'storicoassetglobale' 
                  AND indexdef LIKE '%(ticker, data)%'
                  AND indexdef LIKE '%UNIQUE%'
            """)
            res = cur.fetchone()
            has_unique = res['conteggio'] > 0 if res else False
            
            if not has_unique:
                print("[INFO] Migrazione: Aggiunta vincolo UNIQUE a StoricoAssetGlobale")
                # A. Rimuovi eventuali duplicati prima di applicare il vincolo
                cur.execute("""
                    DELETE FROM StoricoAssetGlobale a USING (
                        SELECT MIN(id) as min_id, ticker, data
                        FROM StoricoAssetGlobale
                        GROUP BY ticker, data
                        HAVING COUNT(*) > 1
                    ) b
                    WHERE a.ticker = b.ticker 
                      AND a.data = b.data 
                      AND a.id <> b.min_id
                """)
                
                # B. Aggiungi il vincolo UNIQUE
                try:
                    cur.execute("ALTER TABLE StoricoAssetGlobale ADD CONSTRAINT unique_ticker_data UNIQUE (ticker, data)")
                except Exception as ex:
                    # Se fallisce (es. se esiste già un'altro tipo di indice unico), logga e continua
                    print(f"[WARNING] Impossibile aggiungere vincolo UNIQUE: {ex}")
            
            # 3. Indici aggiuntivi (non unici) per performance
            cur.execute("CREATE INDEX IF NOT EXISTS idx_storico_ticker ON StoricoAssetGlobale(ticker);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_storico_data ON StoricoAssetGlobale(data);")
            
            con.commit()
            _TABELLA_STORICO_CREATA = True
            return True
    except Exception as e:
        print(f"[ERRORE] Errore creazione/migrazione tabella StoricoAssetGlobale: {e}")
        return False


def _pulisci_storico_vecchio():
    """
    Ottimizza lo storico conservando:
    - Ultimi 5 anni: dettaglio giornaliero
    - Da 5 a 25 anni: dettaglio mensile (solo primo del mese)
    - Oltre 25 anni: elimina
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Elimina dati più vecchi di 25 anni (pulizia profonda)
            data_limite_25y = (datetime.date.today() - datetime.timedelta(days=365*25)).strftime('%Y-%m-%d')
            cur.execute("DELETE FROM StoricoAssetGlobale WHERE data < %s", (data_limite_25y,))
            
            # 2. Downsampling: per dati più vecchi di 5 anni, mantieni solo il 1° del mese
            # Nota: SQLite strftime('%d', data) ritorna il giorno. Se != '01', eliminiamo.
            data_limite_5y = (datetime.date.today() - datetime.timedelta(days=365*5)).strftime('%Y-%m-%d')
            
            # Query ottimizzata: elimina record vecchi che NON sono il primo del mese
            # Postgres syntax: EXTRACT(DAY FROM data) returns numeric day (1-31)
            cur.execute("""
                DELETE FROM StoricoAssetGlobale 
                WHERE data < %s 
                  AND EXTRACT(DAY FROM data) != 1
            """, (data_limite_5y,))
            
            eliminati = cur.rowcount
            if eliminati > 0:
                print(f"[INFO] Ottimizzazione storico: rimossi {eliminati} record giornalieri vecchi")
            
            con.commit()
            return eliminati
    except Exception as e:
        print(f"[ERRORE] Errore ottimizzazione storico vecchio: {e}")
        return 0


def salva_storico_asset_globale(ticker: str, dati_storici: list):
    """
    Salva/aggiorna prezzi storici nella cache globale.
    
    Args:
        ticker: Il ticker dell'asset (es. "AAPL")
        dati_storici: Lista di dict con {'data': 'YYYY-MM-DD', 'prezzo': float}
    
    Returns:
        Numero di record inseriti/aggiornati
    """
    if not dati_storici:
        return 0
    
    # Assicurati che la tabella esista
    _crea_tabella_storico_asset_globale()
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            inseriti = 0
            
            for record in dati_storici:
                # Validazione base per evitare record corrotti/nulli che rompono la transazione
                if not record.get('data') or record.get('prezzo') is None:
                    continue
                
                try:
                    prezzo = float(record['prezzo'])
                    # Evita NaN o Inf se presenti (raro ma possibile con API finanziarie)
                    if prezzo != prezzo or prezzo > 1e15: 
                        continue
                except (ValueError, TypeError):
                    continue

                cur.execute("""
                    INSERT INTO StoricoAssetGlobale (ticker, data, prezzo_chiusura, data_aggiornamento)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (ticker, data) DO UPDATE SET 
                        prezzo_chiusura = EXCLUDED.prezzo_chiusura,
                        data_aggiornamento = CURRENT_TIMESTAMP
                """, (ticker.upper(), record['data'], prezzo))
                inseriti += 1
            
            con.commit()
            return inseriti
    except Exception as e:
        # Se arriviamo qui, l'intera transazione per questo ticker è fallita
        # Il context manager gestirà il rollback automatico della connessione
        print(f"[ERRORE] Errore salvataggio storico asset globale per {ticker}: {e}")
        return 0


def ottieni_storico_asset_globale(ticker: str, data_inizio: str = None, data_fine: str = None):
    """
    Recupera storico prezzi dalla cache globale.
    
    Args:
        ticker: Il ticker dell'asset
        data_inizio: Data inizio filtro (YYYY-MM-DD), opzionale
        data_fine: Data fine filtro (YYYY-MM-DD), opzionale
    
    Returns:
        Lista di dict con {data, prezzo_chiusura} ordinati per data crescente
    """
    # Assicurati che la tabella esista
    _crea_tabella_storico_asset_globale()
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            query = "SELECT data, prezzo_chiusura FROM StoricoAssetGlobale WHERE ticker = %s"
            params = [ticker.upper()]
            
            if data_inizio:
                query += " AND data >= %s"
                params.append(data_inizio)
            
            if data_fine:
                query += " AND data <= %s"
                params.append(data_fine)
            
            query += " ORDER BY data ASC"
            
            cur.execute(query, tuple(params))
            return [{'data': str(row['data']), 'prezzo_chiusura': float(row['prezzo_chiusura'])} for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore recupero storico asset globale: {e}")
        return []


def ultimo_aggiornamento_storico(ticker: str):
    """
    Restituisce la data dell'ultimo record per il ticker.
    """
    # Assicurati che la tabella esista
    _crea_tabella_storico_asset_globale()
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT MAX(data) as ultima_data FROM StoricoAssetGlobale WHERE ticker = %s", (ticker.upper(),))
            result = cur.fetchone()
            if result and result['ultima_data']:
                return str(result['ultima_data'])
            return None
    except Exception as e:
        print(f"[ERRORE] Errore recupero ultimo aggiornamento storico: {e}")
        return None

def _data_piu_vecchia_storico(ticker: str):
    """
    Restituisce la data del record più vecchio per il ticker.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT MIN(data) as prima_data FROM StoricoAssetGlobale WHERE ticker = %s", (ticker.upper(),))
            result = cur.fetchone()
            if result and result['prima_data']:
                return str(result['prima_data'])
            return None
    except Exception as e:
        print(f"[ERRORE] Errore recupero data più vecchia storico: {e}")
        return None


def aggiorna_storico_asset_se_necessario(ticker: str, anni: int = 25):
    """
    Aggiorna lo storico di un asset da yfinance.
    Strategia ibrida:
    - Se nuovo: scarica 25 anni mensili + 5 anni giornalieri.
    - Se esistente: aggiorna incrementalmente (giornaliero).
    """
    # Prima ottimizza i dati vecchi (downsampling)
    _pulisci_storico_vecchio()
    
    # Throttle check: se controllato meno di 1 ora fa, salta
    from datetime import datetime as dt
    ora = datetime.datetime.now()
    if ticker in _LAST_UPDATE_CHECK_CACHE:
        last_check = _LAST_UPDATE_CHECK_CACHE[ticker]
        if (ora - last_check).total_seconds() < 3600:
            # print(f"[DEBUG] Skip update {ticker} (throttled)")
            return False
    
    # Aggiorna ultimo controllo a ORA (indipendentemente dall'esito)
    _LAST_UPDATE_CHECK_CACHE[ticker] = ora
    
    ultima_data = ultimo_aggiornamento_storico(ticker)
    prima_data = _data_piu_vecchia_storico(ticker)
    
    oggi = datetime.date.today()
    oggi_str = oggi.strftime('%Y-%m-%d')
    
    # Calcola data target di inizio
    target_start_date = (oggi - datetime.timedelta(days=anni*365)).strftime('%Y-%m-%d')
    
    # Recupera data inizio trading effettiva dell'asset (inception date)
    from utils.yfinance_manager import ottieni_data_inizio_trading
    inception_date = ottieni_data_inizio_trading(ticker)
    
    # Se abbiamo una inception date, la data target non può essere precedente ad essa
    if inception_date and inception_date > target_start_date:
        target_start_date = inception_date
        # Buffer di sicurezza: se inception è 2019-01-01, e noi abbiamo 2019-01-05, è ok.
    
    # Condizione per download completo:
    # 1. Non abbiamo dati (ultima_data is None)
    # 2. Oppure i dati che abbiamo sono troppo recenti RISPETTO AL POSSIBILE (target_start_date)
    #    Questo significa che l'utente ha chiesto 25 anni ma noi ne abbiamo meno, ED ESISTONO DATI PIÙ VECCHI.
    
    manca_storico_profondo = False
    if prima_data:
        # Se la data più vecchia che abbiamo è POSTERIORE alla valid start date (con un margine di tolleranza di 30gg)
        # Esempio A: Asset vecchio (es. MSFT inizia 1986). Target: 2000. PrimaData: 2020. -> 2020 > 2000 -> MANCA.
        # Esempio B: Asset nuovo (es. VWCE inizia 2019). Target: 2019. PrimaData: 2019-07. -> 2019-07 > 2019-06 (presunto) -> Forse manca qualche mese.
        # Se PrimaData è 2019-07-23 e Inception è 2019-07-23 -> OK (differenza < 30gg)
        
        limit_date_dt = datetime.datetime.strptime(target_start_date, '%Y-%m-%d') + datetime.timedelta(days=30)
        limit_date = limit_date_dt.strftime('%Y-%m-%d')
        
        manca_storico_profondo = prima_data > limit_date
    
    # --- CASO 1: PRIMA IMPORTAZIONE O STORICO INSUFFICIENTE ---
    if not ultima_data or manca_storico_profondo:
        print(f"[INFO] Download completo storico {anni}y per {ticker} (Depth check: {manca_storico_profondo})...")
        inseriti_tot = 0
        
        # 1. Scarica storico lungo (es. 25 anni) a risoluzione MENSILE
        # Usiamo richiesta diretta per specificare l'intervallo '1mo'
        try:
            import requests
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            # Scarica anni richiesti mensili
            params_long = {'interval': '1mo', 'range': f'{anni}y'}
            resp_long = requests.get(url, headers=headers, params=params_long, timeout=15)
            if resp_long.status_code == 200:
                dati_long = _estrai_dati_da_risposta_yf(resp_long.json())
                if dati_long:
                    salvati_long = salva_storico_asset_globale(ticker, dati_long)
                    inseriti_tot += salvati_long
                    print(f"      - Salvati {salvati_long}/{len(dati_long)} punti mensili (base storica)")
        
            # 2. Scarica ultimi 5 anni a risoluzione GIORNALIERA (sovrascrive/dettaglia i recenti)
            # Solo se anni > 5, altrimenti il range è quello richiesto
            if anni >= 5:
                params_short = {'interval': '1d', 'range': '5y'}
                resp_short = requests.get(url, headers=headers, params=params_short, timeout=15)
                if resp_short.status_code == 200:
                    dati_short = _estrai_dati_da_risposta_yf(resp_short.json())
                    if dati_short:
                        salvati_short = salva_storico_asset_globale(ticker, dati_short)
                        inseriti_tot += salvati_short
                        print(f"      - Salvati {salvati_short}/{len(dati_short)} punti giornalieri (dettaglio recente)")
            
            return inseriti_tot > 0
            
        except Exception as e:
            print(f"[ERRORE] Errore download base {ticker}: {e}")
            return False

    # --- CASO 2: AGGIORNAMENTO INCREMENTALE (Solo se abbiamo già storico profondo) ---
    if ultima_data >= oggi_str:
        return False
    
    from datetime import datetime as dt
    ultima_dt = dt.strptime(ultima_data, '%Y-%m-%d')
    oggi_dt = dt.strptime(oggi_str, '%Y-%m-%d')
    giorni_mancanti = (oggi_dt - ultima_dt).days
    
    if giorni_mancanti <= 0:
        return False
    
    print(f"[INFO] Aggiornamento incrementale {ticker}: +{giorni_mancanti} giorni")
    
    # Determina range minimo per coprire il buco
    if giorni_mancanti <= 5: range_yf = '5d'
    elif giorni_mancanti <= 30: range_yf = '1mo'
    elif giorni_mancanti <= 90: range_yf = '3mo'
    elif giorni_mancanti <= 180: range_yf = '6mo'
    elif giorni_mancanti <= 365: range_yf = '1y'
    else: range_yf = '5y' # Se manca più di un anno, riscarica 5y
    
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        params = {'interval': '1d', 'range': range_yf}
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            dati_raw = _estrai_dati_da_risposta_yf(response.json())
            # Filtra solo i dati veramente nuovi (> ultima_data)
            dati_nuovi = [d for d in dati_raw if d['data'] > ultima_data]
            
            if dati_nuovi:
                salva_storico_asset_globale(ticker, dati_nuovi)
                return True
                
        return False
    except Exception as e:
        print(f"[ERRORE] Errore update {ticker}: {e}")
        return False

def _estrai_dati_da_risposta_yf(data: dict) -> list:
    """Helper per estrarre lista {data, prezzo} dal JSON grezzo di YF."""
    results = []
    try:
        if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
            res = data['chart']['result'][0]
            if 'timestamp' in res and 'indicators' in res:
                timestamps = res['timestamp']
                quotes = res['indicators']['quote'][0]
                closes = quotes.get('close', [])
                
                from datetime import datetime as dt
                for i, ts in enumerate(timestamps):
                    if i < len(closes) and closes[i] is not None:
                        data_str = dt.fromtimestamp(ts).strftime('%Y-%m-%d')
                        results.append({
                            'data': data_str,
                            'prezzo': float(closes[i])
                        })
    except Exception:
        pass
    return results

def ottieni_asset_conto(id_conto: int, master_key_b64: Optional[str] = None, is_shared: bool = False, id_utente: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recupera gli asset (azioni, etf, ecc.) di un conto investimento.
    Supporta conti condivisi (richiede id_utente per recuperare chiave famiglia).
    Tenta la decrittazione con entrambe le chiavi (Personale e Famiglia) per robustezza.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        # Determine Keys to Try
        keys_to_try = []
        family_key = None
        
        if id_utente:
             id_famiglia = ottieni_prima_famiglia_utente(id_utente)
             if id_famiglia and master_key:
                  family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        if is_shared:
            if family_key: keys_to_try.append(family_key)
            if master_key: keys_to_try.append(master_key)
        else:
            if master_key: keys_to_try.append(master_key)
            if family_key: keys_to_try.append(family_key)
            
        # Helper for multi-key decryption
        def try_decrypt(val, keys):
            last_res = None
            for k in keys:
                if not k: continue
                try:
                    res = _decrypt_if_key(val, k, crypto, silent=True)
                    if res == "[ENCRYPTED]":
                        last_res = res
                        continue
                    return res
                except: continue
            return last_res if last_res else "[ENCRYPTED]"

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Asset WHERE id_conto = %s", (id_conto,))
            rows = cur.fetchall()
            
            assets = []
            for r in rows:
                try:
                    nome = try_decrypt(r['nome_asset'], keys_to_try)
                    ticker = try_decrypt(r['ticker'], keys_to_try)
                    assets.append({
                        'id': r['id_asset'],
                        'nome': nome,
                        'ticker': ticker,
                        'quantita': float(r['quantita'])
                    })
                except: continue
            return assets
    except Exception as e:
        logger.error(f"Errore ottieni_asset_conto: {e}")
        return []

