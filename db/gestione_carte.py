"""
Funzioni carte: credito/debito, massimali, transazioni
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
    generate_unique_code,
    SERVER_SECRET_KEY,
    crypto as _crypto_instance
)

# Importazioni da altri moduli per evitare NameError
from db.gestione_conti import aggiungi_conto




# --- GESTIONE CARTE ---

def aggiungi_carta(id_utente, nome_carta, tipo_carta, circuito, 
                   id_conto_riferimento=None, id_conto_contabile=None, 
                   id_conto_riferimento_condiviso=None, id_conto_contabile_condiviso=None,
                   massimale=None, giorno_addebito=None, spesa_tenuta=None, soglia_azzeramento=None, giorno_addebito_tenuta=None,
                   addebito_automatico=False, master_key=None, crypto=None, icona=None, colore=None):
    """
    Aggiunge una nuova carta nel database. Cripta i dati sensibili.
    Gestisce automaticamente la creazione/assegnazione del conto contabile e lo storico massimali.
    Supporta conti personali e condivisi.
    """
    try:
        crypto, master_key_bytes = _get_crypto_and_key(master_key)
        
        # 1. Gestione Conto Contabile
        if tipo_carta == 'credito':
            # Se conto contabile non specificato, creane uno automatico (Personale)
            if not id_conto_contabile and not id_conto_contabile_condiviso:
                nome_conto_contabile = f"Saldo {nome_carta}"
                res_conto = aggiungi_conto(id_utente, nome_conto_contabile, "Carta di Credito", 0.0, master_key_b64=master_key)
                if not res_conto or not res_conto[0]:
                     print("[ERRORE] Impossibile creare conto contabile automatico")
                     return False
                id_conto_contabile = res_conto[0]
        else:
            # Debito: default al conto di riferimento
            if not id_conto_contabile and not id_conto_contabile_condiviso:
                id_conto_contabile = id_conto_riferimento
                id_conto_contabile_condiviso = id_conto_riferimento_condiviso

        massimale_enc = _encrypt_if_key(str(massimale) if massimale is not None else None, master_key_bytes, crypto)
        giorno_addebito_enc = _encrypt_if_key(str(giorno_addebito) if giorno_addebito is not None else None, master_key_bytes, crypto)
        spesa_tenuta_enc = _encrypt_if_key(str(spesa_tenuta) if spesa_tenuta is not None else None, master_key_bytes, crypto)
        soglia_azzeramento_enc = _encrypt_if_key(str(soglia_azzeramento) if soglia_azzeramento is not None else None, master_key_bytes, crypto)
        giorno_addebito_tenuta_enc = _encrypt_if_key(str(giorno_addebito_tenuta) if giorno_addebito_tenuta is not None else None, master_key_bytes, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO Carte (
                    id_utente, nome_carta, tipo_carta, circuito, 
                    id_conto_riferimento, id_conto_contabile,
                    id_conto_riferimento_condiviso, id_conto_contabile_condiviso,
                    massimale_encrypted, giorno_addebito_encrypted, spesa_tenuta_encrypted, 
                    soglia_azzeramento_encrypted, giorno_addebito_tenuta_encrypted, addebito_automatico,
                    icona, colore
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_carta
            """, (id_utente, nome_carta, tipo_carta, circuito, 
                  id_conto_riferimento, id_conto_contabile,
                  id_conto_riferimento_condiviso, id_conto_contabile_condiviso,
                  massimale_enc, giorno_addebito_enc, spesa_tenuta_enc, soglia_azzeramento_enc, giorno_addebito_tenuta_enc, addebito_automatico,
                  icona, colore))
            
            row = cur.fetchone()
            id_carta = row.get('id_carta') if row else None
            
            if id_carta and massimale is not None:
                data_validita = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')
                cur.execute("""
                    INSERT INTO StoricoMassimaliCarte (id_carta, data_inizio_validita, massimale_encrypted)
                    VALUES (%s, %s, %s)
                """, (id_carta, data_validita, massimale_enc))

            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta carta: {e}")
        return False

