import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google_auth_manager


def send_email_via_gmail_api(to, subject, message_text):
    """
    Crea e invia un'email usando l'API di Gmail.
    """
    gmail_service = google_auth_manager.get_gmail_service()
    if not gmail_service:
        print("❌ Servizio Gmail non disponibile. Impossibile inviare l'email.")
        return False

    try:
        message = MIMEMultipart('alternative')
        message['to'] = to
        message['subject'] = subject
        # Non è necessario impostare 'from', Gmail lo farà automaticamente

        # Il corpo del messaggio è HTML
        message.attach(MIMEText(message_text, 'html'))

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {'raw': raw_message}

        # Usa 'me' come userId per indicare l'utente autenticato
        sent_message = gmail_service.users().messages().send(userId='me', body=body).execute()
        print(f"✅ Email inviata con successo a {to}. Message ID: {sent_message['id']}")
        return True

    except Exception as e:
        print(f"❌ Errore durante l'invio dell'email via Gmail API a {to}: {e}")
        return False