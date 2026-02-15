"""
Funzioni helper per crittografia, system keys, blind index
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
import hashlib
import datetime
import os
import shutil
import sys
from typing import List, Dict, Any, Optional, Tuple, Union
import threading

# Cache globale per le configurazioni di sistema (thread-safe)
_CONFIG_CACHE = {}
_CONFIG_CACHE_LOCK = threading.Lock()

def invalidate_config_cache():
    """Svuota la cache delle configurazioni."""
    with _CONFIG_CACHE_LOCK:
        _CONFIG_CACHE.clear()
        logger.info("Cache configurazioni svuotata.")
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse as parse_date
import mimetypes
import secrets
import string
import base64
from utils.crypto_manager import CryptoManager
from utils.cache_manager import cache_manager
from utils.logger import setup_logger
import json

# --- BLOCCO DI CODICE PER CORREGGERE IL PERCORSO ---
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
# --- FINE BLOCCO DI CODICE ---

from db.crea_database import setup_database

logger = setup_logger("GestioneDB")

# Load Server Key
SERVER_SECRET_KEY = os.getenv("SERVER_SECRET_KEY")
if not SERVER_SECRET_KEY:
    logger.warning("SERVER_SECRET_KEY not found in .env. Password recovery via email will not work for new encrypted data.")

# --- Helpers ---
def _valida_id_int(val):
    """
    Converte il valore in intero se possibile, altrimenti restituisce None.
    Utile per evitare 'invalid input syntax for type integer: ""' in SQL.
    """
    if val is None: return None
    if isinstance(val, int): return val
    if isinstance(val, str):
        v_stripped = val.strip()
        if v_stripped == "" or not v_stripped.isdigit():
            return None
        return int(v_stripped)
    return None

# --- System Key Helpers ---
_SYSTEM_FERNET_KEY = None
_HASH_SALT = None

def _ensure_system_keys_loaded():
    global _SYSTEM_FERNET_KEY, _HASH_SALT
    # If already loaded, return
    if _SYSTEM_FERNET_KEY and _HASH_SALT:
        return

    secret = os.getenv("SERVER_SECRET_KEY")
    if not secret:
        # logger.warning("SERVER_SECRET_KEY non trovata durante inizializzazione chiavi sistema.")
        return

    import hashlib
    # 1. Hashing Salt
    _HASH_SALT = secret
    # 2. Encryption Key (Fernet)
    srv_key_bytes = hashlib.sha256(secret.encode()).digest()
    _SYSTEM_FERNET_KEY = base64.urlsafe_b64encode(srv_key_bytes)

def get_system_fernet_key():
    _ensure_system_keys_loaded()
    return _SYSTEM_FERNET_KEY

def get_hash_salt():
    _ensure_system_keys_loaded()
    return _HASH_SALT

def _get_system_keys():
    """Ritorna (hash_salt, system_fernet_key) per compatibilità legacy."""
    _ensure_system_keys_loaded()
    return _HASH_SALT, _SYSTEM_FERNET_KEY

def hash_password(password, algo='pbkdf2'):
    """
    Genera l'hash della password.
    Algo supportati: 'sha256' (legacy), 'pbkdf2' (secure).
    Format PBKDF2: pbkdf2:sha256:iterations:salt_b64:hash_b64
    """
    if algo == 'sha256':
        return hashlib.sha256(password.encode()).hexdigest()
    
    # Defaults to PBKDF2
    salt = os.urandom(16)
    iterations = 600000
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
    
    salt_b64 = base64.urlsafe_b64encode(salt).decode()
    hash_b64 = base64.urlsafe_b64encode(hash_bytes).decode()
    
    return f"pbkdf2:sha256:{iterations}:{salt_b64}:{hash_b64}"

def verify_password_hash(password, stored_hash, algo='sha256'):
    """
    Verifica una password contro un hash memorizzato.
    """
    if not stored_hash: return False
    
    if algo == 'sha256':
        return stored_hash == hashlib.sha256(password.encode()).hexdigest()
    
    if algo == 'pbkdf2':
        try:
            # Parse: pbkdf2:sha256:iter:salt:hash
            parts = stored_hash.split(':')
            if len(parts) != 5:
                # Fallback or error
                return False
            
            _, _, iterations_str, salt_b64, hash_b64 = parts
            iterations = int(iterations_str)
            salt = base64.urlsafe_b64decode(salt_b64)
            stored_bytes = base64.urlsafe_b64decode(hash_b64)
            
            computed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
            
            # Constant time check
            import secrets
            return secrets.compare_digest(stored_bytes, computed)
        except Exception:
            return False
            
    return False

def compute_blind_index(value):
    salt = get_hash_salt()
    if not value or not salt: return None
    import hashlib
    return hashlib.sha256((value.lower().strip() + salt).encode()).hexdigest()

def valida_iban_semplice(iban):
    if not iban:
        return True
    iban_pulito = iban.strip().upper()
    return iban_pulito.startswith("IT") and len(iban_pulito) == 27 and iban_pulito[2:].isalnum()

def encrypt_system_data(value):
    key = get_system_fernet_key()
    if not value or not key: return None
    # Usiamo CryptoManager per supportare v2 (AES-GCM)
    from utils.crypto_manager import CryptoManager
    cm = CryptoManager()
    return cm.encrypt_data(value, key)

def decrypt_system_data(value_enc):
    if not value_enc: return None
    
    key = get_system_fernet_key()
    if not key:
        logger.error("[DEBUG] decrypt_system_data: SERVER_SECRET_KEY is missing (Lazy Load failed)!")
        return None
        
    from utils.crypto_manager import CryptoManager
    cm = CryptoManager()
    # decrypt_data gestisce automaticamente prefisso v2 o fallback Fernet
    dec = cm.decrypt_data(value_enc, key, silent=True)
    
    if dec == "[ENCRYPTED]":
        logger.error(f"[DEBUG] decrypt_system_data failed. Value prefix: {value_enc[:10]}...")
        return None
        
    return dec

def generate_unique_code(prefix="", length=8):
    """Genera un codice randomico hex."""
    import secrets
    code = secrets.token_hex(length // 2).upper()
    return f"{prefix}{code}"

def get_server_family_key(id_famiglia):
    """
    Recupera la Family Key decriptata (usando SERVER_SECRET_KEY) per l'automazione background.
    """
    # Force check env again just in case
    if not get_system_fernet_key():
         logger.error("[DEBUG] get_server_family_key: SERVER_SECRET_KEY missing.")
         return None
         
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT server_encrypted_key FROM Famiglie WHERE id_famiglia = %s", (id_famiglia,))
            row = cur.fetchone()
            if row and row['server_encrypted_key']:
                 # Decrypt: Server Encrypted Key -> Family Key B64
                 fk_b64_enc = row['server_encrypted_key']
                 fk_b64 = decrypt_system_data(fk_b64_enc)
                 if not fk_b64:
                     logger.error(f"[DEBUG] get_server_family_key: Decryption returned None for family {id_famiglia}")
                 return fk_b64
    except Exception as e:
        logger.error(f"Error retrieving server family key: {e}")
    return None

def enable_server_automation(id_famiglia, master_key_b64, id_utente, forced_family_key=None):
    """
    Abilita l'automazione server salvando la Family Key criptata con la chiave di sistema.
    Args:
        forced_family_key: (Optional) bytes of family key if already known (avoids redundant decryption).
    """
    if not SERVER_SECRET_KEY:
        logger.error("SERVER_SECRET_KEY missing. Cannot enable automation.")
        return False
        
    try:
        fk_b64 = None
        
        if forced_family_key:
             # Use provided key directly
             fk_b64 = base64.b64encode(forced_family_key).decode('utf-8') if isinstance(forced_family_key, bytes) else forced_family_key
        else:
            # 1. Get Family Key using User's Master Key
            crypto = CryptoManager()
            master_key = master_key_b64.encode()
            
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                row = cur.fetchone()
                if not row or not row['chiave_famiglia_criptata']:
                    logger.error("Family Key not found for user.")
                    return False
                    
                fk_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
        
        if not fk_b64:
             logger.error("Failed to obtain family key for automation enablement.")
             return False
            
        # 2. Encrypt Family Key with System Key
        server_enc_key = encrypt_system_data(fk_b64)
        
        # 3. Save to Famiglie table
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Famiglie SET server_encrypted_key = %s WHERE id_famiglia = %s", (server_enc_key, id_famiglia))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Error enabling server automation: {e}")
        return False

def disable_server_automation(id_famiglia):
    """Disabilita l'automazione server rimuovendo la chiave."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Famiglie SET server_encrypted_key = NULL WHERE id_famiglia = %s", (id_famiglia,))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Error disabling server automation: {e}")
        return False

