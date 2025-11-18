import os
import threading
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import sys

# --- GESTIONE PERCORSI PER ESEGUIBILE ---
APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'BudgetFamiliare')
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR)

# Il token generato dall'utente va in AppData
TOKEN_FILE = os.path.join(APP_DATA_DIR, 'token.json')

# Il file delle credenziali viene cercato prima nella cartella dell'eseguibile, poi in AppData
if getattr(sys, 'frozen', False):
    # Se l'app è un eseguibile, il file è nella cartella temporanea _MEIPASS
    CREDENTIALS_FILE = os.path.join(sys._MEIPASS, 'credentials.json')
else:
    # Se è uno script, è nella root del progetto
    CREDENTIALS_FILE = 'credentials.json'
# --- FINE GESTIONE PERCORSI ---

# Se modifichi questi SCOPES, cancella il file token.json.
# L'utente dovrà ri-autenticarsi.
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",      # Gestire file creati dall'app
    "https://www.googleapis.com/auth/drive.appdata",   # Accedere alla cartella dati dell'applicazione
    "https://www.googleapis.com/auth/gmail.send",      # Inviare email
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]


def get_creds():
    """
    Controlla, rinfresca se necessario, e restituisce le credenziali.
    Restituisce None se non autenticato o se il refresh fallisce.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"Errore caricamento token.json: {e}")
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
            return None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Token scaduto. Rinfresco...")
                creds.refresh(Request())
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
                print("Token rinfrescato con successo.")
            except Exception as e:
                print(f"Errore rinfrescando il token: {e}")
                if os.path.exists(TOKEN_FILE):
                    os.remove(TOKEN_FILE)
                return None
        else:
            return None

    return creds


def get_gmail_service():
    """Costruisce e restituisce l'oggetto del servizio Gmail API autenticato."""
    creds = get_creds()
    if creds:
        try:
            service = build('gmail', 'v1', credentials=creds)
            return service
        except Exception as e:
            print(f"❌ Errore nella creazione del servizio Gmail API: {e}")
            return None
    return None


def is_authenticated() -> bool:
    """
    Controlla se il file token.json esiste e se è valido.
    """
    return get_creds() is not None


def logout():
    """
    Disconnette l'utente eliminando il file token.json.
    """
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
        print(f"File {TOKEN_FILE} eliminato. Utente disconnesso.")
        return True
    return False


def authenticate(controller):
    """
    Avvia il flusso di autenticazione in un thread separato.
    """

    def _run_auth_flow(controller_instance):
        """
        Questa funzione viene eseguita in un thread worker.
        """
        page_instance = controller_instance.page
        try:
            print("Avvio flusso di autenticazione nel thread worker...")

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE,
                SCOPES,
                redirect_uri='http://localhost:8080/'
            )

            creds = flow.run_local_server(port=8080)

            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

            print("Autenticazione completata, token.json salvato.")
            page_instance.session.set("google_auth_token_present", True)

        except Exception as e:
            print(f"Errore durante il flusso di autenticazione: {e}")
            page_instance.session.set("google_auth_token_present", False)

        finally:
            if controller_instance:
                controller_instance.update_all_views()
                controller_instance.page.update()

    print("Avvio del thread di autenticazione...")
    auth_thread = threading.Thread(
        target=_run_auth_flow,
        args=(controller,)
    )
    auth_thread.start()