def ottieni_carte_utente(id_utente, master_key_b64=None):
    """
    Restituisce la lista delle carte attive dell'utente, decriptando i dati sensibili.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Carte WHERE id_utente = %s AND attiva = TRUE", (id_utente,))
            carte_raw = cur.fetchall()
            
            carte = []
            for row in carte_raw:
                try:
                    c = dict(row)
                    c['massimale'] = _decrypt_and_convert(c['massimale_encrypted'], float, master_key, crypto)
                    c['giorno_addebito'] = _decrypt_and_convert(c['giorno_addebito_encrypted'], int, master_key, crypto)
                    c['spesa_tenuta'] = _decrypt_and_convert(c['spesa_tenuta_encrypted'], float, master_key, crypto)
                    c['soglia_azzeramento'] = _decrypt_and_convert(c['soglia_azzeramento_encrypted'], float, master_key, crypto)
                    c['giorno_addebito_tenuta'] = _decrypt_and_convert(c['giorno_addebito_tenuta_encrypted'], int, master_key, crypto)
                    carte.append(c)
                except Exception as e:
                     print(f"[WARN] Errore decriptazione carta {row.get('id_carta')}: {e}")
            return carte
    except Exception as e:
        print(f"[ERRORE] Errore recupero carte utente: {e}")
        return []

def _decrypt_and_convert(encrypted_val, type_func, master_key, crypto):
    """Helper per decriptare e convertire. Ritorna None se vuoto o errore."""
    if not encrypted_val: return None
    val_str = _decrypt_if_key(encrypted_val, master_key, crypto, silent=True)
    if not val_str or val_str == "[ENCRYPTED]": return None
    try:
        return type_func(val_str)
    except:
        return None

def modifica_carta(id_carta, nome_carta=None, tipo_carta=None, circuito=None, 
                   id_conto_riferimento=None, id_conto_contabile=None,
                   id_conto_riferimento_condiviso=None, id_conto_contabile_condiviso=None,
                   massimale=None, giorno_addebito=None, spesa_tenuta=None, soglia_azzeramento=None, giorno_addebito_tenuta=None,
                   addebito_automatico=None, master_key_b64=None, icona=None, colore=None):
    """
    Modifica una carta esistente. Aggiorna solo i campi forniti.
    Gestisce lo storico massimali e la logica esclusiva Conti Personali/Condivisi.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Verifica Cambio Massimale
            should_update_history = False
            massimale_enc_new = None
            
            if massimale is not None:
                cur.execute("SELECT massimale_encrypted FROM Carte WHERE id_carta = %s", (id_carta,))
                row = cur.fetchone()
                curr_enc = row.get('massimale_encrypted') if row else None
                curr_val = _decrypt_if_key(curr_enc, master_key, crypto, silent=True)
                
                try:
                    v1 = float(curr_val) if curr_val else 0.0
                    v2 = float(massimale) if massimale else 0.0
                    if abs(v1 - v2) > 0.001: 
                        should_update_history = True
                except:
                    if str(curr_val) != str(massimale):
                        should_update_history = True
                
                # Encrypt new value for global update
                massimale_enc_new = _encrypt_if_key(str(massimale), master_key, crypto)

            # 2. Costruzione Query Update
            updates = []
            params = []

            if nome_carta is not None:
                updates.append("nome_carta = %s")
                params.append(nome_carta)
            if tipo_carta is not None:
                updates.append("tipo_carta = %s")
                params.append(tipo_carta)
            if circuito is not None:
                updates.append("circuito = %s")
                params.append(circuito)
            if addebito_automatico is not None:
                updates.append("addebito_automatico = %s")
                params.append(addebito_automatico)
            
            # Handle Account Exclusivity: if one provided, set other to NULL
            if id_conto_riferimento is not None: 
                updates.append("id_conto_riferimento = %s")
                params.append(id_conto_riferimento)
                updates.append("id_conto_riferimento_condiviso = NULL")
            elif id_conto_riferimento_condiviso is not None: # Only if personal not provided
                updates.append("id_conto_riferimento_condiviso = %s")
                params.append(id_conto_riferimento_condiviso)
                updates.append("id_conto_riferimento = NULL")

            if id_conto_contabile is not None:
                updates.append("id_conto_contabile = %s")
                params.append(id_conto_contabile)
                updates.append("id_conto_contabile_condiviso = NULL")
            elif id_conto_contabile_condiviso is not None: # Only if personal not provided
                updates.append("id_conto_contabile_condiviso = %s")
                params.append(id_conto_contabile_condiviso)
                updates.append("id_conto_contabile = NULL")

            if massimale is not None:
                updates.append("massimale_encrypted = %s")
                params.append(massimale_enc_new)
            if giorno_addebito is not None:
                updates.append("giorno_addebito_encrypted = %s")
                params.append(_encrypt_if_key(str(giorno_addebito), master_key, crypto))
            if spesa_tenuta is not None:
                updates.append("spesa_tenuta_encrypted = %s")
                params.append(_encrypt_if_key(str(spesa_tenuta), master_key, crypto))
            if soglia_azzeramento is not None:
                updates.append("soglia_azzeramento_encrypted = %s")
                params.append(_encrypt_if_key(str(soglia_azzeramento), master_key, crypto))
            if giorno_addebito_tenuta is not None:
                updates.append("giorno_addebito_tenuta_encrypted = %s")
                params.append(_encrypt_if_key(str(giorno_addebito_tenuta), master_key, crypto))
            
            if icona is not None:
                updates.append("icona = %s")
                params.append(icona)
            if colore is not None:
                updates.append("colore = %s")
                params.append(colore)

            if updates:
                params.append(id_carta)
                query = f"UPDATE Carte SET {', '.join(updates)} WHERE id_carta = %s"
                cur.execute(query, tuple(params))

            # 3. Aggiornamento Storico
            if should_update_history and massimale_enc_new:
                 data_validita = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')
                 cur.execute("""
                    INSERT INTO StoricoMassimaliCarte (id_carta, data_inizio_validita, massimale_encrypted)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id_carta, data_inizio_validita) 
                    DO UPDATE SET massimale_encrypted = EXCLUDED.massimale_encrypted
                 """, (id_carta, data_validita, massimale_enc_new))
            
            con.commit()
            return True
            
    except Exception as e:
        print(f"[ERRORE] Errore modifica carta: {e}")
        return False

