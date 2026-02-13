"""
Funzioni configurazione: feature flags, SMTP, ordinamento
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
from utils.logger import setup_logger
from utils.crypto_manager import CryptoManager
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
import os

from utils.cache_manager import cache_manager
import json

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code,
    SERVER_SECRET_KEY,
    crypto as _crypto_instance
)

# --- Funzioni Configurazioni ---
def get_configurazione(chiave: str, id_famiglia: Optional[str] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> Optional[str]:
    """
    Recupera il valore di una configurazione usando la cache in-memory.
    """
    try:
        def fetch_from_db():
            with get_db_connection() as con:
                cur = con.cursor()
                if id_famiglia is None:
                    cur.execute("SELECT valore FROM Configurazioni WHERE chiave = %s AND id_famiglia IS NULL", (chiave,))
                else:
                    cur.execute("SELECT valore FROM Configurazioni WHERE chiave = %s AND id_famiglia = %s", (chiave, id_famiglia))
                
                res = cur.fetchone()
                if not res:
                    return None
                
                valore = res['valore']
                
                sensitive_keys = ['smtp_server', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from_email', 'smtp_sender']
                
                if chiave in sensitive_keys:
                    try:
                        decrypted = decrypt_system_data(valore)
                        if decrypted:
                            valore = decrypted
                    except Exception as e:
                        logger.warning(f"Failed to system-decrypt {chiave}: {e}")
                return valore

        # Usa get_or_compute per cache in-memory (TTL 10 minuti)
        cache_key = f"db_config:{chiave}"
        return cache_manager.get_or_compute(
            key=cache_key,
            compute_fn=fetch_from_db,
            id_famiglia=id_famiglia,
            ttl_seconds=600
        )
    except Exception as e:
        logger.error(f"Errore recupero configurazione {chiave}: {e}")
        return None

def set_configurazione(chiave: str, valore: str, id_famiglia: Optional[str] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> bool:
    """
    Imposta o aggiorna una configurazione e invalida la cache.
    """
    try:
        # Encrypt sensitive config values
        encrypted_valore = valore
        sensitive_keys = ['smtp_server', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from_email', 'smtp_sender']
        
        if chiave in sensitive_keys and SERVER_SECRET_KEY:
            try:
                encrypted_valore = encrypt_system_data(valore)
            except Exception as e:
                logger.warning(f"Failed to system-encrypt {chiave}: {e}")
        
        with get_db_connection() as con:
            cur = con.cursor()
            if id_famiglia is None:
                cur.execute("""
                    INSERT INTO Configurazioni (chiave, valore, id_famiglia) 
                    VALUES (%s, %s, NULL)
                    ON CONFLICT (chiave) WHERE id_famiglia IS NULL
                    DO UPDATE SET valore = EXCLUDED.valore
                """, (chiave, encrypted_valore))
            else:
                cur.execute("""
                    INSERT INTO Configurazioni (chiave, valore, id_famiglia) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (chiave, id_famiglia) 
                    DO UPDATE SET valore = EXCLUDED.valore
                """, (chiave, encrypted_valore, id_famiglia))
            con.commit()
            
            # Invalida cache
            cache_manager.invalidate(f"db_config:{chiave}", id_famiglia)
            return True
    except Exception as e:
        logger.error(f"Errore salvataggio configurazione {chiave}: {e}")
        return False
    except Exception as e:
        logger.error(f"Errore salvataggio configurazione {chiave}: {e}")
        return False

# --- Gestione Ordinamento FOP ---
def ottieni_ordinamento_conti_carte(id_famiglia: str) -> Optional[dict]:
    """Recupera l'ordinamento personalizzato per conti e carte."""
    import json
    val = get_configurazione("ordinamento_fop", id_famiglia=id_famiglia)
    if not val:
        return None
    try:
        return json.loads(val)
    except:
        return None

def salva_ordinamento_conti_carte(id_famiglia: str, ordinamento_dict: dict) -> bool:
    """Salva l'ordinamento personalizzato per conti e carte."""
    import json
    val = json.dumps(ordinamento_dict)
    return set_configurazione("ordinamento_fop", val, id_famiglia=id_famiglia)


def save_system_config(key: str, value: str, id_utente: Optional[str] = None) -> bool:
    """
    Salva una configurazione di sistema (globale).
    Alias per set_configurazione con id_famiglia=None.
    """
    return set_configurazione(key, value, id_famiglia=None, id_utente=id_utente)

