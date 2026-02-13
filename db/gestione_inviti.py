"""
Funzioni inviti: creazione, verifica token
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
from utils.logger import setup_logger
from utils.crypto_manager import CryptoManager
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
import os

logger = setup_logger(__name__)
import secrets
import string

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code, _get_system_keys,
    HASH_SALT, SYSTEM_FERNET_KEY, SERVER_SECRET_KEY,
    crypto as _crypto_instance
)


# --- Funzioni Gestione Inviti ---
def crea_invito(id_famiglia, email, ruolo):
    token = generate_token()
    if ruolo not in ['admin', 'livello1', 'livello2', 'livello3']:
        return None
        
    # Encrypt email using token as key
    # Derive a 32-byte key from the token
    key = hashlib.sha256(token.encode()).digest()
    key_b64 = base64.b64encode(key) # CryptoManager expects bytes, but let's see _encrypt_if_key
    
    # _encrypt_if_key expects key as bytes. 
    # But wait, CryptoManager.encrypt_data expects key as bytes.
    # Let's use CryptoManager directly to be safe and avoid dependency on master_key logic
    crypto = CryptoManager()
    encrypted_email = crypto.encrypt_data(email.lower(), key)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("INSERT INTO Inviti (id_famiglia, email_invitato, token, ruolo_assegnato) VALUES (%s, %s, %s, %s)",
                        (id_famiglia, encrypted_email, token, ruolo))
            return token
    except Exception as e:
        print(f"[ERRORE] Errore durante la creazione dell'invito: {e}")
        return None


def ottieni_invito_per_token(token):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")
            cur.execute("SELECT id_famiglia, email_invitato, ruolo_assegnato FROM Inviti WHERE token = %s", (token,))
            invito = cur.fetchone()
            if invito:
                # Decrypt email
                encrypted_email = invito['email_invitato']
                key = hashlib.sha256(token.encode()).digest()
                crypto = CryptoManager()
                try:
                    decrypted_email = crypto.decrypt_data(encrypted_email, key)
                except Exception:
                    decrypted_email = encrypted_email # Fallback if not encrypted or error
                
                result = dict(invito)
                result['email_invitato'] = decrypted_email
                
                cur.execute("DELETE FROM Inviti WHERE token = %s", (token,))
                con.commit()
                return result
            else:
                con.rollback()
                return None
    except Exception as e:
        print(f"[ERRORE] Errore durante l'ottenimento/eliminazione dell'invito: {e}")
        if con: con.rollback()
        return None