def elimina_carta(id_carta, soft_delete=True):
    """
    Elimina una carta (soft delete di default per preservare storico)
    e nasconde i conti contabili associati (Saldo Carta).
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Recupera i conti contabili associati PRIMA di modificare la carta
            cur.execute("SELECT id_conto_contabile, id_conto_contabile_condiviso FROM Carte WHERE id_carta = %s", (id_carta,))
            row = cur.fetchone()
            conti_da_nascondere = []
            if row:
                if row['id_conto_contabile']: conti_da_nascondere.append(row['id_conto_contabile'])
                if row['id_conto_contabile_condiviso']: conti_da_nascondere.append(row['id_conto_contabile_condiviso'])
            
            # 2. Esegui eliminazione/soft-delete carta
            if soft_delete:
                cur.execute("UPDATE Carte SET attiva = FALSE WHERE id_carta = %s", (id_carta,))
            else:
                cur.execute("DELETE FROM Carte WHERE id_carta = %s", (id_carta,))
            
            # 3. Nascondi i conti associati
            if conti_da_nascondere:
                # Usa ANY(%s) per passare una lista in Postgres/Psycopg2
                cur.execute("UPDATE Conti SET nascosto = TRUE WHERE id_conto = ANY(%s)", (conti_da_nascondere,))
                
                
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione carta: {e}")
        return False

def ottieni_ids_conti_tecnici_carte(id_utente):
    """
    Recupera gli ID dei conti tecnici (saldo) associati alle CARTE DI CREDITO dell'utente.
    I conti delle carte di debito NON sono tecnici e devono essere visibili.
    Utile per filtrare questi conti dalle liste di selezione.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Solo carte di CREDITO hanno conti tecnici da nascondere
            cur.execute("""
                SELECT id_conto_contabile, id_conto_contabile_condiviso 
                FROM Carte 
                WHERE id_utente = %s AND tipo_carta = 'credito'
            """, (id_utente,))
            rows = cur.fetchall()
            ids = set()
            for r in rows:
                if r['id_conto_contabile']: ids.add(r['id_conto_contabile'])
                if r['id_conto_contabile_condiviso']: ids.add(r['id_conto_contabile_condiviso'])
            return ids
    except Exception as e:
        print(f"[ERRORE] Errore recupero ids conti tecnici carte: {e}")
        return set()


def calcola_totale_speso_carta(id_carta: int, mese: int, anno: int) -> float:
    try:
        with get_db_connection() as conn:
            start_date = f'{anno}-{mese:02d}-01'
            if mese == 12:
                end_date = f'{anno+1}-01-01'
            else:
                end_date = f'{anno}-{mese+1:02d}-01'
            
            cur = conn.cursor()
            
            # 1. Personal Transactions
            q1 = "SELECT SUM(importo) as totale FROM Transazioni WHERE id_carta = %s AND data >= %s AND data < %s"
            cur.execute(q1, (id_carta, start_date, end_date))
            res1 = cur.fetchone()
            val1 = float(res1.get('totale') or 0.0)
            
            # 2. Shared Transactions
            q2 = "SELECT SUM(importo) as totale FROM TransazioniCondivise WHERE id_carta = %s AND data >= %s AND data < %s"
            cur.execute(q2, (id_carta, start_date, end_date))
            res2 = cur.fetchone()
            val2 = float(res2.get('totale') or 0.0)
            
            return abs(val1 + val2)
    except Exception as e:
        print(f'Error calc speso carta: {e}')
        return 0.0


