# File: utils/google_drive_manager.py

import os
import flet as ft
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.discovery import build
import io
import time
from datetime import datetime, timezone

from db.gestione_db import DB_FILE
import google_auth_manager

# Nome del file del database su Google Drive
DB_FILENAME_DRIVE = "budget_familiare.db"


def _get_drive_service(controller):
    """Ottiene un'istanza del servizio Drive autenticato."""
    creds = google_auth_manager.get_creds()
    if not creds:
        controller.show_snack_bar("Autenticazione Google non valida.", success=False)
        return None
    return build('drive', 'v3', credentials=creds)


def check_for_remote_db(controller):
    """
    Controlla l'esistenza e i metadati del file DB su Google Drive.
    Restituisce l'ID del file e la data di ultima modifica, o None.
    """
    drive_service = _get_drive_service(controller)
    if not drive_service:
        return None, None

    try:
        # Cerca il file nella cartella dell'applicazione
        response = drive_service.files().list(
            q=f"name='{DB_FILENAME_DRIVE}' and 'appDataFolder' in parents",
            spaces='appDataFolder',
            fields='files(id, modifiedTime)'
        ).execute()

        files = response.get('files', [])
        if not files:
            print("Nessun file DB trovato su Google Drive.")
            return None, None

        remote_file = files[0]
        file_id = remote_file['id']
        # Converte la data di modifica in un oggetto datetime consapevole del fuso orario
        modified_time_str = remote_file['modifiedTime']
        modified_time = datetime.fromisoformat(modified_time_str.replace('Z', '+00:00'))

        return file_id, modified_time

    except Exception as e:
        print(f"Errore durante il controllo del DB remoto: {e}")
        controller.show_snack_bar("Errore nel controllo su Drive.", success=False)
        return None, None


def download_db(controller, file_id=None):
    """Scarica il database da Google Drive e sovrascrive quello locale."""
    drive_service = _get_drive_service(controller)
    if not drive_service: return False

    try:
        if not file_id:
            file_id, _ = check_for_remote_db(controller)

        if not file_id:
            controller.show_snack_bar("File non trovato su Drive per il download.", success=False)
            return False

        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")

        # Sovrascrivi il file locale
        with open(DB_FILE, 'wb') as f:
            f.write(fh.getvalue())

        print("Download completato e file locale sovrascritto.")
        return True

    except Exception as e:
        print(f"Errore durante il download del DB: {e}")
        controller.show_snack_bar("Errore durante il download.", success=False)
        return False


def upload_db(controller, file_id=None):
    """Carica il database locale su Google Drive."""
    drive_service = _get_drive_service(controller)
    if not drive_service: return False

    file_metadata = {'name': DB_FILENAME_DRIVE}
    media = MediaFileUpload(DB_FILE, mimetype='application/x-sqlite3')

    try:
        if file_id:
            # Aggiorna file esistente
            drive_service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            print("File DB aggiornato su Google Drive.")
        else:
            # Crea nuovo file nella appDataFolder
            file_metadata['parents'] = ['appDataFolder']
            drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            print("File DB creato su Google Drive.")

        return True
    except Exception as e:
        print(f"Errore durante l'upload del DB: {e}")
        controller.show_snack_bar("Errore durante l'upload.", success=False)
        return False


def sync_database_with_drive(controller):
    """
    Funzione principale per la sincronizzazione intelligente del database.
    """
    try:
        remote_file_id, remote_mod_time = check_for_remote_db(controller)

        if not os.path.exists(DB_FILE):
            # Se non c'è un DB locale, scarica quello remoto se esiste
            if remote_file_id:
                print("DB locale non trovato. Scarico da Drive...")
                download_db(controller, remote_file_id)
            else:
                print("Nessun DB locale o remoto. L'app ne creerà uno nuovo.")
            return

        local_mod_time_ts = os.path.getmtime(DB_FILE)
        local_mod_time = datetime.fromtimestamp(local_mod_time_ts, tz=timezone.utc)

        if remote_file_id and remote_mod_time:
            # Confronta le date di modifica
            time_difference = (remote_mod_time - local_mod_time).total_seconds()

            if time_difference > 60:  # Tolleranza di 60 secondi
                print("Versione remota più recente trovata. Chiedo conferma all'utente.")
                controller.page.dialog = controller.confirm_download_dialog
                controller.confirm_download_dialog.open = True
                controller.page.update()
                # L'azione successiva è gestita da _download_confirmato o _download_rifiutato
                return

            elif time_difference < -60:
                print("Versione locale più recente. Eseguo l'upload...")
                if upload_db(controller, remote_file_id):
                    controller.show_snack_bar("Sincronizzazione completata (upload).", success=True)
            else:
                print("I file sono già sincronizzati.")
                controller.show_snack_bar("Database già sincronizzato.", success=True)
        else:
            # Nessun file remoto, carica quello locale
            print("Nessun file remoto trovato. Eseguo l'upload del DB locale...")
            if upload_db(controller):
                controller.show_snack_bar("Database caricato su Drive per la prima volta.", success=True)

    except Exception as e:
        print(f"Errore critico durante la sincronizzazione: {e}")
        controller.show_snack_bar("Errore critico di sincronizzazione.", success=False)
    finally:
        # Aggiorna l'icona di stato a "completato"
        if controller.dashboard_view.sync_status_icon:
            controller.dashboard_view.sync_status_icon.icon = ft.Icons.CLOUD_DONE
            controller.dashboard_view.sync_status_icon.rotate = None  # Ferma la rotazione
            controller.page.update()
