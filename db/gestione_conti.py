"""
Funzioni conti: personali, condivisi, CRUD, saldi
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
from dateutil.relativedelta import relativedelta

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code, _get_system_keys,
    HASH_SALT, SYSTEM_FERNET_KEY, SERVER_SECRET_KEY,
    crypto as _crypto_instance
)


# --- Funzioni Conti ---
def ottieni_conti(id_utente: str, master_key_b64: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_conto, nome_conto, tipo, iban, valore_manuale, rettifica_saldo, config_speciale FROM Conti WHERE id_utente = %s", (id_utente,))
            conti = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            
            # Attempt to retrieve Family Key if possible
            try:
                id_famiglia = ottieni_prima_famiglia_utente(id_utente)
                if id_famiglia and master_key:
                     family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            except: pass

            keys_to_try = [master_key]
            if family_key: keys_to_try.append(family_key)

            # Helper to try keys
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

            if master_key:
                for conto in conti:
                    conto['nome_conto'] = try_decrypt(conto['nome_conto'], keys_to_try)
                    conto['tipo'] = try_decrypt(conto['tipo'], keys_to_try)
                    if 'iban' in conto:
                        conto['iban'] = try_decrypt(conto['iban'], keys_to_try)
                    if 'config_speciale' in conto:
                        conto['config_speciale'] = try_decrypt(conto['config_speciale'], keys_to_try)
                    
                    # Handle numeric fields that might be encrypted
                    for field in ['valore_manuale', 'rettifica_saldo']:
                        if field in conto and conto[field] is not None:
                            decrypted = try_decrypt(conto[field], keys_to_try)
                            try:
                                conto[field] = float(decrypted)
                            except (ValueError, TypeError):
                                conto[field] = decrypted # Keep as is if not a number
            
            return conti
    except Exception as e:
        print(f"[ERRORE] Errore recupero conti: {e}")
        return []

def imposta_conto_default_utente(id_utente, id_conto_personale=None, id_conto_condiviso=None, id_carta_default=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase

            if id_carta_default:
                # Imposta la carta e annulla i conti
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_conto_condiviso_default = NULL, id_carta_default = %s WHERE id_utente = %s",
                    (id_carta_default, id_utente))
            elif id_conto_personale:
                # Imposta il conto personale e annulla gli altri
                cur.execute(
                    "UPDATE Utenti SET id_conto_condiviso_default = NULL, id_carta_default = NULL, id_conto_default = %s WHERE id_utente = %s",
                    (id_conto_personale, id_utente))
            elif id_conto_condiviso:
                # Imposta il conto condiviso e annulla gli altri
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_carta_default = NULL, id_conto_condiviso_default = %s WHERE id_utente = %s",
                    (id_conto_condiviso, id_utente))
            else:  # Se tutti sono None, annulla tutto
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_conto_condiviso_default = NULL, id_carta_default = NULL WHERE id_utente = %s",
                    (id_utente,))

            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante l'impostazione del conto di default: {e}")
        return False

def ottieni_conto_default_utente(id_utente):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("SELECT id_conto_default, id_conto_condiviso_default, id_carta_default FROM Utenti WHERE id_utente = %s",
                        (id_utente,))
            result = cur.fetchone()
            if result:
                if result.get('id_conto_default') is not None:
                    return {'id': result['id_conto_default'], 'tipo': 'personale'}
                elif result.get('id_conto_condiviso_default') is not None:
                    return {'id': result['id_conto_condiviso_default'], 'tipo': 'condiviso'}
                elif result.get('id_carta_default') is not None:
                    return {'id': result['id_carta_default'], 'tipo': 'carta'}
            return None
    except Exception as e:
        print(f"[ERRORE] Errore durante il recupero del conto di default: {e}")
        return None

def aggiungi_saldo_iniziale(id_conto, saldo_iniziale):
    if saldo_iniziale <= 0:
        return None
    data_oggi = datetime.date.today().strftime('%Y-%m-%d')
    descrizione = "SALDO INIZIALE - Setup App"
    return aggiungi_transazione(id_conto=id_conto, data=data_oggi, descrizione=descrizione, importo=saldo_iniziale,
                                id_sottocategoria=None)


# --- Funzioni Conti Personali ---
def aggiungi_conto(id_utente, nome_conto, tipo_conto, iban=None, valore_manuale=0.0, borsa_default=None, master_key_b64=None, id_famiglia=None, config_speciale=None, icona=None, colore=None):
    if not valida_iban_semplice(iban):
        return None, "IBAN non valido"
    iban_pulito = iban.strip().upper() if iban else None
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Use family_key for account name encryption (so other family members can decrypt it)
    encryption_key = master_key
    if master_key and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        if family_key:
            encryption_key = family_key
    
    encrypted_nome = _encrypt_if_key(nome_conto, encryption_key, crypto)
    encrypted_iban = _encrypt_if_key(iban_pulito, master_key, crypto)  # IBAN stays with master_key
    encrypted_config = _encrypt_if_key(config_speciale, encryption_key, crypto) # config_speciale stays with encryption_key
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute(
                "INSERT INTO Conti (id_utente, nome_conto, tipo, iban, valore_manuale, borsa_default, config_speciale, icona, colore) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_conto",
                (id_utente, encrypted_nome, tipo_conto, encrypted_iban, valore_manuale, borsa_default, encrypted_config, icona, colore))
            id_nuovo_conto = cur.fetchone()['id_conto']
            con.commit()
            return id_nuovo_conto, "Conto creato con successo"
    except Exception as e:
        print(f"[ERRORE] Errore generico: {e}")
        return None, f"Errore generico: {e}"


def ottieni_conti_utente(id_utente, master_key_b64=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_conto, nome_conto, tipo, icona, colore FROM Conti WHERE id_utente = %s AND (nascosto = FALSE OR nascosto IS NULL)", (id_utente,))
            results = [dict(row) for row in cur.fetchall()]
            
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key:
                cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s", (id_utente,))
                fam_res = cur.fetchone()
                if fam_res and fam_res['id_famiglia']:
                    family_key = _get_family_key_for_user(fam_res['id_famiglia'], id_utente, master_key, crypto)
            
            for row in results:
                # Try family_key first, then master_key as fallback
                dec_nome = None
                if family_key:
                    dec_nome = _decrypt_if_key(row['nome_conto'], family_key, crypto, silent=True)
                
                if dec_nome and dec_nome != "[ENCRYPTED]" and not dec_nome.startswith("gAAAAA"):
                    row['nome_conto'] = dec_nome
                    row['tipo'] = _decrypt_if_key(row['tipo'], family_key, crypto, silent=True)
                elif master_key:
                    row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto, silent=True)
                    row['tipo'] = _decrypt_if_key(row['tipo'], master_key, crypto, silent=True)
                else:
                    row['nome_conto'] = "[ENCRYPTED]"
                    row['tipo'] = "[ENCRYPTED]"
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero conti: {e}")
        return []


def ottieni_dettagli_conti_utente(id_utente, master_key_b64=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT C.id_conto,
                               C.nome_conto,
                               C.tipo,
                               C.iban,
                               C.borsa_default,
                               C.config_speciale,
                               C.icona,
                               C.colore,
                               CASE
                                   WHEN C.tipo = 'Fondo Pensione' THEN COALESCE(CAST(C.valore_manuale AS TEXT), '0.0')
                                   WHEN C.tipo = 'Investimento'
                                       THEN CAST((SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                             FROM Asset A
                                             WHERE A.id_conto = C.id_conto) AS TEXT)
                                   ELSE CAST((SELECT COALESCE(SUM(T.importo), 0.0) FROM Transazioni T WHERE T.id_conto = C.id_conto) +
                                        COALESCE(CAST(NULLIF(CAST(C.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0) AS TEXT)
                                   END AS saldo_calcolato
                        FROM Conti C
                        WHERE C.id_utente = %s AND (C.nascosto = FALSE OR C.nascosto IS NULL)
                        ORDER BY C.nome_conto
                        """, (id_utente,))
            results = [dict(row) for row in cur.fetchall()]

            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            
            # Get family_key for this user (accounts may be encrypted with it)
            family_key = None
            if master_key:
                cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s", (id_utente,))
                fam_res = cur.fetchone()
                if fam_res and fam_res['id_famiglia']:
                    family_key = _get_family_key_for_user(fam_res['id_famiglia'], id_utente, master_key, crypto)
            
            for row in results:
                # Try family_key first, then master_key as fallback
                decrypted_nome = None
                if family_key:
                    decrypted_nome = _decrypt_if_key(row['nome_conto'], family_key, crypto, silent=True)
                
                if decrypted_nome and decrypted_nome != "[ENCRYPTED]" and not decrypted_nome.startswith("gAAAAA"):
                    row['nome_conto'] = decrypted_nome
                    row['tipo'] = _decrypt_if_key(row['tipo'], family_key, crypto, silent=True)
                elif master_key:
                    # Fallback to master_key for legacy data
                    row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto, silent=True)
                    row['tipo'] = _decrypt_if_key(row['tipo'], master_key, crypto, silent=True)
                
                # IBAN always uses master_key (personal data)
                if master_key:
                    row['iban'] = _decrypt_if_key(row['iban'], master_key, crypto, silent=True)
                
                # Decrypt config_speciale
                config_spec = row.get('config_speciale')
                if config_spec:
                    dec_config = None
                    if family_key:
                        dec_config = _decrypt_if_key(config_spec, family_key, crypto, silent=True)
                    if (not dec_config or dec_config == "[ENCRYPTED]" or dec_config.startswith("gAAAAA")) and master_key:
                        dec_config = _decrypt_if_key(config_spec, master_key, crypto, silent=True)
                    row['config_speciale'] = dec_config
                else:
                    row['config_speciale'] = None
                
                # Handle saldo_calcolato
                saldo_str = row['saldo_calcolato']
                if row['tipo'] == 'Fondo Pensione':
                    if master_key:
                        saldo_str = _decrypt_if_key(saldo_str, master_key, crypto, silent=True)
                
                try:
                    row['saldo_calcolato'] = float(saldo_str) if saldo_str else 0.0
                except (ValueError, TypeError):
                    row['saldo_calcolato'] = 0.0
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero dettagli conti: {e}")
        return []


