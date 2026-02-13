"""
Funzioni obiettivi e salvadanai: CRUD, collegamento
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


# --- GESTIONE OBIETTIVI RISPARMIO (ACCANTONAMENTI) ---



def crea_obiettivo(id_famiglia: str, nome: str, importo_obiettivo: float, data_obiettivo: str, note: str = "", master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, mostra_suggerimento: bool = True) -> bool:
    """
    Crea un nuovo obiettivo di risparmio (v2).
    Nome, importo e note vengono criptati con chiave famiglia.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        key_to_use = family_key if family_key else master_key
        
        # Encrypt data (Names and notes stay encrypted)
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto)
        note_enc = _encrypt_if_key(note, key_to_use, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO Obiettivi_Risparmio (id_famiglia, nome, importo_obiettivo, data_obiettivo, note, mostra_suggerimento_mensile)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (id_famiglia, nome_enc, importo_obiettivo, data_obiettivo, note_enc, mostra_suggerimento))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore creazione obiettivo: {e}")
        return False

def ottieni_obiettivi(id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recupera tutti gli obiettivi, calcolando il totale accumulato dai Salvadanai collegati.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        key_to_use = family_key if family_key else master_key

        with get_db_connection() as con:
            cur = con.cursor()
            # Get goals
            cur.execute("""
                SELECT id, nome, importo_obiettivo, data_obiettivo, note, mostra_suggerimento_mensile
                FROM Obiettivi_Risparmio
                WHERE id_famiglia = %s
                ORDER BY data_obiettivo ASC
            """, (id_famiglia,))
            
            rows = cur.fetchall()
            obiettivi = []
            
            for row in rows:
                try:
                    goal_id = row['id']
                    
                    # Decrypt core data
                    nome = _decrypt_if_key(row['nome'], key_to_use, crypto, silent=True)
                    importo_obj = row['importo_obiettivo'] if row['importo_obiettivo'] else 0.0
                    note = _decrypt_if_key(row['note'], key_to_use, crypto, silent=True)
                    
                    # Calculate accumulated amount using Dynamic Logic (min(Assigned, RealBalance))
                    salvadanai = ottieni_salvadanai_obiettivo(goal_id, id_famiglia, master_key_b64, id_utente)
                    totale_accumulato = sum(s['importo'] for s in salvadanai)

                    obiettivi.append({
                        'id': goal_id,
                        'nome': nome,
                        'importo_obiettivo': float(importo_obj),
                        'data_obiettivo': row['data_obiettivo'],
                        'importo_accumulato': totale_accumulato, 
                        'note': note,
                        'mostra_suggerimento_mensile': row['mostra_suggerimento_mensile']
                    })
                except Exception as ex:
                    # logger.error(f"Errore decrypt obiettivo {row['id']}: {ex}")
                    obiettivi.append({
                         'id': row['id'],
                         'nome': "[ERRORE DECRITTAZIONE]",
                         'importo_obiettivo': 0.0,
                         'data_obiettivo': row['data_obiettivo'],
                         'importo_accumulato': 0.0,
                         'note': "",
                         'mostra_suggerimento_mensile': False
                    })

            return obiettivi
    except Exception as e:
        logger.error(f"Errore recupero obiettivi: {e}")
        return []

def aggiorna_obiettivo(id_obiettivo: int, id_famiglia: str, nome: str, importo_obiettivo: float, data_obiettivo: str, note: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, mostra_suggerimento: bool = True) -> bool:
    """
    Aggiorna un obiettivo esistente.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        key_to_use = family_key if family_key else master_key
        
        # Encrypt data
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto)
        note_enc = _encrypt_if_key(note, key_to_use, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE Obiettivi_Risparmio
                SET nome = %s, 
                    importo_obiettivo = %s,
                    data_obiettivo = %s,
                    note = %s,
                    mostra_suggerimento_mensile = %s
                WHERE id = %s AND id_famiglia = %s
            """, (nome_enc, importo_obiettivo, data_obiettivo, note_enc, mostra_suggerimento, id_obiettivo, id_famiglia))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore aggiornamento obiettivo: {e}")
        return False

