"""
Funzioni giroconti: trasferimenti tra conti
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
from utils.logger import setup_logger
from utils.crypto_manager import CryptoManager
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
import os

logger = setup_logger(__name__)

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code, _get_system_keys,
    HASH_SALT, SYSTEM_FERNET_KEY, SERVER_SECRET_KEY,
    crypto as _crypto_instance
)

# --- Funzioni Giroconti ---
def esegui_giroconto(id_conto_origine, id_conto_destinazione, importo, data, descrizione=None, master_key_b64=None, tipo_origine="personale", tipo_destinazione="personale", id_utente_autore=None, id_famiglia=None):
    # Sanificazione parametri integer
    id_conto_origine = _valida_id_int(id_conto_origine)
    id_conto_destinazione = _valida_id_int(id_conto_destinazione)
    
    if not descrizione:
        descrizione = "Giroconto"
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Per conti condivisi, usa la family key
    family_key = None
    if (tipo_origine == "condiviso" or tipo_destinazione == "condiviso") and id_utente_autore and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente_autore, master_key, crypto)
    
    # Cripta la descrizione con la chiave appropriata
    # Se coinvolge conti condivisi, usa family_key per quelli
    encrypted_descrizione_personale = _encrypt_if_key(descrizione, master_key, crypto)
    encrypted_descrizione_condivisa = _encrypt_if_key(descrizione, family_key if family_key else master_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Prelievo dal conto origine
            if tipo_origine == "personale":
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (%s, %s, %s, %s)",
                    (id_conto_origine, data, encrypted_descrizione_personale, -abs(importo)))
            else:  # condiviso
                cur.execute(
                    "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s)",
                    (id_utente_autore, id_conto_origine, data, encrypted_descrizione_condivisa, -abs(importo)))
            
            # 2. Versamento sul conto destinazione
            if tipo_destinazione == "personale":
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (%s, %s, %s, %s)",
                    (id_conto_destinazione, data, encrypted_descrizione_personale, abs(importo)))
            else:  # condiviso
                cur.execute(
                    "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s)",
                    (id_utente_autore, id_conto_destinazione, data, encrypted_descrizione_condivisa, abs(importo)))
            
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore esecuzione giroconto: {e}")
        return False

