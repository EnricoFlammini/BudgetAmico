"""
Funzioni spese fisse: CRUD, automazione
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
    crypto as _crypto_instance,
    _get_family_key_for_user
)

# Importazioni da altri moduli
from db.gestione_famiglie import ottieni_prima_famiglia_utente, _trova_admin_famiglia


# --- NUOVE FUNZIONI PER SPESE FISSE ---
def aggiungi_spesa_fissa(id_famiglia, nome, importo, id_conto_personale=None, id_conto_condiviso=None, id_sottocategoria=None, giorno_addebito=1, attiva=True, addebito_automatico=False, master_key_b64=None, id_utente=None, id_carta=None, is_giroconto=False, id_conto_personale_beneficiario=None, id_conto_condiviso_beneficiario=None):
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        # Encrypt Name
        key_to_use = family_key if family_key else master_key
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto) if key_to_use else nome

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO SpeseFisse (
                    id_famiglia, nome, importo, id_conto_personale_addebito, id_conto_condiviso_addebito,
                    id_categoria, id_sottocategoria, giorno_addebito, attiva, addebito_automatico, id_carta,
                    is_giroconto, id_conto_personale_beneficiario, id_conto_condiviso_beneficiario
                )
                VALUES (%s, %s, %s, %s, %s, (SELECT id_categoria FROM Sottocategorie WHERE id_sottocategoria = %s), %s, %s, %s, %s, %s, %s, %s, %s)
            """, (id_famiglia, nome_enc, importo, id_conto_personale, id_conto_condiviso, id_sottocategoria, id_sottocategoria, giorno_addebito, attiva, addebito_automatico, id_carta, is_giroconto, id_conto_personale_beneficiario, id_conto_condiviso_beneficiario))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'aggiunta della spesa fissa: {e}")
        return None