def is_server_automation_enabled(id_famiglia):
    """
    Verifica se l'automazione server è abilitata per una famiglia.
    A differenza di get_server_family_key, questa funzione NON richiede SERVER_SECRET_KEY locale.
    Usa questa funzione per decidere se saltare l'elaborazione locale delle spese fisse.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT server_encrypted_key FROM Famiglie WHERE id_famiglia = %s", (id_famiglia,))
            row = cur.fetchone()
            # Se esiste una chiave criptata, l'automazione server è abilitata
            return row is not None and row['server_encrypted_key'] is not None and row['server_encrypted_key'] != ''
    except Exception as e:
        logger.error(f"Error checking server automation status: {e}")
        return False




def ottieni_ruolo_utente(id_famiglia: str, id_utente: str) -> Optional[str]:
    """
    Recupera il ruolo dell'utente nella famiglia.
    Restituisce: 'admin', 'livello1', 'livello2', 'livello3' o None.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT ruolo FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND id_utente = %s", (id_famiglia, id_utente))
            row = cur.fetchone()
            return row['ruolo'] if row else None
    except Exception as e:
        logger.error(f"ottieni_ruolo_utente: {e}")
        return None


def _get_crypto_and_key(master_key_b64=None):
    """
    Returns CryptoManager instance and master_key.
    If master_key_b64 is None, returns (crypto, None) for legacy support.
    """
    crypto = CryptoManager()
    if master_key_b64:
        try:
            # master_key_b64 is the string representation of the base64 encoded key
            # We just need to convert it to bytes
            master_key = master_key_b64.encode()
            return crypto, master_key
        except Exception as e:
            logger.error(f"Errore decodifica master_key: {e}")
            return crypto, None
    return crypto, None

