import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from db.gestione_db import get_smtp_config

# Configurazione logger
logger = logging.getLogger(__name__)

def send_email(to_email, subject, body, smtp_config=None):
    """
    Invia un'email utilizzando le impostazioni SMTP.
    
    Args:
        to_email (str): Indirizzo email del destinatario.
        subject (str): Oggetto dell'email.
        body (str): Corpo dell'email.
        smtp_config (dict, optional): Dizionario con le impostazioni SMTP (server, port, user, password).
                                      Se fornito, usa queste impostazioni invece di quelle salvate/env.
    """
    if smtp_config:
        smtp_server = smtp_config.get('server')
        smtp_port = smtp_config.get('port')
        smtp_user = smtp_config.get('user')
        smtp_password = smtp_config.get('password')
    else:
        # 1. Prova a caricare dal Database
        settings = get_smtp_config()
        # Se settings ha valori validi (non None), usali. 
        # get_smtp_config ritorna un dict con chiavi, ma i valori possono essere None.
        if settings and settings.get('server'): 
            smtp_server = settings.get('server')
            smtp_port = settings.get('port')
            smtp_user = settings.get('user')
            smtp_password = settings.get('password')
        else:
            # 2. Fallback su variabili d'ambiente (opzionale, mantenuto per retrocompatibilità)
            smtp_server = os.getenv("SMTP_SERVER")
            smtp_port = os.getenv("SMTP_PORT")
            smtp_user = os.getenv("SMTP_USER")
            smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
        logger.error("Configurazione SMTP mancante.")
        return False, "Configurazione SMTP mancante."

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email

        part = MIMEText(body, 'html')
        msg.attach(part)

        # Connessione al server SMTP
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls() # Sicurezza TLS
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.quit()

        logger.info(f"Email inviata con successo a {to_email}")
        return True, None

    except Exception as e:
        logger.error(f"Errore durante l'invio dell'email a {to_email}: {e}")
        return False, str(e)
