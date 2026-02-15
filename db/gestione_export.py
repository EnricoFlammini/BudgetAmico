"""
Funzioni export: backup, esportazioni dati famiglia
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
    _get_family_key_for_user,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code,
    SERVER_SECRET_KEY,
    crypto as _crypto_instance
)

from db.gestione_admin import ottieni_versione_db



# --- Funzioni Export ---
def ottieni_riepilogo_conti_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        # Decryption setup
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            
            # --- Personal Accounts ---
            # Cast 0.0 to NUMERIC/REAL to ensure type match in UNION/CASE if needed, though usually automatic.
            # The issue 'CASE types double precision and text' implies one branch is text.
            # COALESCE returns type of first non-null arg. 0.0 is double.
            # Check if fields are correct.
            query_personali = """
                        SELECT U.nome_enc_server, U.cognome_enc_server, U.username,
                               C.nome_conto,
                               C.tipo,
                               C.iban,
                               CASE
                                   WHEN C.tipo = 'Fondo Pensione' THEN CAST(C.valore_manuale AS DOUBLE PRECISION)
                                   WHEN C.tipo = 'Investimento'
                                       THEN (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                             FROM Asset A
                                             WHERE A.id_conto = C.id_conto)
                                   ELSE (SELECT COALESCE(SUM(T.importo), 0.0)
                                         FROM Transazioni T
                                         WHERE T.id_conto = C.id_conto) + COALESCE(CAST(NULLIF(CAST(C.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0)
                                   END                                          AS saldo_calcolato
                        FROM Conti C
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                          AND (C.nascosto IS NOT TRUE)
            """
            
            # --- Shared Accounts ---
            # Fixed missing 'iban' in ContiCondivisi by selecting NULL
            query_condivisi = """
                        SELECT 'Condiviso' as nome_enc_server, NULL as cognome_enc_server, 'Condiviso' as username,
                               CC.nome_conto,
                               CC.tipo,
                               NULL as iban,
                               CASE
                                   WHEN CC.tipo = 'Investimento'
                                       THEN (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                             FROM Asset A
                                             WHERE 0=1) -- Shared Asset support missing in current schema
                                   ELSE (SELECT COALESCE(SUM(TC.importo), 0.0)
                                         FROM TransazioniCondivise TC
                                         WHERE TC.id_conto_condiviso = CC.id_conto_condiviso) + COALESCE(CAST(NULLIF(CAST(CC.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0)
                                   END                                          AS saldo_calcolato
                        FROM ContiCondivisi CC
                        WHERE CC.id_famiglia = %s
            """
            
            # Execute queries
            cur.execute(query_personali, (id_famiglia,))
            personali = [dict(row) for row in cur.fetchall()]
            
            cur.execute(query_condivisi, (id_famiglia,))
            condivisi = [dict(row) for row in cur.fetchall()]
            
            results = personali + condivisi
            
            # Decrypt and Format
            for row in results:
                # Decrypt Member Name
                if row.get('username') == 'Condiviso':
                     row['membro'] = "Condiviso"
                else:
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['membro'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['membro'] = row.get('username', 'Sconosciuto')
                
                # Decrypt Account Name
                if row.get('nome_conto'):
                    decrypted_conto = _decrypt_if_key(row['nome_conto'], family_key, crypto, silent=True)
                    # Check if decryption failed (None, [ENCRYPTED], or returned original encrypted value)
                    if (not decrypted_conto or decrypted_conto == "[ENCRYPTED]" or decrypted_conto == row['nome_conto']) and family_key != master_key:
                        decrypted_conto = _decrypt_if_key(row['nome_conto'], master_key, crypto, silent=True)
                    row['nome_conto'] = decrypted_conto or row['nome_conto']
                
                # Decrypt IBAN
                if row.get('iban'):
                     decrypted_iban = _decrypt_if_key(row['iban'], family_key, crypto, silent=True)
                     if (not decrypted_iban or decrypted_iban == "[ENCRYPTED]" or decrypted_iban == row['iban']) and family_key != master_key:
                         decrypted_iban = _decrypt_if_key(row['iban'], master_key, crypto, silent=True)
                     row['iban'] = decrypted_iban or row['iban']

                # Clean up encrypted/internal fields
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
            
            # Sort by Member, Type, Account Name
            results.sort(key=lambda x: (x.get('membro', ''), x.get('tipo', ''), x.get('nome_conto', '')))
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero riepilogo conti famiglia: {e}")
        return []


def ottieni_dettaglio_portafogli_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        # Decryption setup
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            # Removed Shared Investments UNION as Asset table does not support Shared Accounts yet (missing id_conto_condiviso)
            query = """
                        SELECT U.nome_enc_server, U.cognome_enc_server, U.username,
                               C.nome_conto,
                               A.ticker,
                               A.nome_asset,
                               A.quantita,
                               A.costo_iniziale_unitario,
                               A.prezzo_attuale_manuale as valore_corrente_unitario,
                               (A.quantita * A.costo_iniziale_unitario)             AS investito_totale,
                               (A.quantita * A.prezzo_attuale_manuale)              AS valore_totale,
                               ((A.quantita * A.prezzo_attuale_manuale) - (A.quantita * A.costo_iniziale_unitario)) AS profitto
                        FROM Conti C
                                 JOIN Asset A ON C.id_conto = A.id_conto
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                          AND C.tipo = 'Investimento'
                          
                        ORDER BY username, nome_conto, ticker
            """
            cur.execute(query, (id_famiglia,))
            
            results = [dict(row) for row in cur.fetchall()]
            for row in results:
                # Decrypt Member
                if row.get('username') == 'Condiviso':
                    row['membro'] = "Condiviso"
                else:
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['membro'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['membro'] = row.get('username', 'Sconosciuto')
                
                # Decrypt Account/Ticker/Asset
                for field in ['nome_conto', 'ticker', 'nome_asset']:
                    val = row.get(field)
                    if val:
                        decrypted = _decrypt_if_key(val, family_key, crypto, silent=True)
                        # Check if decryption failed (None, [ENCRYPTED], or returned original encrypted value)
                        if (not decrypted or decrypted == "[ENCRYPTED]" or decrypted == val) and family_key != master_key:
                            decrypted = _decrypt_if_key(val, master_key, crypto, silent=True)
                        row[field] = decrypted or val
                
                # Clean up encrypted/internal fields
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
            
            return results

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero dettaglio portafogli famiglia: {e}")
        return []




def ottieni_transazioni_famiglia_per_export(id_famiglia, data_inizio, data_fine, master_key_b64=None, id_utente=None, filtra_utente_id=None):
    try:
        # Decryption setup
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            
            # --- Personal Transactions ---
            # Transazioni joins Sottocategorie joins Categorie
            # If filtra_utente_id is set, restrict to that user only
            sql_filtro_utente = ""
            params_personali = [id_famiglia, data_inizio, data_fine]
            
            if filtra_utente_id:
                sql_filtro_utente = "AND U.id_utente = %s"
                params_personali.append(filtra_utente_id)

            query_personali = f"""
                        SELECT T.data,
                               U.nome_enc_server, U.cognome_enc_server, U.username,
                               C.nome_conto,
                               T.descrizione,
                               Cat.nome_categoria,
                               T.importo
                        FROM Transazioni T
                                 JOIN Conti C ON T.id_conto = C.id_conto
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                                 LEFT JOIN Sottocategorie S ON T.id_sottocategoria = S.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON S.id_categoria = Cat.id_categoria
                        WHERE AF.id_famiglia = %s
                          AND T.data BETWEEN %s AND %s
                          AND C.tipo != 'Fondo Pensione'
                          {sql_filtro_utente}
            """
            
            # --- Shared Transactions ---
            query_condivise = """
                        SELECT TC.data,
                               'Condiviso' as nome_enc_server, NULL as cognome_enc_server, 'Condiviso' as username,
                               CC.nome_conto,
                               TC.descrizione,
                               Cat.nome_categoria,
                               TC.importo
                        FROM TransazioniCondivise TC
                                 JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                 LEFT JOIN Sottocategorie S ON TC.id_sottocategoria = S.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON S.id_categoria = Cat.id_categoria
                        WHERE CC.id_famiglia = %s
                          AND TC.data BETWEEN %s AND %s
            """
            
            # Exec Personal
            cur.execute(query_personali, tuple(params_personali))
            personali = [dict(row) for row in cur.fetchall()]
            
            # Exec Shared
            cur.execute(query_condivise, (id_famiglia, data_inizio, data_fine))
            condivise = [dict(row) for row in cur.fetchall()]
            
            # Combine
            results = personali + condivise
            
            # Decrypt loop & Filter
            final_results = []
            for row in results:
                # Decrypt Member
                if row.get('username') == 'Condiviso':
                     row['membro'] = "Condiviso"
                else:
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['membro'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['membro'] = row.get('username', 'Sconosciuto')

                # Decrypt Fields (Account, Description, Category)
                for field in ['nome_conto', 'descrizione', 'nome_categoria']:
                    val = row.get(field)
                    if val:
                        # Try Family Key
                        decrypted = _decrypt_if_key(val, family_key, crypto, silent=True)
                        
                        # If failed (ENCRYPTED or None), and we have a different Master Key, try that
                        if (not decrypted or decrypted == "[ENCRYPTED]") and family_key != master_key:
                             decrypted = _decrypt_if_key(val, master_key, crypto, silent=True)
                        
                        # If still failed, keep original val (or handle below)
                        if decrypted and decrypted != "[ENCRYPTED]":
                            row[field] = decrypted
                        else:
                            row[field] = val # Revert to raw if decryption failed completely

                # USER REQ: Eliminate 'Saldo iniziale'
                if str(row.get('descrizione', '')).lower() == "saldo iniziale":
                    continue

                # USER REQ: Rename encrypted giroconti
                desc = row.get('descrizione', '')
                if isinstance(desc, str):
                    if desc.startswith('gAAAA') or desc == "[ENCRYPTED]":
                        row['descrizione'] = "Giroconto (Criptato)"

                # Clean up encrypted/internal fields
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
                
                final_results.append(row)
            
            # USER REQ: Sort Oldest to Newest (Ascending)
            final_results.sort(key=lambda x: x['data'], reverse=False)
            
            return final_results

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero transazioni famiglia per export: {e}")
        return []

def ottieni_dati_immobili_famiglia_per_export(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            # Fixed 'mutuo_residuo' missing. It's in Prestiti table linked by id_prestito_collegato
            query = """
                SELECT I.nome as nome_immobile, I.via || ', ' || I.citta as indirizzo, I.valore_attuale, 
                       P.importo_residuo as mutuo_residuo, I.nuda_proprieta,
                       QI.id_utente, U.nome_enc_server, U.cognome_enc_server, U.username,
                       QI.percentuale
                FROM Immobili I
                LEFT JOIN Prestiti P ON I.id_prestito_collegato = P.id_prestito
                LEFT JOIN QuoteImmobili QI ON I.id_immobile = QI.id_immobile
                LEFT JOIN Utenti U ON QI.id_utente = U.id_utente
                WHERE I.id_famiglia = %s
                ORDER BY I.nome
            """
            cur.execute(query, (id_famiglia,))
            
            results = [dict(row) for row in cur.fetchall()]
            for row in results:
                # Decrypt Member
                if row.get('username'):
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['comproprietario'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['comproprietario'] = row.get('username', 'Sconosciuto')
                else:
                    row['comproprietario'] = "Nessuno/Non assegnato"
                    
                # Decrypt Property details
                for field in ['nome_immobile', 'indirizzo']:
                    val = row.get(field)
                    if val:
                        decrypted = _decrypt_if_key(val, family_key, crypto, silent=True)
                        row[field] = decrypted or val
                
                # Clean up
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
                row.pop('id_utente', None)
                        
            return results
    except Exception as e:
        print(f"[ERRORE] Errore export immobili: {e}")
        return []

def ottieni_dati_prestiti_famiglia_per_export(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            # Fixed 'data_scadenza' missing
            query = """
                SELECT P.nome, P.importo_finanziato as importo_totale, P.importo_residuo as importo_rimanente, P.data_inizio,
                       QP.id_utente, U.nome_enc_server, U.cognome_enc_server, U.username,
                       QP.percentuale
                FROM Prestiti P
                LEFT JOIN QuotePrestiti QP ON P.id_prestito = QP.id_prestito
                LEFT JOIN Utenti U ON QP.id_utente = U.id_utente
                WHERE P.id_famiglia = %s
                ORDER BY P.nome
            """
            cur.execute(query, (id_famiglia,))
            
            results = [dict(row) for row in cur.fetchall()]
            for row in results:
                 # Decrypt Member
                if row.get('username'):
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['intestatario'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['intestatario'] = row.get('username', 'Sconosciuto')
                else:
                    row['intestatario'] = "Nessuno/Non assegnato"
                
                # Decrypt name
                if row.get('nome'):
                     decrypted = _decrypt_if_key(row['nome'], family_key, crypto, silent=True)
                     row['nome'] = decrypted or row['nome']
                
                # Clean up
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
                row.pop('id_utente', None)
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore export prestiti: {e}")
        return []

def ottieni_dati_spese_fisse_famiglia_per_export(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            # SpeseFisse uses 'id_conto_personale_addebito' and 'id_conto_condiviso_addebito'
            query = """
                SELECT SF.nome, SF.importo, SF.giorno_addebito, SF.attiva, SF.addebito_automatico,
                       SF.id_conto_personale_addebito, C.nome_conto as nome_conto_personale, U.nome_enc_server, U.cognome_enc_server, U.username,
                       SF.id_conto_condiviso_addebito, CC.nome_conto as nome_conto_condiviso,
                       Cat.nome_categoria,
                       SC.nome_sottocategoria
                FROM SpeseFisse SF
                LEFT JOIN Conti C ON SF.id_conto_personale_addebito = C.id_conto
                LEFT JOIN Utenti U ON C.id_utente = U.id_utente
                LEFT JOIN ContiCondivisi CC ON SF.id_conto_condiviso_addebito = CC.id_conto_condiviso
                LEFT JOIN Categorie Cat ON SF.id_categoria = Cat.id_categoria
                LEFT JOIN Sottocategorie SC ON SF.id_sottocategoria = SC.id_sottocategoria
                WHERE SF.id_famiglia = %s
                ORDER BY SF.giorno_addebito
            """
            cur.execute(query, (id_famiglia,))
            
            results = [dict(row) for row in cur.fetchall()]
            for row in results:
                # Resolve Account Name and Owner
                if row.get('id_conto_personale_addebito'):
                     # Personal Account
                    # Decrypt Member
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['conto_addebito'] = f"{row.get('nome_conto_personale')} ({n or ''} {c or ''})".strip()
                    else:
                        row['conto_addebito'] = f"{row.get('nome_conto_personale')} ({row.get('username', '?')})"
                else:
                    # Shared Account
                    row['conto_addebito'] = f"{row.get('nome_conto_condiviso')} (Condiviso)"
                
                # Decrypt Expense Name
                if row.get('nome'):
                     decrypted = _decrypt_if_key(row['nome'], family_key, crypto, silent=True)
                     row['nome'] = decrypted or row['nome']
                
                # Decrypt Account Names
                # nome_conto_personale and nome_conto_condiviso are potentially encrypted
                conto_name = row.get('nome_conto_personale') or row.get('nome_conto_condiviso')
                if conto_name:
                    decrypted_conto = _decrypt_if_key(conto_name, family_key, crypto, silent=True)
                    if not decrypted_conto and family_key != master_key:
                        decrypted_conto = _decrypt_if_key(conto_name, master_key, crypto, silent=True)
                    conto_name = decrypted_conto or conto_name
                
                if row.get('id_conto_personale_addebito'):
                     n = decrypt_system_data(row.get('nome_enc_server'))
                     c = decrypt_system_data(row.get('cognome_enc_server'))
                     owner = f"{n or ''} {c or ''}".strip() or row.get('username')
                     row['conto_addebito'] = f"{conto_name} ({owner})"
                else:
                    row['conto_addebito'] = f"{conto_name} (Condiviso)"

                # Decrypt Category/Subcat
                if row.get('nome_categoria'):
                     decrypted = _decrypt_if_key(row['nome_categoria'], family_key, crypto, silent=True)
                     row['nome_categoria'] = decrypted or row['nome_categoria']
                
                # Clean up
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
                row.pop('id_conto_personale_addebito', None)
                row.pop('id_conto_condiviso_addebito', None)
                row.pop('nome_conto_personale', None)
                row.pop('nome_conto_condiviso', None)
                
            return results
    except Exception as e:
        print(f"[ERRORE] Errore export spese fisse: {e}")
        return []

def ottieni_backup_completo_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    """
    Raccoglie TUTTI i dati della famiglia (e dei suoi membri) per un backup completo.
    Decripta i dati sensibili se viene fornita la master_key.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        backup = {
            "metadata": {
                "id_famiglia": id_famiglia,
                "data_backup": datetime.datetime.now().isoformat(),
                "versione_db": ottieni_versione_db()
            },
            "tabelle": {}
        }

        with get_db_connection() as con:
            cur = con.cursor()

            # 1. Famiglia
            cur.execute("SELECT * FROM Famiglie WHERE id_famiglia = %s", (id_famiglia,))
            fam = cur.fetchone()
            if not fam: return None
            fam_dict = dict(fam)
            if family_key:
                decrypted_nome = _decrypt_if_key(fam_dict.get('nome_famiglia'), family_key, crypto, silent=True)
                fam_dict['nome_famiglia'] = decrypted_nome or fam_dict['nome_famiglia']
            backup["tabelle"]["Famiglie"] = [fam_dict]

            # 2. Membri
            cur.execute("SELECT * FROM Appartenenza_Famiglia WHERE id_famiglia = %s", (id_famiglia,))
            membri = [dict(row) for row in cur.fetchall()]
            backup["tabelle"]["Appartenenza_Famiglia"] = membri
            id_utenti = [m['id_utente'] for m in membri]

            # 3. Utenti
            if id_utenti:
                cur.execute("SELECT * FROM Utenti WHERE id_utente = ANY(%s)", (id_utenti,))
                utenti = [dict(row) for row in cur.fetchall()]
                for u in utenti:
                    if u.get('username_enc'): u['username'] = decrypt_system_data(u['username_enc']) or u['username']
                    if u.get('email_enc'): u['email'] = decrypt_system_data(u['email_enc']) or u['email']
                    if u.get('nome_enc_server'): u['nome'] = decrypt_system_data(u['nome_enc_server']) or u['nome']
                    if u.get('cognome_enc_server'): u['cognome'] = decrypt_system_data(u['cognome_enc_server']) or u['cognome']
                backup["tabelle"]["Utenti"] = utenti

            # 4. Conti & Carte
            if id_utenti:
                cur.execute("SELECT * FROM Conti WHERE id_utente = ANY(%s)", (id_utenti,))
                backup["tabelle"]["Conti"] = [dict(row) for row in cur.fetchall()]
                
                cur.execute("SELECT * FROM Carte WHERE id_utente = ANY(%s)", (id_utenti,))
                carte = [dict(row) for row in cur.fetchall()]
                for c in carte:
                    if family_key:
                        for f in ['massimale_encrypted', 'giorno_addebito_encrypted', 'spesa_tenuta_encrypted', 'soglia_azzeramento_encrypted', 'giorno_addebito_tenuta_encrypted']:
                            if c.get(f): c[f.replace('_encrypted', '')] = _decrypt_if_key(c[f], family_key, crypto, silent=True)
                backup["tabelle"]["Carte"] = carte

            cur.execute("SELECT * FROM ContiCondivisi WHERE id_famiglia = %s", (id_famiglia,))
            backup["tabelle"]["ContiCondivisi"] = [dict(row) for row in cur.fetchall()]

            # 5. Asset & Storico
            if id_utenti:
                cur.execute("SELECT * FROM Asset WHERE id_conto IN (SELECT id_conto FROM Conti WHERE id_utente = ANY(%s))", (id_utenti,))
                backup["tabelle"]["Asset"] = [dict(row) for row in cur.fetchall()]
                cur.execute("SELECT * FROM Storico_Asset WHERE id_conto IN (SELECT id_conto FROM Conti WHERE id_utente = ANY(%s))", (id_utenti,))
                backup["tabelle"]["Storico_Asset"] = [dict(row) for row in cur.fetchall()]

            # 6. Transazioni
            if id_utenti:
                cur.execute("SELECT * FROM Transazioni WHERE id_conto IN (SELECT id_conto FROM Conti WHERE id_utente = ANY(%s))", (id_utenti,))
                backup["tabelle"]["Transazioni"] = [dict(row) for row in cur.fetchall()]

            cur.execute("SELECT * FROM TransazioniCondivise WHERE id_conto_condiviso IN (SELECT id_conto_condiviso FROM ContiCondivisi WHERE id_famiglia = %s)", (id_famiglia,))
            backup["tabelle"]["TransazioniCondivise"] = [dict(row) for row in cur.fetchall()]

            # 7. Prestiti & Ammortamento
            cur.execute("SELECT * FROM Prestiti WHERE id_famiglia = %s", (id_famiglia,))
            prestiti = [dict(row) for row in cur.fetchall()]
            backup["tabelle"]["Prestiti"] = prestiti
            id_prestiti = [p['id_prestito'] for p in prestiti]
            if id_prestiti:
                cur.execute("SELECT * FROM PianoAmmortamento WHERE id_prestito = ANY(%s)", (id_prestiti,))
                backup["tabelle"]["PianoAmmortamento"] = [dict(row) for row in cur.fetchall()]
                cur.execute("SELECT * FROM StoricoPagamentiRate WHERE id_prestito = ANY(%s)", (id_prestiti,))
                backup["tabelle"]["StoricoPagamentiRate"] = [dict(row) for row in cur.fetchall()]
                cur.execute("SELECT * FROM QuotePrestiti WHERE id_prestito = ANY(%s)", (id_prestiti,))
                backup["tabelle"]["QuotePrestiti"] = [dict(row) for row in cur.fetchall()]

            # 8. Immobili
            cur.execute("SELECT * FROM Immobili WHERE id_famiglia = %s", (id_famiglia,))
            immobili = [dict(row) for row in cur.fetchall()]
            backup["tabelle"]["Immobili"] = immobili
            id_immobili = [i['id_immobile'] for i in immobili]
            if id_immobili:
                cur.execute("SELECT * FROM QuoteImmobili WHERE id_immobile = ANY(%s)", (id_immobili,))
                backup["tabelle"]["QuoteImmobili"] = [dict(row) for row in cur.fetchall()]

            # 9. Spese Fisse
            cur.execute("SELECT * FROM SpeseFisse WHERE id_famiglia = %s", (id_famiglia,))
            backup["tabelle"]["SpeseFisse"] = [dict(row) for row in cur.fetchall()]

            # 1 category and subcategories
            cur.execute("SELECT * FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
            cats = [dict(row) for row in cur.fetchall()]
            backup["tabelle"]["Categorie"] = cats
            id_cats = [c['id_categoria'] for c in cats]
            if id_cats:
                cur.execute("SELECT * FROM Sottocategorie WHERE id_categoria = ANY(%s)", (id_cats,))
                backup["tabelle"]["Sottocategorie"] = [dict(row) for row in cur.fetchall()]

            # 10. Budget & Storico
            cur.execute("SELECT * FROM Budget WHERE id_famiglia = %s", (id_famiglia,))
            budgets = [dict(row) for row in cur.fetchall()]
            for b in budgets:
                if family_key: b['importo_limite'] = _decrypt_if_key(b['importo_limite'], family_key, crypto, silent=True)
            backup["tabelle"]["Budget"] = budgets

            cur.execute("SELECT * FROM Budget_Storico WHERE id_famiglia = %s", (id_famiglia,))
            b_storico = [dict(row) for row in cur.fetchall()]
            for bs in b_storico:
                if family_key:
                    bs['importo_limite'] = _decrypt_if_key(bs['importo_limite'], family_key, crypto, silent=True)
                    bs['importo_speso'] = _decrypt_if_key(bs['importo_speso'], family_key, crypto, silent=True)
            backup["tabelle"]["Budget_Storico"] = b_storico

            # 11. Salvadanai & Obiettivi
            cur.execute("SELECT * FROM Salvadanai WHERE id_famiglia = %s", (id_famiglia,))
            salvadanai = [dict(row) for row in cur.fetchall()]
            for s in salvadanai:
                if family_key: s['importo_assegnato'] = _decrypt_if_key(s['importo_assegnato'], family_key, crypto, silent=True)
            backup["tabelle"]["Salvadanai"] = salvadanai

            cur.execute("SELECT * FROM Obiettivi_Risparmio WHERE id_famiglia = %s", (id_famiglia,))
            obiettivi = [dict(row) for row in cur.fetchall()]
            for o in obiettivi:
                if family_key: o['importo_obiettivo'] = _decrypt_if_key(o['importo_obiettivo'], family_key, crypto, silent=True)
            backup["tabelle"]["Obiettivi_Risparmio"] = obiettivi
            
            # 12. Contatti
            cur.execute("SELECT * FROM Contatti WHERE id_famiglia = %s OR id_utente = ANY(%s)", (id_famiglia, id_utenti))
            contatti = [dict(row) for row in cur.fetchall()]
            for co in contatti:
                if family_key:
                    for f in ['nome_encrypted', 'cognome_encrypted', 'societa_encrypted', 'iban_encrypted', 'email_encrypted', 'telefono_encrypted']:
                        if co.get(f): co[f.replace('_encrypted', '')] = _decrypt_if_key(co[f], family_key, crypto, silent=True)
            backup["tabelle"]["Contatti"] = contatti

            # 13. Configurazioni
            cur.execute("SELECT * FROM Configurazioni WHERE id_famiglia = %s", (id_famiglia,))
            backup["tabelle"]["Configurazioni"] = [dict(row) for row in cur.fetchall()]

            return backup
    except Exception as e:
        print(f"[ERRORE] Backup dati fallito: {e}")
        import traceback
        traceback.print_exc()
        return None

