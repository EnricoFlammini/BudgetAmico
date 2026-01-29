"""
DBLogHandler - Handler per intercettare log standard Python e scriverli su database.

Questo modulo fornisce un logging.Handler personalizzato che intercetta
i log del sistema standard Python e li scrive nel database PostqreSQL,
permettendo la visualizzazione dall'interfaccia admin.
"""

import logging
import threading
from typing import Optional, Dict, Set
from db.supabase_manager import get_db_connection

# Cache delle configurazioni (aggiornata periodicamente)
_config_cache: Dict[str, dict] = {}
_cache_lock = threading.Lock()
_cache_last_update = 0
CACHE_TTL_SECONDS = 60  # Ricarica configurazione ogni 60 secondi


def _get_level_value(level_name: str) -> int:
    """Converte nome livello in valore numerico."""
    levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }
    return levels.get(level_name.upper(), logging.INFO)


def load_logger_config() -> Dict[str, dict]:
    """Carica la configurazione dei logger dal database."""
    global _config_cache, _cache_last_update
    
    import time
    current_time = time.time()
    
    # Usa cache se ancora valida
    with _cache_lock:
        if current_time - _cache_last_update < CACHE_TTL_SECONDS and _config_cache:
            return _config_cache.copy()
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT componente, abilitato, livello_minimo FROM Config_Logger")
            rows = cur.fetchall()
            
            new_config = {}
            for row in rows:
                new_config[row['componente']] = {
                    'abilitato': row['abilitato'],
                    'livello_minimo': row['livello_minimo'],
                    'livello_value': _get_level_value(row['livello_minimo'])
                }
            
            with _cache_lock:
                _config_cache = new_config
                _cache_last_update = current_time
            
            return new_config
    except Exception as e:
        print(f"[DBLogHandler] Errore caricamento config: {e}")
        return _config_cache.copy() if _config_cache else {}


def invalidate_config_cache():
    """Invalida la cache della configurazione (chiamare dopo modifiche)."""
    global _cache_last_update
    with _cache_lock:
        _cache_last_update = 0


def update_logger_config(componente: str, abilitato: bool, livello_minimo: str = 'INFO') -> bool:
    """Aggiorna la configurazione di un logger nel database."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO Config_Logger (componente, abilitato, livello_minimo)
                VALUES (%s, %s, %s)
                ON CONFLICT (componente) 
                DO UPDATE SET abilitato = EXCLUDED.abilitato, livello_minimo = EXCLUDED.livello_minimo
            """, (componente, abilitato, livello_minimo))
            conn.commit()
        
        # Invalida cache
        invalidate_config_cache()
        return True
    except Exception as e:
        print(f"[DBLogHandler] Errore aggiornamento config: {e}")
        return False


def get_all_components() -> list:
    """Recupera tutti i componenti configurati."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT componente, abilitato, livello_minimo FROM Config_Logger ORDER BY componente")
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[DBLogHandler] Errore recupero componenti: {e}")
        return []


class DBLogHandler(logging.Handler):
    """
    Handler che intercetta i log e li scrive nel database.
    
    Si attiva solo se il componente è abilitato nella configurazione.
    """
    
    def __init__(self, componente: str):
        super().__init__()
        self.componente = componente
    
    def emit(self, record: logging.LogRecord):
        """Emette un record di log sul database se abilitato."""
        try:
            # Carica configurazione
            config = load_logger_config()
            
            # Verifica se componente è abilitato
            comp_config = config.get(self.componente)
            if not comp_config or not comp_config.get('abilitato'):
                return  # Non loggare
            
            # Verifica livello minimo
            min_level = comp_config.get('livello_value', logging.INFO)
            if record.levelno < min_level:
                return  # Livello troppo basso
            
            # Scrivi nel database (in thread separato)
            self._write_to_db(record)
            
        except Exception:
            # Non propagare errori dal handler
            pass
    
    def _write_to_db(self, record: logging.LogRecord):
        """Scrive il record nel database in modo asincrono."""
        def _insert():
            try:
                with get_db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Mappa livello
                    level_name = record.levelname
                    
                    # Prepara messaggio
                    message = self.format(record) if self.formatter else record.getMessage()
                    
                    # Prepara dettagli (exception info se presente)
                    details = None
                    if record.exc_info:
                        import traceback
                        import json
                        details = json.dumps({
                            'traceback': ''.join(traceback.format_exception(*record.exc_info))
                        })
                    
                    # Estrai contesto utente/famiglia se presente in extra
                    id_utente = getattr(record, 'id_utente', None)
                    id_famiglia = getattr(record, 'id_famiglia', None)
                    
                    cur.execute("""
                        INSERT INTO Log_Sistema (livello, componente, messaggio, dettagli, id_utente, id_famiglia)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (level_name, self.componente, message, details, id_utente, id_famiglia))
                    
                    conn.commit()
            except Exception as e:
                # Fallback: stampa su console
                print(f"[DBLogHandler] Errore scrittura DB: {e}")
        
        # Esegui in thread separato
        thread = threading.Thread(target=_insert, daemon=True)
        thread.start()


# --- Funzione di utilità per integrare il handler ---

_attached_handlers: Set[str] = set()

def attach_db_handler_to_logger(logger_name: str):
    """
    Aggiunge il DBLogHandler a un logger esistente.
    Chiamare dopo setup_logger() per abilitare il logging su DB.
    """
    global _attached_handlers
    
    if logger_name in _attached_handlers:
        return  # Già aggiunto
    
    logger = logging.getLogger(logger_name)
    handler = DBLogHandler(logger_name)
    handler.setLevel(logging.DEBUG)  # Cattura tutto, filtra dopo
    logger.addHandler(handler)
    
    _attached_handlers.add(logger_name)


def attach_db_handler_to_all_loggers():
    """Aggiunge il DBLogHandler a tutti i logger noti."""
    known_loggers = [
        'BackgroundService',
        'YFinanceManager', 
        'AppController',
        'GestioneDB',
        'AuthView',
        'SupabaseManager',
        'CryptoManager',
        'WebAppController',
        'Main',
        'WebDashboardView',
        'DashboardView',
        'TransactionDialog',
        'PersonaleTab',
        'ImpostazioniTab',
        'CacheManager',
    ]
    
    for name in known_loggers:
        attach_db_handler_to_logger(name)
