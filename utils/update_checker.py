"""
Modulo per controllo aggiornamenti da GitHub Releases.
"""
import requests
import re
from typing import Optional, Dict, Any

# URL API GitHub Releases - CONFIGURARE CON IL TUO REPOSITORY
GITHUB_REPO = "EnricoFlammini/BudgetAmico"  # Formato: "owner/repo"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_version(version_str: str) -> tuple:
    """
    Converte una stringa versione in tupla per confronto.
    Es: "v.0.21.00" -> (0, 21, 0)
        "0.21.00" -> (0, 21, 0)
    """
    # Rimuovi prefissi come "v" o "v."
    cleaned = re.sub(r'^v\.?', '', version_str.strip())
    
    # Estrai numeri
    numbers = re.findall(r'\d+', cleaned)
    
    # Converti in tupla di interi
    return tuple(int(n) for n in numbers) if numbers else (0,)


def compare_versions(local: str, remote: str) -> int:
    """
    Confronta due versioni.
    Ritorna:
        1 se remote > local (aggiornamento disponibile)
        0 se remote == local
       -1 se remote < local
    """
    local_tuple = parse_version(local)
    remote_tuple = parse_version(remote)
    
    # Pareggia le lunghezze
    max_len = max(len(local_tuple), len(remote_tuple))
    local_tuple = local_tuple + (0,) * (max_len - len(local_tuple))
    remote_tuple = remote_tuple + (0,) * (max_len - len(remote_tuple))
    
    if remote_tuple > local_tuple:
        return 1
    elif remote_tuple < local_tuple:
        return -1
    return 0


def check_for_updates(current_version: str) -> Optional[Dict[str, Any]]:
    """
    Controlla se c'è un aggiornamento disponibile su GitHub.
    
    Args:
        current_version: Versione corrente dell'app (es. "0.21.00")
        
    Returns:
        Dict con info aggiornamento se disponibile, None altrimenti.
        {
            "version": "0.22.00",
            "download_url": "https://...",
            "changelog": "Note di rilascio",
            "html_url": "URL pagina release"
        }
    """
    try:
        response = requests.get(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10
        )
        
        if response.status_code == 404:
            # Nessuna release pubblicata
            print("[UPDATE] Nessuna release trovata su GitHub")
            return None
            
        response.raise_for_status()
        release_data = response.json()
        
        # Estrai versione dal tag
        remote_version = release_data.get("tag_name", "")
        
        # Confronta versioni
        if compare_versions(current_version, remote_version) > 0:
            # Cerca il link di download dell'eseguibile
            download_url = None
            assets = release_data.get("assets", [])
            
            for asset in assets:
                asset_name = asset.get("name", "").lower()
                # Cerca file .exe o .zip
                if asset_name.endswith(".exe") or "budgetamico" in asset_name:
                    download_url = asset.get("browser_download_url")
                    break
            
            # Se non c'è un asset, usa il link alla pagina della release
            if not download_url:
                download_url = release_data.get("html_url")
            
            return {
                "version": remote_version,
                "download_url": download_url,
                "changelog": release_data.get("body", ""),
                "html_url": release_data.get("html_url")
            }
        
        # Versione corrente è aggiornata
        print(f"[UPDATE] App aggiornata. Locale: {current_version}, Remota: {remote_version}")
        return None
        
    except requests.RequestException as e:
        print(f"[UPDATE] Errore controllo aggiornamenti: {e}")
        return None
    except Exception as e:
        print(f"[UPDATE] Errore imprevisto: {e}")
        return None


def get_release_page_url() -> str:
    """Restituisce l'URL della pagina releases del repository."""
    return f"https://github.com/{GITHUB_REPO}/releases"