def elimina_obiettivo(id_obiettivo: int, id_famiglia: str) -> bool:
    """
    Elimina un obiettivo.
    IMPORTANTE: Scollega prima i salvadanai per NON cancellare i fondi fisici (Soldi).
    I salvadanai diventeranno "Orfani" (visibili nel conto) e l'utente potrà gestirli.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Step 1: Unlink Piggy Banks (Save the Money!)
            cur.execute("""
                UPDATE Salvadanai 
                SET id_obiettivo = NULL 
                WHERE id_obiettivo = %s AND id_famiglia = %s
            """, (id_obiettivo, id_famiglia))
            
            # Step 2: Delete Goal
            cur.execute("DELETE FROM Obiettivi_Risparmio WHERE id = %s AND id_famiglia = %s", (id_obiettivo, id_famiglia))
            
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore eliminazione obiettivo: {e}")
        return False

# --- GESTIONE SALVADANAI (Obiettivi v2) ---

def crea_salvadanaio(id_famiglia: str, nome: str, importo: float, id_obiettivo: Optional[int] = None, id_conto: Optional[int] = None, id_asset: Optional[int] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, incide_su_liquidita: bool = False, id_conto_condiviso: Optional[int] = None, usa_saldo_totale: bool = False) -> Optional[int]:
    """
    Crea un salvadanaio.
    Richiede id_conto (Personale) OPPURE id_conto_condiviso (Condiviso).
    Returns the ID of the new piggy bank, or None on failure.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        # Enforce Family Key for Shared PBs
        if id_conto_condiviso:
            if not family_key:
                logger.error("Tentativo di creare salvadanaio condiviso senza chiave famiglia.")
                return None
            key_to_use = family_key
        else:
            key_to_use = family_key if family_key else master_key
            if not key_to_use: return None
        
        note_enc = _encrypt_if_key("", key_to_use, crypto)
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            
            # Use id_conto_condiviso if provided
            cur.execute("""
                INSERT INTO Salvadanai (id_famiglia, id_obiettivo, id_conto, id_conto_condiviso, id_asset, nome, importo_assegnato, note, incide_su_liquidita, usa_saldo_totale)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_salvadanaio
            """, (id_famiglia, id_obiettivo, id_conto, id_conto_condiviso, id_asset, nome_enc, importo, note_enc, incide_su_liquidita, usa_saldo_totale))
            
            row = cur.fetchone()
            con.commit()
            
            if row:
                return row['id_salvadanaio']
            return None
            
    except Exception as e:
        logger.error(f"Errore crea_salvadanaio: {e}")
        return None

def scollega_salvadanaio_obiettivo(id_salvadanaio: int, id_famiglia: str) -> bool:
    """
    Scollega un salvadanaio da un obiettivo (lo rende 'libero' ma non lo elimina).
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE Salvadanai 
                SET id_obiettivo = NULL 
                WHERE id_salvadanaio = %s AND id_famiglia = %s
            """, (id_salvadanaio, id_famiglia))
            con.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Errore scollega_salvadanaio_obiettivo: {e}")
        return False

