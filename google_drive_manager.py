import os
import flet as ft
import datetime
import google_auth_manager
from db.gestione_db import DB_FILE  # Importiamo il percorso del nostro DB
import io  # Necessario per il download

# Importa le librerie Google per le API
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from dateutil import parser as date_parser  # Per confrontare le date

# --- Costanti ---
DB_FILENAME = 'budget_familiare.db'
DB_MIMETYPE = 'application/x-sqlite3'


def _get_drive_service(controller=None):
    """
    Helper interno per ottenere l'oggetto "service" di Drive
    con le credenziali corrette.
    """
    creds = google_auth_manager.get_creds()
    if not creds:
        if controller:
            controller.show_snack_bar("Errore Drive: Credenziali non valide.", success=False)
        print("Errore Drive: Nessuna credenziale valida trovata.")
        return None

    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except HttpError as error:
        print(f"Errore durante la costruzione del service di Drive: {error}")
        if controller:
            controller.show_snack_bar(f"Errore Drive: {error}", success=False)
        return None


def _find_remote_db_file(service, controller=None):
    """
    Cerca su Drive il file del database.
    Restituisce l'intero oggetto file se trovato, altrimenti None.
    """
    try:
        q = f"name='{DB_FILENAME}' and trashed=false"

        response = service.files().list(
            q=q,
            spaces='drive',
            fields='files(id, name, modifiedTime)'  # Chiediamo la data di modifica
        ).execute()

        files = response.get('files', [])
        if not files:
            print(f"File '{DB_FILENAME}' non trovato su Google Drive.")
            return None

        # Restituisce il primo file trovato
        file_data = files[0]
        print(f"File '{DB_FILENAME}' trovato su Drive (ID: {file_data.get('id')}).")
        return file_data

    except HttpError as error:
        print(f"Errore durante la ricerca del file su Drive: {error}")
        if controller:
            controller.show_snack_bar(f"Errore Drive: {error}", success=False)
        return None


# --- NUOVA FUNZIONE ---
def get_remote_db_metadata():
    """
    Restituisce i metadati (id, modifiedTime) del file DB su Drive.
    """
    service = _get_drive_service() # Non serve il controller qui, è solo una lettura
    if not service:
        return None

    remote_file = _find_remote_db_file(service)
    return remote_file


# --- FUNZIONE AGGIORNATA ---
def download_db(remote_file_id, controller=None):
    """
    Scarica il file da Drive e sovrascrive il file DB_FILE locale.
    Restituisce True/False.
    """
    print(f"Avvio download del file {remote_file_id}...")
    service = _get_drive_service()
    if not service:
        return False

    try:
        request = service.files().get_media(fileId=remote_file_id)

        # Apriamo un file locale in "write binary" (wb)
        # Usiamo io.BytesIO come buffer intermedio
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")

        # Download completato. Ora scriviamo il buffer sul file
        with open(DB_FILE, 'wb') as f:
            f.write(fh.getvalue())

        print(f"File locale '{DB_FILE}' sovrascritto con successo.")
        return True

    except HttpError as error:
        print(f"Errore durante il download del file: {error}")
        if controller:
            controller.show_snack_bar(f"Errore Download: {error}", success=False)
        return False
    except Exception as e:
        print(f"Errore generico durante il download: {e}")
        if controller:
            controller.show_snack_bar(f"Errore Download: {e}", success=False)
        return False


def upload_db(controller=None):
    """
    Carica il file DB locale su Google Drive.
    Se il file esiste già, lo aggiorna. Altrimenti, lo crea.
    Restituisce True/False in base al successo.
    """
    print("Avvio upload database su Google Drive...")
    service = _get_drive_service(controller)
    if not service:
        return False

    if not os.path.exists(DB_FILE):
        print(f"Errore: File database locale non trovato in {DB_FILE}")
        if controller:
            controller.show_snack_bar("Errore: File DB locale non trovato.", success=False)
        return False

    remote_file = _find_remote_db_file(service, controller)

    # --- NUOVO BLOCCO: CONTROLLO DATA MODIFICA ---
    if remote_file:
        try:
            # Ottieni data modifica file locale (in UTC per confronto)
            local_mtime_ts = os.path.getmtime(DB_FILE)
            local_mtime_dt = datetime.datetime.fromtimestamp(local_mtime_ts, tz=datetime.timezone.utc)

            # Ottieni data modifica file remoto (già in UTC)
            remote_mtime_str = remote_file.get('modifiedTime')
            remote_mtime_dt = date_parser.parse(remote_mtime_str)

            if local_mtime_dt <= remote_mtime_dt:
                print("Sincronizzazione saltata: il file su Google Drive è già aggiornato.")
                return True # Consideriamo l'operazione un successo, non c'era nulla da fare.
        except Exception as e:
            print(f"⚠️ Avviso: impossibile confrontare le date dei file. Procedo con l'upload. Errore: {e}")

    media = MediaFileUpload(DB_FILE, mimetype=DB_MIMETYPE)

    try:
        if remote_file:
            remote_file_id = remote_file.get('id')
            print(f"Aggiornamento file esistente (ID: {remote_file_id})...")
            service.files().update(
                fileId=remote_file_id,
                media_body=media
            ).execute()
            print("Upload (Update) completato.")

        else:
            print("File non trovato. Creazione nuovo file su Drive...")
            file_metadata = {'name': DB_FILENAME}
            service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            print("Upload (Create) completato.")

        return True

    except HttpError as error:
        print(f"Errore durante l'upload del file: {error}")
        if controller and controller.dashboard_view.sync_status_icon:
            controller.dashboard_view.sync_status_icon.icon = ft.Icons.CLOUD_OFF
            controller.dashboard_view.sync_status_icon.rotate = None
            controller.page.update()
        return False
    except Exception as e:
        print(f"Errore generico durante l'upload: {e}")
        if controller and controller.dashboard_view.sync_status_icon:
            controller.dashboard_view.sync_status_icon.icon = ft.Icons.CLOUD_OFF
            controller.dashboard_view.sync_status_icon.rotate = None
            controller.page.update()
        return False
    finally:
        # Assicura che l'icona torni allo stato normale in ogni caso
        if controller and controller.dashboard_view.sync_status_icon:
            controller.dashboard_view.sync_status_icon.icon = ft.Icons.CLOUD_DONE
            controller.dashboard_view.sync_status_icon.rotate = None
            controller.page.update()