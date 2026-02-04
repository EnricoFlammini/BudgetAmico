import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from db.gestione_db import get_smtp_config

# Configurazione logger
logger = logging.getLogger(__name__)

def send_email(to_email, subject, body, smtp_config=None, attachment_bytes=None, attachment_name=None):
    """
    Invia un'email utilizzando le impostazioni SMTP con supporto opzionale per allegati.
    
    Args:
        to_email (str): Indirizzo email del destinatario.
        subject (str): Oggetto dell'email.
        body (str): Corpo dell'email.
        smtp_config (dict, optional): Dizionario con le impostazioni SMTP.
        attachment_bytes (bytes, optional): Contenuto dell'allegato in byte.
        attachment_name (str, optional): Nome del file allegato.
    """
    settings = None
    if smtp_config and smtp_config.get('server'):
        smtp_server = smtp_config.get('server')
        smtp_port = smtp_config.get('port')
        smtp_user = smtp_config.get('user')
        smtp_password = smtp_config.get('password')
    else:
        settings = get_smtp_config()
        if settings and settings.get('server'): 
            smtp_server = settings.get('server')
            smtp_port = settings.get('port')
            smtp_user = settings.get('user')
            smtp_password = settings.get('password')
        else:
            smtp_server = os.getenv("SMTP_SERVER")
            smtp_port = os.getenv("SMTP_PORT")
            smtp_user = os.getenv("SMTP_USER")
            smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
        logger.error(f"Configurazione SMTP incompleta: server={bool(smtp_server)}, port={bool(smtp_port)}, user={bool(smtp_user)}, pass={bool(smtp_password)}")
        return False, "Configurazione SMTP incompleta."

    # Email Mittente (Sender): Alcuni provider (come Brevo) richiedono un mittente verificato
    # che può essere diverso dall'utente SMTP.
    from_email = smtp_config.get('sender') if smtp_config and smtp_config.get('sender') else \
                (settings.get('sender') if (settings and settings.get('sender')) else smtp_user)

    print(f"[DEBUG] [SMTP] Protocollo: {smtp_server}:{smtp_port}")
    print(f"[DEBUG] [SMTP] Auth User: {smtp_user}")
    print(f"[DEBUG] [SMTP] From Header: {from_email}")
    print(f"[DEBUG] [SMTP] To: {to_email}")

    try:
        from email.mime.application import MIMEApplication
        
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email

        # Corpo email (HTML)
        msg.attach(MIMEText(body, 'html'))

        # Aggiunta allegato se presente
        if attachment_bytes and attachment_name:
            print(f"[DEBUG] [SMTP] Allegato presente: {attachment_name} ({len(attachment_bytes)} bytes)")
            part = MIMEApplication(attachment_bytes)
            part.add_header('Content-Disposition', 'attachment', filename=attachment_name)
            msg.attach(part)

        # Connessione al server SMTP
        server = smtplib.SMTP(smtp_server, int(smtp_port), timeout=15)
        # server.set_debuglevel(1) # Forza log smtplib su console (diretto a stderr)
        server.starttls()
        server.login(smtp_user, smtp_password)
        
        # USA from_email come mittente busta per massima compatibilità
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()

        logger.info(f"Email inviata con successo a {to_email}")
        return True, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Errore durante l'invio dell'email a {to_email}: {e}")
        return False, str(e)