def ottieni_transazioni_carta(id_carta, mese, anno, master_key_b64=None, id_utente=None):
    """
    Recupera le transazioni (personali e condivise) associate a una carta per un dato mese/anno.
    Decripta le descrizioni se necessario.
    """
    import calendar
    try:
        start_date = datetime.date(anno, mese, 1)
        _, last_day = calendar.monthrange(anno, mese)
        end_date = datetime.date(anno, mese, last_day)

        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        family_key = None
        if master_key and id_utente:
             id_famiglia = ottieni_prima_famiglia_utente(id_utente)
             if id_famiglia:
                 family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        transazioni = []

        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Transazioni Personali
            cur.execute("""
                SELECT 
                    T.id_transazione, T.data, T.descrizione, T.importo, 
                    S.nome_sottocategoria, C.nome_categoria
                FROM Transazioni T
                LEFT JOIN Sottocategorie S ON T.id_sottocategoria = S.id_sottocategoria
                LEFT JOIN Categorie C ON S.id_categoria = C.id_categoria
                WHERE T.id_carta = %s 
                  AND T.data >= %s AND T.data <= %s
                ORDER BY T.data DESC
            """, (id_carta, start_date, end_date))
            
            rows_p = cur.fetchall()
            for r in rows_p:
                t = dict(r)
                t['tipo'] = 'Personale'
                
                # Decrypt description - Try Master Key then Family Key fallback
                desc = _decrypt_if_key(t['descrizione'], master_key, crypto, silent=True)
                if desc == "[ENCRYPTED]" and family_key:
                    res = _decrypt_if_key(t['descrizione'], family_key, crypto, silent=True)
                    if res != "[ENCRYPTED]":
                        desc = res
                t['descrizione'] = desc
                
                if family_key:
                    t['nome_sottocategoria'] = _decrypt_if_key(t['nome_sottocategoria'], family_key, crypto, silent=True)
                    t['nome_categoria'] = _decrypt_if_key(t['nome_categoria'], family_key, crypto, silent=True)
                
                transazioni.append(t)

            # 2. Transazioni Condivise
            cur.execute("""
                SELECT 
                    TC.id_transazione_condivisa as id_transazione, TC.data, TC.descrizione, TC.importo, 
                    S.nome_sottocategoria, C.nome_categoria,
                    U.username as autore
                FROM TransazioniCondivise TC
                LEFT JOIN Sottocategorie S ON TC.id_sottocategoria = S.id_sottocategoria
                LEFT JOIN Categorie C ON S.id_categoria = C.id_categoria
                LEFT JOIN Utenti U ON TC.id_utente_autore = U.id_utente
                WHERE TC.id_carta = %s
                  AND TC.data >= %s AND TC.data <= %s
                ORDER BY TC.data DESC
            """, (id_carta, start_date, end_date))
            
            rows_c = cur.fetchall()
            for r in rows_c:
                t = dict(r)
                t['tipo'] = 'Condivisa'
                
                # Decrypt description - Try Family Key then Master Key fallback
                desc = t['descrizione']
                if family_key:
                    desc = _decrypt_if_key(desc, family_key, crypto, silent=True)
                
                if (desc == "[ENCRYPTED]" or desc == t['descrizione']) and master_key:
                     res = _decrypt_if_key(t['descrizione'], master_key, crypto, silent=True)
                     if res != "[ENCRYPTED]":
                         desc = res
                t['descrizione'] = desc

                if family_key:
                    t['nome_sottocategoria'] = _decrypt_if_key(t['nome_sottocategoria'], family_key, crypto, silent=True)
                    t['nome_categoria'] = _decrypt_if_key(t['nome_categoria'], family_key, crypto, silent=True)
                transazioni.append(t)
                
        transazioni.sort(key=lambda x: x['data'], reverse=True)
        return transazioni

    except Exception as e:
        print(f"[ERRORE] Errore recupero transazioni carta: {e}")
        return []


def ottieni_mesi_disponibili_carta(id_carta):
    """
    Restituisce una lista di tuple (anno, mese) distinte in cui sono presenti transazioni per la carta.
    Ordinata dalla più recente.
    """
    try:
        mesi = set()
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Personali
            cur.execute("""
                SELECT DISTINCT EXTRACT(YEAR FROM data::date) as anno, EXTRACT(MONTH FROM data::date) as mese
                FROM Transazioni
                WHERE id_carta = %s
            """, (id_carta,))
            for row in cur.fetchall():
                mesi.add((int(row['anno']), int(row['mese'])))
                
            # Condivise
            cur.execute("""
                SELECT DISTINCT EXTRACT(YEAR FROM data::date) as anno, EXTRACT(MONTH FROM data::date) as mese
                FROM TransazioniCondivise
                WHERE id_carta = %s
            """, (id_carta,))
            for row in cur.fetchall():
                mesi.add((int(row['anno']), int(row['mese'])))
        
        lista_mesi = sorted(list(mesi), key=lambda x: (x[0], x[1]), reverse=True)
        return lista_mesi
    except Exception as e:
        print(f"[ERRORE] Errore recupero mesi carta: {e}")
        return []