def modifica_conto(id_conto, id_utente, nome_conto, tipo_conto, iban=None, valore_manuale=None, borsa_default=None, master_key_b64=None, id_famiglia=None, config_speciale=None, icona=None, colore=None):
    if not valida_iban_semplice(iban):
        return False, "IBAN non valido"
    iban_pulito = iban.strip().upper() if iban else None
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Use family_key for account name encryption (so other family members can decrypt it)
    encryption_key = master_key
    if master_key and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        if family_key:
            encryption_key = family_key
    
    encrypted_nome = _encrypt_if_key(nome_conto, encryption_key, crypto)
    encrypted_iban = _encrypt_if_key(iban_pulito, master_key, crypto)  # IBAN stays with master_key
    encrypted_config = _encrypt_if_key(config_speciale, encryption_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()

            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase 
            # Se il valore manuale non viene passato, non lo aggiorniamo (manteniamo quello esistente)
            if valore_manuale is not None:
                cur.execute("UPDATE Conti SET nome_conto = %s, tipo = %s, iban = %s, valore_manuale = %s, borsa_default = %s, config_speciale = %s, icona = %s, colore = %s WHERE id_conto = %s AND id_utente = %s",
                            (encrypted_nome, tipo_conto, encrypted_iban, valore_manuale, borsa_default, encrypted_config, icona, colore, id_conto, id_utente))
            else:
                cur.execute("UPDATE Conti SET nome_conto = %s, tipo = %s, iban = %s, borsa_default = %s, config_speciale = %s, icona = %s, colore = %s WHERE id_conto = %s AND id_utente = %s",
                             (encrypted_nome, tipo_conto, encrypted_iban, borsa_default, encrypted_config, icona, colore, id_conto, id_utente))
            
            rows_affected = cur.rowcount

            con.commit()
            return rows_affected > 0, "Conto modificato con successo"
    except Exception as e:
        print(f"[ERRORE] Errore generico: {e}")
        return False, f"Errore generico: {e}"


def esegui_ripristino_satispay(id_conto, id_utente, master_key_b64=None):
    """
    Esegue il ripristino del budget per un conto Satispay.
    """
    try:
        from db.gestione_db import ottieni_dettagli_conto, aggiungi_transazione, _get_crypto_and_key, _decrypt_if_key, _encrypt_if_key
        import json
        from datetime import datetime

        # 1. Recupera dettagli conto
        conto = ottieni_dettagli_conto(id_conto, master_key_b64)
        if not conto or conto.get('tipo', '').lower() != 'portafoglio elettronico':
            return False, "Conto non trovato o tipo non valido"

        config = json.loads(conto.get('config_speciale') or '{}')
        if config.get('sottotipo') != 'satispay':
            return False, "Non è un conto Satispay"

        budget_settimanale = float(config.get('budget_settimanale', 0))
        id_conto_collegato = config.get('id_conto_collegato')
        if not id_conto_collegato:
            return False, "Conto collegato non configurato"

        # 2. Verifica se è Lunedì (già fatto dal chiamante, ma per sicurezza...)
        # La richiesta dice che il ripristino è fisso il Lunedì.

        # 3. Calcola delta
        saldo_attuale = float(conto.get('saldo_calcolato', 0))
        delta = budget_settimanale - saldo_attuale

        if delta == 0:
            # Aggiorna ultimo_ripristino per non riprovare oggi
            config['ultimo_ripristino'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            modifica_conto(id_conto, id_utente, conto['nome_conto'], conto['tipo'], 
                           iban=conto.get('iban'), valore_manuale=conto.get('valore_manuale'),
                           borsa_default=conto.get('borsa_default'), 
                           master_key_b64=master_key_b64, config_speciale=json.dumps(config))
            return True, "Budget già allineato"

        # 4. Crea Giroconto
        desc = "Ripristino Budget Satispay"
        data_invio = datetime.now().strftime("%Y-%m-%d")
        
        if delta > 0:
            # Sposta da conto collegato a Satispay
            from_conto = id_conto_collegato
            to_conto = id_conto
            importo = delta
        else:
            # Sposta da Satispay a conto collegato (ritorno eccedenza)
            from_conto = id_conto
            to_conto = id_conto_collegato
            importo = abs(delta)

        # Usiamo aggiungi_giroconto (se esiste) o due transazioni
        # Per semplicità qui usiamo aggiungi_transazione per entrambi i lati
        # Ma è meglio usare la funzione dedicata se disponibile.
        # Assumo che aggiungi_giroconto sia disponibile.
        from db.gestione_db import aggiungi_giroconto
        success, msg = aggiungi_giroconto(id_utente, from_conto, to_conto, importo, data_invio, desc, master_key_b64=master_key_b64)
        
        if success:
            # 5. Aggiorna configurazione
            config['ultimo_ripristino'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            modifica_conto(id_conto, id_utente, conto['nome_conto'], conto['tipo'], 
                           iban=conto.get('iban'), valore_manuale=conto.get('valore_manuale'),
                           borsa_default=conto.get('borsa_default'), 
                           master_key_b64=master_key_b64, config_speciale=json.dumps(config))
            return True, "Ripristino completato"
        else:
            return False, f"Fallimento giroconto: {msg}"

    except Exception as e:
        print(f"[ERRORE] Ripristino Satispay: {e}")
        return False, f"Errore: {e}"


def controlla_ripristini_satispay(id_utente, master_key_b64=None):
    """
    Controlla se ci sono conti Satispay che necessitano di ripristino.
    Eseguito al login o tramite scheduler.
    """
    try:
        from datetime import datetime, timedelta
        import json
        
        # 1. Recupera tutti i conti dell'utente
        conti = ottieni_dettagli_conti_utente(id_utente, master_key_b64)
        
        oggi = datetime.now()
        is_lunedi = oggi.weekday() == 0
        
        for conto in conti:
            if conto.get('tipo', '').lower() == 'portafoglio elettronico':
                config_str = conto.get('config_speciale')
                if not config_str: continue
                
                try:
                    config = json.loads(config_str)
                    if config.get('sottotipo') == 'satispay':
                        # Verifica se è ora di ripristinare
                        ultimo_rip_str = config.get('ultimo_ripristino')
                        esegui = False
                        
                        if not ultimo_rip_str:
                            # Mai eseguito, se è lunedì eseguiamo
                            if is_lunedi: esegui = True
                        else:
                            ultimo_rip = datetime.strptime(ultimo_rip_str, "%Y-%m-%d %H:%M:%S")
                            # Se l'ultimo ripristino è di una settimana diversa e oggi è lunedì
                            if oggi.date() > ultimo_rip.date() and is_lunedi:
                                # Verifica che sia passata almeno una settimana o che sia un nuovo lunedì
                                if (oggi - ultimo_rip).days >= 1:
                                    esegui = True
                        
                        if esegui:
                            print(f"Avvio ripristino automatico Satispay per conto {conto['id_conto']}")
                            esegui_ripristino_satispay(conto['id_conto'], id_utente, master_key_b64)
                            
                except Exception as ex:
                    print(f"[ERRORE] Parsing config_speciale per conto {conto['id_conto']}: {ex}")
                    
        return True
    except Exception as e:
        print(f"[ERRORE] controlla_ripristini_satispay: {e}")
        return False


def ottieni_saldo_iniziale_conto(id_conto):
    """Recupera l'importo della transazione 'Saldo Iniziale' per un conto."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT importo FROM Transazioni WHERE id_conto = %s AND descrizione = 'Saldo Iniziale'", (id_conto,))
            res = cur.fetchone()
            return res['importo'] if res else 0.0
    except Exception as e:
        print(f"[ERRORE] Errore recupero saldo iniziale: {e}")
        return 0.0


def aggiorna_saldo_iniziale_conto(id_conto, nuovo_saldo):
    """
    Aggiorna la transazione 'Saldo Iniziale' o la crea se non esiste.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_transazione FROM Transazioni WHERE id_conto = %s AND descrizione = 'Saldo Iniziale'", (id_conto,))
            res = cur.fetchone()
            
            if res:
                id_transazione = res['id_transazione']
                if nuovo_saldo == 0:
                    # Opzionale: eliminare la transazione se saldo è 0?
                    # Per ora aggiorniamo a 0 per mantenere la storia che è stato inizializzato
                    modifica_transazione(id_transazione, datetime.date.today().strftime('%Y-%m-%d'), "Saldo Iniziale", nuovo_saldo)
                else:
                    modifica_transazione(id_transazione, datetime.date.today().strftime('%Y-%m-%d'), "Saldo Iniziale", nuovo_saldo)
            elif nuovo_saldo != 0:
                aggiungi_transazione(id_conto, datetime.date.today().strftime('%Y-%m-%d'), "Saldo Iniziale", nuovo_saldo)
            
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiornamento saldo iniziale: {e}")
        return False


def elimina_conto(id_conto, id_utente):
    """
    Elimina un conto se vuoto, oppure lo nasconde se ha transazioni ma saldo = 0.
    Ritorna: True = eliminato, "NASCOSTO" = nascosto, "SALDO_NON_ZERO" = errore, False = errore generico
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT tipo, valore_manuale, COALESCE(CAST(rettifica_saldo AS NUMERIC), 0.0) as rettifica_saldo FROM Conti WHERE id_conto = %s AND id_utente = %s", (id_conto, id_utente))
            res = cur.fetchone()
            if not res: return False
            tipo = res['tipo']
            valore_manuale = res['valore_manuale']
            rettifica_saldo = float(res['rettifica_saldo']) if res['rettifica_saldo'] else 0.0

            saldo = 0.0
            num_transazioni = 0

            if tipo == 'Fondo Pensione':
                saldo = valore_manuale if valore_manuale else 0
            elif tipo == 'Investimento':
                cur.execute(
                    "SELECT COALESCE(SUM(quantita * prezzo_attuale_manuale), 0.0) AS saldo, COUNT(*) AS num_transazioni FROM Asset WHERE id_conto = %s",
                    (id_conto,))
                res = cur.fetchone()
                saldo = res['saldo']
                num_transazioni = res['num_transazioni']
            else:
                # Per conti Corrente/Risparmio/Contanti: somma transazioni + rettifica_saldo
                cur.execute("SELECT COALESCE(SUM(importo), 0.0) AS saldo, COUNT(*) AS num_transazioni FROM Transazioni T WHERE T.id_conto = %s", (id_conto,))
                res = cur.fetchone()
                saldo = float(res['saldo']) + rettifica_saldo
                num_transazioni = res['num_transazioni']

            if abs(saldo) > 1e-9:
                return "SALDO_NON_ZERO"
            
            # Se ci sono transazioni ma saldo = 0, NASCONDI il conto invece di bloccare
            if num_transazioni > 0:
                cur.execute("UPDATE Conti SET nascosto = TRUE WHERE id_conto = %s AND id_utente = %s", (id_conto, id_utente))
                return "NASCOSTO"

            # Se non ci sono transazioni, elimina veramente
            cur.execute("DELETE FROM Conti WHERE id_conto = %s AND id_utente = %s", (id_conto, id_utente))
            return cur.rowcount > 0
    except Exception as e:
        error_message = f"Errore generico durante l'eliminazione del conto: {e}"
        print(f"[ERRORE] {error_message}")
        return False, error_message


def admin_imposta_saldo_conto_corrente(id_conto, nuovo_saldo):
    """
    [SOLO ADMIN] Calcola e imposta la rettifica per forzare un nuovo saldo, senza cancellare le transazioni.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Calcola il saldo corrente basato solo sulle transazioni
            cur.execute("SELECT COALESCE(SUM(importo), 0.0) AS saldo FROM Transazioni WHERE id_conto = %s", (id_conto,))
            saldo_transazioni = cur.fetchone()['saldo']
            # La rettifica è la differenza tra il nuovo saldo desiderato e il saldo delle transazioni
            rettifica = nuovo_saldo - saldo_transazioni
            cur.execute("UPDATE Conti SET rettifica_saldo = %s WHERE id_conto = %s", (rettifica, id_conto))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore in admin_imposta_saldo_conto_corrente: {e}")
        return False


def admin_imposta_saldo_conto_condiviso(id_conto_condiviso, nuovo_saldo):
    """
    [SOLO ADMIN] Calcola e imposta la rettifica per forzare un nuovo saldo su un conto CONDIVISO.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Calcola il saldo corrente basato solo sulle transazioni
            cur.execute("SELECT COALESCE(SUM(importo), 0.0) AS saldo FROM TransazioniCondivise WHERE id_conto_condiviso = %s", (id_conto_condiviso,))
            saldo_transazioni = cur.fetchone()['saldo']
            # La rettifica è la differenza tra il nuovo saldo desiderato e il saldo delle transazioni
            rettifica = nuovo_saldo - saldo_transazioni
            cur.execute("UPDATE ContiCondivisi SET rettifica_saldo = %s WHERE id_conto_condiviso = %s", (rettifica, id_conto_condiviso))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore in admin_imposta_saldo_conto_condiviso: {e}")
        return False

def ottieni_dettagli_conto(id_conto, master_key_b64=None):
    """
    Recupera i dettagli di un singolo conto personale.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Conti WHERE id_conto = %s", (id_conto,))
            row = cur.fetchone()
            if not row: return None
            
            c = dict(row)
            
            # Determine if we need family_key (account names/types might be encrypted with it)
            family_key = None
            if master_key:
                cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s", (c['id_utente'],))
                fam_res = cur.fetchone()
                if fam_res and fam_res['id_famiglia']:
                    family_key = _get_family_key_for_user(fam_res['id_famiglia'], c['id_utente'], master_key, crypto)

            # Decrypt fields with fallbacks
            # Nome Conto
            dec_nome = None
            if family_key:
                dec_nome = _decrypt_if_key(c['nome_conto'], family_key, crypto, silent=True)
            if not dec_nome or dec_nome == "[ENCRYPTED]" or dec_nome.startswith("gAAAAA"):
                dec_nome = _decrypt_if_key(c['nome_conto'], master_key, crypto, silent=True)
            c['nome_conto'] = dec_nome

            # Tipo
            dec_tipo = None
            if family_key:
                dec_tipo = _decrypt_if_key(c['tipo'], family_key, crypto, silent=True)
            if not dec_tipo or dec_tipo == "[ENCRYPTED]" or dec_tipo.startswith("gAAAAA"):
                dec_tipo = _decrypt_if_key(c['tipo'], master_key, crypto, silent=True)
            c['tipo'] = dec_tipo

            # IBAN (Always Master)
            c['iban'] = _decrypt_if_key(c['iban'], master_key, crypto, silent=True)

            # Config Speciale
            dec_config = None
            if family_key:
                dec_config = _decrypt_if_key(c['config_speciale'], family_key, crypto, silent=True)
            if not dec_config or dec_config == "[ENCRYPTED]" or dec_config.startswith("gAAAAA"):
                dec_config = _decrypt_if_key(c['config_speciale'], master_key, crypto, silent=True)
            c['config_speciale'] = dec_config
            
            # Saldo
            cur.execute("SELECT COALESCE(SUM(importo), 0.0) as saldo FROM Transazioni WHERE id_conto = %s", (id_conto,))
            saldo_trans = cur.fetchone()['saldo']
            c['saldo_calcolato'] = float(saldo_trans) + (float(c['rettifica_saldo']) if c['rettifica_saldo'] else 0.0)
            
            return c
    except Exception as e:
        print(f"[ERRORE] ottieni_dettagli_conto: {e}")
        return None

def ottieni_dettagli_conto_condiviso(id_conto_condiviso, master_key_b64=None, id_utente=None):
    """
    Recupera i dettagli di un conto condiviso, inclusi i partecipanti e il saldo.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Fetch basic details (includes icona, colore)
            cur.execute("SELECT * FROM ContiCondivisi WHERE id_conto_condiviso = %s", (id_conto_condiviso,))
            row = cur.fetchone()
            if not row:
                return None
                
            dettagli = dict(row)
            dettagli['id_conto'] = dettagli['id_conto_condiviso']
            dettagli['condiviso'] = True
            
            # Decrypt Name using family key if possible
            if master_key and id_utente:
                 family_key = _get_family_key_for_user(dettagli['id_famiglia'], id_utente, master_key, crypto)
                 
                 # 1. Nome Conto
                 dec_nome = None
                 if family_key:
                     dec_nome = _decrypt_if_key(dettagli['nome_conto'], family_key, crypto, silent=True)
                 if not dec_nome or dec_nome == "[ENCRYPTED]" or dec_nome.startswith("gAAAAA"):
                     dec_nome = _decrypt_if_key(dettagli['nome_conto'], master_key, crypto, silent=True)
                 dettagli['nome_conto'] = dec_nome

                 # 2. Config Speciale
                 dec_config = None
                 if family_key:
                     dec_config = _decrypt_if_key(dettagli['config_speciale'], family_key, crypto, silent=True)
                 if not dec_config or dec_config == "[ENCRYPTED]" or dec_config.startswith("gAAAAA"):
                     dec_config = _decrypt_if_key(dettagli['config_speciale'], master_key, crypto, silent=True)
                 dettagli['config_speciale'] = dec_config

            # Fetch participants
            cur.execute("""
                SELECT U.id_utente, 
                       COALESCE(U.nome || ' ' || U.cognome, U.username) as nome_visualizzato,
                       U.username
                FROM PartecipazioneContoCondiviso PCC
                JOIN Utenti U ON PCC.id_utente = U.id_utente
                WHERE PCC.id_conto_condiviso = %s
            """, (id_conto_condiviso,))
            dettagli['partecipanti'] = [dict(r) for r in cur.fetchall()]
            
            # Calculate Balance
            cur.execute("SELECT COALESCE(SUM(importo), 0.0) as saldo FROM TransazioniCondivise WHERE id_conto_condiviso = %s", (id_conto_condiviso,))
            saldo_trans = cur.fetchone()['saldo']
            dettagli['saldo_calcolato'] = float(saldo_trans) + (float(dettagli['rettifica_saldo']) if dettagli['rettifica_saldo'] else 0.0)

            return dettagli
            
    except Exception as e:
        print(f"[ERRORE] ottieni_dettagli_conto_condiviso: {e}")
        return None

def ottieni_conti_condivisi_famiglia(id_famiglia, id_utente, master_key_b64=None):
    """
    Recupera la lista dei conti condivisi per una famiglia.
    Filtra in base alla visibilità (tipo_condivisione='famiglia' o 'utenti' con inclusione).
    Restituisce una lista di dizionari con dettagli e saldo calcolato.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
             # Ottieni la chiave famiglia
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        conti = []
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Recupera i conti
            # Se tipo='famiglia', visibile a tutti. Se 'utenti', verifica partecipazione.
            query = """
                SELECT DISTINCT CC.*
                FROM ContiCondivisi CC
                LEFT JOIN PartecipazioneContoCondiviso PCC ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND (
                      CC.tipo_condivisione = 'famiglia' 
                      OR (CC.tipo_condivisione = 'utenti' AND PCC.id_utente = %s)
                      OR (CC.id_conto_condiviso IN (SELECT id_conto_condiviso FROM ContiCondivisi WHERE id_famiglia=%s AND tipo_condivisione='utenti' AND EXISTS (SELECT 1 FROM Appartenenza_Famiglia WHERE id_famiglia=%s AND id_utente=%s AND ruolo='admin'))) -- Admin vede tutto? Per ora assumiamo di sì o no? La richiesta dice "tutti i conti... condivisi". Assumo visibilità basata su regole.
                  )
            """
            # Semplificazione: Admin vede tutto?
            # Se l'utente è admin della famiglia, dovrebbe vedere tutto?
            # Per ora atteniamoci alla logica di partecipazione standard.
            # Se è 'utenti', deve essere nella tabella PartecipazioneContoCondiviso.
            
            cur.execute("""
                SELECT DISTINCT CC.*
                FROM ContiCondivisi CC
                LEFT JOIN PartecipazioneContoCondiviso PCC ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND (
                      CC.tipo_condivisione = 'famiglia' 
                      OR (CC.tipo_condivisione = 'utenti' AND PCC.id_utente = %s)
                  )
            """, (id_famiglia, id_utente))
            
            rows = cur.fetchall()
            
            for row in rows:
                c = dict(row)
                
                # Decrypt Name
                nome_conto = c['nome_conto']
                if family_key:
                    nome_conto = _decrypt_if_key(nome_conto, family_key, crypto)
                c['nome_conto'] = nome_conto

                # Decrypt config_speciale
                config_spec = c.get('config_speciale')
                if config_spec:
                    dec_config = None
                    if family_key:
                        dec_config = _decrypt_if_key(config_spec, family_key, crypto, silent=True)
                    if (not dec_config or dec_config == "[ENCRYPTED]" or dec_config.startswith("gAAAAA")) and master_key:
                        # Fallback to master_key (unlikely for shared, but for safety)
                        dec_config = _decrypt_if_key(config_spec, master_key, crypto, silent=True)
                    c['config_speciale'] = dec_config
                else:
                    c['config_speciale'] = None

                # Calcola Saldo
                cur.execute("""
                    SELECT COALESCE(SUM(importo), 0.0) as saldo 
                    FROM TransazioniCondivise 
                    WHERE id_conto_condiviso = %s
                """, (c['id_conto_condiviso'],))
                saldo_trans = cur.fetchone()['saldo']
                c['saldo_calcolato'] = saldo_trans + (c['rettifica_saldo'] or 0.0)
                
                # Campi compatibili con FE
                c['id_conto'] = c['id_conto_condiviso'] # Alias per uniformità
                c['condiviso'] = True
                
                # Partecipanti (per info)
                cur.execute("""
                    SELECT U.username
                    FROM PartecipazioneContoCondiviso PCC
                    JOIN Utenti U ON PCC.id_utente = U.id_utente
                    WHERE PCC.id_conto_condiviso = %s
                """, (c['id_conto_condiviso'],))
                partecipanti = cur.fetchall()
                c['partecipanti_str'] = ", ".join([p['username'] or "Utente Sconosciuto" for p in partecipanti])
                
                conti.append(c)
                
        return conti

    except Exception as e:
        print(f"[ERRORE] ottieni_conti_condivisi_famiglia: {e}")
        return []
def crea_conto_condiviso(id_famiglia, nome_conto, tipo_conto, tipo_condivisione, lista_utenti=None, id_utente=None, master_key_b64=None, config_speciale=None, icona=None, colore=None):
    # Encrypt with family key if available
    encrypted_nome = nome_conto
    if id_utente and master_key_b64:
        try:
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            # Get family key for this family
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND id_utente = %s", (id_famiglia, id_utente))
                row = cur.fetchone()
                if row and row['chiave_famiglia_criptata']:
                    # Decrypt to get family_key_b64, then decode to bytes
                    family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                    family_key_bytes = base64.b64decode(family_key_b64)
                    encrypted_config = _encrypt_if_key(config_speciale, family_key_bytes, crypto)
                else:
                    encrypted_config = config_speciale # Fallback if no key
        except Exception as e:
            print(f"[ERRORE] Encryption failed in crea_conto_condiviso: {e}")
            encrypted_config = config_speciale
    else:
        encrypted_config = config_speciale
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase

            cur.execute(
                "INSERT INTO ContiCondivisi (id_famiglia, nome_conto, tipo, tipo_condivisione, config_speciale, icona, colore) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_conto_condiviso",
                (id_famiglia, encrypted_nome, tipo_conto, tipo_condivisione, encrypted_config, icona, colore))
            id_nuovo_conto_condiviso = cur.fetchone()['id_conto_condiviso']

            if tipo_condivisione == 'utenti' and lista_utenti:
                for uid in lista_utenti:
                    cur.execute(
                        "INSERT INTO PartecipazioneContoCondiviso (id_conto_condiviso, id_utente) VALUES (%s, %s)",
                        (id_nuovo_conto_condiviso, uid))

            con.commit()
            return id_nuovo_conto_condiviso
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la creazione conto condiviso: {e}")
        return None


def modifica_conto_condiviso(id_conto_condiviso, nome_conto, tipo=None, tipo_condivisione=None, lista_utenti=None, id_utente=None, master_key_b64=None, config_speciale=None, icona=None, colore=None):
    # Encrypt with family key if available
    encrypted_nome = nome_conto
    if id_utente and master_key_b64:
        try:
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            # Get family key for this account's family
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT id_famiglia FROM ContiCondivisi WHERE id_conto_condiviso = %s", (id_conto_condiviso,))
                res = cur.fetchone()
                if res:
                    id_famiglia = res['id_famiglia']
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND id_utente = %s", (id_famiglia, id_utente))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        # Decrypt to get family_key_b64, then decode to bytes
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key_bytes = base64.b64decode(family_key_b64)
                        encrypted_nome = crypto.encrypt_data(nome_conto, family_key_bytes)
                        encrypted_config = _encrypt_if_key(config_speciale, family_key_bytes, crypto)
                    else:
                        encrypted_config = config_speciale
                else:
                    encrypted_config = config_speciale
        except Exception as e:
            print(f"[ERRORE] Encryption failed in modifica_conto_condiviso: {e}")
            encrypted_config = config_speciale
    else:
        encrypted_config = config_speciale

    try:
        with get_db_connection() as con:
            cur = con.cursor()

            
            # Update Nome, Tipo, TipoCondivisione, config_speciale, icona, colore
            sql = "UPDATE ContiCondivisi SET nome_conto = %s, config_speciale = %s, icona = %s, colore = %s"
            params = [encrypted_nome, encrypted_config, icona, colore]
            
            if tipo:
                sql += ", tipo = %s"
                params.append(tipo)
            
            if tipo_condivisione:
                sql += ", tipo_condivisione = %s"
                params.append(tipo_condivisione)
            
            sql += " WHERE id_conto_condiviso = %s"
            params.append(id_conto_condiviso)
            
            cur.execute(sql, tuple(params))
            
            # Handle Participants if 'utenti'
            # If switching TO utenti, or modifying utenti list
            target_scope = tipo_condivisione # Should be passed
            
            # If not passed, we might need to fetch? 
            # But caller SHOULD pass it. If not passed, assume no change?
            # Safe bet: If lista_utenti is NOT None, we assume we want to update list.
            # AND if passed scope is 'utenti'.
            
            if target_scope == 'utenti' and lista_utenti is not None:
                cur.execute("DELETE FROM PartecipazioneContoCondiviso WHERE id_conto_condiviso = %s",
                            (id_conto_condiviso,))
                for uid in lista_utenti:
                    cur.execute(
                        "INSERT INTO PartecipazioneContoCondiviso (id_conto_condiviso, id_utente) VALUES (%s, %s)",
                        (id_conto_condiviso, uid))
            elif target_scope == 'famiglia':
                # If switching to family, maybe clear specific participants?
                # Cleanliness: Yes.
                cur.execute("DELETE FROM PartecipazioneContoCondiviso WHERE id_conto_condiviso = %s", (id_conto_condiviso,))

            con.commit() # Explicit commit needed context context autocommits? yes context usually commits except if error.
                         # DbContext usually handles commit on exit.
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica conto condiviso: {e}")
        return False


def elimina_conto_condiviso(id_conto_condiviso):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase Supabase
            cur.execute("DELETE FROM ContiCondivisi WHERE id_conto_condiviso = %s", (id_conto_condiviso,))
            con.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione conto condiviso: {e}")
        return None


def ottieni_conti_condivisi_utente(id_utente, master_key_b64=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        -- Recupera l'elenco dei conti condivisi a cui l'utente partecipa, includendo il saldo calcolato.
                        SELECT CC.id_conto_condiviso         AS id_conto,
                               CC.id_famiglia,
                               CC.nome_conto,
                               CC.tipo,
                               CC.tipo_condivisione,
                               CC.icona,
                               CC.colore,
                               1                             AS is_condiviso,
                               COALESCE(SUM(T.importo), 0.0) + COALESCE(CAST(NULLIF(CAST(CC.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0) AS saldo_calcolato
                        FROM ContiCondivisi CC
                                 LEFT JOIN PartecipazioneContoCondiviso PCC
                                           ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                                 LEFT JOIN TransazioniCondivise T ON CC.id_conto_condiviso = T.id_conto_condiviso -- Join per calcolare il saldo
                        WHERE (PCC.id_utente = %s AND CC.tipo_condivisione = 'utenti')
                           OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s) AND
                               CC.tipo_condivisione = 'famiglia')
                        GROUP BY CC.id_conto_condiviso, CC.id_famiglia, CC.nome_conto, CC.tipo,
                                 CC.tipo_condivisione, CC.rettifica_saldo, CC.icona, CC.colore -- GROUP BY per tutte le colonne non aggregate
                        ORDER BY CC.nome_conto
                        """, (id_utente, id_utente))
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            if master_key_b64 and results:
                try:
                    crypto, master_key = _get_crypto_and_key(master_key_b64)
                    
                    # Fetch all family keys for the user
                    family_ids = list(set(r['id_famiglia'] for r in results if r['id_famiglia']))
                    family_keys = {}
                    if family_ids:
                        # Use a loop or IN clause. IN clause is better.
                        placeholders = ','.join(['%s'] * len(family_ids))
                        cur.execute(f"SELECT id_famiglia, chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia IN ({placeholders})",
                                    (id_utente, *family_ids))
                        for row in cur.fetchall():
                            if row['chiave_famiglia_criptata']:
                                try:
                                    # Decrypt to get family_key_b64 (string), then decode to bytes
                                    family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                                    family_key_bytes = base64.b64decode(family_key_b64)
                                    family_keys[row['id_famiglia']] = family_key_bytes
                                except Exception as e:
                                    print(f"[DEBUG] Could not decrypt family key: {e}")
                                    pass

                    for row in results:
                        fam_id = row.get('id_famiglia')
                        if fam_id and fam_id in family_keys:
                            row['nome_conto'] = _decrypt_if_key(row['nome_conto'], family_keys[fam_id], crypto, silent=True)
                            # Fallback to master_key if family_key decryption fails
                            if row['nome_conto'] == "[ENCRYPTED]" and isinstance(row['nome_conto'], str) and row['nome_conto'].startswith("gAAAAA"):
                                row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
                except Exception as e:
                    print(f"[ERRORE] Decryption error in ottieni_conti_condivisi_utente: {e}")
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero conti condivisi utente: {e}")
        return []



def ottieni_utenti_famiglia(id_famiglia):
    id_famiglia = _valida_id_int(id_famiglia)
    if not id_famiglia: return []
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT U.id_utente, 
                               U.username,
                               U.nome_enc_server,
                               U.cognome_enc_server
                        FROM Utenti U
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                        """, (id_famiglia,))
            
            results = []
            for row in cur.fetchall():
                 n = decrypt_system_data(row.get('nome_enc_server'))
                 c = decrypt_system_data(row.get('cognome_enc_server'))
                 
                 display = row['username']
                 if n or c:
                     display = f"{n or ''} {c or ''}".strip()
                 
                 results.append({
                     'id_utente': row['id_utente'],
                     'nome_visualizzato': display
                 })
                 
            return sorted(results, key=lambda x: x['nome_visualizzato'])

    except Exception as e:
        print(f"[ERRORE] Errore recupero utenti famiglia: {e}")
        return []


def ottieni_tutti_i_conti_utente(id_utente, master_key_b64=None):
    """
    Restituisce una lista unificata di conti personali e conti condivisi a cui l'utente partecipa.
    Ogni conto avrà un flag 'is_condiviso'.
    """
    conti_personali = ottieni_dettagli_conti_utente(id_utente, master_key_b64=master_key_b64)  # Usa dettagli per avere saldo
    conti_condivisi = ottieni_conti_condivisi_utente(id_utente, master_key_b64=master_key_b64)

    risultato_unificato = []
    for conto in conti_personali:
        conto['is_condiviso'] = False
        risultato_unificato.append(conto)
    for conto in conti_condivisi:
        conto['is_condiviso'] = True
        risultato_unificato.append(conto)

    return risultato_unificato


def ottieni_tutti_i_conti_famiglia(id_famiglia, id_utente_richiedente, master_key_b64=None):
    """
    Restituisce TUTTI i conti di TUTTI i membri della famiglia, inclusi quelli condivisi e salvadanai.
    Utile per la visibilità globale 'Altri Familiari'.
    """
    try:
        # 1. Recupera tutti i membri della famiglia
        utenti = ottieni_utenti_famiglia(id_famiglia)
        
        # Crypto context
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key:
            family_key = _get_family_key_for_user(id_famiglia, id_utente_richiedente, master_key, crypto)
        
        risultato = []
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            for u in utenti:
                uid = u['id_utente']
                # Conti Personali di questo utente
                cur.execute("""
                    SELECT id_conto, nome_conto, tipo, config_speciale, icona, colore
                    FROM Conti 
                    WHERE id_utente = %s AND (nascosto = FALSE OR nascosto IS NULL)
                """, (uid,))
                
                for row in cur.fetchall():
                    r = dict(row)
                    r['is_condiviso'] = False
                    r['id_utente_owner'] = uid
                    r['nome_owner'] = u['nome_visualizzato']
                    
                    # Decrypt nome_conto, tipo and config_speciale
                    # 1. Try family_key (most common for shared context)
                    dec_nome = _decrypt_if_key(r['nome_conto'], family_key, crypto, silent=True)
                    dec_tipo = _decrypt_if_key(r['tipo'], family_key, crypto, silent=True)
                    dec_config = _decrypt_if_key(r['config_speciale'], family_key, crypto, silent=True)
                    
                    # 2. Fallback to master_key if it's the owner's account and first attempt failed/skipped
                    if uid == id_utente_richiedente and master_key:
                        # Se è ancora criptato o ha fallito, prova master_key
                        if dec_nome == "[ENCRYPTED]" or (isinstance(dec_nome, str) and dec_nome.startswith("gAAAAA")):
                            dec_nome = _decrypt_if_key(r['nome_conto'], master_key, crypto, silent=True)
                        if dec_tipo == "[ENCRYPTED]" or (isinstance(dec_tipo, str) and dec_tipo.startswith("gAAAAA")):
                            dec_tipo = _decrypt_if_key(r['tipo'], master_key, crypto, silent=True)
                        if dec_config == "[ENCRYPTED]" or (isinstance(dec_config, str) and dec_config.startswith("gAAAAA")):
                            dec_config = _decrypt_if_key(r['config_speciale'], master_key, crypto, silent=True)
                    
                    r['nome_conto'] = dec_nome
                    r['tipo'] = dec_tipo
                    r['config_speciale'] = dec_config
                    risultato.append(r)
                    
                # Carte di questo utente
                cur.execute("SELECT id_carta, nome_carta, id_conto_contabile, id_conto_contabile_condiviso, icona, colore FROM Carte WHERE id_utente = %s", (uid,))
                for row in cur.fetchall():
                    dec_nome = _decrypt_if_key(row['nome_carta'], family_key, crypto, silent=True)
                    if (dec_nome == "[ENCRYPTED]" or (isinstance(dec_nome, str) and dec_nome.startswith("gAAAAA"))) and uid == id_utente_richiedente and master_key:
                        dec_nome = _decrypt_if_key(row['nome_carta'], master_key, crypto, silent=True)
                    
                    id_acc = row['id_conto_contabile'] or row['id_conto_contabile_condiviso']
                    flag = 'S' if row['id_conto_contabile_condiviso'] else 'P'
                        
                    risultato.append({
                        'id_conto': f"CARD_{row['id_carta']}_{id_acc}_{flag}",
                        'nome_conto': dec_nome,
                        'tipo': 'Carta',
                        'id_utente_owner': uid,
                        'nome_owner': u['nome_visualizzato'],
                        'is_condiviso': False,
                        'icona': row.get('icona'),
                        'colore': row.get('colore')
                    })

            # 3. Conti Condivisi della famiglia
            cur.execute("SELECT id_conto_condiviso as id_conto, nome_conto, tipo, config_speciale, icona, colore FROM ContiCondivisi WHERE id_famiglia = %s", (id_famiglia,))
            for row in cur.fetchall():
                r = dict(row)
                r['is_condiviso'] = True
                r['nome_conto'] = _decrypt_if_key(r['nome_conto'], family_key, crypto, silent=True)
                r['tipo'] = _decrypt_if_key(r['tipo'], family_key, crypto, silent=True)
                r['config_speciale'] = _decrypt_if_key(r['config_speciale'], family_key, crypto, silent=True)
                r['id_utente_owner'] = None
                r['nome_owner'] = "Condiviso"
                risultato.append(r)
                
            # 4. Salvadanai della famiglia
            cur.execute("SELECT id_salvadanaio, nome FROM Salvadanai WHERE id_famiglia = %s", (id_famiglia,))
            for row in cur.fetchall():
                 risultato.append({
                     'id_conto': f"PB_{row['id_salvadanaio']}",
                     'nome_conto': _decrypt_if_key(row['nome'], family_key, crypto, silent=True),
                     'tipo': 'Salvadanaio',
                     'id_utente_owner': None,
                     'nome_owner': "Famiglia",
                     'is_condiviso': False
                 })

        return risultato
    except Exception as e:
        print(f"[ERRORE] ottieni_tutti_i_conti_famiglia: {e}")
        return []
        print(f"[ERRORE] Errore generico durante il recupero di tutti i conti famiglia: {e}")
        return []

def ottieni_mesi_disponibili_conto(id_conto: str) -> List[Tuple[int, int]]:
    """
    Restituisce una lista di tuple (anno, mese) per i quali esistono transazioni
    per il conto specificato.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT DISTINCT EXTRACT(YEAR FROM data::date) as anno, EXTRACT(MONTH FROM data::date) as mese
                FROM Transazioni
                WHERE id_conto = %s
                ORDER BY anno DESC, mese DESC
            """, (id_conto,))
            return [(int(row['anno']), int(row['mese'])) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Errore ottieni_mesi_disponibili_conto: {e}")
        return []

def ottieni_transazioni_conto_mese(id_conto: str, mese: int, anno: int, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, id_famiglia: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recupera le transazioni di un conto per un mese specifico.
    Decripta i dati se necessario.
    """
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"
    
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    
    # Priority: usually Master Key for personal, Family for shared.
    keys_to_try = []
    if master_key: keys_to_try.append(master_key)
    if family_key: keys_to_try.append(family_key)

    # Helper to try keys
    def try_decrypt(val, keys):
        last_res = None
        for k in keys:
             if not k: continue
             try:
                 # Pass silent=True to avoid excessive error logs
                 res = _decrypt_if_key(val, k, crypto, silent=True)
                 if res == "[ENCRYPTED]":
                     last_res = res
                     continue
                 return res
             except: continue
        return last_res if last_res else "[ENCRYPTED]"

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Query Transazioni
            cur.execute("""
                SELECT T.id_transazione, T.data, T.importo, T.descrizione,
                       C.nome_categoria, S.nome_sottocategoria
                FROM Transazioni T
                LEFT JOIN Sottocategorie S ON T.id_sottocategoria = S.id_sottocategoria
                LEFT JOIN Categorie C ON S.id_categoria = C.id_categoria
                WHERE T.id_conto = %s
                  AND T.data BETWEEN %s AND %s
                ORDER BY T.data DESC, T.id_transazione DESC
            """, (id_conto, data_inizio, data_fine))
            
            transazioni = []
            for row in cur.fetchall():
                t = dict(row)
                # Decrypt text fields with fallback
                t['descrizione'] = try_decrypt(t['descrizione'], keys_to_try)
                
                # Category names might be encrypted with family key if they belong to family
                if t['nome_categoria']:
                     t['nome_categoria'] = try_decrypt(t['nome_categoria'], keys_to_try)
                
                transazioni.append(t)
                
            return transazioni
            
    except Exception as e:
        logger.error(f"Errore ottieni_transazioni_conto_mese: {e}")
        return []


def ottieni_mesi_disponibili_conto_condiviso(id_conto_condiviso: str) -> List[Tuple[int, int]]:
    """
    Restituisce (anno, mese) per i quali esistono transazioni condivise.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT DISTINCT EXTRACT(YEAR FROM data::date) as anno, EXTRACT(MONTH FROM data::date) as mese
                FROM TransazioniCondivise
                WHERE id_conto_condiviso = %s
                ORDER BY anno DESC, mese DESC
            """, (id_conto_condiviso,))
            return [(int(row['anno']), int(row['mese'])) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Errore ottieni_mesi_disponibili_conto_condiviso: {e}")
        return []

def ottieni_transazioni_conto_condiviso_mese(id_conto_condiviso: str, mese: int, anno: int, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, id_famiglia: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recupera le transazioni condivise per un mese specifico.
    """
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"
    
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    
    # Priority: usually Family Key for shared.
    keys_to_try = []
    if family_key: keys_to_try.append(family_key)
    if master_key: keys_to_try.append(master_key)

    # Helper to try keys
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

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            """
            Struttura TransazioniCondivise prevista:
            id_transazione_condivisa, id_conto_condiviso, data, descrizione, importo, 
            id_sottocategoria, id_utente_autore
            """
            
            cur.execute("""
                SELECT T.id_transazione_condivisa as id_transazione, T.data, T.importo, T.descrizione,
                       C.nome_categoria, S.nome_sottocategoria,
                       U.username, U.nome_enc_server
                FROM TransazioniCondivise T
                LEFT JOIN Sottocategorie S ON T.id_sottocategoria = S.id_sottocategoria
                LEFT JOIN Categorie C ON S.id_categoria = C.id_categoria
                LEFT JOIN Utenti U ON T.id_utente_autore = U.id_utente
                WHERE T.id_conto_condiviso = %s
                  AND T.data BETWEEN %s AND %s
                ORDER BY T.data DESC, T.id_transazione_condivisa DESC
            """, (id_conto_condiviso, data_inizio, data_fine))
            
            transazioni = []
            for row in cur.fetchall():
                t = dict(row)
                t['is_shared'] = True # Mark as shared explicitly
                
                # Decrypt text
                t['descrizione'] = try_decrypt(t['descrizione'], keys_to_try)
                
                if t['nome_categoria']:
                     t['nome_categoria'] = try_decrypt(t['nome_categoria'], keys_to_try)
                
                # Resolve Author Name
                # Assuming username is blind indexed/encrypted logic, might display fallback
                # or decrypt 'nome_enc_server' if available (system encrypted)
                author = "Utente"
                if t['nome_enc_server']:
                     dec_name = decrypt_system_data(t['nome_enc_server'])
                     if dec_name: author = dec_name
                elif t['username']:
                     # Legacy or plain username?
                     author = t['username']
                
                t['autore'] = author

                transazioni.append(t)
                
            return transazioni
            
    except Exception as e:
        logger.error(f"Errore ottieni_transazioni_conto_condiviso_mese: {e}")
        return []