def ottieni_salvadanai_conto(id_conto: int, id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, is_condiviso: bool = False) -> List[Dict[str, Any]]:
    """
    Recupera i salvadanai collegati a uno specifico conto (personale o condiviso).
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            if is_condiviso:
                cur.execute("SELECT * FROM Salvadanai WHERE id_conto_condiviso = %s", (id_conto,))
            else:
                cur.execute("SELECT * FROM Salvadanai WHERE id_conto = %s", (id_conto,))
                
            rows = [dict(row) for row in cur.fetchall()]
            
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente and id_famiglia:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            if is_condiviso:
                 keys_to_try = [family_key] if family_key else []
            else:
                 keys_to_try = []
                 if family_key: keys_to_try.append(family_key)
                 if master_key: keys_to_try.append(master_key)
            
            # logger.info(f"DEBUG PB: User={id_utente}, Fam={id_famiglia}. Keys to try: {len(keys_to_try)} (MK={bool(master_key)}, FK={bool(family_key)})")

            def try_decrypt(val, keys):
                last_res = None
                for i, k in enumerate(keys):
                    if not k: continue
                    try:
                        res = _decrypt_if_key(val, k, crypto, silent=True)
                        # logger.info(f"DEBUG PB Decrypt Try {i}: ValPrefix={val[:10] if isinstance(val, str) else type(val)}... Res={res[:10] if isinstance(res, str) else res}")
                        if res == "[ENCRYPTED]":
                            last_res = res
                            continue
                        return res
                    except Exception as e:
                        # logger.error(f"DEBUG PB Decrypt Exception: {e}")
                        continue
                return last_res if last_res else "[ENCRYPTED]"
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

            results = []
            for r in rows:
                nome = try_decrypt(r['nome'], keys_to_try)
                importo = float(r['importo_assegnato']) if r['importo_assegnato'] else 0.0

                results.append({
                    'id': r['id_salvadanaio'],
                    'nome': nome,
                    'importo': importo,
                    'id_obiettivo': r['id_obiettivo'], # Useful for filtering
                    'incide_su_liquidita': r.get('incide_su_liquidita', False)
                })
            
            return results
    except Exception as e:
        logger.error(f"Errore ottieni_salvadanai_conto: {e}")
        return []

def esegui_giroconto_salvadanaio(
    id_conto: int,
    id_salvadanaio: int,
    direzione: str, # 'verso_salvadanaio' (Conto -> PB) o 'da_salvadanaio' (PB -> Conto)
    importo: float,
    data: str = None,
    descrizione: str = None,
    master_key_b64: Optional[str] = None,
    id_utente: Optional[str] = None,
    id_famiglia: Optional[str] = None,
    parent_is_shared: bool = False # New flag
) -> bool:
    # Sanificazione parametri integer
    id_conto = _valida_id_int(id_conto)
    id_salvadanaio = _valida_id_int(id_salvadanaio)

    if not data: data = datetime.date.today().strftime('%Y-%m-%d')
    if not descrizione: descrizione = "Giroconto Salvadanaio"
    
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    key_to_use = family_key if family_key else master_key

    # Encrypt description
    if parent_is_shared:
        # For Shared Trans, use family key usually, or master key? 
        # Shared Trans usually use Family Key if encrypted. 
        # But 'esegui_giroconto' uses family_key for shared description.
        desc_enc = _encrypt_if_key(descrizione, key_to_use, crypto)
    else:
        desc_enc = _encrypt_if_key(descrizione, master_key, crypto)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get current PB Amount
            cur.execute("SELECT importo_assegnato, nome FROM Salvadanai WHERE id_salvadanaio = %s", (id_salvadanaio,))
            row = cur.fetchone()
            if not row: raise Exception("Salvadanaio non trovato")
            
            current_pb_amount = float(row['importo_assegnato']) if row['importo_assegnato'] else 0.0
            
            # Determine correct table and column for Account Transaction
            if parent_is_shared:
                table_trans = "TransazioniCondivise"
                col_id = "id_conto_condiviso"
                # Shared Trans table also needs id_utente_autore
                extra_cols = ", id_utente_autore"
                extra_vals = ", %s"
                extra_params = (id_utente,)
            else:
                table_trans = "Transazioni"
                col_id = "id_conto"
                extra_cols = ""
                extra_vals = ""
                extra_params = ()

            if direzione == 'verso_salvadanaio':
                # Conto -> PB
                # 1. Create Transaction Out on Account
                query = f"INSERT INTO {table_trans} ({col_id}, data, descrizione, importo{extra_cols}) VALUES (%s, %s, %s, %s{extra_vals})"
                params = (id_conto, data, desc_enc, -abs(importo)) + extra_params
                cur.execute(query, params)
                
                # 2. Increase PB
                new_pb_amount = current_pb_amount + abs(importo)
                
            elif direzione == 'da_salvadanaio':
                # PB -> Conto
                if current_pb_amount < abs(importo):
                     raise Exception("Fondi insufficienti nel salvadanaio")
                
                # 1. Create Transaction In on Account
                query = f"INSERT INTO {table_trans} ({col_id}, data, descrizione, importo{extra_cols}) VALUES (%s, %s, %s, %s{extra_vals})"
                params = (id_conto, data, desc_enc, abs(importo)) + extra_params
                cur.execute(query, params)
                             
                # 2. Decrease PB
                new_pb_amount = current_pb_amount - abs(importo)
            
            else:
                raise Exception(f"Direzione sconosciuta: {direzione}")

            cur.execute("UPDATE Salvadanai SET importo_assegnato = %s WHERE id_salvadanaio = %s", (new_pb_amount, id_salvadanaio))
            
            con.commit()
            return True

    except Exception as e:
        logger.error(f"Errore esegui_giroconto_salvadanaio: {e}")
        return False

def ottieni_salvadanai_obiettivo(id_obiettivo: int, id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        key_to_use = family_key if family_key else master_key
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT s.id_salvadanaio, s.nome, s.importo_assegnato, s.id_conto, s.id_conto_condiviso, s.id_asset,
                       c.nome_conto, a.nome_asset, a.ticker
                FROM Salvadanai s
                LEFT JOIN Conti c ON s.id_conto = c.id_conto
                LEFT JOIN Asset a ON s.id_asset = a.id_asset
                WHERE s.id_obiettivo = %s AND s.id_famiglia = %s
            """, (id_obiettivo, id_famiglia))
            
            rows = cur.fetchall()
            results = []
            for row in rows:
                # Decryption Strategy: Try Family Key first, then Master Key
                # This handles mixed history (PBs created with Family Key vs Master Key).
                
                nome = "[ENCRYPTED]"
                imp_str = "0.0"
                usa_saldo_totale = row.get('usa_saldo_totale', False)
                
                # Helper to try keys
                def try_decrypt(val, keys):
                    last_res = None
                    for k in keys:
                        if not k: continue
                        try:
                            # Pass silent=True to avoid excessive logging during trial
                            res = _decrypt_if_key(val, k, crypto, silent=True) # Assuming _decrypt_if_key passes silent arg (Modified below?)
                            
                            if res == "[ENCRYPTED]":
                                last_res = res
                                continue # Try next key
                            
                            return res
                        except: continue
                    return last_res if last_res else "[ENCRYPTED]"

                keys_to_try = [family_key, master_key] if family_key else [master_key]
                
                try:
                    nome = try_decrypt(row['nome'], keys_to_try)
                    importo_nominale = float(row['importo_assegnato']) if row['importo_assegnato'] else 0.0
                    
                    source_name = "Manuale / Esterno"
                    source_balance = 0.0
                    source_found = False
                    
                    # --- BALANCE CALCULATION START ---
                    
                    # 1. Linked to Account (Personal)
                    if row['id_conto']:
                        try:
                            # Only calculate Account Balance if needed (for usa_saldo_totale)
                            # Standard PBs (Physical) hold their own funds, so we generally trust importo_assegnato.
                            
                            if usa_saldo_totale:
                                # Fetch manual value (Pension) and rectification (Checking) logic
                                cur.execute("SELECT tipo, valore_manuale, rettifica_saldo FROM Conti WHERE id_conto = %s", (row['id_conto'],))
                                c_res = cur.fetchone()
                                
                                if c_res:
                                    if c_res['tipo'] == 'Fondo Pensione' and c_res['valore_manuale'] is not None:
                                         # Pension Fund -> Use encrypted manual value
                                         val_man_enc = c_res['valore_manuale']
                                         val_man_dec = try_decrypt(val_man_enc, keys_to_try)
                                         try: source_balance = float(val_man_dec)
                                         except: source_balance = 0.0
                                    else:
                                         # Standard Account -> Sum Transactions + Rectification
                                         cur.execute("SELECT SUM(importo) as saldo FROM Transazioni WHERE id_conto = %s", (row['id_conto'],))
                                         t_res = cur.fetchone()
                                         trans_sum = float(t_res['saldo']) if t_res and t_res['saldo'] is not None else 0.0
                                         
                                         rettifica = 0.0
                                         if c_res['rettifica_saldo']:
                                             try:
                                                 r_dec = try_decrypt(c_res['rettifica_saldo'], keys_to_try)
                                                 rettifica = float(r_dec)
                                             except: pass
                                         
                                         source_balance = trans_sum + rettifica
                                    source_found = True
                        except Exception as e:
                            # logger.warning(f"Error fetching balance for conto {row['id_conto']}: {e}")
                            pass

                    # 2. Linked to Shared Account
                    elif row['id_conto_condiviso']:
                        try:
                            # Similar logic for shared.. only if usa_saldo_totale needed
                             if usa_saldo_totale:
                                cur.execute("SELECT valore_manuale FROM ContiCondivisi WHERE id_conto_condiviso = %s", (row['id_conto_condiviso'],))
                                cc_res = cur.fetchone()
                                if cc_res and cc_res['valore_manuale'] is not None:
                                    val_man_enc = cc_res['valore_manuale']
                                    val_man_dec = try_decrypt(val_man_enc, keys_to_try) 
                                    try: source_balance = float(val_man_dec)
                                    except: source_balance = 0.0
                                else:
                                     cur.execute("SELECT SUM(importo) as saldo FROM TransazioniCondivise WHERE id_conto_condiviso = %s", (row['id_conto_condiviso'],))
                                     t_res = cur.fetchone()
                                     source_balance = float(t_res['saldo']) if t_res and t_res['saldo'] is not None else 0.0
                                source_found = True
                        except: pass

                    # 3. Linked to Asset (ALWAYS Virtual -> Need Source Balance)
                    elif row['id_asset']:
                         try:
                             cur.execute("SELECT quantita, prezzo_attuale_manuale, costo_iniziale_unitario FROM Asset WHERE id_asset = %s", (row['id_asset'],))
                             a_res = cur.fetchone()
                             if a_res:
                                 qty = float(a_res['quantita'])
                                 price = float(a_res['prezzo_attuale_manuale']) if a_res['prezzo_attuale_manuale'] else float(a_res['costo_iniziale_unitario'])
                                 source_balance = qty * price
                                 source_found = True
                         except: pass

                    # --- BALANCE CALCULATION END ---

                    # Decrypt Source Name (Account) if present
                    if row['nome_conto']:
                        # Try both keys (Legacy Support)
                        source_name = f"Conto: {try_decrypt(row['nome_conto'], keys_to_try)}"
                    
                    # Decrypt Source Name (Asset) if present
                    if row['nome_asset']: 
                        # Asset lookup strategy
                        # Try keys for Asset Name AND Ticker
                        s_asset = try_decrypt(row['nome_asset'], keys_to_try)
                        s_ticker = try_decrypt(row['ticker'], keys_to_try)
                        
                        if s_asset != "[ENCRYPTED]":
                            source_name = f"Asset: {s_asset} ({s_ticker})"
                        else:
                             source_name = f"Asset: [Privato/Encrypted]"
                                     
                    if row['id_conto_condiviso']:
                        # Fetch Shared Account Name
                        try:
                            cur.execute("SELECT nome_conto FROM ContiCondivisi WHERE id_conto_condiviso = %s", (row['id_conto_condiviso'],))
                            cc_row = cur.fetchone()
                            if cc_row:
                                cc_name = try_decrypt(cc_row['nome_conto'], keys_to_try)
                                source_name = f"Conto Condiviso: {cc_name}"
                        except:
                            source_name = "Conto Condiviso" 
                    
                    # Final Importo logic remain same
                    
                    final_importo = importo_nominale
                    
                    # Special Rule for Assets or Dynamic Accounts
                    # Assets are ALWAYS virtual, so we cap.
                    # Accounts are only capped if usa_saldo_totale (dynamic tracking), otherwise we trust the assigned amount (Physical PB).
                    
                    if row['id_asset'] and source_found:
                         # Heuristic: If assigned is 0, assume user wants Full Value (since empty field implies that).
                         # Also checking usa_saldo_totale flag.
                         if usa_saldo_totale or importo_nominale == 0:
                              final_importo = max(0.0, source_balance)
                         else:
                              final_importo = max(0.0, min(importo_nominale, source_balance))
                    
                    elif (row['id_conto'] or row['id_conto_condiviso']) and usa_saldo_totale and source_found:
                         final_importo = max(0.0, source_balance)
                         
                    # Else (Fixed Account PB): use importo_nominale as is.
                        
                    results.append({
                        'id': row['id_salvadanaio'],
                        'nome': nome,
                        'importo': final_importo,
                        'source': source_name,
                        'usa_saldo_totale': usa_saldo_totale, # Useful for UI?
                        'source_balance': source_balance # useful for debug?
                    })
                except Exception as ex:
                    # logger.error(f"Error processing salvadanaio {row['id_salvadanaio']}: {ex}")
                    results.append({
                        'id': row['id_salvadanaio'],
                        'nome': "[ENCRYPTED]",
                        'importo': 0.0,
                        'source': "Errore Decrittazione"
                    })

            return results
    except Exception as e:
        logger.error(f"Errore ottieni_salvadanai: {e}")
        return []