def modifica_spesa_fissa(id_spesa_fissa, nome, importo, id_conto_personale=None, id_conto_condiviso=None, id_sottocategoria=None, giorno_addebito=1, attiva=True, addebito_automatico=False, master_key_b64=None, id_utente=None, id_carta=None, is_giroconto=False, id_conto_personale_beneficiario=None, id_conto_condiviso_beneficiario=None):
    try:
        # Recupera famiglia
        id_famiglia = None
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia FROM SpeseFisse WHERE id_spesa_fissa = %s", (id_spesa_fissa,))
            res = cur.fetchone()
            if res: id_famiglia = res['id_famiglia']

        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente and id_famiglia:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        key_to_use = family_key if family_key else master_key
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto) if key_to_use else nome

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE SpeseFisse
                SET nome = %s, importo = %s, id_conto_personale_addebito = %s, id_conto_condiviso_addebito = %s,
                    id_sottocategoria = %s, id_categoria = (SELECT id_categoria FROM Sottocategorie WHERE id_sottocategoria = %s),
                    giorno_addebito = %s, attiva = %s, addebito_automatico = %s, id_carta = %s,
                    is_giroconto = %s, id_conto_personale_beneficiario = %s, id_conto_condiviso_beneficiario = %s
                WHERE id_spesa_fissa = %s
            """, (nome_enc, importo, id_conto_personale, id_conto_condiviso, id_sottocategoria, id_sottocategoria, giorno_addebito, attiva, addebito_automatico, id_carta, is_giroconto, id_conto_personale_beneficiario, id_conto_condiviso_beneficiario, id_spesa_fissa))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante la modifica della spesa fissa: {e}")
        return False


def modifica_stato_spesa_fissa(id_spesa_fissa, nuovo_stato):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE SpeseFisse SET attiva = %s WHERE id_spesa_fissa = %s",
                        (1 if nuovo_stato else 0, id_spesa_fissa))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante la modifica dello stato della spesa fissa: {e}")
        return False


def elimina_spesa_fissa(id_spesa_fissa):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM SpeseFisse WHERE id_spesa_fissa = %s", (id_spesa_fissa,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante l'eliminazione della spesa fissa: {e}")
        return False


def ottieni_spese_fisse_famiglia(id_famiglia, master_key_b64=None, id_utente=None, forced_family_key_b64=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                SELECT 
                    SF.id_spesa_fissa,
                    SF.id_famiglia,
                    SF.nome,
                    SF.importo,
                    SF.id_conto_personale_addebito,
                    SF.id_conto_condiviso_addebito,
                    SF.id_categoria,
                    SF.id_sottocategoria,
                    SF.giorno_addebito,
                    SF.attiva,
                    SF.addebito_automatico,
                    SF.id_carta,
                    COALESCE(CP.nome_conto, CC.nome_conto) as nome_conto,
                    CARTE.nome_carta,
                    CARTE.id_conto_contabile as id_conto_carta_pers,
                    CARTE.id_conto_contabile_condiviso as id_conto_carta_cond,
                    CARTE.id_conto_riferimento as id_carta_rif_pers,
                    CARTE.id_conto_riferimento_condiviso as id_carta_rif_cond,
                    U_CP.username_enc as username_enc_conto,
                    U_CARTE.username_enc as username_enc_carta
                FROM SpeseFisse SF
                LEFT JOIN Conti CP ON SF.id_conto_personale_addebito = CP.id_conto
                LEFT JOIN Utenti U_CP ON CP.id_utente = U_CP.id_utente
                LEFT JOIN ContiCondivisi CC ON SF.id_conto_condiviso_addebito = CC.id_conto_condiviso
                LEFT JOIN Carte CARTE ON SF.id_carta = CARTE.id_carta
                LEFT JOIN Utenti U_CARTE ON CARTE.id_utente = U_CARTE.id_utente
                LEFT JOIN Conti CP_BEN ON SF.id_conto_personale_beneficiario = CP_BEN.id_conto
                LEFT JOIN ContiCondivisi CC_BEN ON SF.id_conto_condiviso_beneficiario = CC_BEN.id_conto_condiviso
                WHERE SF.id_famiglia = %s
                ORDER BY SF.nome
            """, (id_famiglia,))
            spese = [dict(row) for row in cur.fetchall()]

            # Decrypt nome if keys available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            
            if forced_family_key_b64:
                 try:
                     family_key = base64.b64decode(forced_family_key_b64)
                 except: pass
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
                for spesa in spese:
                    spesa['nome'] = _decrypt_if_key(spesa['nome'], family_key, crypto, silent=True)
                    
                    # Decripta nome beneficiario se presente
                    if spesa.get('id_conto_personale_beneficiario'):
                         # Assuming personal beneficiary is mostly own account or decrypted easily if needed.
                         pass 
                    
                    # Decripta anche il nome del conto
                    if spesa.get('nome_conto'):
                         # Prova prima con family_key (per conti condivisi)
                        if spesa.get('id_conto_condiviso_addebito'):
                            spesa['nome_conto'] = _decrypt_if_key(spesa['nome_conto'], family_key, crypto, silent=True)
                        else:
                            # Conto personale: prova con master_key prima (se l'utente è il proprietario)
                             spesa['nome_conto'] = _decrypt_if_key(spesa['nome_conto'], master_key, crypto, silent=True) # Usa master key utente corrente
                             
                             # Se fallisce decriptazione e abbiamo username proprietario
                             if CryptoManager.is_encrypted(spesa['nome_conto']):
                                 user_conto_enc = spesa.get('username_enc_conto')
                                 if user_conto_enc:
                                     user_conto = decrypt_system_data(user_conto_enc)
                                     if user_conto:
                                        spesa['nome_conto'] = f"Conto di {user_conto}"

                    if spesa.get('nome_carta'):
                        spesa['nome_carta'] = _decrypt_if_key(spesa['nome_carta'], family_key, crypto, silent=True)
                        if CryptoManager.is_encrypted(spesa['nome_carta']) and family_key != master_key:
                            test_dec = _decrypt_if_key(spesa['nome_carta'], master_key, crypto, silent=True)
                            if test_dec and not CryptoManager.is_encrypted(test_dec): 
                                spesa['nome_carta'] = test_dec
                            elif spesa.get('username_enc_carta'):
                                user_carta = decrypt_system_data(spesa.get('username_enc_carta'))
                                if user_carta:
                                    spesa['nome_carta'] = f"Carta di {user_carta}"

                    # Sovrascrivi nome_conto se c'è una carta
                    if spesa.get('id_carta') and spesa.get('nome_carta'):
                         spesa['nome_conto'] = f"{spesa['nome_carta']} (Carta)"
            else:
                 # Fallback without family key (should theoretically not happen for family view if logged in properly)
                 # Try decrypting with master_key just in case (e.g. personal items)
                 if master_key:
                     for spesa in spese:
                         # Decrypt card if present
                         if spesa.get('id_carta') and spesa.get('nome_carta'):
                             dec = _decrypt_if_key(spesa['nome_carta'], master_key, crypto, silent=True)
                             if dec and not CryptoManager.is_encrypted(dec): 
                                 spesa['nome_carta'] = dec
                             elif spesa.get('username_enc_carta'):
                                 user_carta = decrypt_system_data(spesa.get('username_enc_carta'))
                                 if user_carta:
                                     spesa['nome_carta'] = f"Carta di {user_carta}"

                             spesa['nome_conto'] = f"{spesa['nome_carta']} (Carta)"
                             
                         elif spesa.get('nome_conto') and not spesa.get('id_conto_condiviso_addebito'):
                             # Try decrypt personal account
                             dec = _decrypt_if_key(spesa['nome_conto'], master_key, crypto, silent=True)
                             if dec and not CryptoManager.is_encrypted(dec):
                                 spesa['nome_conto'] = dec
                             elif spesa.get('username_enc_conto'):
                                 user_conto = decrypt_system_data(spesa.get('username_enc_conto'))
                                 if user_conto:
                                     spesa['nome_conto'] = f"Conto di {user_conto}"

            return spese
    except Exception as e:
        print(f"[ERRORE] Errore durante il recupero delle spese fisse: {e}")
        return []

