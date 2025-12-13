
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler

# Directory dei log
# Usa APPDATA se disponibile (Windows), altrimenti fallback logica precedente o home
appdata = os.getenv('APPDATA')
if appdata:
    LOG_DIR = os.path.join(appdata, 'BudgetAmico', 'logs')
    SETTINGS_DIR = os.path.join(appdata, 'BudgetAmico')
else:
    # Fallback per non-Windows o dev
    LOG_DIR = os.path.join(os.path.expanduser('~'), '.budgetamico', 'logs')
    SETTINGS_DIR = os.path.join(os.path.expanduser('~'), '.budgetamico')

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, 'app.log')
LOGGING_ENABLED_FILE = os.path.join(SETTINGS_DIR, 'logging_enabled.txt')


def is_logging_enabled():
    """Controlla se il logging è abilitato. Default: disabilitato."""
    try:
        if os.path.exists(LOGGING_ENABLED_FILE):
            with open(LOGGING_ENABLED_FILE, 'r') as f:
                return f.read().strip().lower() == 'true'
        return False  # Default: disabilitato
    except:
        return False


def set_logging_enabled(enabled: bool):
    """Imposta lo stato del logging (richiede riavvio app per applicare)."""
    try:
        if not os.path.exists(SETTINGS_DIR):
            os.makedirs(SETTINGS_DIR)
        with open(LOGGING_ENABLED_FILE, 'w') as f:
            f.write('true' if enabled else 'false')
        return True
    except Exception as e:
        print(f"[LOGGER] Errore salvataggio impostazione logging: {e}")
        return False


class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    Handler che gestisce i PermissionError su Windows durante la rotazione.
    Su Windows, i file possono essere bloccati - in tal caso salta la rotazione.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            # Su Windows, file potrebbe essere bloccato - salta rotazione silenziosamente
            pass
        except Exception as e:
            # Log altri errori ma non crashare
            print(f"[LOGGER] Rollover error (ignored): {e}")


def setup_logger(name="BudgetAmico"):
    """
    Configura e restituisce un logger.
    Se il logging è disabilitato, restituisce un logger con NullHandler.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Evita di aggiungere handler multipli se il logger è già configurato
    if logger.handlers:
        return logger

    # Controlla se il logging è abilitato
    if not is_logging_enabled():
        # Logging disabilitato - usa NullHandler per silenziare tutto
        logger.addHandler(logging.NullHandler())
        return logger

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File Handler con rotazione giornaliera - delay=True per evitare blocchi Windows
    file_handler = SafeTimedRotatingFileHandler(
        LOG_FILE, when="midnight", interval=1, backupCount=2, 
        delay=True, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Console Handler con encoding sicuro per Windows
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def cleanup_old_logs(hours=48):
    """
    Rimuove i file di log più vecchi di 'hours'.
    """
    now = time.time()
    cutoff = now - (hours * 3600)

    for filename in os.listdir(LOG_DIR):
        file_path = os.path.join(LOG_DIR, filename)
        if os.path.isfile(file_path):
            file_mtime = os.path.getmtime(file_path)
            if file_mtime < cutoff:
                try:
                    os.remove(file_path)
                    print(f"[LOGGER] Rimosso log vecchio: {filename}")
                except Exception as e:
                    print(f"[LOGGER] Errore rimozione {filename}: {e}")

# Esegui pulizia all'inizializzazione del modulo
cleanup_old_logs()