def _encrypt_if_key(data, master_key, crypto=None):
    """Encrypts data if master_key is available, otherwise returns data as-is."""
    if not master_key or not data:
        return data
    if not crypto:
        crypto = CryptoManager()
    return crypto.encrypt_data(data, master_key)

def _decrypt_if_key(encrypted_data, master_key, crypto=None, silent=False):
    if not master_key or not encrypted_data:
        return encrypted_data
    if not crypto:
        crypto = CryptoManager()
    
    # print(f"[DEBUG] _decrypt_if_key called. Key len: {len(master_key)}, Data len: {len(encrypted_data)}")
    
    # Handle non-string inputs (e.g. numbers before migration)
    if not isinstance(encrypted_data, str):
        return encrypted_data

    # Check if data looks like an encrypted token (v2 GCM or legacy Fernet)
    if not CryptoManager.is_encrypted(encrypted_data):
        return encrypted_data

    decrypted = crypto.decrypt_data(encrypted_data, master_key, silent=silent)
    
    # Fallback for unencrypted numbers (during migration)
    if decrypted == "[ENCRYPTED]":
        try:
            # Check if it's a valid number
            float(encrypted_data)
            return encrypted_data
        except ValueError:
            pass
            
    return decrypted


# Singleton CryptoManager instance
crypto = CryptoManager()


# --- Cross-Module Shared Functions ---
# Queste funzioni sono usate da molti moduli e sono centralizzate qui
# per evitare import circolari.

# Cache per le chiavi famiglia per evitare continue query al DB
_family_key_cache = {}
_FAMILY_KEY_CACHE_LOCK = threading.Lock()


def _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto_instance=None):
    """
    Recupera e decripta la family key per un utente specifico.
    Usa cache in-memory per evitare query ripetute.
    """
    id_famiglia = _valida_id_int(id_famiglia)
    id_utente = _valida_id_int(id_utente)
    if not id_famiglia or not id_utente: return None

    # Check cache first
    cache_key = (id_famiglia, id_utente)
    with _FAMILY_KEY_CACHE_LOCK:
        if cache_key in _family_key_cache:
            return _family_key_cache[cache_key]

    if not crypto_instance:
        crypto_instance = CryptoManager()

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
            row = cur.fetchone()
            if row and row['chiave_famiglia_criptata']:
                fk_b64 = crypto_instance.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                family_key = base64.b64decode(fk_b64)
                
                # Update cache
                with _FAMILY_KEY_CACHE_LOCK:
                    _family_key_cache[cache_key] = family_key
                return family_key
            else:
                logger.warning(f"_get_family_key_for_user: No chiave_famiglia_criptata for user {id_utente} in famiglia {id_famiglia}")
    except Exception as e:
        logger.error(f"_get_family_key_for_user failed for user {id_utente}, famiglia {id_famiglia}: {e}")
    return None


def _get_key_for_transaction(id_conto, master_key, crypto_instance=None):
    """
    Determina la chiave corretta per criptare una transazione.
    Se il conto appartiene a un membro di una famiglia, usa la Family Key.
    Altrimenti usa la Master Key.
    """
    if not master_key or not id_conto:
        return master_key
    
    if not crypto_instance:
        crypto_instance = CryptoManager()
        
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT AF.chiave_famiglia_criptata 
                FROM Conti C
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE C.id_conto = %s
            """, (id_conto,))
            row = cur.fetchone()
            
            if row and row['chiave_famiglia_criptata']:
                fk_b64 = crypto_instance.decrypt_data(row['chiave_famiglia_criptata'], master_key, silent=True)
                if fk_b64 and fk_b64 != "[ENCRYPTED]":
                    return base64.b64decode(fk_b64)
    except Exception:
        pass
        
    return master_key


def _get_famiglia_and_utente_from_conto(id_conto):
    """Recupera id_famiglia e id_utente dal conto."""
    try:
        with get_db_connection() as con:
             cur = con.cursor()
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
        logger.error(f"_get_famiglia_and_utente_from_conto: {e}")
        return None, None


def _trova_admin_famiglia(id_famiglia):
    """Helper per trovare l'ID di un utente admin nella famiglia."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND ruolo = 'admin' LIMIT 1", (id_famiglia,))
            res = cur.fetchone()
            return res['id_utente'] if res else None
    except Exception as e:
        logger.error(f"_trova_admin_famiglia: {e}")
        return None
