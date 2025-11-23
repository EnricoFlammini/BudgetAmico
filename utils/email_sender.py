import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# Configurazione logger
logger = logging.getLogger(__name__)

from utils.config_manager import get_smtp_settings

def send_email(to_email, subject, body_html):
    """
    Invia un'email utilizzando un server SMTP configurato.
    Priorità: Configurazione salvata (config.json) > Variabili d'ambiente.
    """
    # 1. Prova a caricare da config.json
    smtp_settings = get_smtp_settings()
    smtp_server = smtp_settings.get('server')
    smtp_port = smtp_settings.get('port')
    smtp_user = smtp_settings.get('user')
    smtp_password = smtp_settings.get('password')

    # 2. Fallback su variabili d'ambiente se mancano dati nel config
    if not smtp_server: smtp_server = os.environ.get("SMTP_SERVER")
    if not smtp_port: smtp_port = os.environ.get("SMTP_PORT")
    if not smtp_user: smtp_user = os.environ.get("SMTP_USER")
    if not smtp_password: smtp_password = os.environ.get("SMTP_PASSWORD")

    if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
        logger.error("Configurazione SMTP mancante. Controlla le variabili d'ambiente.")
        print("❌ Configurazione SMTP mancante. Controlla le variabili d'ambiente.")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email

        part = MIMEText(body_html, 'html')
        msg.attach(part)

        # Connessione al server SMTP
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls() # Sicurezza TLS
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.quit()

        logger.info(f"Email inviata con successo a {to_email}")
        print(f"✅ Email inviata con successo a {to_email}")
        return True

    except Exception as e:
        logger.error(f"Errore durante l'invio dell'email a {to_email}: {e}")
        print(f"❌ Errore durante l'invio dell'email a {to_email}: {e}")
        return False