def get_smtp_config(id_famiglia: Optional[str] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Recupera la configurazione SMTP completa. Tutti i valori vengono decriptati automaticamente.
    
    Returns:
        Un dizionario contenente 'server', 'port', 'user', 'password', 'provider'.
    """
    logger.debug(f"get_smtp_config called with id_famiglia={id_famiglia}, id_utente={id_utente}, master_key_present={bool(master_key_b64)}")
    return {
        'server': get_configurazione('smtp_server', id_famiglia, master_key_b64, id_utente),
        'port': get_configurazione('smtp_port', id_famiglia, master_key_b64, id_utente),
        'user': get_configurazione('smtp_user', id_famiglia, master_key_b64, id_utente),
        'password': get_configurazione('smtp_password', id_famiglia, master_key_b64, id_utente),
        'sender': get_configurazione('smtp_sender', id_famiglia, master_key_b64, id_utente),
        'provider': get_configurazione('smtp_provider', id_famiglia)  # provider is not sensitive
    }

def save_smtp_config(settings: Dict[str, Any], id_famiglia: Optional[str] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> bool:
    """
    Salva la configurazione SMTP. Tutti i valori sensibili vengono criptati automaticamente.
    
    Args:
        settings: Dizionario con le impostazioni SMTP.
        id_famiglia, master_key_b64, id_utente: Parametri per la crittografia.
    """
    try:
        set_configurazione('smtp_server', settings.get('server'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_port', settings.get('port'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_user', settings.get('user'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_password', settings.get('password'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_sender', settings.get('sender'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_provider', settings.get('provider'), id_famiglia)  # provider is not sensitive
        return True
    except Exception as e:
        logger.error(f"Errore salvataggio SMTP config: {e}")
        return False


# --- Funzioni Gestione Budget Famiglia ---

def get_impostazioni_budget_famiglia(id_famiglia: str, anno: int = None, mese: int = None) -> Dict[str, Union[float, str]]:
    """
    Recupera le impostazioni del budget famiglia.
    Se anno e mese sono forniti, recupera dallo storico.
    """
    import datetime
    today = datetime.date.today()
    is_current = (anno is None or (anno == today.year and mese == today.month))
    
    if is_current:
        return {
            'entrate_mensili': float(get_configurazione('budget_entrate_mensili', id_famiglia) or 0),
            'risparmio_tipo': get_configurazione('budget_risparmio_tipo', id_famiglia) or 'percentuale',
            'risparmio_valore': float(get_configurazione('budget_risparmio_valore', id_famiglia) or 0)
        }
    else:
        chiave_base = f"budget_storico_{anno}_{mese:02d}"
        return {
            'entrate_mensili': float(get_configurazione(f"{chiave_base}_entrate", id_famiglia) or 0),
            'risparmio_tipo': get_configurazione(f"{chiave_base}_risparmio_tipo", id_famiglia) or 'percentuale',
            'risparmio_valore': float(get_configurazione(f"{chiave_base}_risparmio_valore", id_famiglia) or 0)
        }

def set_impostazioni_budget_famiglia(id_famiglia: str, entrate_mensili: float, risparmio_tipo: str, risparmio_valore: float, anno: int = None, mese: int = None) -> bool:
    """
    Salva le impostazioni del budget famiglia.
    Se anno e mese sono forniti, salva nello storico.
    """
    try:
        import datetime
        today = datetime.date.today()
        is_current = (anno is None or (anno == today.year and mese == today.month))
        
        if is_current:
            set_configurazione('budget_entrate_mensili', str(entrate_mensili), id_famiglia)
            set_configurazione('budget_risparmio_tipo', risparmio_tipo, id_famiglia)
            set_configurazione('budget_risparmio_valore', str(risparmio_valore), id_famiglia)
        else:
            chiave_base = f"budget_storico_{anno}_{mese:02d}"
            set_configurazione(f"{chiave_base}_entrate", str(entrate_mensili), id_famiglia)
            set_configurazione(f"{chiave_base}_risparmio_tipo", risparmio_tipo, id_famiglia)
            set_configurazione(f"{chiave_base}_risparmio_valore", str(risparmio_valore), id_famiglia)
        return True
    except Exception as e:
        logger.error(f"Errore salvataggio impostazioni budget: {e}")
        return False

        return False

# --- Funzioni Gestione Visibilità Funzioni (Feature Flags per Famiglia) ---

CONTROLLABLE_FEATURES = [
    {"key": "investimenti", "label": "Investimenti", "icon": "TRENDING_UP"},
    {"key": "spese_fisse", "label": "Spese Fisse", "icon": "CALENDAR_MONTH"},
    {"key": "prestiti", "label": "Prestiti", "icon": "MONEY_OFF"},
    {"key": "immobili", "label": "Immobili", "icon": "HOME_WORK"},
    {"key": "budget", "label": "Budget (Analisi)", "icon": "PIE_CHART"},
    {"key": "famiglia", "label": "Gestione Famiglia", "icon": "DIVERSITY_3"},
    {"key": "accantonamenti", "label": "Risparmi/Accantonamenti", "icon": "SAVINGS"},
    {"key": "divisore", "label": "Divisore Spese", "icon": "CALCULATE"},
    {"key": "carte", "label": "Carte di Credito/Debito", "icon": "CREDIT_CARD"},
    {"key": "contatti", "label": "Rubrica Contatti", "icon": "CONTACT_PHONE"},
]

def get_disabled_features(id_famiglia: str) -> List[str]:
    """
    Recupera la lista delle funzioni disabilitate per una famiglia.
    Restituisce una lista di stringhe (chiavi delle feature).
    """
    try:
        val_str = get_configurazione('disabled_features', id_famiglia)
        if not val_str:
            return []
        return json.loads(val_str)
    except Exception as e:
        logger.error(f"Errore get_disabled_features: {e}")
        return []

def set_disabled_features(id_famiglia: str, features_list: List[str]) -> bool:
    """
    Salva la lista delle funzioni disabilitate per una famiglia.
    """
    try:
        val_str = json.dumps(features_list)
        return set_configurazione('disabled_features', val_str, id_famiglia)
    except Exception as e:
        logger.error(f"Errore set_disabled_features: {e}")
        return False

