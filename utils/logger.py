
import logging
import os
import time
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler

# Directory dei log
# Usa APPDATA se disponibile (Windows), altrimenti fallback logica precedente o home
appdata = os.getenv('APPDATA')
if appdata:
    LOG_DIR = os.path.join(appdata, 'BudgetAmico', 'logs')
else:
    # Fallback per non-Windows o dev
    LOG_DIR = os.path.join(os.path.expanduser('~'), '.budgetamico', 'logs')

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, 'app.log')

def setup_logger(name="BudgetAmico"):
    """
    Configura e restituisce un logger.
    Gestisce la rotazione dei file e la cancellazione dei log vecchi.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Evita di aggiungere handler multipli se il logger è già configurato
    if logger.handlers:
        return logger

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File Handler con rotazione giornaliera, mantiene ultimi 2 file (48h circa se 1 file al giorno)
    # Oppure usiamo cleanup manuale per essere precisi sulle 48h
    file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", interval=1, backupCount=2)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Console Handler
    console_handler = logging.StreamHandler()
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