def elimina_salvadanaio(id_salvadanaio: int, id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> bool:
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        key_to_use = family_key if family_key else master_key

        with get_db_connection() as con:
            cur = con.cursor()
            
            # Fetch PB info
            cur.execute("""
                SELECT id_conto, id_conto_condiviso, importo_assegnato, id_asset, usa_saldo_totale
                FROM Salvadanai
                WHERE id_salvadanaio = %s AND id_famiglia = %s
            """, (id_salvadanaio, id_famiglia))
            
            row = cur.fetchone()
            if not row: return False # Not found
            
            # Check if refund needed
            needs_refund = False
            amount_to_refund = 0.0
            
            # Only refund if Physical PB (Linked to Account, not Asset, and NOT dynamic)
            # If dynamic (usa_saldo_totale), it tracks account balance, so no dedicated funds to move back.
            # If Asset, it's virtual.
            
            if (row['id_conto'] or row['id_conto_condiviso']) and not row['usa_saldo_totale'] and not row['id_asset']:
                try:
                    if row['importo_assegnato'] is not None:
                        amount_to_refund = float(row['importo_assegnato'])
                        if amount_to_refund > 0:
                            needs_refund = True
                except Exception as e:
                    logger.error(f"Error reading refund amount: {e}")
                    return False # ABORT
            
            if needs_refund:
                # Refund to Account
                parent_is_shared = bool(row['id_conto_condiviso'])
                id_conto_target = row['id_conto'] if row['id_conto'] else row['id_conto_condiviso']
                
                success_refund = esegui_giroconto_salvadanaio(
                    id_conto=id_conto_target,
                    id_salvadanaio=id_salvadanaio,
                    direzione='da_salvadanaio',
                    importo=amount_to_refund,
                    descrizione=f"Chiusura Salvadanaio",
                    master_key_b64=master_key_b64,
                    id_utente=id_utente,
                    id_famiglia=id_famiglia,
                    parent_is_shared=parent_is_shared
                )
                
                if not success_refund:
                    logger.error("Refund failed during deletion. Aborting deletion to save funds.")
                    return False # ABORT
            
            # Proceed to Delete ONLY if Refund success or not needed
            cur.execute("DELETE FROM Salvadanai WHERE id_salvadanaio = %s AND id_famiglia = %s", (id_salvadanaio, id_famiglia))
            con.commit()
            return True

    except Exception as e:
        logger.error(f"Errore eliminazione salvadanaio: {e}")
        return False

def admin_rettifica_salvadanaio(id_salvadanaio: int, nuovo_importo: float, master_key_b64: Optional[str], id_utente: str, is_shared: bool = False) -> bool:
    """
    Rettifica manuale (ADMIN) dell'importo di un salvadanaio.
    Sovrascrive il valore.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        # Determine Key
        family_key = None
        id_famiglia = ottieni_prima_famiglia_utente(id_utente)
        if id_famiglia and master_key:
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        if is_shared:
            if not family_key:
                logger.error("Rettifica salvadanaio condiviso impossibile: chiave famiglia assente.")
                return False
            key_to_use = family_key
        else:
            key_to_use = family_key if family_key else master_key
            
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Salvadanai SET importo_assegnato = %s WHERE id_salvadanaio = %s", (nuovo_importo, id_salvadanaio))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore rettifica salvadanaio: {e}")
        return False

def collega_salvadanaio_obiettivo(id_salvadanaio: int, id_obiettivo: int, id_famiglia: str) -> bool:
    """
    Collega un salvadanaio esistente a un obiettivo.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Salvadanai SET id_obiettivo = %s WHERE id_salvadanaio = %s AND id_famiglia = %s", (id_obiettivo, id_salvadanaio, id_famiglia))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore collegamento salvadanaio-obiettivo: {e}")
        return False

