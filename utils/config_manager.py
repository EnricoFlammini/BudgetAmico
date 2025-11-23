import json
import os
import logging

# Configurazione logger
logger = logging.getLogger(__name__)

# Percorso del file di configurazione
APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'BudgetAmico')
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.json')

def load_config():
    """Carica la configurazione dal file JSON."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Errore durante il caricamento della configurazione: {e}")
        return {}

def save_config(data):
    """Salva la configurazione nel file JSON."""
    if not os.path.exists(APP_DATA_DIR):
        os.makedirs(APP_DATA_DIR)
        
    try:
        # Carica la configurazione esistente per non sovrascrivere altri dati
        current_config = load_config()
        current_config.update(data)
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(current_config, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Errore durante il salvataggio della configurazione: {e}")
        return False

def get_smtp_settings():
    """Restituisce i parametri SMTP dalla configurazione."""
    config = load_config()
    return config.get('smtp', {})

def save_smtp_settings(server, port, user, password, provider=None):
    """Salva i parametri SMTP."""
    smtp_data = {
        'server': server,
        'port': port,
        'user': user,
        'password': password,
        'provider': provider
    }
    return save_config({'smtp': smtp_data})
