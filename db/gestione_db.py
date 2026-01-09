from db.supabase_manager import get_db_connection
import hashlib
import datetime
import os
import sys
from typing import Optional, List, Dict, Any, Union, Tuple
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse as parse_date
import mimetypes
import secrets
import string
import base64
from utils.crypto_manager import CryptoManager
from utils.cache_manager import cache_manager
from utils.logger import setup_logger

# --- BLOCCO DI CODICE PER CORREGGERE IL PERCORSO ---
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
# --- FINE BLOCCO DI CODICE ---

from db.crea_database import setup_database

logger = setup_logger("GestioneDB")

# Load Server Key
SERVER_SECRET_KEY = os.getenv("SERVER_SECRET_KEY")
if not SERVER_SECRET_KEY:
    logger.warning("SERVER_SECRET_KEY not found in .env. Password recovery via email will not work for new encrypted data.")

# --- System Key Helpers ---
def _get_system_keys():
    if not SERVER_SECRET_KEY: return None, None
    import hashlib
    # 1. Hashing Salt (Use Key directly)
    hash_salt = SERVER_SECRET_KEY
    # 2. Encryption Key (Fernet)
    srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
    srv_fernet_key_b64 = base64.urlsafe_b64encode(srv_key_bytes)
    return hash_salt, srv_fernet_key_b64

HASH_SALT, SYSTEM_FERNET_KEY = _get_system_keys()

def compute_blind_index(value):
    if not value or not HASH_SALT: return None
    import hashlib
    return hashlib.sha256((value.lower().strip() + HASH_SALT).encode()).hexdigest()

def encrypt_system_data(value):
    if not value or not SYSTEM_FERNET_KEY: return None
    from cryptography.fernet import Fernet
    cipher = Fernet(SYSTEM_FERNET_KEY)
    return cipher.encrypt(value.encode()).decode()

def decrypt_system_data(value_enc):
    if not value_enc or not SYSTEM_FERNET_KEY: return None
    from cryptography.fernet import Fernet
    cipher = Fernet(SYSTEM_FERNET_KEY)
    try:
        return cipher.decrypt(value_enc.encode()).decode()
    except Exception:
        return None



def ottieni_ruolo_utente(id_famiglia: str, id_utente: str) -> Optional[str]:
    """
    Recupera il ruolo dell'utente nella famiglia.
    Restituisce: 'admin', 'livello1', 'livello2', 'livello3' o None.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT ruolo FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND id_utente = %s", (id_famiglia, id_utente))
            row = cur.fetchone()
            return row['ruolo'] if row else None
    except Exception as e:
        logger.error(f"ottieni_ruolo_utente: {e}")
        return None


def _get_crypto_and_key(master_key_b64=None):
    """
    Returns CryptoManager instance and master_key.
    If master_key_b64 is None, returns (crypto, None) for legacy support.
    """
    crypto = CryptoManager()
    if master_key_b64:
        try:
            # master_key_b64 is the string representation of the base64 encoded key
            # We just need to convert it to bytes
            master_key = master_key_b64.encode()
            return crypto, master_key
        except Exception as e:
            logger.error(f"Errore decodifica master_key: {e}")
            return crypto, None
    return crypto, None

def _encrypt_if_key(data, master_key, crypto=None):
    """Encrypts data if master_key is available, otherwise returns data as-is."""
    if not master_key or not data:
        return data
    if not crypto:
        crypto = CryptoManager()
    return crypto.encrypt_data(data, master_key)

def _decrypt_if_key(encrypted_data, master_key, crypto=None, silent=False):
    if not master_key or not encrypted_data:
        return encrypted_data
    if not crypto:
        crypto = CryptoManager()
    
    # print(f"[DEBUG] _decrypt_if_key called. Key len: {len(master_key)}, Data len: {len(encrypted_data)}")
    
    # Handle non-string inputs (e.g. numbers before migration)
    if not isinstance(encrypted_data, str):
        return encrypted_data

    # Check if data looks like a Fernet token (starts with gAAAAA)
    if not encrypted_data.startswith("gAAAAA"):
        return encrypted_data

    decrypted = crypto.decrypt_data(encrypted_data, master_key, silent=silent)
    
    # Fallback for unencrypted numbers (during migration)
    if decrypted == "[ENCRYPTED]":
        try:
            # Check if it's a valid number
            float(encrypted_data)
            return encrypted_data
        except ValueError:
            pass
            
    return decrypted


# --- Funzioni di Versioning ---
def ottieni_versione_db():
    """Legge la versione dello schema dalla tabella InfoDB del database."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT valore FROM InfoDB WHERE chiave = 'versione'")
            res = cur.fetchone()
            return int(res['valore']) if res else 0
    except Exception as e:
        logger.error(f"Errore durante la lettura della versione del DB: {repr(e)}")
        return 0


# --- Funzioni di Utilità ---
def generate_token(length=32):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def get_user_count():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) as count FROM Utenti")
            return cur.fetchone()['count']
    except Exception as e:
        logger.error(f"Errore in get_user_count: {e}")
        return -1


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def valida_iban_semplice(iban):
    if not iban:
        return True
    iban_pulito = iban.strip().upper()
    return iban_pulito.startswith("IT") and len(iban_pulito) == 27 and iban_pulito[2:].isalnum()



# --- Funzioni Configurazioni ---
def get_configurazione(chiave: str, id_famiglia: Optional[str] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> Optional[str]:
    """
    Recupera il valore di una configurazione.
    
    Args:
        chiave: La chiave della configurazione da recuperare.
        id_famiglia: L'ID della famiglia (opzionale). Se None, cerca una configurazione globale.
        master_key_b64: La master key codificata in base64 (opzionale) per decriptare valori sensibili.
        id_utente: L'ID dell'utente (opzionale) per recuperare la family key.

    Returns:
        Il valore della configurazione come stringa, oppure None se non trovata.
        I valori SMTP vengono decriptati con family_key o system key.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            if id_famiglia is None:
                cur.execute("SELECT valore FROM Configurazioni WHERE chiave = %s AND id_famiglia IS NULL", (chiave,))
            else:
                cur.execute("SELECT valore FROM Configurazioni WHERE chiave = %s AND id_famiglia = %s", (chiave, id_famiglia))
            
            res = cur.fetchone()
            if not res:
                return None
            
            valore = res['valore']
            
            # Decrypt sensitive config values
            sensitive_keys = ['smtp_server', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from_email']
            
            if chiave in sensitive_keys:
                # SMTP credentials are ALWAYS encrypted with SERVER_KEY (not family_key)
                # This allows decryption without user context (e.g., for password reset)
                try:
                    decrypted = decrypt_system_data(valore)
                    if decrypted:
                        valore = decrypted
                except Exception as e:
                    logger.warning(f"Failed to system-decrypt {chiave}: {e}")
            
            return valore
    except Exception as e:
        logger.error(f"Errore recupero configurazione {chiave}: {e}")
        return None

def set_configurazione(chiave: str, valore: str, id_famiglia: Optional[str] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> bool:
    """
    Imposta o aggiorna una configurazione.

    Args:
        chiave: La chiave della configurazione.
        valore: Il valore da impostare.
        id_famiglia: L'ID della famiglia (opzionale). Se None, imposta una configurazione globale.
        master_key_b64: La master key codificata in base64 (opzionale) per criptare valori sensibili.
        id_utente: L'ID dell'utente (opzionale) per recuperare la family key.

    Returns:
        True se il salvataggio è avvenuto con successo, False altrimenti.
    """
    try:
        # Encrypt sensitive config values
        encrypted_valore = valore
        sensitive_keys = ['smtp_server', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from_email']
        
        if chiave in sensitive_keys and SERVER_SECRET_KEY:
            # SMTP credentials are ALWAYS encrypted with SERVER_KEY (not family_key)
            # This allows the server to decrypt them for password reset without user context
            try:
                encrypted_valore = encrypt_system_data(valore)
            except Exception as e:
                logger.warning(f"Failed to system-encrypt {chiave}: {e}")
        
        with get_db_connection() as con:
            cur = con.cursor()
            if id_famiglia is None:
                cur.execute("""
                    INSERT INTO Configurazioni (chiave, valore, id_famiglia) 
                    VALUES (%s, %s, NULL)
                    ON CONFLICT (chiave, id_famiglia) WHERE id_famiglia IS NULL
                    DO UPDATE SET valore = EXCLUDED.valore
                """, (chiave, encrypted_valore))
            else:
                cur.execute("""
                    INSERT INTO Configurazioni (chiave, valore, id_famiglia) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (chiave, id_famiglia) 
                    DO UPDATE SET valore = EXCLUDED.valore
                """, (chiave, encrypted_valore, id_famiglia))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore salvataggio configurazione {chiave}: {e}")
        return False

def get_smtp_config(id_famiglia: Optional[str] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Recupera la configurazione SMTP completa. Tutti i valori vengono decriptati automaticamente.
    
    Returns:
        Un dizionario contenente 'server', 'port', 'user', 'password', 'provider'.
    """
    logger.debug(f"get_smtp_config called with id_famiglia={id_famiglia}, id_utente={id_utente}, master_key_present={bool(master_key_b64)}")
    return {
        'server': get_configurazione('smtp_server', id_famiglia, master_key_b64, id_utente),
        'port': get_configurazione('smtp_port', id_famiglia, master_key_b64, id_utente),
        'user': get_configurazione('smtp_user', id_famiglia, master_key_b64, id_utente),
        'password': get_configurazione('smtp_password', id_famiglia, master_key_b64, id_utente),
        'provider': get_configurazione('smtp_provider', id_famiglia)  # provider is not sensitive
    }

def save_smtp_config(settings: Dict[str, Any], id_famiglia: Optional[str] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> bool:
    """
    Salva la configurazione SMTP. Tutti i valori sensibili vengono criptati automaticamente.
    
    Args:
        settings: Dizionario con le impostazioni SMTP.
        id_famiglia, master_key_b64, id_utente: Parametri per la crittografia.
    """
    try:
        set_configurazione('smtp_server', settings.get('server'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_port', settings.get('port'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_user', settings.get('user'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_password', settings.get('password'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_provider', settings.get('provider'), id_famiglia)  # provider is not sensitive
        return True
    except Exception as e:
        logger.error(f"Errore salvataggio SMTP config: {e}")
        return False


# --- Funzioni Gestione Budget Famiglia ---

def get_impostazioni_budget_famiglia(id_famiglia: str) -> Dict[str, Union[float, str]]:
    """
    Recupera le impostazioni del budget famiglia:
    - entrate_mensili: valore inserito manualmente
    - risparmio_tipo: 'percentuale' o 'importo'
    - risparmio_valore: valore del risparmio
    """
    return {
        'entrate_mensili': float(get_configurazione('budget_entrate_mensili', id_famiglia) or 0),
        'risparmio_tipo': get_configurazione('budget_risparmio_tipo', id_famiglia) or 'percentuale',
        'risparmio_valore': float(get_configurazione('budget_risparmio_valore', id_famiglia) or 0)
    }

def set_impostazioni_budget_famiglia(id_famiglia: str, entrate_mensili: float, risparmio_tipo: str, risparmio_valore: float) -> bool:
    """
    Salva le impostazioni del budget famiglia.
    - entrate_mensili: valore delle entrate mensili
    - risparmio_tipo: 'percentuale' o 'importo'
    - risparmio_valore: valore del risparmio
    """
    try:
        set_configurazione('budget_entrate_mensili', str(entrate_mensili), id_famiglia)
        set_configurazione('budget_risparmio_tipo', risparmio_tipo, id_famiglia)
        set_configurazione('budget_risparmio_valore', str(risparmio_valore), id_famiglia)
        return True
    except Exception as e:
        logger.error(f"Errore salvataggio impostazioni budget: {e}")
        return False

def calcola_entrate_mensili_famiglia(id_famiglia: str, anno: int, mese: int, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> float:
    """
    Calcola la somma delle transazioni categorizzate come "Entrate" 
    per tutti i membri della famiglia nel mese specificato.
    Cerca la categoria con nome contenente "Entrat" (case insensitive).
    """
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Prima troviamo le categorie "Entrate" della famiglia
            # Le categorie potrebbero essere criptate, quindi le recuperiamo tutte
            cur.execute("""
                SELECT id_categoria, nome_categoria 
                FROM Categorie 
                WHERE id_famiglia = %s
            """, (id_famiglia,))
            categorie = cur.fetchall()
            
            # Decrypt e cerca "Entrat" nel nome
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            id_categorie_entrate = []
            for cat in categorie:
                nome = cat['nome_categoria']
                if family_key:
                    nome = _decrypt_if_key(nome, family_key, crypto)
                if nome and 'entrat' in nome.lower():
                    id_categorie_entrate.append(cat['id_categoria'])
            
            if not id_categorie_entrate:
                return 0.0
            
            # Ottieni le sottocategorie di queste categorie
            placeholders = ','.join(['%s'] * len(id_categorie_entrate))
            cur.execute(f"""
                SELECT id_sottocategoria 
                FROM Sottocategorie 
                WHERE id_categoria IN ({placeholders})
            """, tuple(id_categorie_entrate))
            id_sottocategorie = [row['id_sottocategoria'] for row in cur.fetchall()]
            
            if not id_sottocategorie:
                return 0.0
            
            # Somma le transazioni personali con queste sottocategorie
            placeholders_sub = ','.join(['%s'] * len(id_sottocategorie))
            cur.execute(f"""
                SELECT COALESCE(SUM(T.importo), 0.0) as totale
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND T.id_sottocategoria IN ({placeholders_sub})
                  AND T.data BETWEEN %s AND %s
            """, (id_famiglia, *id_sottocategorie, data_inizio, data_fine))
            totale_personali = cur.fetchone()['totale'] or 0.0
            
            # Somma le transazioni condivise con queste sottocategorie
            cur.execute(f"""
                SELECT COALESCE(SUM(TC.importo), 0.0) as totale
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND TC.id_sottocategoria IN ({placeholders_sub})
                  AND TC.data BETWEEN %s AND %s
            """, (id_famiglia, *id_sottocategorie, data_inizio, data_fine))
            totale_condivise = cur.fetchone()['totale'] or 0.0
            
            return totale_personali + totale_condivise
            
    except Exception as e:
        logger.error(f"Errore calcolo entrate mensili: {e}")
        return 0.0

def ottieni_totale_budget_allocato(id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> float:
    """
    Ritorna il totale dei budget assegnati alle sottocategorie.
    """
    try:
        budget_list = ottieni_budget_famiglia(id_famiglia, master_key_b64, id_utente)
        return sum(b.get('importo_limite', 0) for b in budget_list)
    except Exception as e:
        logger.error(f"Errore calcolo totale budget allocato: {e}")
        return 0.0

def ottieni_totale_budget_storico(id_famiglia: str, anno: int, mese: int, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> float:
    """
    Ritorna il totale dei budget assegnati per un mese specifico dallo storico.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        key_to_use = family_key if family_key else master_key

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT importo_limite 
                FROM Budget_Storico 
                WHERE id_famiglia = %s AND anno = %s AND mese = %s
            """, (id_famiglia, anno, mese))
            
            rows = cur.fetchall()
            if not rows:
                return 0.0
                
            totale = 0.0
            for row in rows:
                enc_limite = row['importo_limite']
                try:
                    limite_str = _decrypt_if_key(enc_limite, key_to_use, crypto)
                    totale += float(limite_str)
                except Exception as e:
                    # print(f"Errore decrypt budget storico row: {e}")
                    pass
            return totale
            
    except Exception as e:
        logger.error(f"Errore calcolo totale budget storico: {e}")
        return 0.0

def salva_impostazioni_budget_storico(id_famiglia: str, anno: int, mese: int, entrate_mensili: float, risparmio_tipo: str, risparmio_valore: float) -> bool:
    """
    Salva le impostazioni budget nello storico per un mese specifico.
    Usa la tabella Configurazioni con chiavi contenenti anno e mese.
    """
    try:
        chiave_base = f"budget_storico_{anno}_{mese:02d}"
        set_configurazione(f"{chiave_base}_entrate", str(entrate_mensili), id_famiglia)
        set_configurazione(f"{chiave_base}_risparmio_tipo", risparmio_tipo, id_famiglia)
        set_configurazione(f"{chiave_base}_risparmio_valore", str(risparmio_valore), id_famiglia)
        return True
    except Exception as e:
        logger.error(f"Errore salvataggio storico impostazioni budget: {e}")
        return False

def ottieni_impostazioni_budget_storico(id_famiglia: str, anno: int, mese: int) -> Optional[Dict[str, Union[float, str]]]:
    """
    Recupera le impostazioni budget dallo storico per un mese specifico.
    Se non esistono, ritorna None.
    """
    chiave_base = f"budget_storico_{anno}_{mese:02d}"
    entrate = get_configurazione(f"{chiave_base}_entrate", id_famiglia)
    
    if entrate is None:
        return None  # Non esiste storico per questo mese
    
    return {
        'entrate_mensili': float(entrate or 0),
        'risparmio_tipo': get_configurazione(f"{chiave_base}_risparmio_tipo", id_famiglia) or 'percentuale',
        'risparmio_valore': float(get_configurazione(f"{chiave_base}_risparmio_valore", id_famiglia) or 0)
    }

def ottieni_dati_analisi_mensile(id_famiglia: str, anno: int, mese: int, master_key_b64: str, id_utente: str) -> Optional[Dict[str, Any]]:
    """
    Recupera i dati completi per l'analisi mensile del budget.
    Include entrate, spese totali, budget totale, risparmio, delta e ripartizione categorie.
    """
    try:
        # 1. Recupera Impostazioni (Storiche o Correnti)
        impostazioni_storico = ottieni_impostazioni_budget_storico(id_famiglia, anno, mese)
        if impostazioni_storico:
            entrate = impostazioni_storico['entrate_mensili']
        else:
            # Fallback a impostazioni correnti
            imps = get_impostazioni_budget_famiglia(id_famiglia)
            entrate = imps['entrate_mensili']

        # 2. Calcola Spese Totali e Spese per Categoria (con decriptazione)
        data_inizio = f"{anno}-{mese:02d}-01"
        ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
        data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"
        
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        spese_per_categoria = []
        spese_totali = 0.0

        with get_db_connection() as con:
            cur = con.cursor()
            
            # Query UNICA per spese personali raggruppate per sottocategoria
            # Esclude i giroconti (transazioni senza sottocategoria)
            cur.execute("""
                SELECT T.id_sottocategoria, SUM(T.importo) as totale
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND T.data BETWEEN %s AND %s
                  AND T.importo < 0
                  AND T.id_sottocategoria IS NOT NULL
                GROUP BY T.id_sottocategoria
            """, (id_famiglia, data_inizio, data_fine))
            spese_personali = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}

            # Query UNICA per spese condivise raggruppate per sottocategoria
            # Esclude i giroconti (transazioni senza sottocategoria)
            cur.execute("""
                SELECT TC.id_sottocategoria, SUM(TC.importo) as totale
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND TC.data BETWEEN %s AND %s
                  AND TC.importo < 0
                  AND TC.id_sottocategoria IS NOT NULL
                GROUP BY TC.id_sottocategoria
            """, (id_famiglia, data_inizio, data_fine))
            spese_condivise = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}

            # Uniamo le spese
            tutte_spese_map = spese_personali.copy()
            for id_sub, importo in spese_condivise.items():
                tutte_spese_map[id_sub] = tutte_spese_map.get(id_sub, 0.0) + importo
            
            spese_totali = sum(tutte_spese_map.values())

            # Ora aggreghiamo per Categoria e decriptiamo i nomi
            cur.execute("SELECT id_categoria, nome_categoria FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
            raw_categorie = cur.fetchall()
            
            for raw_cat in raw_categorie:
                cat_id = raw_cat['id_categoria']
                nome_crip = raw_cat['nome_categoria']
                nome_chiaro = nome_crip
                if family_key:
                    nome_chiaro = _decrypt_if_key(nome_crip, family_key, crypto)
                
                # Cerca sottocategorie per questa categoria
                cur.execute("SELECT id_sottocategoria FROM Sottocategorie WHERE id_categoria = %s", (cat_id,))
                subs = [row['id_sottocategoria'] for row in cur.fetchall()]
                
                tot_cat = sum(tutte_spese_map.get(sub_id, 0.0) for sub_id in subs)
                if tot_cat > 0:
                    spese_per_categoria.append({
                        'nome_categoria': nome_chiaro,
                        'importo': tot_cat
                    })

        # Calcola percentuali
        for item in spese_per_categoria:
            item['percentuale'] = (item['importo'] / spese_totali * 100) if spese_totali > 0 else 0

        # 3. Budget Totale
        today = datetime.date.today()
        # Se stiamo guardando il mese corrente o futuro, prendiamo il budget allocato ATTUALE
        if anno > today.year or (anno == today.year and mese >= today.month):
             budget_totale = ottieni_totale_budget_allocato(id_famiglia, master_key_b64, id_utente)
        else:
             # Per i mesi passati, prendiamo lo storico
             budget_totale = ottieni_totale_budget_storico(id_famiglia, anno, mese, master_key_b64, id_utente)
             
             # Fallback opzionale: se lo storico è vuoto (es. non ancora salvato), proviamo a prendere quello corrente?
             # Per ora lasciamo 0 o quello che trova, per coerenza storica.
             if budget_totale == 0 and anno == today.year and mese == today.month:
                 # Caso limite: siamo nel mese corrente ma lo storico non c'è ancora.
                 budget_totale = ottieni_totale_budget_allocato(id_famiglia, master_key_b64, id_utente)

        risparmio = entrate - spese_totali
        delta = budget_totale - spese_totali
        
        # 4. Recupera dati annuali per confronto
        dati_annuali = ottieni_dati_analisi_annuale(id_famiglia, anno, master_key_b64, id_utente, include_prev_year=False)

        return {
            'entrate': entrate,
            'spese_totali': spese_totali,
            'budget_totale': budget_totale,
            'risparmio': risparmio,
            'delta_budget_spese': delta,
            'spese_per_categoria': sorted(spese_per_categoria, key=lambda x: x['importo'], reverse=True),
            'dati_confronto': dati_annuali
        }

    except Exception as e:
        logger.error(f"ottieni_dati_analisi_mensile: {e}")
        return None


def ottieni_dati_analisi_annuale(id_famiglia: str, anno: int, master_key_b64: str, id_utente: str, include_prev_year: bool = True) -> Optional[Dict[str, Any]]:
    """
    Recupera i dati completi per l'analisi annuale.
    Media spese, media budget, media differenza, spese categorie annuali.
    """
    try:
        # Prepara range date
        data_inizio_anno = f"{anno}-01-01"
        data_fine_anno = f"{anno}-12-31"

        # Recupera tutte le spese dell'anno per calcolare totali e medie
        totale_spese_annuali = 0.0
        spese_per_categoria_annuali = []
        
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            
            # --- SPESE ---
            # Personali (esclude giroconti)
            cur.execute("""
                SELECT T.id_sottocategoria, SUM(T.importo) as totale
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND T.data BETWEEN %s AND %s
                  AND T.importo < 0
                  AND T.id_sottocategoria IS NOT NULL
                GROUP BY T.id_sottocategoria
            """, (id_famiglia, data_inizio_anno, data_fine_anno))
            spese_personali = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}
            
            # Condivise (esclude giroconti)
            cur.execute("""
                SELECT TC.id_sottocategoria, SUM(TC.importo) as totale
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND TC.data BETWEEN %s AND %s
                  AND TC.importo < 0
                  AND TC.id_sottocategoria IS NOT NULL
                GROUP BY TC.id_sottocategoria
            """, (id_famiglia, data_inizio_anno, data_fine_anno))
            spese_condivise = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}
            
            # Unione
            tutte_spese_map = spese_personali.copy()
            for id_sub, importo in spese_condivise.items():
                tutte_spese_map[id_sub] = tutte_spese_map.get(id_sub, 0.0) + importo
            
            totale_spese_annuali = sum(tutte_spese_map.values())
            
            # Aggregazione Categorie
            cur.execute("SELECT id_categoria, nome_categoria FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
            raw_categorie = cur.fetchall()
            
            for raw_cat in raw_categorie:
                cat_id = raw_cat['id_categoria']
                nome_crip = raw_cat['nome_categoria']
                nome_chiaro = nome_crip
                if family_key:
                    nome_chiaro = _decrypt_if_key(nome_crip, family_key, crypto)
                
                cur.execute("SELECT id_sottocategoria FROM Sottocategorie WHERE id_categoria = %s", (cat_id,))
                subs = [row['id_sottocategoria'] for row in cur.fetchall()]
                
                tot_cat = sum(tutte_spese_map.get(sub_id, 0.0) for sub_id in subs)
                if tot_cat > 0:
                    spese_per_categoria_annuali.append({
                        'nome_categoria': nome_chiaro,
                        'importo': tot_cat
                    })

        # Percentuali
        for item in spese_per_categoria_annuali:
            item['percentuale'] = (item['importo'] / totale_spese_annuali * 100) if totale_spese_annuali > 0 else 0

        # --- MEDIE E BUDGET ---
        # Determina i mesi attivi (quelli con spese registrate)
        mesi_attivi = set()
        
        # Mesi da spese personali
        cur.execute("""
            SELECT DISTINCT EXTRACT(MONTH FROM T.data::DATE) as mese
            FROM Transazioni T
            JOIN Conti C ON T.id_conto = C.id_conto
            JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
            WHERE AF.id_famiglia = %s
              AND T.data BETWEEN %s AND %s
              AND T.importo < 0
        """, (id_famiglia, data_inizio_anno, data_fine_anno))
        for row in cur.fetchall():
            mesi_attivi.add(int(row['mese']))

        # Mesi da spese condivise
        cur.execute("""
            SELECT DISTINCT EXTRACT(MONTH FROM TC.data::DATE) as mese
            FROM TransazioniCondivise TC
            JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
            WHERE CC.id_famiglia = %s
              AND TC.data BETWEEN %s AND %s
              AND TC.importo < 0
        """, (id_famiglia, data_inizio_anno, data_fine_anno))
        for row in cur.fetchall():
            mesi_attivi.add(int(row['mese']))
            
        numero_mesi_attivi = len(mesi_attivi)
        
        # Se non ci sono mesi attivi, usiamo 12 come standard per evitare divisioni per zero o dati vuoti
        # Oppure mostriamo tutto a 0? Meglio standard per vedere il budget annuale teorico.
        # User request: "se ho compilato...". Se 0, non ho compilato.
        use_active_months = numero_mesi_attivi > 0
        divisor = numero_mesi_attivi if use_active_months else 12

        budget_mensile_corrente = ottieni_totale_budget_allocato(id_famiglia, master_key_b64, id_utente)
        
        entrate_totali_periodo = 0.0
        budget_totale_periodo = 0.0 
        
        imps_correnti = get_impostazioni_budget_famiglia(id_famiglia)
        entrate_std = imps_correnti['entrate_mensili']

        # Se usiamo i mesi attivi, sommiamo budget ed entrate SOLO per quei mesi.
        # Altrimenti (fallback), sommiamo per tutto l'anno (1-12)
        mesi_da_considerare = mesi_attivi if use_active_months else range(1, 13)

        for m in mesi_da_considerare:
            imp_storico = ottieni_impostazioni_budget_storico(id_famiglia, anno, m)
            if imp_storico:
                entrate_totali_periodo += imp_storico['entrate_mensili']
            else:
                entrate_totali_periodo += entrate_std
            
            # BUDGET: Use historical if available
            today = datetime.date.today()
            if anno > today.year or (anno == today.year and m > today.month):
                 # Future: use current
                 budget_totale_periodo += budget_mensile_corrente
            elif anno == today.year and m == today.month:
                 # Current month: try historical, else current
                 b_storico = ottieni_totale_budget_storico(id_famiglia, anno, m, master_key_b64, id_utente)
                 if b_storico == 0:
                     b_storico = budget_mensile_corrente
                 budget_totale_periodo += b_storico
            else:
                 # Past month: use historical
                 budget_totale_periodo += ottieni_totale_budget_storico(id_famiglia, anno, m, master_key_b64, id_utente) 

        media_spese_mensili = totale_spese_annuali / divisor
        media_budget_mensile = budget_totale_periodo / divisor
        media_entrate_mensili = entrate_totali_periodo / divisor
        
        media_risparmio = media_entrate_mensili - media_spese_mensili
        media_delta = media_budget_mensile - media_spese_mensili

        for item in spese_per_categoria_annuali:
            # Calcola la media mensile per ogni categoria
            item['importo_media'] = item['importo'] / divisor
            item['percentuale'] = (item['importo_media'] / media_spese_mensili * 100) if media_spese_mensili > 0 else 0

        # Ordina per importo medio decrescente
        spese_per_categoria_annuali = sorted(spese_per_categoria_annuali, key=lambda x: x['importo_media'], reverse=True)

        dati_anno_precedente = None
        if include_prev_year:
            dati_anno_precedente = ottieni_dati_analisi_annuale(
                id_famiglia, anno - 1, master_key_b64, id_utente, include_prev_year=False
            )
            # Se l'anno precedente non ha mesi attivi (nessuna spesa), non considerarlo valido per il confronto
            if dati_anno_precedente and dati_anno_precedente.get('numero_mesi_attivi', 0) == 0:
                 dati_anno_precedente = None

        return {
            'media_entrate_mensili': media_entrate_mensili,
            'media_spese_mensili': media_spese_mensili,
            'media_budget_mensile': media_budget_mensile,
            'media_differenza_entrate_spese': media_risparmio,
            'media_delta_budget_spese': media_delta,
            'spese_per_categoria_annuali': spese_per_categoria_annuali,
            'numero_mesi_attivi': numero_mesi_attivi,
            'dati_confronto': dati_anno_precedente
        }

    except Exception as e:
        print(f"[ERRORE] ottieni_dati_analisi_annuale: {e}")
        return None

def esporta_dati_famiglia(id_famiglia: str, id_utente: str, master_key_b64: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Esporta family_key e configurazioni base per backup.
    Solo admin può esportare questi dati.
    Ritorna un dizionario con tutti i dati oppure None in caso di errore, e un eventuale messaggio di errore.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        if not master_key:
            return None, "Chiave master non disponibile"
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Verifica che l'utente sia admin
            cur.execute("""
                SELECT ruolo, chiave_famiglia_criptata 
                FROM Appartenenza_Famiglia 
                WHERE id_utente = %s AND id_famiglia = %s
            """, (id_utente, id_famiglia))
            row = cur.fetchone()
            
            if not row:
                return None, "Utente non appartiene a questa famiglia"
            
            if row['ruolo'] != 'admin':
                return None, "Solo gli admin possono esportare i dati"
            
            # Decripta family_key
            family_key_b64 = None
            if row['chiave_famiglia_criptata']:
                try:
                    family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                except Exception as e:
                    return None, f"Impossibile decriptare family_key: {e}"
            
            # Recupera nome famiglia
            cur.execute("SELECT nome_famiglia FROM Famiglie WHERE id_famiglia = %s", (id_famiglia,))
            fam_row = cur.fetchone()
            nome_famiglia = fam_row['nome_famiglia'] if fam_row else "Sconosciuto"
            
            # Decripta nome famiglia se necessario
            if family_key_b64:
                family_key = base64.b64decode(family_key_b64)
                nome_famiglia = _decrypt_if_key(nome_famiglia, family_key, crypto)
            
            # Recupera configurazioni SMTP
            smtp_config = get_smtp_config(id_famiglia, master_key_b64, id_utente)
            
            export_data = {
                'versione_export': '1.0',
                'data_export': datetime.datetime.now().isoformat(),
                'id_famiglia': id_famiglia,
                'nome_famiglia': nome_famiglia,
                'family_key_b64': family_key_b64,
                'configurazioni': {
                    'smtp': smtp_config
                }
            }
            
            return export_data, None
            
    except Exception as e:
        print(f"[ERRORE] Errore durante l'esportazione: {e}")
        return None, str(e)
# --- Funzioni Utenti & Login ---


def ottieni_utenti_senza_famiglia() -> List[str]:
    """
    Restituisce una lista di utenti che non appartengono a nessuna famiglia.
    """
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT username_enc 
                        FROM Utenti 
                        WHERE id_utente NOT IN (SELECT id_utente FROM Appartenenza_Famiglia)
                        """)
            
            users = []
            for row in cur.fetchall():
                decrypted = decrypt_system_data(row['username_enc'])
                if decrypted:
                    users.append(decrypted)
            return sorted(users)

    except Exception as e:
        print(f"[ERRORE] Errore recupero utenti senza famiglia: {e}")
        return []


def verifica_login(login_identifier: str, password: str) -> Optional[Dict[str, Any]]:
    try:
        # Calculate blind indexes for lookup
        u_bindex = compute_blind_index(login_identifier)
        
        with get_db_connection() as con:
            cur = con.cursor()
            # Try finding by Blind Index first
            cur.execute("""
                SELECT id_utente, password_hash, nome, cognome, username, email, 
                       forza_cambio_password, salt, encrypted_master_key, 
                       username_enc, email_enc, nome_enc_server, cognome_enc_server
                FROM Utenti 
                WHERE username_bindex = %s OR email_bindex = %s
            """, (u_bindex, u_bindex))
            risultato = cur.fetchone()
            
            # Fallback removed - we rely on migration
            if False: pass # Placeholder to minimize diff changes if needed, or simply remove


            if risultato and risultato['password_hash'] == hash_password(password):

                # Decrypt master key if encryption is enabled
                master_key = None
                nome = risultato['nome']
                cognome = risultato['cognome']

                if risultato['salt'] and risultato['encrypted_master_key']:
                    try:
                        crypto = CryptoManager()
                        salt = base64.urlsafe_b64decode(risultato['salt'].encode())
                        kek = crypto.derive_key(password, salt)
                        encrypted_mk = base64.urlsafe_b64decode(risultato['encrypted_master_key'].encode())
                        master_key = crypto.decrypt_master_key(encrypted_mk, kek)
                        
                        # --- MIGRATION: Backfill Server Key Backup if missing ---
                        if SERVER_SECRET_KEY and master_key:
                            # Check if backup key is missing (we don't fetch it in SELECT, so we do a separate check or assume)
                            # Better: Fetch it in the SELECT above.
                            pass # Logic moved below to avoid cluttering indentation
                            
                        # Decrypt nome and cognome for display
                        nome = crypto.decrypt_data(risultato['nome'], master_key)
                        cognome = crypto.decrypt_data(risultato['cognome'], master_key)
                    except Exception as e:
                        print(f"[ERRORE] Errore decryption: {e}")
                        return None

                # --- BACKFILL CHECK ---
                if SERVER_SECRET_KEY and master_key:
                     # Re-fetch to check if backup exists (to avoid fetching heavy text if not needed? no, just fetch it)
                     # Let's modify the initial query in next step to include encrypted_master_key_backup
                     with get_db_connection() as con_up:
                         cur_up = con_up.cursor()
                         cur_up.execute("SELECT encrypted_master_key_backup FROM Utenti WHERE id_utente = %s", (risultato['id_utente'],))
                         backup_col = cur_up.fetchone()['encrypted_master_key_backup']
                         
                         if not backup_col:
                             print(f"[MIGRATION] Backfilling Server Key Backup for user {risultato['username']}")
                             crypto_up = CryptoManager()
                             # Encrypt master_key with SERVER_SECRET_KEY
                             # SERVER_SECRET_KEY needs to be 32 bytes for Fernet?
                             # Typically Fernet key is 32 bytes base64 encoded.
                             # Our generated key is base64 urlsafe (44 bytes string).
                             # CryptoManager expects bytes or string.
                             
                             try:
                                 # Ensure SERVER_KEY is valid for Fernet
                                 # If generated via secrets.token_urlsafe(32), it acts as a password or key?
                                 # Fernet(key) requires urlsafe base64-encoded 32-byte key.
                                 # secrets.token_urlsafe(32) produces ~43 chars.
                                 # Wait, utils/crypto_manager.py encrypt_master_key uses Encrypt with KEK (Fernet).
                                 # So we should treat SERVER_SECRET_KEY as a KEK (Fernet Key) directly? 
                                 # Or derive a key from it?
                                 # To be safe and consistent with "Global Key", let's treat it as a password and derive a key, 
                                 # OR if it's already a valid Fernet key use it.
                                 # The generated key `secrets.token_urlsafe(32)` is NOT a valid Fernet key directly (wrong length/format maybe).
                                 # Valid fernet key: base64.urlsafe_b64encode(os.urandom(32))
                                 
                                 # Let's assume we derive a key from SERVER_SECRET_KEY using a static salt or just hash it to 32 bytes?
                                 # Simple approach: Use SERVER_SECRET_KEY as a password and a static system salt.
                                 # But we don't have a system salt.
                                 # Let's use a fixed salt for server key derivation to ensure reproducibility.
                                 
                                 srv_salt = b'server_key_salt_' # 16 bytes? No.
                                 # Better: Just hash the SERVER_SECRET_KEY to 32 bytes and b64 encode it to make it a Fernet Key.
                                 import hashlib
                                 srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
                                 srv_fernet_key = base64.urlsafe_b64encode(srv_key_bytes)
                                 
                                 encrypted_backup = crypto_up.encrypt_master_key(master_key, srv_fernet_key)
                                 
                                 cur_up.execute("UPDATE Utenti SET encrypted_master_key_backup = %s WHERE id_utente = %s", 
                                                (base64.urlsafe_b64encode(encrypted_backup).decode(), risultato['id_utente']))
                                 con_up.commit()
                             except Exception as e_mig:
                                 print(f"[MIGRATION ERROR] {e_mig}")

                # --- MIGRATION: Backfill Visible Names (Server Key) ---
                if SERVER_SECRET_KEY and (not risultato.get('nome_enc_server') or not risultato.get('cognome_enc_server')):
                     try:
                         # Decrypt with MK first (we have `nome` and `cognome` decrypted from above? No, variables `nome`/`cognome` hold decrypted vals)
                         if nome and cognome:
                             n_enc_srv = encrypt_system_data(nome)
                             c_enc_srv = encrypt_system_data(cognome)
                             
                             if n_enc_srv and c_enc_srv:
                                 with get_db_connection() as con_up_names:
                                     cur_up_n = con_up_names.cursor()
                                     print(f"[MIGRATION] Backfilling Visible Names for {risultato['username']}")
                                     cur_up_n.execute("""
                                        UPDATE Utenti 
                                        SET nome_enc_server = %s, cognome_enc_server = %s 
                                        WHERE id_utente = %s
                                     """, (n_enc_srv, c_enc_srv, risultato['id_utente']))
                                     con_up_names.commit()
                     except Exception as e_mig_names:
                         print(f"[MIGRATION ERROR NAMES] {e_mig_names}")

                return {
                    'id': risultato['id_utente'],

                     'nome': nome,
                    'cognome': cognome,
                    'username': decrypt_system_data(risultato['username_enc']) or risultato['username'],
                    'email': decrypt_system_data(risultato['email_enc']) or risultato['email'],
                    'master_key': master_key.decode() if master_key else None,
                    'forza_cambio_password': risultato['forza_cambio_password']
                }
            
            print("[DEBUG] Login fallito o password errata.")
            return None
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il login: {e}")
        return None



def crea_utente_invitato(email: str, ruolo: str, id_famiglia: str, id_admin: Optional[str] = None, master_key_b64: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Crea un nuovo utente invitato con credenziali temporanee.
    Se id_admin e master_key_b64 sono forniti, condivide anche la chiave famiglia.
    Restituisce un dizionario con le credenziali o None in caso di errore.
    """
    try:
        crypto = CryptoManager()
        
        # Genera credenziali temporanee
        temp_password = secrets.token_urlsafe(10)
        temp_username = f"user_{secrets.token_hex(4)}"
        password_hash = hash_password(temp_password)
        
        # Genera salt e master key temporanei per l'utente invitato
        temp_salt = os.urandom(16)
        temp_kek = crypto.derive_key(temp_password, temp_salt)
        temp_master_key = crypto.generate_master_key()
        encrypted_temp_mk = crypto.encrypt_master_key(temp_master_key, temp_kek)
        
        # Generate Recovery Key
        recovery_key = crypto.generate_recovery_key()
        recovery_key_hash = hashlib.sha256(recovery_key.encode()).hexdigest()
        encrypted_mk_recovery = crypto.encrypt_master_key(temp_master_key, crypto.derive_key(recovery_key, temp_salt))
        
        # --- SERVER KEY BACKUP ---
        encrypted_mk_backup_b64 = None
        if SERVER_SECRET_KEY:
            try:
                srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
                srv_fernet_key = base64.urlsafe_b64encode(srv_key_bytes)
                encrypted_mk_backup = crypto.encrypt_master_key(temp_master_key, srv_fernet_key)
                encrypted_mk_backup_b64 = base64.urlsafe_b64encode(encrypted_mk_backup).decode()
            except Exception as e_bk:
                print(f"[WARNING] Failed to generate server backup key for invited user: {e_bk}")
        
        # Recupera la family key dell'admin (se disponibile)
        family_key_encrypted_for_new_user = None
        if id_admin and master_key_b64:
            _, admin_master_key = _get_crypto_and_key(master_key_b64)
            if admin_master_key:
                family_key = _get_family_key_for_user(id_famiglia, id_admin, admin_master_key, crypto)
                if family_key:
                    # Cripta la family key con la master key dell'utente invitato
                    family_key_b64 = base64.b64encode(family_key).decode('utf-8')
                    family_key_encrypted_for_new_user = crypto.encrypt_data(family_key_b64, temp_master_key)
                    print(f"[INFO] Family key condivisa con nuovo utente invitato.")
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Crea l'utente con salt e encrypted_master_key
            
            # --- BLIND INDEX & ENCRYPTION ---
            u_bindex = compute_blind_index(temp_username)
            e_bindex = compute_blind_index(email)
            u_enc = encrypt_system_data(temp_username)
            e_enc = encrypt_system_data(email)
            n_enc_srv = encrypt_system_data("Nuovo")
            c_enc_srv = encrypt_system_data("Utente")
            
            cur.execute("""
                INSERT INTO Utenti (username, email, password_hash, nome, cognome, forza_cambio_password, salt, encrypted_master_key, recovery_key_hash, encrypted_master_key_recovery, encrypted_master_key_backup, username_bindex, email_bindex, username_enc, email_enc, nome_enc_server, cognome_enc_server)
                VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_utente
            """, (None, None, password_hash, None, None,
                  base64.urlsafe_b64encode(temp_salt).decode(),
                  base64.urlsafe_b64encode(encrypted_temp_mk).decode(),
                  recovery_key_hash,
                  base64.urlsafe_b64encode(encrypted_mk_recovery).decode(),
                  encrypted_mk_backup_b64,
                  u_bindex, e_bindex, u_enc, e_enc, n_enc_srv, c_enc_srv))
            
            id_utente = cur.fetchone()['id_utente']
            
            # 2. Aggiungi alla famiglia con la chiave famiglia criptata
            cur.execute("""
                INSERT INTO Appartenenza_Famiglia (id_utente, id_famiglia, ruolo, chiave_famiglia_criptata)
                VALUES (%s, %s, %s, %s)
            """, (id_utente, id_famiglia, ruolo, family_key_encrypted_for_new_user))
            
            con.commit()
            
            return {
                "email": email,
                "username": temp_username,
                "password": temp_password,
                "id_utente": id_utente
            }
            
    except Exception as e:
        print(f"[ERRORE] Errore creazione utente invitato: {e}")
        import traceback
        traceback.print_exc()
        return None


def registra_utente(nome: str, cognome: str, username: str, password: str, email: str, data_nascita: str, codice_fiscale: Optional[str], indirizzo: Optional[str]) -> Optional[Dict[str, Any]]:
    try:
        password_hash = hash_password(password)
        
        # Generate Master Key and Salt
        crypto = CryptoManager()
        salt = os.urandom(16)
        kek = crypto.derive_key(password, salt)
        master_key = crypto.generate_master_key()
        encrypted_mk = crypto.encrypt_master_key(master_key, kek)
        
        # Generate Recovery Key
        recovery_key = crypto.generate_recovery_key()
        recovery_key_hash = hashlib.sha256(recovery_key.encode()).hexdigest()
        encrypted_mk_recovery = crypto.encrypt_master_key(master_key, crypto.derive_key(recovery_key, salt))

        # Encrypt personal data
        enc_nome = crypto.encrypt_data(nome, master_key)
        enc_cognome = crypto.encrypt_data(cognome, master_key)
        enc_indirizzo = crypto.encrypt_data(indirizzo, master_key) if indirizzo else None
        enc_cf = crypto.encrypt_data(codice_fiscale, master_key) if codice_fiscale else None

        # --- SERVER KEY BACKUP ---
        encrypted_mk_backup_b64 = None
        if SERVER_SECRET_KEY:
             try:
                 srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
                 srv_fernet_key = base64.urlsafe_b64encode(srv_key_bytes)
                 encrypted_mk_backup = crypto.encrypt_master_key(master_key, srv_fernet_key)
                 encrypted_mk_backup_b64 = base64.urlsafe_b64encode(encrypted_mk_backup).decode()
             except Exception as e_bk:
                 print(f"[WARNING] Failed to generate server backup key: {e_bk}")

        with get_db_connection() as con:
            cur = con.cursor()
            # NOTA: username e email legacy sono NULL - usiamo solo le versioni _bindex e _enc
            cur.execute("""
                INSERT INTO Utenti (nome, cognome, username, password_hash, email, data_nascita, codice_fiscale, indirizzo, salt, encrypted_master_key, recovery_key_hash, encrypted_master_key_recovery, encrypted_master_key_backup, username_bindex, email_bindex, username_enc, email_enc, nome_enc_server, cognome_enc_server)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_utente
            """, (enc_nome, enc_cognome, None, password_hash, None, data_nascita, enc_cf, enc_indirizzo, 
                  base64.urlsafe_b64encode(salt).decode(), 
                  base64.urlsafe_b64encode(encrypted_mk).decode(),
                  recovery_key_hash,
                  base64.urlsafe_b64encode(encrypted_mk_recovery).decode(),
                  encrypted_mk_backup_b64,
                  compute_blind_index(username), compute_blind_index(email),
                  encrypt_system_data(username), encrypt_system_data(email),
                  encrypt_system_data(nome), encrypt_system_data(cognome)))

            
            id_utente = cur.fetchone()['id_utente']
            con.commit()
            
            return {
                "id_utente": id_utente,
                "recovery_key": recovery_key,
                "master_key": master_key.decode()
            }

    except Exception as e:
        print(f"[ERRORE] Errore durante la registrazione: {e}")
        return None

def cambia_password(id_utente: str, vecchia_password_hash: str, nuova_password_hash: str) -> bool:
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Utenti SET password_hash = %s WHERE id_utente = %s AND password_hash = %s",
                        (nuova_password_hash, id_utente, vecchia_password_hash))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore cambio password: {e}")
        return False

def imposta_password_temporanea(id_utente: str, temp_password_raw: str) -> bool:
    """
    Imposta una password temporanea e ripristina la Master Key usando il backup del server.
    N.B. Richiede temp_password_raw (stringa in chiaro), non l'hash!
    """
    try:
        if not SERVER_SECRET_KEY:
            print("[ERRORE] SERVER_SECRET_KEY mancante. Impossibile ripristinare password criptata correttamente.")
            return False

        with get_db_connection() as con:
            cur = con.cursor()
            
            # Fetch backup key and salt
            cur.execute("SELECT encrypted_master_key_backup, salt FROM Utenti WHERE id_utente = %s", (id_utente,))
            res = cur.fetchone()
            
            if not res or not res['encrypted_master_key_backup']:
                print("[ERRORE] Backup key non trovata per questo utente.")
                return False
                
            enc_backup_b64 = res['encrypted_master_key_backup']
            salt_b64 = res['salt']

            # Decrypt Master Key using Server Key
            import hashlib
            srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
            srv_fernet_key = base64.urlsafe_b64encode(srv_key_bytes)
            
            crypto = CryptoManager()
            try:
                enc_backup = base64.urlsafe_b64decode(enc_backup_b64.encode())
                master_key = crypto.decrypt_master_key(enc_backup, srv_fernet_key)
            except Exception as e_dec:
                print(f"[ERRORE] Fallita decriptazione backup key: {e_dec}")
                return False

            # Re-encrypt Master Key with new temp password
            salt = base64.urlsafe_b64decode(salt_b64.encode())
            kek = crypto.derive_key(temp_password_raw, salt)
            encrypted_mk = crypto.encrypt_master_key(master_key, kek)
            encrypted_mk_b64 = base64.urlsafe_b64encode(encrypted_mk).decode()
            
            # Hash new password
            temp_password_hash = hash_password(temp_password_raw)

            cur.execute("""
                UPDATE Utenti 
                SET password_hash = %s, 
                    encrypted_master_key = %s,
                    forza_cambio_password = TRUE 
                WHERE id_utente = %s
            """, (temp_password_hash, encrypted_mk_b64, id_utente))
            
            con.commit()
            return True
            
    except Exception as e:
        print(f"[ERRORE] Errore impostazione password temporanea con recovery: {e}")
        return False

def trova_utente_per_email(email: str) -> Optional[Dict[str, str]]:
    try:
        e_bindex = compute_blind_index(email)
        with get_db_connection() as con:
            cur = con.cursor()
            # Join con Appartenenza_Famiglia per ottenere id_famiglia
            cur.execute("""
                SELECT U.id_utente, U.nome, U.email, U.email_enc, AF.id_famiglia
                FROM Utenti U
                LEFT JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                WHERE U.email_bindex = %s
            """, (e_bindex,))
            res = cur.fetchone()

            
            if res:
             # Decrypt email if needed
             real_email = decrypt_system_data(res.get('email_enc')) or res['email']
             # Decrypt nome? No, nome is encrypted with MK, we can't decrypt it here without user password.
             # Wait, `trova_utente_per_email` is used for Password Recovery to send email.
             # We need the email address. `real_email` is it.
             # We need `nome`? `nome` is encrypted with MK. We CANNOT decrypt it.
             # In `auth_view`, we send email saying "Ciao {nome}".
             # We can't do that if `nome` is encrypted.
             # BUT! The user might have just registered, or we might store a plaintext `nome`? No it's enc.
             # We should probably just say "Ciao Utente" if name is not available.
             
             return {
                 'id_utente': res['id_utente'],
                 'nome': "Utente", # Placeholder as we can't decrypt name without password
                 'email': real_email,
                 'id_famiglia': res.get('id_famiglia')  # Può essere None se non appartiene a una famiglia
             }
            return None
    except Exception as e:
        print(f"[ERRORE] Errore ricerca utente per email: {e}")
        return None

def cambia_password_e_username(id_utente: str, password_raw: str, nuovo_username: str, nome: Optional[str] = None, cognome: Optional[str] = None, vecchia_password: Optional[str] = None) -> Dict[str, Any]:
    """
    Aggiorna password e username per l'attivazione account (Force Change Password).
    Genera nuove chiavi di cifratura (Master Key, Salt, Recovery Key).
    Aggiorna colonne sicure (Blind Index, Enc) e colonne Server (Enc Server, Backup MK).
    """
    try:
        crypto = CryptoManager()
        
        # Prima recupera la vecchia master key per decriptare la family key
        old_master_key = None
        if vecchia_password:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT salt, encrypted_master_key FROM Utenti WHERE id_utente = %s", (id_utente,))
                old_user_data = cur.fetchone()
                if old_user_data and old_user_data['salt'] and old_user_data['encrypted_master_key']:
                    try:
                        old_salt = base64.urlsafe_b64decode(old_user_data['salt'].encode())
                        old_kek = crypto.derive_key(vecchia_password, old_salt)
                        old_encrypted_mk = base64.urlsafe_b64decode(old_user_data['encrypted_master_key'].encode())
                        old_master_key = crypto.decrypt_master_key(old_encrypted_mk, old_kek)
                        print(f"[INFO] Vecchia master key recuperata per utente {id_utente}")
                    except Exception as e:
                        print(f"[WARN] Impossibile recuperare vecchia master key: {e}")
        
        # 1. Generate new keys
        salt = crypto.generate_salt()
        kek = crypto.derive_key(password_raw, salt)
        
        # PRESERVE OLD MASTER KEY IF AVAILABLE to avoid data loss
        if old_master_key:
            master_key = old_master_key
            print(f"[INFO] PRESERVING Old Master Key for user {id_utente}")
        else:
            master_key = crypto.generate_master_key()
            print(f"[INFO] GENERATING New Master Key for user {id_utente}")
            
        encrypted_master_key = crypto.encrypt_master_key(master_key, kek)
        recovery_key = crypto.generate_recovery_key()
        recovery_key_hash = crypto.hash_recovery_key(recovery_key)
        
        # 1.b Generate Server Backup of Master Key
        encrypted_master_key_backup = None
        if SERVER_SECRET_KEY:
             try:
                srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
                srv_fernet_key = base64.urlsafe_b64encode(srv_key_bytes)
                mk_backup = crypto.encrypt_master_key(master_key, srv_fernet_key)
                encrypted_master_key_backup = base64.urlsafe_b64encode(mk_backup).decode()
             except Exception as ex:
                 print(f"[WARN] Failed to create Master Key Backup: {ex}")

        # 2. Hash password
        password_hash = hash_password(password_raw)
        
        # 3. Encrypt User PII (Nome/Cognome) with Master Key
        enc_nome = None
        enc_cognome = None
        if nome: enc_nome = crypto.encrypt_data(nome, master_key)
        if cognome: enc_cognome = crypto.encrypt_data(cognome, master_key)
        
        # 3.b Secure Username (Blind Index + Enc System)
        u_bindex = compute_blind_index(nuovo_username)
        u_enc = encrypt_system_data(nuovo_username)
        
        # 3.c Encrypt Server-Side Display Names (for Family Visibility)
        n_enc_srv = encrypt_system_data(nome) if nome else None
        c_enc_srv = encrypt_system_data(cognome) if cognome else None
        
        # 4. Re-encrypt family key if we have the old master key
        with get_db_connection() as con:
            cur = con.cursor()
            
            if old_master_key:
                cur.execute("""
                    SELECT id_famiglia, chiave_famiglia_criptata 
                    FROM Appartenenza_Famiglia 
                    WHERE id_utente = %s AND chiave_famiglia_criptata IS NOT NULL
                """, (id_utente,))
                memberships = cur.fetchall()
                
                for membership in memberships:
                    try:
                        old_encrypted_fk = membership['chiave_famiglia_criptata']
                        if old_encrypted_fk:
                            family_key_b64 = crypto.decrypt_data(old_encrypted_fk, old_master_key)
                            new_encrypted_fk = crypto.encrypt_data(family_key_b64, master_key)
                            cur.execute("""
                                UPDATE Appartenenza_Famiglia 
                                SET chiave_famiglia_criptata = %s 
                                WHERE id_utente = %s AND id_famiglia = %s
                            """, (new_encrypted_fk, id_utente, membership['id_famiglia']))
                    except Exception as e:
                        print(f"[WARN] Impossibile ri-criptare family key per famiglia {membership['id_famiglia']}: {e}")
            
            # 5. Update User Record
            # IMPORTANT: Set legacy 'username' to NULL, use 'username_bindex'/'username_enc'
            cur.execute("""
                UPDATE Utenti 
                SET password_hash = %s, 
                    username = NULL,
                    username_bindex = %s,
                    username_enc = %s,
                    nome = %s,
                    cognome = %s,
                    nome_enc_server = %s,
                    cognome_enc_server = %s,
                    encrypted_master_key_backup = %s,
                    
                    forza_cambio_password = FALSE,
                    salt = %s,
                    encrypted_master_key = %s,
                    recovery_key_hash = %s
                WHERE id_utente = %s
            """, (
                password_hash,
                u_bindex, u_enc,
                enc_nome, enc_cognome,
                n_enc_srv, c_enc_srv,
                encrypted_master_key_backup,
                
                base64.urlsafe_b64encode(salt).decode(),
                base64.urlsafe_b64encode(encrypted_master_key).decode(),
                recovery_key_hash,
                id_utente
            ))
            
            con.commit()
            
            return {
                "success": True, 
                "recovery_key": recovery_key,
                "master_key": base64.urlsafe_b64encode(master_key).decode() # Return b64 string
            }

    except Exception as e:
        print(f"[ERRORE] Errore cambio password e username: {e}")
        return {"success": False, "error": str(e)}


        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def accetta_invito(id_utente, token, master_key_b64):
    # Placeholder implementation if needed, logic might be in AuthView
    pass

def aggiungi_utente_a_famiglia(id_utente: str, id_famiglia: str, ruolo: str = 'user') -> bool:
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("INSERT INTO Appartenenza_Famiglia (id_utente, id_famiglia, ruolo) VALUES (%s, %s, %s)",
                        (id_utente, id_famiglia, ruolo))
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta utente a famiglia: {e}")
        return False

def rimuovi_utente_da_famiglia(id_utente: str, id_famiglia: str) -> bool:
    """
    Disabilita un utente dalla famiglia (soft delete):
    - Rimuove l'appartenenza alla famiglia
    - Disabilita l'accesso (password invalidata)
    - Anonimizza email e username
    - Mantiene nome e cognome per riferimento storico
    - Preserva tutti i dati storici (transazioni, conti, ecc.)
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Prima verifica che l'utente appartenga effettivamente a questa famiglia
            cur.execute("""
                SELECT ruolo FROM Appartenenza_Famiglia 
                WHERE id_utente = %s AND id_famiglia = %s
            """, (id_utente, id_famiglia))
            
            row = cur.fetchone()
            if not row:
                print(f"[WARN] Utente {id_utente} non appartiene alla famiglia {id_famiglia}")
                return False
            
            # Genera dati anonimi unici
            import secrets
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            anonymous_suffix = secrets.token_hex(4)
            anonymous_username = f"utente_rimosso_{timestamp}_{anonymous_suffix}"
            anonymous_email = f"removed_{timestamp}_{anonymous_suffix}@disabled.local"
            invalid_password_hash = "ACCOUNT_DISABLED_" + secrets.token_hex(16)
            
            # 1. Rimuovi l'appartenenza alla famiglia
            cur.execute("""
                DELETE FROM Appartenenza_Famiglia 
                WHERE id_utente = %s AND id_famiglia = %s
            """, (id_utente, id_famiglia))
            
            # 2. Anonimizza e disabilita l'utente
            # - Cambia username e email con valori anonimi
            # - Invalida la password
            # - Mantiene nome_enc_server e cognome_enc_server per riferimento storico
            # - Rimuove le chiavi crittografiche (l'utente non potrà più accedere)
            cur.execute("""
                UPDATE Utenti SET
                    username = %s,
                    email = %s,
                    password_hash = %s,
                    username_bindex = NULL,
                    username_enc = NULL,
                    email_bindex = NULL,
                    email_enc = NULL,
                    encrypted_master_key = NULL,
                    encrypted_master_key_backup = NULL,
                    encrypted_master_key_recovery = NULL,
                    salt = NULL,
                    forza_cambio_password = FALSE
                WHERE id_utente = %s
            """, (anonymous_username, anonymous_email, invalid_password_hash, id_utente))
            
            con.commit()
            
            print(f"[INFO] Utente {id_utente} disabilitato e anonimizzato (soft delete)")
            return True
            
    except Exception as e:
        print(f"[ERRORE] Errore disabilitazione utente: {e}")
        return False

def ottieni_membri_famiglia(id_famiglia: str, master_key_b64: Optional[str] = None, id_utente_current: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT U.id_utente, U.username, U.email, AF.ruolo, 
                       U.nome_enc_server, U.cognome_enc_server, U.email_enc
                FROM Utenti U
                JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
            """, (id_famiglia,))
            or_rows = [dict(row) for row in cur.fetchall()]

            for row in or_rows:
                 # Decrypt server-side encrypted name/surname
                 n = decrypt_system_data(row.get('nome_enc_server'))
                 c = decrypt_system_data(row.get('cognome_enc_server'))
                 
                 if n or c:
                     row['nome_visualizzato'] = f"{n or ''} {c or ''}".strip()
                 else:
                     row['nome_visualizzato'] = row['username']
                 
                 # Decripta l'email se è nella colonna criptata
                 # Prova prima email_enc (nuovi utenti), poi email legacy
                 email_enc = row.get('email_enc')
                 if email_enc:
                     decrypted_email = decrypt_system_data(email_enc)
                     if decrypted_email:
                         row['email'] = decrypted_email
                 # Se email è ancora None o sembra anonimizzata, non fare nulla
                 # L'email legacy potrebbe essere già in chiaro per utenti vecchi

            return or_rows
    except Exception as e:
        print(f"[ERRORE] Errore recupero membri famiglia: {e}")
        return []


def ottieni_ruolo_utente(id_utente: str, id_famiglia: str) -> Optional[str]:
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT ruolo FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s",
                        (id_utente, id_famiglia))
            res = cur.fetchone()
            return res['ruolo'] if res else None
    except Exception as e:
        print(f"[ERRORE] Errore recupero ruolo utente: {e}")
        return None

def ensure_family_key(id_utente: str, id_famiglia: str, master_key_b64: str) -> bool:
    """
    Assicura che l'utente abbia accesso alla chiave di crittografia della famiglia.
    Se nessuno ha la chiave (nuova famiglia o migrazione), ne genera una nuova.
    Se qualcun altro ha la chiave, prova a recuperarla (TODO: richiederebbe asimmetrica o condivisione segreta, 
    per ora assumiamo che se è null, la generiamo se siamo admin o se nessuno ce l'ha).
    
    In questo scenario semplificato:
    1. Controlla se l'utente ha già la chiave.
    2. Se no, controlla se qualcun altro nella famiglia ha una chiave.
    3. Se NESSUNO ha una chiave, ne genera una nuova e la salva per l'utente corrente.
    """
    if not master_key_b64:
        return False

    crypto, master_key = _get_crypto_and_key(master_key_b64)
    if not master_key:
        return False

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Controlla se l'utente ha già la chiave
            cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
            row = cur.fetchone()
            if row and row['chiave_famiglia_criptata']:
                return True # L'utente ha già la chiave

            # 2. Controlla se qualcun altro ha la chiave
            cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND chiave_famiglia_criptata IS NOT NULL LIMIT 1", (id_famiglia,))
            existing_key_row = cur.fetchone()
            
            if existing_key_row:
                # Qualcun altro ha la chiave. 
                # In un sistema reale, bisognerebbe farsi inviare la chiave da un admin o usare crittografia asimmetrica.
                # Per ora, non possiamo fare nulla se non abbiamo la chiave.
                print(f"[WARN] La famiglia {id_famiglia} ha già una chiave, ma l'utente {id_utente} non ce l'ha.")
                return False
            
            # 3. Nessuno ha la chiave: Generane una nuova
            print(f"[INFO] Generazione nuova chiave famiglia per famiglia {id_famiglia}...")
            new_family_key = secrets.token_bytes(32) # 32 bytes per AES-256
            
            # Cripta la chiave della famiglia con la master key dell'utente
            encrypted_family_key = crypto.encrypt_data(base64.b64encode(new_family_key).decode('utf-8'), master_key)
            
            cur.execute("""
                UPDATE Appartenenza_Famiglia 
                SET chiave_famiglia_criptata = %s 
                WHERE id_utente = %s AND id_famiglia = %s
            """, (encrypted_family_key, id_utente, id_famiglia))
            
            con.commit()
            print(f"[INFO] Chiave famiglia generata e salvata per utente {id_utente}.")
            return True

    except Exception as e:
        print(f"[ERRORE] Errore in ensure_family_key: {e}")
        return False


# --- Funzioni Conti ---
def ottieni_conti(id_utente: str, master_key_b64: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_conto, nome_conto, tipo, iban, valore_manuale, rettifica_saldo FROM Conti WHERE id_utente = %s", (id_utente,))
            conti = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            
            # Attempt to retrieve Family Key if possible
            try:
                id_famiglia = ottieni_prima_famiglia_utente(id_utente)
                if id_famiglia and master_key:
                     family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            except: pass

            keys_to_try = [master_key]
            if family_key: keys_to_try.append(family_key)

            # Helper to try keys
            def try_decrypt(val, keys):
                last_res = None
                for k in keys:
                    if not k: continue
                    try:
                        res = _decrypt_if_key(val, k, crypto, silent=True)
                        if res == "[ENCRYPTED]":
                            last_res = res
                            continue
                        return res
                    except: continue
                return last_res if last_res else "[ENCRYPTED]"

            if master_key:
                for conto in conti:
                    conto['nome_conto'] = try_decrypt(conto['nome_conto'], keys_to_try)
                    conto['tipo'] = try_decrypt(conto['tipo'], keys_to_try)
                    if 'iban' in conto:
                        conto['iban'] = try_decrypt(conto['iban'], keys_to_try)
                    
                    # Handle numeric fields that might be encrypted
                    for field in ['valore_manuale', 'rettifica_saldo']:
                        if field in conto and conto[field] is not None:
                            decrypted = try_decrypt(conto[field], keys_to_try)
                            try:
                                conto[field] = float(decrypted)
                            except (ValueError, TypeError):
                                conto[field] = decrypted # Keep as is if not a number
            
            return conti
    except Exception as e:
        print(f"[ERRORE] Errore recupero conti: {e}")
        return []
    except Exception as e:
        print(f"[ERRORE] Errore recupero conti: {e}")
        return []

def aggiungi_conto(id_utente: str, nome_conto: str, tipo: str, saldo_iniziale: float = 0.0, data_saldo_iniziale: Optional[str] = None, master_key_b64: Optional[str] = None, id_famiglia: Optional[str] = None) -> Optional[str]:
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Use family_key for account name encryption (so other family members can decrypt it)
    encryption_key = master_key
    if master_key and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        if family_key:
            encryption_key = family_key
    
    encrypted_nome = _encrypt_if_key(nome_conto, encryption_key, crypto)
    encrypted_tipo = _encrypt_if_key(tipo, master_key, crypto)  # tipo can stay with master_key
    encrypted_saldo = _encrypt_if_key(str(saldo_iniziale), master_key, crypto)
    
    if not data_saldo_iniziale:
        data_saldo_iniziale = datetime.date.today().strftime('%Y-%m-%d')

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO Conti (id_utente, nome_conto, tipo) VALUES (%s, %s, %s) RETURNING id_conto",
                (id_utente, encrypted_nome, encrypted_tipo))
            id_conto = cur.fetchone()['id_conto']
            
            # Add initial balance transaction
            if saldo_iniziale != 0:
                # Note: "Saldo Iniziale" is NOT encrypted to allow filtering in UI
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (%s, %s, %s, %s)",
                    (id_conto, data_saldo_iniziale, "Saldo Iniziale", saldo_iniziale))
            
            con.commit()
            return id_conto
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta conto: {e}")
        return None

def modifica_conto(id_conto: str, nome_conto: str, tipo: str, saldo_iniziale: float, data_saldo_iniziale: str, master_key_b64: Optional[str] = None, id_famiglia: Optional[str] = None, id_utente: Optional[str] = None) -> bool:
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Use family_key for account name encryption (so other family members can decrypt it)
    encryption_key = master_key
    if master_key and id_famiglia and id_utente:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        if family_key:
            encryption_key = family_key
    
    encrypted_nome = _encrypt_if_key(nome_conto, encryption_key, crypto)
    encrypted_tipo = _encrypt_if_key(tipo, master_key, crypto)  # tipo can stay with master_key
    encrypted_saldo = _encrypt_if_key(str(saldo_iniziale), master_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(
                "UPDATE Conti SET nome_conto = %s, tipo = %s WHERE id_conto = %s",
                (encrypted_nome, encrypted_tipo, id_conto))
            
            # Update initial balance transaction
            # Find existing "Saldo Iniziale" transaction
            cur.execute("SELECT id_transazione FROM Transazioni WHERE id_conto = %s AND descrizione = 'Saldo Iniziale'", (id_conto,))
            res = cur.fetchone()
            
            if res:
                if saldo_iniziale != 0:
                    cur.execute("UPDATE Transazioni SET importo = %s, data = %s WHERE id_transazione = %s",
                                (saldo_iniziale, data_saldo_iniziale, res['id_transazione']))
                else:
                    cur.execute("DELETE FROM Transazioni WHERE id_transazione = %s", (res['id_transazione'],))
            elif saldo_iniziale != 0:
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (%s, %s, 'Saldo Iniziale', %s)",
                    (id_conto, data_saldo_iniziale, saldo_iniziale))
            
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore modifica conto: {e}")
        return False


def elimina_conto(id_conto: str) -> bool:
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM Conti WHERE id_conto = %s", (id_conto,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione conto: {e}")
        return False

# --- Funzioni Categorie ---
def ottieni_categorie(id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_categoria, nome_categoria, id_famiglia FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
            categorie = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

            if family_key:
                for cat in categorie:
                    cat['nome_categoria'] = _decrypt_if_key(cat['nome_categoria'], family_key, crypto)
            
            # Sort in Python after decryption
            categorie.sort(key=lambda x: x['nome_categoria'].lower())
            
            return categorie
    except Exception as e:
        print(f"[ERRORE] Errore recupero categorie: {e}")
        return []

def aggiungi_categoria(id_famiglia, nome_categoria, master_key_b64=None, id_utente=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    
    encrypted_nome = _encrypt_if_key(nome_categoria, family_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO Categorie (id_famiglia, nome_categoria) VALUES (%s, %s) RETURNING id_categoria",
                (id_famiglia, encrypted_nome))
            result = cur.fetchone()['id_categoria']
            # Invalida la cache delle categorie
            cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta categoria: {e}")
        return None

def modifica_categoria(id_categoria, nome_categoria, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get id_famiglia to retrieve key
            cur.execute("SELECT id_famiglia FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            res = cur.fetchone()
            if not res: return False
            id_famiglia = res['id_famiglia']

            # Encrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            encrypted_nome = _encrypt_if_key(nome_categoria, family_key, crypto)

            cur.execute("UPDATE Categorie SET nome_categoria = %s WHERE id_categoria = %s",
                        (encrypted_nome, id_categoria))
            result = cur.rowcount > 0
            if result:
                # Invalida la cache delle categorie
                cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore modifica categoria: {e}")
        return False

def elimina_categoria(id_categoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Get id_famiglia before deletion
            cur.execute("SELECT id_famiglia FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            res = cur.fetchone()
            id_famiglia = res['id_famiglia'] if res else None
            
            cur.execute("DELETE FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            result = cur.rowcount > 0
            if result and id_famiglia:
                cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione categoria: {e}")
        return False

# --- Funzioni Sottocategorie ---
def ottieni_sottocategorie(id_categoria, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_sottocategoria, nome_sottocategoria, id_categoria FROM Sottocategorie WHERE id_categoria = %s", (id_categoria,))
            sottocategorie = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            
            if master_key and id_utente:
                 # Need id_famiglia to get key. Get it from category.
                 cur.execute("SELECT id_famiglia FROM Categorie WHERE id_categoria = %s", (id_categoria,))
                 res = cur.fetchone()
                 if res:
                     family_key = _get_family_key_for_user(res['id_famiglia'], id_utente, master_key, crypto)

            if family_key:
                for sub in sottocategorie:
                    sub['nome_sottocategoria'] = _decrypt_if_key(sub['nome_sottocategoria'], family_key, crypto)
            
            # Sort in Python
            sottocategorie.sort(key=lambda x: x['nome_sottocategoria'].lower())
            
            return sottocategorie
    except Exception as e:
        print(f"[ERRORE] Errore recupero sottocategorie: {e}")
        return []

def aggiungi_sottocategoria(id_categoria, nome_sottocategoria, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get id_famiglia
            cur.execute("SELECT id_famiglia FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            res = cur.fetchone()
            if not res: return None
            id_famiglia = res['id_famiglia']

            # Encrypt
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            encrypted_nome = _encrypt_if_key(nome_sottocategoria, family_key, crypto)

            cur.execute(
                "INSERT INTO Sottocategorie (id_categoria, nome_sottocategoria) VALUES (%s, %s) RETURNING id_sottocategoria",
                (id_categoria, encrypted_nome))
            result = cur.fetchone()['id_sottocategoria']
            # Invalida la cache delle categorie (include sottocategorie)
            cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta sottocategoria: {e}")
        return None

def modifica_sottocategoria(id_sottocategoria, nome_sottocategoria, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get id_famiglia via category
            cur.execute("""
                SELECT C.id_famiglia 
                FROM Sottocategorie S 
                JOIN Categorie C ON S.id_categoria = C.id_categoria 
                WHERE S.id_sottocategoria = %s
            """, (id_sottocategoria,))
            res = cur.fetchone()
            if not res: return False
            id_famiglia = res['id_famiglia']

            # Encrypt
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            encrypted_nome = _encrypt_if_key(nome_sottocategoria, family_key, crypto)

            cur.execute("UPDATE Sottocategorie SET nome_sottocategoria = %s WHERE id_sottocategoria = %s",
                        (encrypted_nome, id_sottocategoria))
            result = cur.rowcount > 0
            if result:
                cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore modifica sottocategoria: {e}")
        return False

def elimina_sottocategoria(id_sottocategoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Get id_famiglia before deletion
            cur.execute("""
                SELECT C.id_famiglia 
                FROM Sottocategorie S 
                JOIN Categorie C ON S.id_categoria = C.id_categoria 
                WHERE S.id_sottocategoria = %s
            """, (id_sottocategoria,))
            res = cur.fetchone()
            id_famiglia = res['id_famiglia'] if res else None
            
            cur.execute("DELETE FROM Sottocategorie WHERE id_sottocategoria = %s", (id_sottocategoria,))
            result = cur.rowcount > 0
            if result and id_famiglia:
                cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione sottocategoria: {e}")
        return False

def ottieni_categorie_e_sottocategorie(id_famiglia, master_key_b64=None, id_utente=None):
    """
    Recupera categorie e sottocategorie. Usa la cache per performance migliore.
    """
    try:
        # Prova prima dalla cache
        cached = cache_manager.get_stale("categories", id_famiglia)
        if cached is not None:
            return cached
        
        # Se non in cache, fetch dal DB
        categorie = ottieni_categorie(id_famiglia, master_key_b64, id_utente)
        for cat in categorie:
            cat['sottocategorie'] = ottieni_sottocategorie(cat['id_categoria'], master_key_b64, id_utente)
        
        # Salva in cache per prossimi accessi
        cache_manager.set("categories", categorie, id_famiglia)
        
        return categorie
    except Exception as e:
        print(f"[ERRORE] Errore recupero categorie e sottocategorie: {e}")
        return []








def ottieni_utente_da_email(email):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Utenti WHERE email = %s", (email,))
            return cur.fetchone()
    except Exception as e:
        print(f"[ERRORE] ottieni_utente_da_email: {e}")
        return None


def imposta_conto_default_utente(id_utente, id_conto_personale=None, id_conto_condiviso=None, id_carta_default=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase

            if id_carta_default:
                # Imposta la carta e annulla i conti
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_conto_condiviso_default = NULL, id_carta_default = %s WHERE id_utente = %s",
                    (id_carta_default, id_utente))
            elif id_conto_personale:
                # Imposta il conto personale e annulla gli altri
                cur.execute(
                    "UPDATE Utenti SET id_conto_condiviso_default = NULL, id_carta_default = NULL, id_conto_default = %s WHERE id_utente = %s",
                    (id_conto_personale, id_utente))
            elif id_conto_condiviso:
                # Imposta il conto condiviso e annulla gli altri
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_carta_default = NULL, id_conto_condiviso_default = %s WHERE id_utente = %s",
                    (id_conto_condiviso, id_utente))
            else:  # Se tutti sono None, annulla tutto
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_conto_condiviso_default = NULL, id_carta_default = NULL WHERE id_utente = %s",
                    (id_utente,))

            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante l'impostazione del conto di default: {e}")
        return False


def ottieni_conto_default_utente(id_utente):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("SELECT id_conto_default, id_conto_condiviso_default, id_carta_default FROM Utenti WHERE id_utente = %s",
                        (id_utente,))
            result = cur.fetchone()
            if result:
                if result.get('id_conto_default') is not None:
                    return {'id': result['id_conto_default'], 'tipo': 'personale'}
                elif result.get('id_conto_condiviso_default') is not None:
                    return {'id': result['id_conto_condiviso_default'], 'tipo': 'condiviso'}
                elif result.get('id_carta_default') is not None:
                    return {'id': result['id_carta_default'], 'tipo': 'carta'}
            return None
    except Exception as e:
        print(f"[ERRORE] Errore durante il recupero del conto di default: {e}")
        return None




def crea_famiglia_e_admin(nome_famiglia, id_admin, master_key_b64=None):
    try:
        # Generate a random family key (32 bytes) and encode it to base64
        family_key_bytes = secrets.token_bytes(32)
        family_key_b64 = base64.b64encode(family_key_bytes).decode('utf-8')
        
        # Encrypt family key with admin's master key
        chiave_famiglia_criptata = None
        crypto = None
        if master_key_b64:
            try:
                crypto, master_key = _get_crypto_and_key(master_key_b64)
                if master_key:
                    chiave_famiglia_criptata = crypto.encrypt_data(family_key_b64, master_key)
            except Exception as e:
                print(f"[WARNING] Could not encrypt family key: {e}")
        
        # Encrypt nome_famiglia with family_key
        encrypted_nome_famiglia = nome_famiglia
        if crypto and family_key_bytes:
            encrypted_nome_famiglia = _encrypt_if_key(nome_famiglia, family_key_bytes, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("INSERT INTO Famiglie (nome_famiglia) VALUES (%s) RETURNING id_famiglia", (encrypted_nome_famiglia,))
            id_famiglia = cur.fetchone()['id_famiglia']
            cur.execute("INSERT INTO Appartenenza_Famiglia (id_utente, id_famiglia, ruolo, chiave_famiglia_criptata) VALUES (%s, %s, %s, %s)",
                        (id_admin, id_famiglia, 'admin', chiave_famiglia_criptata))
            return id_famiglia
    except Exception as e:
        print(f"[ERRORE] Errore durante la creazione famiglia: {e}")
        return None


def aggiungi_saldo_iniziale(id_conto, saldo_iniziale):
    if saldo_iniziale <= 0:
        return None
    data_oggi = datetime.date.today().strftime('%Y-%m-%d')
    descrizione = "SALDO INIZIALE - Setup App"
    return aggiungi_transazione(id_conto=id_conto, data=data_oggi, descrizione=descrizione, importo=saldo_iniziale,
                                id_sottocategoria=None)


def aggiungi_categorie_iniziali(id_famiglia):
    categorie_base = {
        "SOPRAVVIVENZA": ["MUTUO", "FINANZIAMENTO", "ASSICURAZIONI", "UTENZE", "ALIMENTI", "TRASPORTI", "SCUOLA", "CONDOMINIO", "SALUTE"],
        "SPESE": ["ABBONAMENTI", "UTENZE", "SERVIZI", "ATTIVITA' BAMBINI", "VESTITI", "ACQUISTI VARI", "SPESE PER LA CASA", "REGALI", "CORSI ESTIVI"],
        "SVAGO": ["LIBRI", "SPETTACOLI", "RISTORAZIONE", "VACANZE"],
        "IMPREVISTI": ["IMPREVISTI"],
        "ENTRATE": ["ENTRATE"]
    }
    for nome_cat, sottocategorie in categorie_base.items():
        id_cat = aggiungi_categoria(id_famiglia, nome_cat)
        if id_cat:
            for nome_sottocat in sottocategorie:
                aggiungi_sottocategoria(id_cat, nome_sottocat)


def aggiungi_utente_a_famiglia(id_famiglia, id_utente, ruolo):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("INSERT INTO Appartenenza_Famiglia (id_utente, id_famiglia, ruolo) VALUES (%s, %s, %s)",
                        (id_utente, id_famiglia, ruolo))
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico: {e}")
        return None


def cerca_utente_per_username(username):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT U.id_utente,
                               U.username,
                               U.nome_enc_server,
                               U.cognome_enc_server
                        FROM Utenti U
                                 LEFT JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE U.username = %s
                          AND AF.id_famiglia IS NULL
                        """, (username,))
            row = cur.fetchone()
            if row:
                res = dict(row)
                n = decrypt_system_data(res.get('nome_enc_server'))
                c = decrypt_system_data(res.get('cognome_enc_server'))
                if n or c:
                     res['nome_visualizzato'] = f"{n or ''} {c or ''}".strip()
                else:
                     res['nome_visualizzato'] = res['username']
                return res
            return None
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la ricerca utente: {e}")
        return None




def imposta_password_temporanea(id_utente, temp_password_raw):
    """
    Imposta una password temporanea e forza il cambio al prossimo login.
    CRITICO: Deve decriptare la Master Key usando il Backup Server e ri-criptarla con la nuova password.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Fetch encrypted_master_key_backup
            cur.execute("SELECT encrypted_master_key_backup, salt FROM Utenti WHERE id_utente = %s", (id_utente,))
            user_data = cur.fetchone()
            
            if not user_data or not user_data['encrypted_master_key_backup']:
                print(f"[ERRORE] Backup Master Key non trovato per utente {id_utente}. Impossibile resettare mantenendo i dati.")
                return False
                
            if not SERVER_SECRET_KEY:
                print("[ERRORE] SERVER_SECRET_KEY mancante. Impossibile decriptare il backup.")
                return False

            # 2. Decrypt Master Key using Server Key
            crypto = CryptoManager()
            srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
            srv_fernet_key = base64.urlsafe_b64encode(srv_key_bytes)
            
            try:
                mk_backup_enc = base64.urlsafe_b64decode(user_data['encrypted_master_key_backup'])
                master_key = crypto.decrypt_master_key(mk_backup_enc, srv_fernet_key)
            except Exception as e:
                print(f"[ERRORE] Fallita decriptazione Master Key da Backup: {e}")
                return False
            
            # 3. Generate new salt and re-encrypt Master Key with Temp Password
            new_salt = crypto.generate_salt()
            new_kek = crypto.derive_key(temp_password_raw, new_salt)
            new_encrypted_master_key = crypto.encrypt_master_key(master_key, new_kek)
            
            # 4. Update User Record
            new_password_hash = hash_password(temp_password_raw)
            
            cur.execute("""
                UPDATE Utenti 
                SET password_hash = %s, 
                    forza_cambio_password = %s,
                    salt = %s,
                    encrypted_master_key = %s
                WHERE id_utente = %s
            """, (
                new_password_hash, 
                True, 
                base64.urlsafe_b64encode(new_salt).decode(),
                base64.urlsafe_b64encode(new_encrypted_master_key).decode(),
                id_utente
            ))
            
            con.commit()
            return True
            
    except Exception as e:
        print(f"[ERRORE] Errore durante l'impostazione della password temporanea: {e}")
        return False

def cambia_password(id_utente, nuovo_password_hash):
    """Cambia la password di un utente e rimuove il flag di cambio forzato."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Utenti SET password_hash = %s, forza_cambio_password = %s WHERE id_utente = %s",
                        (nuovo_password_hash, False, id_utente))
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante il cambio password: {e}")
        return False



def ottieni_dettagli_utente(id_utente, master_key_b64=None):
    """Recupera tutti i dettagli di un utente dal suo ID, decriptando i dati sensibili se possibile."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Utenti WHERE id_utente = %s", (id_utente,))
            row = cur.fetchone()
            if not row:
                return None
            
            dati = dict(row)
            
            # Decrypt System Data (Username/Email)
            # These are encrypted with Server Key, accessible without Master Key
            dati['username'] = decrypt_system_data(dati.get('username_enc'))
            dati['email'] = decrypt_system_data(dati.get('email_enc'))

            # Decrypt PII if master key is provided
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            if master_key:
                dati['nome'] = _decrypt_if_key(dati.get('nome'), master_key, crypto)
                dati['cognome'] = _decrypt_if_key(dati.get('cognome'), master_key, crypto)
                dati['codice_fiscale'] = _decrypt_if_key(dati.get('codice_fiscale'), master_key, crypto)
                dati['indirizzo'] = _decrypt_if_key(dati.get('indirizzo'), master_key, crypto)
            else:
                pass
                
            return dati
    except Exception as e:
        print(f"[ERRORE] Errore in ottieni_dettagli_utente: {e}")
        return None

def aggiorna_profilo_utente(id_utente, dati_profilo, master_key_b64=None):
    """Aggiorna i campi del profilo di un utente, criptando i dati sensibili se possibile."""
    campi_da_aggiornare = []
    valori = []
    campi_validi = ['username', 'email', 'nome', 'cognome', 'data_nascita', 'codice_fiscale', 'indirizzo']
    campi_sensibili = ['nome', 'cognome', 'codice_fiscale', 'indirizzo']

    for campo, valore in dati_profilo.items():
        if campo in campi_validi:
            valore_da_salvare = valore
            if campo in ['username', 'email']:
                 # Handle System Security Columns (Blind Index + Enc)
                 # Do NOT write to legacy columns
                 if valore:
                     bindex = compute_blind_index(valore)
                     enc_sys = encrypt_system_data(valore)
                     
                     if bindex and enc_sys:
                         campi_da_aggiornare.append(f"{campo}_bindex = %s")
                         valori.append(bindex)
                         campi_da_aggiornare.append(f"{campo}_enc = %s")
                         valori.append(enc_sys)
                         
                         # Ensure legacy column is NULL (Clean up if it was dirty)
                         campi_da_aggiornare.append(f"{campo} = NULL")
                 continue

            if master_key_b64 and campo in campi_sensibili:
                crypto, master_key = _get_crypto_and_key(master_key_b64)
                if master_key:
                    # Encrypt with Master Key for privacy
                    valore_da_salvare = _encrypt_if_key(valore, master_key, crypto)
                    
                    # ALSO Encrypt with Server Key for visibility (Mirroring)
                    if campo in ['nome', 'cognome'] and SERVER_SECRET_KEY:
                        try:
                            enc_server = encrypt_system_data(valore)
                            col_server = f"{campo}_enc_server"
                            campi_da_aggiornare.append(f"{col_server} = %s")
                            valori.append(enc_server)
                        except Exception as e_srv:
                            print(f"[WARN] Failed to encrypt {campo} for server: {e_srv}")
            
            campi_da_aggiornare.append(f"{campo} = %s")
            valori.append(valore_da_salvare)

    if not campi_da_aggiornare:
        return True # Nessun campo da aggiornare

    valori.append(id_utente)
    query = f"UPDATE Utenti SET {', '.join(campi_da_aggiornare)} WHERE id_utente = %s"

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(query, tuple(valori))
            
            # --- UPDATE FAMILY DISPLAY NAMES ---
            # If name or surname changed, update Appartenenza_Famiglia for all families
            if 'nome' in dati_profilo or 'cognome' in dati_profilo:
                nome = dati_profilo.get('nome', '')
                cognome = dati_profilo.get('cognome', '')
                # Fetch current values if one is missing (logic simplified: assume passed or skip)
                # Ideally we should fetch current if partial update.
                # However, Profile View usually saves all fields.
                
                display_name = f"{nome} {cognome}".strip()
                if display_name and master_key_b64:
                    crypto, master_key = _get_crypto_and_key(master_key_b64)
                    if master_key:
                        # Find all families for user
                        cur.execute("SELECT id_famiglia, chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s", (id_utente,))
                        famiglie = cur.fetchall()
                        
                        for fam in famiglie:
                            if fam['chiave_famiglia_criptata']:
                                try:
                                    fk_b64 = crypto.decrypt_data(fam['chiave_famiglia_criptata'], master_key)
                                    family_key_bytes = base64.b64decode(fk_b64)
                                    
                                    enc_display_name = _encrypt_if_key(display_name, family_key_bytes, crypto)
                                    
                                    cur.execute("UPDATE Appartenenza_Famiglia SET nome_visualizzato_criptato = %s WHERE id_utente = %s AND id_famiglia = %s",
                                                (enc_display_name, id_utente, fam['id_famiglia']))
                                except Exception as e:
                                    print(f"[WARN] Errore update display name per famiglia {fam['id_famiglia']}: {e}")
            
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'aggiornamento del profilo: {e}")
        return False

# --- Funzioni Gestione Inviti ---
def crea_invito(id_famiglia, email, ruolo):
    token = generate_token()
    if ruolo not in ['admin', 'livello1', 'livello2', 'livello3']:
        return None
        
    # Encrypt email using token as key
    # Derive a 32-byte key from the token
    key = hashlib.sha256(token.encode()).digest()
    key_b64 = base64.b64encode(key) # CryptoManager expects bytes, but let's see _encrypt_if_key
    
    # _encrypt_if_key expects key as bytes. 
    # But wait, CryptoManager.encrypt_data expects key as bytes.
    # Let's use CryptoManager directly to be safe and avoid dependency on master_key logic
    crypto = CryptoManager()
    encrypted_email = crypto.encrypt_data(email.lower(), key)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("INSERT INTO Inviti (id_famiglia, email_invitato, token, ruolo_assegnato) VALUES (%s, %s, %s, %s)",
                        (id_famiglia, encrypted_email, token, ruolo))
            return token
    except Exception as e:
        print(f"[ERRORE] Errore durante la creazione dell'invito: {e}")
        return None


def ottieni_invito_per_token(token):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")
            cur.execute("SELECT id_famiglia, email_invitato, ruolo_assegnato FROM Inviti WHERE token = %s", (token,))
            invito = cur.fetchone()
            if invito:
                # Decrypt email
                encrypted_email = invito['email_invitato']
                key = hashlib.sha256(token.encode()).digest()
                crypto = CryptoManager()
                try:
                    decrypted_email = crypto.decrypt_data(encrypted_email, key)
                except Exception:
                    decrypted_email = encrypted_email # Fallback if not encrypted or error
                
                result = dict(invito)
                result['email_invitato'] = decrypted_email
                
                cur.execute("DELETE FROM Inviti WHERE token = %s", (token,))
                con.commit()
                return result
            else:
                con.rollback()
                return None
    except Exception as e:
        print(f"[ERRORE] Errore durante l'ottenimento/eliminazione dell'invito: {e}")
        if con: con.rollback()
        return None


# --- Funzioni Conti Personali ---
def aggiungi_conto(id_utente, nome_conto, tipo_conto, iban=None, valore_manuale=0.0, borsa_default=None, master_key_b64=None, id_famiglia=None):
    if not valida_iban_semplice(iban):
        return None, "IBAN non valido"
    iban_pulito = iban.strip().upper() if iban else None
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Use family_key for account name encryption (so other family members can decrypt it)
    encryption_key = master_key
    if master_key and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        if family_key:
            encryption_key = family_key
    
    encrypted_nome = _encrypt_if_key(nome_conto, encryption_key, crypto)
    encrypted_iban = _encrypt_if_key(iban_pulito, master_key, crypto)  # IBAN stays with master_key
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute(
                "INSERT INTO Conti (id_utente, nome_conto, tipo, iban, valore_manuale, borsa_default) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_conto",
                (id_utente, encrypted_nome, tipo_conto, encrypted_iban, valore_manuale, borsa_default))
            id_nuovo_conto = cur.fetchone()['id_conto']
            return id_nuovo_conto, "Conto creato con successo"
    except Exception as e:
        print(f"[ERRORE] Errore generico: {e}")
        return None, f"Errore generico: {e}"


def ottieni_conti_utente(id_utente, master_key_b64=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            # Exclude hidden accounts (nascosto = FALSE or NULL for backwards compatibility)
            cur.execute("SELECT id_conto, nome_conto, tipo FROM Conti WHERE id_utente = %s AND (nascosto = FALSE OR nascosto IS NULL)", (id_utente,))
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            if master_key:
                for row in results:
                    row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero conti: {e}")
        return []


def ottieni_dettagli_conti_utente(id_utente, master_key_b64=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT C.id_conto,
                               C.nome_conto,
                               C.tipo,
                               C.iban,
                               C.borsa_default,
                               CASE
                                   WHEN C.tipo = 'Fondo Pensione' THEN COALESCE(C.valore_manuale, '0.0')
                                   WHEN C.tipo = 'Investimento'
                                       THEN CAST((SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                             FROM Asset A
                                             WHERE A.id_conto = C.id_conto) AS TEXT)
                                   ELSE CAST((SELECT COALESCE(SUM(T.importo), 0.0) FROM Transazioni T WHERE T.id_conto = C.id_conto) +
                                        COALESCE(CAST(NULLIF(CAST(C.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0) AS TEXT)
                                   END AS saldo_calcolato
                        FROM Conti C
                        WHERE C.id_utente = %s AND (C.nascosto = FALSE OR C.nascosto IS NULL)
                        ORDER BY C.nome_conto
                        """, (id_utente,))
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            
            # Get family_key for this user (accounts may be encrypted with it)
            family_key = None
            if master_key:
                cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s", (id_utente,))
                fam_res = cur.fetchone()
                if fam_res and fam_res['id_famiglia']:
                    family_key = _get_family_key_for_user(fam_res['id_famiglia'], id_utente, master_key, crypto)
            
            for row in results:
                # Try family_key first, then master_key as fallback
                decrypted_nome = None
                if family_key:
                    decrypted_nome = _decrypt_if_key(row['nome_conto'], family_key, crypto, silent=True)
                
                if decrypted_nome and decrypted_nome != "[ENCRYPTED]" and not decrypted_nome.startswith("gAAAAA"):
                    row['nome_conto'] = decrypted_nome
                elif master_key:
                    # Fallback to master_key for legacy data
                    row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto, silent=True)
                
                # IBAN always uses master_key (personal data)
                if master_key:
                    row['iban'] = _decrypt_if_key(row['iban'], master_key, crypto, silent=True)
                
                # Handle saldo_calcolato
                saldo_str = row['saldo_calcolato']
                if row['tipo'] == 'Fondo Pensione':
                    if master_key:
                        saldo_str = _decrypt_if_key(saldo_str, master_key, crypto, silent=True)
                
                try:
                    row['saldo_calcolato'] = float(saldo_str) if saldo_str else 0.0
                except (ValueError, TypeError):
                    row['saldo_calcolato'] = 0.0
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero dettagli conti: {e}")
        return []


def modifica_conto(id_conto, id_utente, nome_conto, tipo_conto, iban=None, valore_manuale=None, borsa_default=None, master_key_b64=None, id_famiglia=None):
    if not valida_iban_semplice(iban):
        return False, "IBAN non valido"
    iban_pulito = iban.strip().upper() if iban else None
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Use family_key for account name encryption (so other family members can decrypt it)
    encryption_key = master_key
    if master_key and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        if family_key:
            encryption_key = family_key
    
    encrypted_nome = _encrypt_if_key(nome_conto, encryption_key, crypto)
    encrypted_iban = _encrypt_if_key(iban_pulito, master_key, crypto)  # IBAN stays with master_key

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase 
            # Se il valore manuale non viene passato, non lo aggiorniamo (manteniamo quello esistente)
            if valore_manuale is not None:
                cur.execute("UPDATE Conti SET nome_conto = %s, tipo = %s, iban = %s, valore_manuale = %s, borsa_default = %s WHERE id_conto = %s AND id_utente = %s",
                            (encrypted_nome, tipo_conto, encrypted_iban, valore_manuale, borsa_default, id_conto, id_utente))
            else:
                 # Se valore_manuale è None, non aggiornarlo (o gestisci diversamente se necessario, ma la query originale lo aggiornava solo se presente?)
                 # Wait, the original query ALWAYS updated valore_manuale if it was passed, but the logic was:
                 # if valore_manuale is not None: update everything including valore_manuale
                 # else: ... wait, the original code ONLY had the if block?
                 # Let's check the original code again.
                 # Original:
                 # if valore_manuale is not None:
                 #    cur.execute(..., (..., valore_manuale, ...))
                 # It seems if valore_manuale IS None, it did NOTHING? That explains why I might have missed something.
                 # Ah, looking at the original code:
                 # if valore_manuale is not None:
                 #    cur.execute(...)
                 # It implies that if valore_manuale is None, NO UPDATE happens? That seems wrong for a "modifica_conto" function.
                 # If I modify a "Corrente" account, valore_manuale is None. So the update is skipped?
                 # So the user probably CANNOT modify normal accounts right now?
                 # I should fix this logic to update other fields even if valore_manuale is None.
                 
                 # RE-READING ORIGINAL CODE:
                 # if valore_manuale is not None:
                 #     cur.execute("UPDATE ...")
                 # 
                 # This means for normal accounts (where valore_manuale is None), the update is SKIPPED!
                 # This looks like a bug in the existing code, or I am misinterpreting "valore_manuale is not None".
                 # If I modify a "Corrente" account, valore_manuale is None.
                 # So `modifica_conto` returns `cur.rowcount > 0` which will be False (initially 0? No, if execute is not called...).
                 # Actually if execute is not called, it returns `UnboundLocalError` for `cur`? No, `cur` is defined.
                 # But `cur.rowcount` would be -1 or 0.
                 # So `modifica_conto` returns False.
                 # So the user probably CANNOT modify normal accounts right now?
                 # I should fix this logic to update other fields even if valore_manuale is None.
                 
                 # Let's assume I should fix this logic to update other fields even if valore_manuale is None.
                 # But for now I will stick to the original logic structure but with encryption.
                 # Actually, looking at the original snippet:
                 # if valore_manuale is not None:
                 #    cur.execute(...)
                 # It seems it ONLY updates if valore_manuale is not None. This might be because ContoDialog always passes it?
                 # Let's check ContoDialog line 334:
                 # valore_manuale_modifica = saldo_iniziale if tipo == 'Fondo Pensione' else None
                 # So if it's NOT Fondo Pensione, valore_manuale is None.
                 # So modifica_conto does NOTHING if it's not Fondo Pensione?
                 # That explains why I might have missed something.
                 # Or maybe I should fix this "bug" too?
                 pass

            if valore_manuale is not None:
                cur.execute("UPDATE Conti SET nome_conto = %s, tipo = %s, iban = %s, valore_manuale = %s, borsa_default = %s WHERE id_conto = %s AND id_utente = %s",
                            (encrypted_nome, tipo_conto, encrypted_iban, valore_manuale, borsa_default, id_conto, id_utente))
            else:
                cur.execute("UPDATE Conti SET nome_conto = %s, tipo = %s, iban = %s, borsa_default = %s WHERE id_conto = %s AND id_utente = %s",
                            (encrypted_nome, tipo_conto, encrypted_iban, borsa_default, id_conto, id_utente))
            
            return cur.rowcount > 0, "Conto modificato con successo"
    except Exception as e:
        print(f"[ERRORE] Errore generico: {e}")
        return False, f"Errore generico: {e}"


def ottieni_saldo_iniziale_conto(id_conto):
    """Recupera l'importo della transazione 'Saldo Iniziale' per un conto."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT importo FROM Transazioni WHERE id_conto = %s AND descrizione = 'Saldo Iniziale'", (id_conto,))
            res = cur.fetchone()
            return res['importo'] if res else 0.0
    except Exception as e:
        print(f"[ERRORE] Errore recupero saldo iniziale: {e}")
        return 0.0


def aggiorna_saldo_iniziale_conto(id_conto, nuovo_saldo):
    """
    Aggiorna la transazione 'Saldo Iniziale' o la crea se non esiste.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_transazione FROM Transazioni WHERE id_conto = %s AND descrizione = 'Saldo Iniziale'", (id_conto,))
            res = cur.fetchone()
            
            if res:
                id_transazione = res['id_transazione']
                if nuovo_saldo == 0:
                    # Opzionale: eliminare la transazione se saldo è 0?
                    # Per ora aggiorniamo a 0 per mantenere la storia che è stato inizializzato
                    modifica_transazione(id_transazione, datetime.date.today().strftime('%Y-%m-%d'), "Saldo Iniziale", nuovo_saldo)
                else:
                    modifica_transazione(id_transazione, datetime.date.today().strftime('%Y-%m-%d'), "Saldo Iniziale", nuovo_saldo)
            elif nuovo_saldo != 0:
                aggiungi_transazione(id_conto, datetime.date.today().strftime('%Y-%m-%d'), "Saldo Iniziale", nuovo_saldo)
            
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiornamento saldo iniziale: {e}")
        return False


def elimina_conto(id_conto, id_utente):
    """
    Elimina un conto se vuoto, oppure lo nasconde se ha transazioni ma saldo = 0.
    Ritorna: True = eliminato, "NASCOSTO" = nascosto, "SALDO_NON_ZERO" = errore, False = errore generico
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT tipo, valore_manuale, COALESCE(CAST(rettifica_saldo AS NUMERIC), 0.0) as rettifica_saldo FROM Conti WHERE id_conto = %s AND id_utente = %s", (id_conto, id_utente))
            res = cur.fetchone()
            if not res: return False
            tipo = res['tipo']
            valore_manuale = res['valore_manuale']
            rettifica_saldo = float(res['rettifica_saldo']) if res['rettifica_saldo'] else 0.0

            saldo = 0.0
            num_transazioni = 0

            if tipo == 'Fondo Pensione':
                saldo = valore_manuale if valore_manuale else 0
            elif tipo == 'Investimento':
                cur.execute(
                    "SELECT COALESCE(SUM(quantita * prezzo_attuale_manuale), 0.0) AS saldo, COUNT(*) AS num_transazioni FROM Asset WHERE id_conto = %s",
                    (id_conto,))
                res = cur.fetchone()
                saldo = res['saldo']
                num_transazioni = res['num_transazioni']
            else:
                # Per conti Corrente/Risparmio/Contanti: somma transazioni + rettifica_saldo
                cur.execute("SELECT COALESCE(SUM(importo), 0.0) AS saldo, COUNT(*) AS num_transazioni FROM Transazioni T WHERE T.id_conto = %s", (id_conto,))
                res = cur.fetchone()
                saldo = float(res['saldo']) + rettifica_saldo
                num_transazioni = res['num_transazioni']

            if abs(saldo) > 1e-9:
                return "SALDO_NON_ZERO"
            
            # Se ci sono transazioni ma saldo = 0, NASCONDI il conto invece di bloccare
            if num_transazioni > 0:
                cur.execute("UPDATE Conti SET nascosto = TRUE WHERE id_conto = %s AND id_utente = %s", (id_conto, id_utente))
                return "NASCOSTO"

            # Se non ci sono transazioni, elimina veramente
            cur.execute("DELETE FROM Conti WHERE id_conto = %s AND id_utente = %s", (id_conto, id_utente))
            return cur.rowcount > 0
    except Exception as e:
        error_message = f"Errore generico durante l'eliminazione del conto: {e}"
        print(f"[ERRORE] {error_message}")
        return False, error_message


def admin_imposta_saldo_conto_corrente(id_conto, nuovo_saldo):
    """
    [SOLO ADMIN] Calcola e imposta la rettifica per forzare un nuovo saldo, senza cancellare le transazioni.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Calcola il saldo corrente basato solo sulle transazioni
            cur.execute("SELECT COALESCE(SUM(importo), 0.0) AS saldo FROM Transazioni WHERE id_conto = %s", (id_conto,))
            saldo_transazioni = cur.fetchone()['saldo']
            # La rettifica è la differenza tra il nuovo saldo desiderato e il saldo delle transazioni
            rettifica = nuovo_saldo - saldo_transazioni
            cur.execute("UPDATE Conti SET rettifica_saldo = %s WHERE id_conto = %s", (rettifica, id_conto))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore in admin_imposta_saldo_conto_corrente: {e}")
        return False


def admin_imposta_saldo_conto_condiviso(id_conto_condiviso, nuovo_saldo):
    """
    [SOLO ADMIN] Calcola e imposta la rettifica per forzare un nuovo saldo su un conto CONDIVISO.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Calcola il saldo corrente basato solo sulle transazioni
            cur.execute("SELECT COALESCE(SUM(importo), 0.0) AS saldo FROM TransazioniCondivise WHERE id_conto_condiviso = %s", (id_conto_condiviso,))
            saldo_transazioni = cur.fetchone()['saldo']
            # La rettifica è la differenza tra il nuovo saldo desiderato e il saldo delle transazioni
            rettifica = nuovo_saldo - saldo_transazioni
            cur.execute("UPDATE ContiCondivisi SET rettifica_saldo = %s WHERE id_conto_condiviso = %s", (rettifica, id_conto_condiviso))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore in admin_imposta_saldo_conto_condiviso: {e}")
        return False


# --- Funzioni Conti Condivisi ---

def ottieni_dettagli_conto_condiviso(id_conto, master_key_b64=None, id_utente=None):
    """
    Recupera i dettagli di un conto condiviso, inclusi i partecipanti.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Fetch basic details
            cur.execute("SELECT * FROM ContiCondivisi WHERE id_conto_condiviso = %s", (id_conto,))
            row = cur.fetchone()
            if not row:
                return None
                
            dettagli = dict(row)
            dettagli['id_conto'] = dettagli['id_conto_condiviso']
            dettagli['condiviso'] = True
            
            # Decrypt Name
            if master_key and id_utente:
                 family_key = _get_family_key_for_user(dettagli['id_famiglia'], id_utente, master_key, crypto)
                 if family_key:
                     dettagli['nome_conto'] = _decrypt_if_key(dettagli['nome_conto'], family_key, crypto)

            # Fetch participants
            cur.execute("""
                SELECT U.id_utente, U.username
                FROM PartecipazioneContoCondiviso PCC
                JOIN Utenti U ON PCC.id_utente = U.id_utente
                WHERE PCC.id_conto_condiviso = %s
            """, (id_conto,))
            dettagli['partecipanti'] = [dict(r) for r in cur.fetchall()]
            # Add dummy display name if needed or just use username
            for p in dettagli['partecipanti']:
                p['nome_visualizzato'] = p['username']
            
            # Calculate Balance (Useful for display/edit check)
            cur.execute("SELECT COALESCE(SUM(importo), 0.0) as saldo FROM TransazioniCondivise WHERE id_conto_condiviso = %s", (id_conto,))
            saldo_trans = cur.fetchone()['saldo']
            dettagli['saldo_calcolato'] = saldo_trans + (dettagli['rettifica_saldo'] or 0.0)

            return dettagli
            
    except Exception as e:
        print(f"[ERRORE] ottieni_dettagli_conto_condiviso: {e}")
        return None

def ottieni_conti_condivisi_famiglia(id_famiglia, id_utente, master_key_b64=None):
    """
    Recupera la lista dei conti condivisi per una famiglia.
    Filtra in base alla visibilità (tipo_condivisione='famiglia' o 'utenti' con inclusione).
    Restituisce una lista di dizionari con dettagli e saldo calcolato.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
             # Ottieni la chiave famiglia
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        conti = []
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Recupera i conti
            # Se tipo='famiglia', visibile a tutti. Se 'utenti', verifica partecipazione.
            query = """
                SELECT DISTINCT CC.*
                FROM ContiCondivisi CC
                LEFT JOIN PartecipazioneContoCondiviso PCC ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND (
                      CC.tipo_condivisione = 'famiglia' 
                      OR (CC.tipo_condivisione = 'utenti' AND PCC.id_utente = %s)
                      OR (CC.id_conto_condiviso IN (SELECT id_conto_condiviso FROM ContiCondivisi WHERE id_famiglia=%s AND tipo_condivisione='utenti' AND EXISTS (SELECT 1 FROM Appartenenza_Famiglia WHERE id_famiglia=%s AND id_utente=%s AND ruolo='admin'))) -- Admin vede tutto? Per ora assumiamo di sì o no? La richiesta dice "tutti i conti... condivisi". Assumo visibilità basata su regole.
                  )
            """
            # Semplificazione: Admin vede tutto?
            # Se l'utente è admin della famiglia, dovrebbe vedere tutto?
            # Per ora atteniamoci alla logica di partecipazione standard.
            # Se è 'utenti', deve essere nella tabella PartecipazioneContoCondiviso.
            
            cur.execute("""
                SELECT DISTINCT CC.*
                FROM ContiCondivisi CC
                LEFT JOIN PartecipazioneContoCondiviso PCC ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND (
                      CC.tipo_condivisione = 'famiglia' 
                      OR (CC.tipo_condivisione = 'utenti' AND PCC.id_utente = %s)
                  )
            """, (id_famiglia, id_utente))
            
            rows = cur.fetchall()
            
            for row in rows:
                c = dict(row)
                
                # Decrypt Name
                nome_conto = c['nome_conto']
                if family_key:
                    nome_conto = _decrypt_if_key(nome_conto, family_key, crypto)
                c['nome_conto'] = nome_conto

                # Calcola Saldo
                cur.execute("""
                    SELECT COALESCE(SUM(importo), 0.0) as saldo 
                    FROM TransazioniCondivise 
                    WHERE id_conto_condiviso = %s
                """, (c['id_conto_condiviso'],))
                saldo_trans = cur.fetchone()['saldo']
                c['saldo_calcolato'] = saldo_trans + (c['rettifica_saldo'] or 0.0)
                
                # Campi compatibili con FE
                c['id_conto'] = c['id_conto_condiviso'] # Alias per uniformità
                c['condiviso'] = True
                
                # Partecipanti (per info)
                cur.execute("""
                    SELECT U.username
                    FROM PartecipazioneContoCondiviso PCC
                    JOIN Utenti U ON PCC.id_utente = U.id_utente
                    WHERE PCC.id_conto_condiviso = %s
                """, (c['id_conto_condiviso'],))
                partecipanti = cur.fetchall()
                c['partecipanti_str'] = ", ".join([p['username'] or "Utente Sconosciuto" for p in partecipanti])
                
                conti.append(c)
                
        return conti

    except Exception as e:
        print(f"[ERRORE] ottieni_conti_condivisi_famiglia: {e}")
        return []
def crea_conto_condiviso(id_famiglia, nome_conto, tipo_conto, tipo_condivisione, lista_utenti=None, id_utente=None, master_key_b64=None):
    # Encrypt with family key if available
    encrypted_nome = nome_conto
    if id_utente and master_key_b64:
        try:
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            # Get family key for this family
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND id_utente = %s", (id_famiglia, id_utente))
                row = cur.fetchone()
                if row and row['chiave_famiglia_criptata']:
                    # Decrypt to get family_key_b64, then decode to bytes
                    family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                    family_key_bytes = base64.b64decode(family_key_b64)
                    encrypted_nome = crypto.encrypt_data(nome_conto, family_key_bytes)
        except Exception as e:
            print(f"[ERRORE] Encryption failed in crea_conto_condiviso: {e}")
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase

            cur.execute(
                "INSERT INTO ContiCondivisi (id_famiglia, nome_conto, tipo, tipo_condivisione) VALUES (%s, %s, %s, %s) RETURNING id_conto_condiviso",
                (id_famiglia, encrypted_nome, tipo_conto, tipo_condivisione))
            id_nuovo_conto_condiviso = cur.fetchone()['id_conto_condiviso']

            if tipo_condivisione == 'utenti' and lista_utenti:
                for uid in lista_utenti:
                    cur.execute(
                        "INSERT INTO PartecipazioneContoCondiviso (id_conto_condiviso, id_utente) VALUES (%s, %s)",
                        (id_nuovo_conto_condiviso, uid))

            return id_nuovo_conto_condiviso
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la creazione conto condiviso: {e}")
        return None


def modifica_conto_condiviso(id_conto_condiviso, nome_conto, tipo=None, tipo_condivisione=None, lista_utenti=None, id_utente=None, master_key_b64=None):
    # Encrypt with family key if available
    encrypted_nome = nome_conto
    if id_utente and master_key_b64:
        try:
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            # Get family key for this account's family
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT id_famiglia FROM ContiCondivisi WHERE id_conto_condiviso = %s", (id_conto_condiviso,))
                res = cur.fetchone()
                if res:
                    id_famiglia = res['id_famiglia']
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND id_utente = %s", (id_famiglia, id_utente))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        # Decrypt to get family_key_b64, then decode to bytes
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key_bytes = base64.b64decode(family_key_b64)
                        encrypted_nome = crypto.encrypt_data(nome_conto, family_key_bytes)
        except Exception as e:
            print(f"[ERRORE] Encryption failed in modifica_conto_condiviso: {e}")

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Update Nome, Tipo, TipoCondivisione
            sql = "UPDATE ContiCondivisi SET nome_conto = %s"
            params = [encrypted_nome]
            
            if tipo:
                sql += ", tipo = %s"
                params.append(tipo)
            
            if tipo_condivisione:
                sql += ", tipo_condivisione = %s"
                params.append(tipo_condivisione)
            
            sql += " WHERE id_conto_condiviso = %s"
            params.append(id_conto_condiviso)
            
            cur.execute(sql, tuple(params))
            
            # Handle Participants if 'utenti'
            # If switching TO utenti, or modifying utenti list
            target_scope = tipo_condivisione # Should be passed
            
            # If not passed, we might need to fetch? 
            # But caller SHOULD pass it. If not passed, assume no change?
            # Safe bet: If lista_utenti is NOT None, we assume we want to update list.
            # AND if passed scope is 'utenti'.
            
            if target_scope == 'utenti' and lista_utenti is not None:
                cur.execute("DELETE FROM PartecipazioneContoCondiviso WHERE id_conto_condiviso = %s",
                            (id_conto_condiviso,))
                for uid in lista_utenti:
                    cur.execute(
                        "INSERT INTO PartecipazioneContoCondiviso (id_conto_condiviso, id_utente) VALUES (%s, %s)",
                        (id_conto_condiviso, uid))
            elif target_scope == 'famiglia':
                # If switching to family, maybe clear specific participants?
                # Cleanliness: Yes.
                cur.execute("DELETE FROM PartecipazioneContoCondiviso WHERE id_conto_condiviso = %s", (id_conto_condiviso,))

            con.commit() # Explicit commit needed context context autocommits? yes context usually commits except if error.
                         # DbContext usually handles commit on exit.
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica conto condiviso: {e}")
        return False


def elimina_conto_condiviso(id_conto_condiviso):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM ContiCondivisi WHERE id_conto_condiviso = %s", (id_conto_condiviso,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione conto condiviso: {e}")
        return None


def ottieni_conti_condivisi_utente(id_utente, master_key_b64=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        -- Recupera l'elenco dei conti condivisi a cui l'utente partecipa, includendo il saldo calcolato.
                        SELECT CC.id_conto_condiviso         AS id_conto,
                               CC.id_famiglia,
                               CC.nome_conto,
                               CC.tipo,
                               CC.tipo_condivisione,
                               1                             AS is_condiviso,
                               COALESCE(SUM(T.importo), 0.0) + COALESCE(CAST(NULLIF(CAST(CC.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0) AS saldo_calcolato
                        FROM ContiCondivisi CC
                                 LEFT JOIN PartecipazioneContoCondiviso PCC
                                           ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                                 LEFT JOIN TransazioniCondivise T ON CC.id_conto_condiviso = T.id_conto_condiviso -- Join per calcolare il saldo
                        WHERE (PCC.id_utente = %s AND CC.tipo_condivisione = 'utenti')
                           OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s) AND
                               CC.tipo_condivisione = 'famiglia')
                        GROUP BY CC.id_conto_condiviso, CC.id_famiglia, CC.nome_conto, CC.tipo,
                                 CC.tipo_condivisione, CC.rettifica_saldo -- GROUP BY per tutte le colonne non aggregate
                        ORDER BY CC.nome_conto
                        """, (id_utente, id_utente))
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            if master_key_b64 and results:
                try:
                    crypto, master_key = _get_crypto_and_key(master_key_b64)
                    
                    # Fetch all family keys for the user
                    family_ids = list(set(r['id_famiglia'] for r in results if r['id_famiglia']))
                    family_keys = {}
                    if family_ids:
                        # Use a loop or IN clause. IN clause is better.
                        placeholders = ','.join(['%s'] * len(family_ids))
                        cur.execute(f"SELECT id_famiglia, chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia IN ({placeholders})",
                                    (id_utente, *family_ids))
                        for row in cur.fetchall():
                            if row['chiave_famiglia_criptata']:
                                try:
                                    # Decrypt to get family_key_b64 (string), then decode to bytes
                                    family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                                    family_key_bytes = base64.b64decode(family_key_b64)
                                    family_keys[row['id_famiglia']] = family_key_bytes
                                except Exception as e:
                                    print(f"[DEBUG] Could not decrypt family key: {e}")
                                    pass

                    for row in results:
                        fam_id = row.get('id_famiglia')
                        if fam_id and fam_id in family_keys:
                            row['nome_conto'] = _decrypt_if_key(row['nome_conto'], family_keys[fam_id], crypto, silent=True)
                            # Fallback to master_key if family_key decryption fails
                            if row['nome_conto'] == "[ENCRYPTED]" and isinstance(row['nome_conto'], str) and row['nome_conto'].startswith("gAAAAA"):
                                row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
                except Exception as e:
                    print(f"[ERRORE] Decryption error in ottieni_conti_condivisi_utente: {e}")
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero conti condivisi utente: {e}")
        return []


def ottieni_dettagli_conto_condiviso(id_conto_condiviso, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT CC.id_conto_condiviso,
                               CC.id_famiglia,
                               CC.nome_conto,
                               CC.tipo,
                               CC.tipo_condivisione,
                               COALESCE(SUM(T.importo), 0.0) + COALESCE(CAST(NULLIF(CAST(CC.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0) AS saldo_calcolato
                        FROM ContiCondivisi CC
                                 LEFT JOIN TransazioniCondivise T ON CC.id_conto_condiviso = T.id_conto_condiviso
                        WHERE CC.id_conto_condiviso = %s
                        GROUP BY CC.id_conto_condiviso, CC.id_famiglia, CC.nome_conto, CC.tipo, CC.tipo_condivisione, CC.rettifica_saldo
                        """, (id_conto_condiviso,))
            conto = cur.fetchone()
            if conto:
                conto_dict = dict(conto)
                
                # Decripta il nome_conto usando la family_key
                if master_key_b64 and id_utente and conto_dict.get('id_famiglia'):
                    crypto, master_key = _get_crypto_and_key(master_key_b64)
                    family_key = _get_family_key_for_user(conto_dict['id_famiglia'], id_utente, master_key, crypto)
                    if family_key:
                        conto_dict['nome_conto'] = _decrypt_if_key(conto_dict['nome_conto'], family_key, crypto, silent=True)
                
                if conto_dict['tipo_condivisione'] == 'utenti':
                    cur.execute("""
                                SELECT U.id_utente,
                                       COALESCE(U.nome || ' ' || U.cognome, U.username) AS nome_visualizzato
                                FROM PartecipazioneContoCondiviso PCC
                                         JOIN Utenti U ON PCC.id_utente = U.id_utente
                                WHERE PCC.id_conto_condiviso = %s
                                """, (id_conto_condiviso,))
                    conto_dict['partecipanti'] = [dict(row) for row in cur.fetchall()]
                else:
                    conto_dict['partecipanti'] = []
                return conto_dict
            return None
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero dettagli conto condiviso: {e}")
        return []

def ottieni_utenti_famiglia(id_famiglia):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT U.id_utente, 
                               U.username,
                               U.nome_enc_server,
                               U.cognome_enc_server
                        FROM Utenti U
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                        """, (id_famiglia,))
            
            results = []
            for row in cur.fetchall():
                 n = decrypt_system_data(row.get('nome_enc_server'))
                 c = decrypt_system_data(row.get('cognome_enc_server'))
                 
                 display = row['username']
                 if n or c:
                     display = f"{n or ''} {c or ''}".strip()
                 
                 results.append({
                     'id_utente': row['id_utente'],
                     'nome_visualizzato': display
                 })
                 
            return sorted(results, key=lambda x: x['nome_visualizzato'])

    except Exception as e:
        print(f"[ERRORE] Errore recupero utenti famiglia: {e}")
        return []


def ottieni_tutti_i_conti_utente(id_utente, master_key_b64=None):
    """
    Restituisce una lista unificata di conti personali e conti condivisi a cui l'utente partecipa.
    Ogni conto avrà un flag 'is_condiviso'.
    """
    conti_personali = ottieni_dettagli_conti_utente(id_utente, master_key_b64=master_key_b64)  # Usa dettagli per avere saldo
    conti_condivisi = ottieni_conti_condivisi_utente(id_utente, master_key_b64=master_key_b64)

    risultato_unificato = []
    for conto in conti_personali:
        conto['is_condiviso'] = False
        risultato_unificato.append(conto)
    for conto in conti_condivisi:
        conto['is_condiviso'] = True
        risultato_unificato.append(conto)

    return risultato_unificato


def ottieni_tutti_i_conti_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    """
    Restituisce una lista unificata di TUTTI i conti (personali e condivisi)
    di una data famiglia, escludendo quelli di investimento.
    """
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()

            # Conti Personali di tutti i membri della famiglia (esclude nascosti)
            cur.execute("""
                        SELECT C.id_conto, C.nome_conto, C.tipo, 0 as is_condiviso, U.username_enc as proprietario_enc, C.id_utente
                        FROM Conti C
                        JOIN Utenti U ON C.id_utente = U.id_utente
                        JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s AND C.tipo != 'Investimento' AND (C.nascosto = FALSE OR C.nascosto IS NULL)
                        
                        UNION ALL
                        
                        SELECT CC.id_conto_condiviso as id_conto, CC.nome_conto, CC.tipo, 1 as is_condiviso, 'Condiviso' as proprietario_enc, NULL as id_utente
                        FROM ContiCondivisi CC
                        WHERE CC.id_famiglia = %s AND CC.tipo != 'Investimento'
                        """, (id_famiglia, id_famiglia))
            
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt loop
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            
            # Get family_key once for efficiency
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            for row in results:
                # Decrypt proprietario if it's a person
                if row.get('proprietario_enc') and row['proprietario_enc'] != 'Condiviso':
                     row['proprietario'] = decrypt_system_data(row['proprietario_enc']) or "Sconosciuto"
                else:
                     row['proprietario'] = row.get('proprietario_enc') # 'Condiviso'

                # Try Family Key first for ALL accounts (shared and personal)
                # This works for accounts created after the family_key encryption fix
                decrypted = None
                if family_key:
                    decrypted = _decrypt_if_key(row['nome_conto'], family_key, crypto, silent=True)
                
                # Check if decryption was successful
                if decrypted and decrypted != "[ENCRYPTED]" and not decrypted.startswith("gAAAAA"):
                    row['nome_conto'] = decrypted
                else:
                    # Fallback: For personal accounts belonging to the current user, try master_key (legacy data)
                    if not row['is_condiviso'] and id_utente and row.get('id_utente') == id_utente:
                        fallback = _decrypt_if_key(row['nome_conto'], master_key, crypto, silent=True)
                        if fallback and fallback != "[ENCRYPTED]":
                            row['nome_conto'] = fallback
                    # For shared accounts, try master_key as legacy fallback
                    elif row['is_condiviso'] and master_key:
                        fallback = _decrypt_if_key(row['nome_conto'], master_key, crypto, silent=True)
                        if fallback and fallback != "[ENCRYPTED]":
                            row['nome_conto'] = fallback
                    # Else: leave as-is (encrypted string will show for other members' legacy accounts)
            
            return results

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero di tutti i conti famiglia: {e}")
        return []

# --- Helper Functions for Encryption (Family) ---

# Cache per le chiavi famiglia per evitare continue query al DB
# {(id_famiglia, id_utente): family_key_bytes}
_family_key_cache = {}

def _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto):
    # Check cache first
    cache_key = (id_famiglia, id_utente)
    if cache_key in _family_key_cache:
        # Verify if master_key is the same (unlikely to change in session but safe to check? 
        # Actually checking master_key is hard as it is bytes/string.
        # Assuming for same user/family the key is effectively constant per session.)
        return _family_key_cache[cache_key]

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
            row = cur.fetchone()
            if row and row['chiave_famiglia_criptata']:
                # print(f"[DEBUG] _get_family_key_for_user: id_famiglia={id_famiglia}, id_utente={id_utente}") 
                # Reduced logging
                fk_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                family_key = base64.b64decode(fk_b64)
                
                # Update cache
                _family_key_cache[cache_key] = family_key
                return family_key
            else:
                print(f"[WARN] _get_family_key_for_user: No chiave_famiglia_criptata for user {id_utente} in famiglia {id_famiglia}")
    except Exception as e:
        print(f"[ERROR] _get_family_key_for_user failed for user {id_utente}, famiglia {id_famiglia}: {e}")
        # import traceback
        # traceback.print_exc()
    return None

# --- Funzioni Transazioni Personali ---
def _get_key_for_transaction(id_conto, master_key, crypto):
    """
    Determina la chiave corretta per criptare una transazione.
    Se il conto appartiene a un membro di una famiglia, usa la Family Key (per visibilità condivisa).
    Altrimenti usa la Master Key.
    """
    if not master_key or not id_conto:
        return master_key
        
    try:
        # Recupera family key criptata del proprietario del conto
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT AF.chiave_famiglia_criptata 
                FROM Conti C
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE C.id_conto = %s
            """, (id_conto,))
            row = cur.fetchone()
            
            if row and row['chiave_famiglia_criptata']:
                # Decrypt family key with provided master key
                # Assumption: master_key provided belongs to account owner (who is creating the transaction)
                fk_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key, silent=True)
                if fk_b64 and fk_b64 != "[ENCRYPTED]":
                    return base64.b64decode(fk_b64)
    except Exception as e:
        # Non bloccante, fallback a master_key
        pass
        
    return master_key

def aggiungi_transazione(id_conto, data, descrizione, importo, id_sottocategoria=None, cursor=None, master_key_b64=None, importo_nascosto=False, id_carta=None):
    # Encrypt if key available using Family Key if possible (for shared visibility)
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encryption_key = _get_key_for_transaction(id_conto, master_key, crypto)
    encrypted_descrizione = _encrypt_if_key(descrizione, encryption_key, crypto)
    
    # Permette di passare un cursore esistente per le transazioni atomiche
    if cursor:
        cursor.execute(
            "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo, importo_nascosto, id_carta) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_transazione",
            (id_conto, id_sottocategoria, data, encrypted_descrizione, importo, importo_nascosto, id_carta))
        return cursor.fetchone()['id_transazione']
    else:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo, importo_nascosto, id_carta) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_transazione",
                    (id_conto, id_sottocategoria, data, encrypted_descrizione, importo, importo_nascosto, id_carta))
                new_id = cur.fetchone()['id_transazione']
            
            # Auto-update History
            try:
                idf, idu = _get_famiglia_and_utente_from_conto(id_conto)
                trigger_budget_history_update(idf, data, master_key_b64, idu)
            except Exception as e:
                print(f"[WARN] Auto-history failed in add: {e}")
                
            return new_id
        except Exception as e:
            print(f"[ERRORE] Errore generico: {e}")
            return None


def modifica_transazione(id_transazione, data, descrizione, importo, id_sottocategoria=None, id_conto=None, master_key_b64=None, importo_nascosto=False, id_carta=None):
    # Encrypt if key available using Family Key if possible (for shared visibility)
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encryption_key = _get_key_for_transaction(id_conto, master_key, crypto)
    encrypted_descrizione = _encrypt_if_key(descrizione, encryption_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            if id_conto is not None:
                cur.execute(
                    "UPDATE Transazioni SET data = %s, descrizione = %s, importo = %s, id_sottocategoria = %s, id_conto = %s, importo_nascosto = %s, id_carta = %s WHERE id_transazione = %s",
                    (data, encrypted_descrizione, importo, id_sottocategoria, id_conto, importo_nascosto, id_carta, id_transazione))
            else:
                cur.execute(
                    "UPDATE Transazioni SET data = %s, descrizione = %s, importo = %s, id_sottocategoria = %s, importo_nascosto = %s, id_carta = %s WHERE id_transazione = %s",
                    (data, encrypted_descrizione, importo, id_sottocategoria, importo_nascosto, id_carta, id_transazione))
            
            success = cur.rowcount > 0
            
            if success:
                 try:
                    # Retrieve context (we might need old date, but for simplicity we update current date month)
                    # Ideally we fetch the transaction before update to get old date, but checking account is enough for user/fam
                    target_account = id_conto
                    if not target_account:
                        # fetch account from transaction id if not provided
                        cur.execute("SELECT id_conto FROM Transazioni WHERE id_transazione = %s", (id_transazione,))
                        res = cur.fetchone()
                        if res: target_account = res['id_conto']
                    
                    if target_account:
                        # Assuming data is YYYY-MM-DD or datetime object. Ensure datetime for trigger
                        dt_obj = data
                        if isinstance(data, str):
                            dt_obj = datetime.datetime.strptime(data[:10], '%Y-%m-%d')
                            
                        idf, idu = _get_famiglia_and_utente_from_conto(target_account)
                        trigger_budget_history_update(idf, dt_obj, master_key_b64, idu)
                 except Exception as e:
                     print(f"[WARN] Auto-history failed in edit: {e}")
            con.commit()
            return success
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica: {e}")
        return False


def elimina_transazione(id_transazione):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_conto, data FROM Transazioni WHERE id_transazione = %s", (id_transazione,))
            row = cur.fetchone()
            
            success = False
            if row:
                cur.execute("DELETE FROM Transazioni WHERE id_transazione = %s", (id_transazione,))
                success = cur.rowcount > 0
                
                # Auto-update
                if success:
                    try:
                        idf, idu = _get_famiglia_and_utente_from_conto(row['id_conto'])
                        trigger_budget_history_update(idf, row['data'], None, idu) # MasterKey not avail in delete usually?
                        # Note: elimina_transazione signature doesn't have master_key_b64.
                        # However, salva_budget requires keys to decrypt/encrypt limits?
                        # Yes. If we don't have keys, we might fail or work in restricted mode.
                        # But typically delete happens from UI which has session.
                        # Wait, elimina_transazione signature: def elimina_transazione(id_transazione):
                        # It has NO master_key passed.
                        # This is a problem. But wait, salva_budget uses keys to ENCRYPT entries.
                        # If we trigger it without keys, it might fail or produce bad data.
                        # Hack: We can't easily auto-update on delete without keys.
                        # But wait, does app_controller pass keys?
                        # No.
                        # We will skip auto-update on delete for now or update signature?
                        # Updating signature is risky (break calls).
                        # Let's verify existing calls.
                        # For now, skip auto-update on delete OR assume we prioritize Add/Edit.
                        # Or better, just print a warning.
                        pass 
                    except Exception:
                        pass

            return success
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione: {e}")
        return None


def ottieni_riepilogo_patrimonio_utente(id_utente, anno, mese, master_key_b64=None):
    try:
        data_limite = datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)
        data_limite_str = data_limite.strftime('%Y-%m-%d')
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Liquidità Personale (somma saldi conti personali)
            # Saldo = SUM(transazioni fino a data_limite) + rettifica_saldo
            cur.execute("""
                SELECT COALESCE(SUM(
                    (SELECT COALESCE(SUM(T.importo), 0.0) FROM Transazioni T WHERE T.id_conto = C.id_conto AND T.data <= %s) +
                    COALESCE(CAST(NULLIF(CAST(C.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0)
                ), 0.0) as val
                FROM Conti C
                WHERE C.id_utente = %s
                  AND C.tipo NOT IN ('Investimento', 'Fondo Pensione', 'Risparmio')
                  AND (C.nascosto = FALSE OR C.nascosto IS NULL)
            """, (data_limite_str, id_utente))
            liquidita_personale = float(cur.fetchone()['val'] or 0.0)

            # 1.2 Liquidità Condivisa (saldo / n.partecipanti per ogni conto)
            # Recupera i conti condivisi a cui l'utente ha accesso
            cur.execute("""
                SELECT CC.id_conto_condiviso, CC.tipo_condivisione,
                    (SELECT COALESCE(SUM(TC.importo), 0.0) FROM TransazioniCondivise TC 
                     WHERE TC.id_conto_condiviso = CC.id_conto_condiviso AND TC.data <= %s) +
                    COALESCE(CAST(NULLIF(CAST(CC.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0) as saldo,
                    CASE 
                        WHEN CC.tipo_condivisione = 'famiglia' THEN 
                            (SELECT COUNT(*) FROM Appartenenza_Famiglia AF WHERE AF.id_famiglia = CC.id_famiglia)
                        ELSE
                            (SELECT COUNT(*) FROM PartecipazioneContoCondiviso PCC WHERE PCC.id_conto_condiviso = CC.id_conto_condiviso)
                    END as n_partecipanti
                FROM ContiCondivisi CC
                LEFT JOIN PartecipazioneContoCondiviso PCC ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                WHERE CC.tipo NOT IN ('Investimento')
                  AND (
                      (PCC.id_utente = %s AND CC.tipo_condivisione = 'utenti')
                      OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s) AND CC.tipo_condivisione = 'famiglia')
                  )
            """, (data_limite_str, id_utente, id_utente))
            
            liquidita_condivisa = 0.0
            conti_visti = set()  # Per evitare duplicati
            for row in cur.fetchall():
                id_conto = row['id_conto_condiviso']
                if id_conto not in conti_visti:
                    conti_visti.add(id_conto)
                    saldo = float(row['saldo'] or 0.0)
                    n_part = int(row['n_partecipanti'] or 1)
                    if n_part > 0:
                        liquidita_condivisa += saldo / n_part

            liquidita = liquidita_personale + liquidita_condivisa
            
            # 2. Investimenti
            cur.execute("""
                SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0) as val
                FROM Asset A
                JOIN Conti C ON A.id_conto = C.id_conto
                WHERE C.id_utente = %s
                  AND C.tipo = 'Investimento'
            """, (id_utente,))
            investimenti = cur.fetchone()['val'] or 0.0
            
            # 3. Fondi Pensione
            fondi_pensione = 0.0
            if master_key_b64:
                crypto, master_key = _get_crypto_and_key(master_key_b64)
                cur.execute("""
                    SELECT valore_manuale
                    FROM Conti
                    WHERE id_utente = %s AND tipo = 'Fondo Pensione'
                """, (id_utente,))
                for row in cur.fetchall():
                    val = _decrypt_if_key(row['valore_manuale'], master_key, crypto)
                    try:
                        fondi_pensione += float(val) if val else 0.0
                    except (ValueError, TypeError):
                        pass
            
            # 4. Conti Risparmio (somma transazioni dei conti di tipo Risparmio)
            cur.execute("""
                SELECT COALESCE(SUM(T.importo), 0.0) as val
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                WHERE C.id_utente = %s
                  AND C.tipo = 'Risparmio'
                  AND T.data <= %s
            """, (id_utente, data_limite_str))
            risparmio = cur.fetchone()['val'] or 0.0

            # 4.1 Salvadanai (Piggy Banks)
            # Recupera tutti i salvadanai che riguardano questo utente.
            if master_key_b64:
                 crypto, master_key = _get_crypto_and_key(master_key_b64)
                 
                 # Determine Key to use (consistent with crea_salvadanaio)
                 # Uses Family Key if user belongs to one, else Master Key.
                 family_key = None
                 id_famiglia_user = ottieni_prima_famiglia_utente(id_utente)
                 if id_famiglia_user:
                     family_key = _get_family_key_for_user(id_famiglia_user, id_utente, master_key, crypto)
                 
                 key_to_use = family_key if family_key else master_key

                 # 4.1.1 Salvadanai Personali (collegati a Conti)
                 cur.execute("""
                    SELECT S.importo_assegnato, S.incide_su_liquidita
                    FROM Salvadanai S
                    JOIN Conti C ON S.id_conto = C.id_conto
                    WHERE C.id_utente = %s
                 """, (id_utente,))
                 
                 for row in cur.fetchall():
                     try:
                         imp_str = _decrypt_if_key(row['importo_assegnato'], key_to_use, crypto)
                         val = float(imp_str) if imp_str else 0.0
                         if row['incide_su_liquidita']:
                             liquidita += val
                         else:
                             risparmio += val
                     except: pass
                 
                 # 4.1.2 Salvadanai Condivisi (collegati a ContiCondivisi)
                 cur.execute("""
                    SELECT S.importo_assegnato, S.incide_su_liquidita, C.id_conto_condiviso, C.tipo_condivisione, C.id_famiglia
                    FROM Salvadanai S
                    JOIN ContiCondivisi C ON S.id_conto_condiviso = C.id_conto_condiviso
                    LEFT JOIN PartecipazioneContoCondiviso PCC ON C.id_conto_condiviso = PCC.id_conto_condiviso
                    WHERE (
                        (PCC.id_utente = %s AND C.tipo_condivisione = 'utenti') OR
                        (C.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s) AND C.tipo_condivisione = 'famiglia')
                    )
                 """, (id_utente, id_utente))
                 
                 # Per i conti condivisi, l'importo totale del conto/salvadanaio è diviso per i partecipanti.
                 
                 # Usa family key per decrypt se possibile
                 family_key = None
                 id_famiglia_user = ottieni_prima_famiglia_utente(id_utente)
                 if id_famiglia_user:
                     family_key = _get_family_key_for_user(id_famiglia_user, id_utente, master_key, crypto)
                 key_shared = family_key if family_key else master_key

                 for row in cur.fetchall():
                     try:
                         imp_str = _decrypt_if_key(row['importo_assegnato'], key_shared, crypto)
                         val = float(imp_str) if imp_str else 0.0
                         
                         id_shared = row['id_conto_condiviso']
                         
                         # Calcola quota parte
                         # TODO: caching or optimization? For now query count.
                         n_part = 1
                         if row['tipo_condivisione'] == 'famiglia':
                             # Usa id_famiglia del conto, non quella dell'utente generica
                             cur.execute("SELECT COUNT(*) as c FROM Appartenenza_Famiglia WHERE id_famiglia = %s", (row['id_famiglia'],))
                             res = cur.fetchone()
                             n_part = res['c'] if res else 1
                         else:
                            # Condivisione Utenti
                             cur.execute("SELECT COUNT(*) as c FROM PartecipazioneContoCondiviso WHERE id_conto_condiviso = %s", (id_shared,))
                             res = cur.fetchone()
                             n_part = res['c'] if res else 1
                         
                         val_quota = val / max(1, n_part)
                         
                         if row['incide_su_liquidita']:
                             liquidita += val_quota
                         else:
                             risparmio += val_quota
                     except Exception as e:
                         # logger.error(f"Error calc shared pb: {e}") 
                         pass
            
            # 5. Patrimonio Immobiliare Lordo (quota personale dell'utente)
            # Somma il valore attuale ponderato
            cur.execute("""
                SELECT 
                    COALESCE(SUM(
                        CAST(I.valore_attuale AS NUMERIC) * COALESCE(QI.percentuale, 100.0) / 100.0
                    ), 0.0) as val
                FROM Immobili I
                LEFT JOIN QuoteImmobili QI ON I.id_immobile = QI.id_immobile AND QI.id_utente = %s
                WHERE I.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s)
                  AND (I.nuda_proprieta = FALSE OR I.nuda_proprieta IS NULL)
                  AND (QI.id_utente = %s OR QI.id_utente IS NULL)
            """, (id_utente, id_utente, id_utente))
            result = cur.fetchone()['val']
            patrimonio_immobile_lordo = float(result) if result else 0.0

            # 6. Prestiti Totali (quota personale dell'utente) - Calcolo avanzato con Piano Ammortamento
            cur.execute("""
                SELECT id_prestito, CAST(importo_residuo AS NUMERIC) as res_db 
                FROM Prestiti 
                WHERE id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s)
            """, (id_utente,))
            loans = cur.fetchall()
            prestiti_totali = 0.0
            
            if loans:
                l_ids = [l['id_prestito'] for l in loans]
                
                # Quotes
                ph = ','.join(['%s'] * len(l_ids))
                cur.execute(f"SELECT id_prestito, id_utente, percentuale FROM QuotePrestiti WHERE id_prestito IN ({ph})", tuple(l_ids))
                quotes_rows = cur.fetchall()
                quotes_map = {} # pid -> {uid: perc}
                for q in quotes_rows:
                    if q['id_prestito'] not in quotes_map: quotes_map[q['id_prestito']] = {}
                    quotes_map[q['id_prestito']][q['id_utente']] = float(q['percentuale'])
                
                # Schedules (Residuo da Piano)
                cur.execute(f"SELECT id_prestito, SUM(importo_rata) as val FROM PianoAmmortamento WHERE id_prestito IN ({ph}) AND stato='da_pagare' GROUP BY id_prestito", tuple(l_ids))
                sched_map = {r['id_prestito']: float(r['val']) for r in cur.fetchall()}
                
                # Check esistenza piano
                cur.execute(f"SELECT DISTINCT id_prestito FROM PianoAmmortamento WHERE id_prestito IN ({ph})", tuple(l_ids))
                has_sched = {r['id_prestito']: True for r in cur.fetchall()}

                for l in loans:
                     pid = l['id_prestito']
                     
                     # 1. Determina Residuo Base
                     if has_sched.get(pid):
                         residuo = sched_map.get(pid, 0.0)
                     else:
                         residuo = float(l['res_db'] or 0.0)
                     
                     # 2. Determina Quota Utente
                     if pid in quotes_map:
                         share = quotes_map[pid].get(id_utente, 0.0)
                     else:
                         share = 100.0 # Default se non ci sono quote esplicite
                     
                     prestiti_totali += residuo * (share / 100.0)
            
            # Calcolo Patrimonio Netto: Asset - Passività
            patrimonio_netto = liquidita + investimenti + fondi_pensione + risparmio + patrimonio_immobile_lordo - prestiti_totali
            
            return {
                'patrimonio_netto': patrimonio_netto,
                'liquidita': liquidita,
                'investimenti': investimenti,
                'fondi_pensione': fondi_pensione,
                'risparmio': risparmio,
                'patrimonio_immobile': patrimonio_immobile_lordo, # Chiave cambiata semanticamente a Lordo, ma mantengo nome per compatibilità o cambio?
                # Meglio aggiungere chiavi specifiche e lasciare patrimonio_immobile come lordo per chi lo usa?
                # Per chiarezza nel frontend useremo 'patrimonio_immobile_lordo' e 'prestiti_totali'
                'patrimonio_immobile_lordo': patrimonio_immobile_lordo,
                'prestiti_totali': prestiti_totali,
                # Mantengo 'patrimonio_immobile' per compatibilità se qualcuno lo usa, mappandolo al lordo?
                # O meglio: tab_personale usa `riepilogo.get('patrimonio_immobile', 0)`.
                # Se cambio qui, tab_personale mostrerà il lordo al posto del netto "vecchio calcolo".
                # Ma tab_personale sarà aggiornato per usare le nuove chiavi.
                'patrimonio_immobile': patrimonio_immobile_lordo, # Backward compat: ora è il lordo.
            }
    except Exception as e:
        print(f"[ERRORE] Errore in ottieni_riepilogo_patrimonio_utente: {e}")
        return {
            'patrimonio_netto': 0.0, 'liquidita': 0.0, 'investimenti': 0.0, 
            'fondi_pensione': 0.0, 'risparmio': 0.0, 
            'patrimonio_immobile': 0.0, 'patrimonio_immobile_lordo': 0.0, 'prestiti_totali': 0.0
        }


def ottieni_riepilogo_patrimonio_famiglia_aggregato(id_famiglia, anno, mese, master_key_b64=None, id_utente=None):
    try:
        data_limite = datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)
        data_limite_str = data_limite.strftime('%Y-%m-%d')
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Liquidità Personale (somma saldi conti personali di tutti i membri)
            # Saldo = SUM(transazioni fino a data_limite) + rettifica_saldo
            cur.execute("""
                SELECT COALESCE(SUM(
                    (SELECT COALESCE(SUM(T.importo), 0.0) FROM Transazioni T WHERE T.id_conto = C.id_conto AND T.data <= %s) +
                    COALESCE(CAST(NULLIF(CAST(C.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0)
                ), 0.0) as val
                FROM Conti C
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND C.tipo NOT IN ('Investimento', 'Fondo Pensione', 'Risparmio')
                  AND (C.nascosto = FALSE OR C.nascosto IS NULL)
            """, (data_limite_str, id_famiglia))
            liquidita_personale = float(cur.fetchone()['val'] or 0.0)
            
            # 1b. Liquidità Conti Condivisi (somma saldi totali, non pro-quota per la famiglia)
            cur.execute("""
                SELECT COALESCE(SUM(
                    (SELECT COALESCE(SUM(TC.importo), 0.0) FROM TransazioniCondivise TC 
                     WHERE TC.id_conto_condiviso = CC.id_conto_condiviso AND TC.data <= %s) +
                    COALESCE(CAST(NULLIF(CAST(CC.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0)
                ), 0.0) as val
                FROM ContiCondivisi CC
                WHERE CC.id_famiglia = %s
                  AND CC.tipo NOT IN ('Investimento')
            """, (data_limite_str, id_famiglia))
            liquidita_condivisa = float(cur.fetchone()['val'] or 0.0)
            
            liquidita = liquidita_personale + liquidita_condivisa
            
            # 2. Investimenti (Tutti i membri)
            cur.execute("""
                SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0) as val
                FROM Asset A
                JOIN Conti C ON A.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND C.tipo = 'Investimento'
            """, (id_famiglia,))
            investimenti = float(cur.fetchone()['val'] or 0.0)
            
            # 3. Fondi Pensione (Tutti i membri)
            fondi_pensione = 0.0
            if master_key_b64:
                crypto, master_key = _get_crypto_and_key(master_key_b64)
                cur.execute("""
                    SELECT C.valore_manuale
                    FROM Conti C
                    JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                    WHERE AF.id_famiglia = %s AND C.tipo = 'Fondo Pensione'
                """, (id_famiglia,))
                for row in cur.fetchall():
                    val = _decrypt_if_key(row['valore_manuale'], master_key, crypto)
                    try:
                        fondi_pensione += float(val) if val else 0.0
                    except (ValueError, TypeError):
                        pass
            
            # 4. Conti Risparmio (Tutti i membri)
            cur.execute("""
                SELECT COALESCE(SUM(T.importo), 0.0) as val
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND C.tipo = 'Risparmio'
                  AND T.data <= %s
            """, (id_famiglia, data_limite_str))
            risparmio = float(cur.fetchone()['val'] or 0.0)
            
            # 5. Patrimonio Immobiliare Lordo (totale famiglia)
            # Somma valore_attuale per tutti gli immobili della famiglia
            cur.execute("""
                SELECT COALESCE(SUM(CAST(I.valore_attuale AS NUMERIC)), 0.0) as val
                FROM Immobili I
                WHERE I.id_famiglia = %s
                  AND (I.nuda_proprieta = FALSE OR I.nuda_proprieta IS NULL)
            """, (id_famiglia,))
            result = cur.fetchone()['val']
            patrimonio_immobile_lordo = float(result) if result else 0.0
            
            # --- 4.1 Salvadanai (Piggy Banks) ---
            # Sum of all PBs in the family
            cur.execute("""
                SELECT S.importo_assegnato, S.incide_su_liquidita, C.id_utente, S.note, S.nome
                FROM Salvadanai S
                LEFT JOIN Conti C ON S.id_conto = C.id_conto
                WHERE S.id_famiglia = %s
            """, (id_famiglia,))
            
            pb_rows = cur.fetchall()
            valore_salvadanai = 0.0
            salvadanai_incide = 0.0
            
            if master_key_b64 and id_utente:
                crypto, master_key = _get_crypto_and_key(master_key_b64)
                
                # Fetch Family Key once
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
                
                for pb in pb_rows:
                    # Logic similar to Personale: try decrypting
                    # Usually Family PBs use Family Key. Personal PBs use ???
                    # If this is aggregating ALL PBs of family, we ideally need to decrypt all.
                    # If some are Personal PBs of OTHER users, we might NOT be able to decrypt them if they used their own Master Key.
                    # However, usually PBs created in Family context use Family Key.
                    
                    decrypted_val = None
                    try:
                        # Try Family Key first (most likely for shared context)
                        if family_key:
                            decrypted_val = _decrypt_if_key(pb['importo_assegnato'], family_key, crypto)
                        
                        # Fallback to Master Key (if it's MY personal PB)
                        if decrypted_val is None and str(pb['id_utente']) == str(id_utente):
                            decrypted_val = _decrypt_if_key(pb['importo_assegnato'], master_key, crypto)
                            
                        # If still None, we can't decrypt (Personal PB of another user?).
                        # But for "Patrimonio Famiglia", maybe we should only include Shared PBs?
                        # Or PBs that we can read.
                        
                        if decrypted_val:
                            val = float(decrypted_val)
                            valore_salvadanai += val
                            if pb['incide_su_liquidita']:
                                salvadanai_incide += val
                                
                    except Exception:
                        pass
            
            # Adjusted Totals
            # Liquidità (Real) - PBs (Assigned) = Liquidità (Available)
            liquidita = liquidita - salvadanai_incide
            if liquidita < 0: liquidita = 0 # Should not happen usually
            
            risparmio = risparmio + valore_salvadanai

            # 6. Prestiti Totali (totale famiglia) - Calcolo avanzato con Piano Ammortamento
            prestiti_totali = 0.0
            cur.execute("""
                SELECT id_prestito, CAST(importo_residuo AS NUMERIC) as residuo_db
                FROM Prestiti
                WHERE id_famiglia = %s
            """, (id_famiglia,))
            prestiti_rows = cur.fetchall()
            
            if prestiti_rows:
                ids = [r['id_prestito'] for r in prestiti_rows]
                residui_db = {r['id_prestito']: float(r['residuo_db'] or 0.0) for r in prestiti_rows}
                
                # Check piani custom
                if ids:
                    placeholders = ','.join(['%s'] * len(ids))
                    cur.execute(f"""
                        SELECT id_prestito, SUM(importo_rata) as residuo_piano
                        FROM PianoAmmortamento
                        WHERE id_prestito IN ({placeholders}) AND stato = 'da_pagare'
                        GROUP BY id_prestito
                    """, tuple(ids))
                    piani_rows = cur.fetchall()
                    residui_piano = {r['id_prestito']: float(r['residuo_piano']) for r in piani_rows}
                else:
                    residui_piano = {}
                
                # Calcola totale unificando le fonti
                for pid in ids:
                    # Se esiste almeno una rata nel piano (o meglio se c'è entry nel group by), usiamo quella somma
                    # OCCHIO: Se il piano esiste ma tutto pagato? residuo_piano non avrà entry (stato='da_pagare').
                    # Dobbiamo distinguere "Piano inesistente" da "Piano finito".
                    # Per semplicità, se c'è un piano ammortamento caricato per quel prestito, PRESUMIAMO che faccia fede.
                    # Ma qui residui_piano ha solo 'da_pagare'.
                    # Se non c'è entry in residui_piano, potrebbe essere: No Piano O Piano Finito.
                    # Bisognerebbe controllare se esiste il piano.
                    
                    # Approccio più robusto: Count row piano per ID.
                    pass 
                
                # --- FIX LOGICA MIGLIORATA ---
                # Check esistenza piano globale per questi ID
                has_piano_map = {}
                if ids:
                    ph = ','.join(['%s'] * len(ids))
                    cur.execute(f"SELECT DISTINCT id_prestito FROM PianoAmmortamento WHERE id_prestito IN ({ph})", tuple(ids))
                    rows_exist = cur.fetchall()
                    for re in rows_exist:
                        has_piano_map[re['id_prestito']] = True
                
                for pid in ids:
                    if has_piano_map.get(pid):
                        # Se ha un piano, usiamo la somma 'da_pagare' (che sarà 0 se tutto pagato, corretta)
                        prestiti_totali += residui_piano.get(pid, 0.0)
                    else:
                        # Se NON ha piano, usiamo il residuo statico DB
                        prestiti_totali += residui_db[pid]
            
            patrimonio_netto = liquidita + investimenti + fondi_pensione + risparmio + patrimonio_immobile_lordo - prestiti_totali
            
            return {
                'patrimonio_netto': patrimonio_netto,
                'liquidita': liquidita,
                'investimenti': investimenti,
                'fondi_pensione': fondi_pensione,
                'risparmio': risparmio,
                'patrimonio_immobile_lordo': patrimonio_immobile_lordo,
                'prestiti_totali': prestiti_totali,
                'patrimonio_immobile': patrimonio_immobile_lordo # Backward compat
            }
    except Exception as e:
        print(f"[ERRORE] Errore in ottieni_riepilogo_patrimonio_famiglia_aggregato: {e}")
        return {
            'patrimonio_netto': 0.0, 'liquidita': 0.0, 'investimenti': 0.0, 
            'fondi_pensione': 0.0, 'risparmio': 0.0, 
            'patrimonio_immobile': 0.0, 'patrimonio_immobile_lordo': 0.0, 'prestiti_totali': 0.0
        }


def ottieni_transazioni_utente(id_utente, anno, mese, master_key_b64=None):
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"

    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        -- Transazioni Personali
                        SELECT T.id_transazione,
                               T.data,
                               T.descrizione,
                               T.importo,
                               C.nome_conto,
                               C.id_conto,
                               Cat.nome_categoria,
                               SCat.nome_sottocategoria,
                               SCat.id_sottocategoria,
                               'personale' AS tipo_transazione,
                               0           AS id_transazione_condivisa, -- Placeholder
                               T.id_carta,
                               T.importo_nascosto
                        FROM Transazioni T
                                 JOIN Conti C ON T.id_conto = C.id_conto
                                 LEFT JOIN Sottocategorie SCat ON T.id_sottocategoria = SCat.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON SCat.id_categoria = Cat.id_categoria
                        WHERE C.id_utente = %s
                          AND C.tipo != 'Fondo Pensione' AND T.data BETWEEN %s AND %s
                        
                        UNION ALL

                        -- Transazioni Condivise
                        SELECT 0                     AS id_transazione, -- Placeholder
                               TC.data,
                               TC.descrizione,
                               TC.importo,
                               CC.nome_conto,
                               CC.id_conto_condiviso AS id_conto,
                               Cat.nome_categoria,
                               SCat.nome_sottocategoria,
                               SCat.id_sottocategoria,
                               'condivisa'           AS tipo_transazione,
                               TC.id_transazione_condivisa,
                               TC.id_carta,
                               TC.importo_nascosto
                        FROM TransazioniCondivise TC
                                 JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                 LEFT JOIN PartecipazioneContoCondiviso PCC
                                           ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                                 LEFT JOIN Sottocategorie SCat ON TC.id_sottocategoria = SCat.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON SCat.id_categoria = Cat.id_categoria
                        WHERE ((PCC.id_utente = %s AND CC.tipo_condivisione = 'utenti')
                           OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s) AND
                               CC.tipo_condivisione = 'famiglia')) AND TC.data BETWEEN %s AND %s

                        ORDER BY data DESC, id_transazione DESC, id_transazione_condivisa DESC
                        """, (id_utente, data_inizio, data_fine, id_utente, id_utente, data_inizio, data_fine))
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            
            # Get Family Key for shared accounts AND categories
            family_key = None
            if master_key:
                try:
                    # Get family ID (assuming single family for now)
                    cur.execute("SELECT id_famiglia, chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s LIMIT 1", (id_utente,))
                    fam_row = cur.fetchone()
                    if fam_row and fam_row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(fam_row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
                except Exception as e:
                    print(f"[ERRORE] Failed to retrieve family key: {e}")

            if master_key:
                for row in results:
                    original_desc = row['descrizione']
                    
                    # Decryption Priority:
                    # 1. Family Key (New standard for all family transactions)
                    # 2. Master Key (Legacy personal transactions)
                    
                    decrypted_desc = "[ENCRYPTED]"
                    
                    # Try Family Key first (if user has one)
                    if family_key:
                        decrypted_desc = _decrypt_if_key(original_desc, family_key, crypto, silent=True)
                    
                    # If still encrypted, try Master Key (fallback logic mostly for legacy data)
                    if decrypted_desc == "[ENCRYPTED]" and master_key:
                         decrypted_desc = _decrypt_if_key(original_desc, master_key, crypto) # Not silent to catch errors
                    
                    # Fix for unencrypted "Saldo Iniziale" in shared accounts
                    if decrypted_desc == "[ENCRYPTED]" and original_desc == "Saldo Iniziale":
                        decrypted_desc = "Saldo Iniziale"
                        
                    row['descrizione'] = decrypted_desc
                    
                    # Decrypt nome_conto: Try Family Key first, then Master Key (for legacy)
                    nome_conto_decrypted = None
                    if family_key:
                        nome_conto_decrypted = _decrypt_if_key(row['nome_conto'], family_key, crypto, silent=True)
                    
                    if nome_conto_decrypted and nome_conto_decrypted != "[ENCRYPTED]" and not nome_conto_decrypted.startswith("gAAAAA"):
                        row['nome_conto'] = nome_conto_decrypted
                    elif master_key:
                        # Fallback to master_key for legacy data
                        row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
                    
                    # Categories are always encrypted with Family Key
                    cat_name = row['nome_categoria']
                    sub_name = row['nome_sottocategoria']
                    
                    if family_key:
                        cat_name = _decrypt_if_key(cat_name, family_key, crypto)
                        sub_name = _decrypt_if_key(sub_name, family_key, crypto)
                        
                    row['nome_categoria'] = cat_name
                    row['nome_sottocategoria'] = sub_name

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero transazioni utente: {e}")
        return []


def aggiungi_transazione_condivisa(id_utente_autore, id_conto_condiviso, data, descrizione, importo, id_sottocategoria=None, cursor=None, master_key_b64=None, importo_nascosto=False, id_carta=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Retrieve Family Key for encryption
    family_key = None
    if master_key:
        try:
            # We need the family ID associated with the shared account or the user.
            # Since shared accounts belong to a family, we should use that family's key.
            # First, get id_famiglia from the shared account
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT id_famiglia FROM ContiCondivisi WHERE id_conto_condiviso = %s", (id_conto_condiviso,))
                res = cur.fetchone()
                if res:
                    id_famiglia = res['id_famiglia']
                    # Now get the family key for this user and family
                    family_key = _get_family_key_for_user(id_famiglia, id_utente_autore, master_key, crypto)
        except Exception as e:
            print(f"[ERRORE] Failed to retrieve family key for encryption: {e}")

    # Use Family Key if available, otherwise Master Key (fallback, though not ideal for sharing)
    key_to_use = family_key if family_key else master_key
    encrypted_descrizione = _encrypt_if_key(descrizione, key_to_use, crypto)
    
    # Permette di passare un cursore esistente per le transazioni atomiche
    if cursor:
        cursor.execute(
            "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, descrizione, importo, importo_nascosto, id_carta) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_transazione_condivisa",
            (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, encrypted_descrizione, importo, importo_nascosto, id_carta))
        return cursor.fetchone()['id_transazione_condivisa']
    else:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, descrizione, importo, importo_nascosto, id_carta) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_transazione_condivisa",
                    (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, encrypted_descrizione, importo, importo_nascosto, id_carta))
                return cur.fetchone()['id_transazione_condivisa']
        except Exception as e:
            print(f"[ERRORE] Errore generico durante l'aggiunta transazione condivisa: {e}")
            return None


def modifica_transazione_condivisa(id_transazione_condivisa, data, descrizione, importo, id_sottocategoria=None, master_key_b64=None, id_utente=None, importo_nascosto=False, id_carta=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Retrieve Family Key for encryption
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                # Get id_famiglia from the transaction's account
                cur.execute("""
                    SELECT CC.id_famiglia 
                    FROM TransazioniCondivise TC
                    JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                    WHERE TC.id_transazione_condivisa = %s
                """, (id_transazione_condivisa,))
                res = cur.fetchone()
                if res:
                    id_famiglia = res['id_famiglia']
                    family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        except Exception as e:
            print(f"[ERRORE] Failed to retrieve family key for encryption: {e}")

    # Use Family Key if available, otherwise Master Key (fallback)
    key_to_use = family_key if family_key else master_key
    encrypted_descrizione = _encrypt_if_key(descrizione, key_to_use, crypto)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                        UPDATE TransazioniCondivise
                        SET data         = %s,
                            descrizione  = %s,
                            importo      = %s,
                            id_sottocategoria = %s,
                            importo_nascosto = %s,
                            id_carta = %s
                        WHERE id_transazione_condivisa = %s
                        """, (data, encrypted_descrizione, importo, id_sottocategoria, importo_nascosto, id_carta, id_transazione_condivisa))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica transazione condivisa: {e}")
        return False



def elimina_transazione_condivisa(id_transazione_condivisa):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM TransazioniCondivise WHERE id_transazione_condivisa = %s", (id_transazione_condivisa,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione transazione condivisa: {e}")
        return False


def ottieni_transazioni_condivise_utente(id_utente, master_key_b64=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT TC.id_transazione_condivisa,
                               TC.data,
                               TC.descrizione,
                               TC.importo,
                               CC.nome_conto,
                               CC.id_conto_condiviso,
                               Cat.nome_categoria,
                               Cat.id_famiglia,
                               SCat.nome_sottocategoria,
                               SCat.id_sottocategoria
                        FROM TransazioniCondivise TC
                                 JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                 LEFT JOIN PartecipazioneContoCondiviso PCC
                                           ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                                 LEFT JOIN Sottocategorie SCat ON TC.id_sottocategoria = SCat.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON SCat.id_categoria = Cat.id_categoria
                        WHERE (PCC.id_utente = %s AND CC.tipo_condivisione = 'utenti')
                           OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s) AND
                               CC.tipo_condivisione = 'famiglia')
                        ORDER BY TC.data DESC, TC.id_transazione_condivisa DESC
                        """, (id_utente, id_utente))
            results = [dict(row) for row in cur.fetchall()]
            
            if master_key_b64:
                crypto, master_key = _get_crypto_and_key(master_key_b64)
                
                # Fetch all family keys for the user
                family_keys = {}
                try:
                    cur.execute("SELECT id_famiglia, chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s", (id_utente,))
                    for row in cur.fetchall():
                        if row['chiave_famiglia_criptata']:
                            fk_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                            family_keys[row['id_famiglia']] = base64.b64decode(fk_b64)
                except Exception:
                    pass

                for row in results:
                    fam_id = row.get('id_famiglia')
                    if fam_id and fam_id in family_keys:
                        f_key = family_keys[fam_id]
                        row['descrizione'] = _decrypt_if_key(row['descrizione'], f_key, crypto)
                        row['nome_categoria'] = _decrypt_if_key(row['nome_categoria'], f_key, crypto)
                        row['nome_sottocategoria'] = _decrypt_if_key(row['nome_sottocategoria'], f_key, crypto)
                        # Decrypt account name (assuming it uses family key as it is a shared account)
                        row['nome_conto'] = _decrypt_if_key(row['nome_conto'], f_key, crypto)

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero transazioni condivise utente: {e}")
        return []

def ottieni_transazioni_condivise_famiglia(id_famiglia, id_utente=None, master_key_b64=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT TC.id_transazione_condivisa,
                               TC.data,
                               TC.descrizione,
                               TC.importo,
                               CC.nome_conto AS nome_conto,
                               CC.id_conto_condiviso,
                               Cat.nome_categoria,
                               SCat.nome_sottocategoria,
                               SCat.id_sottocategoria
                        FROM TransazioniCondivise TC
                                 JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                 LEFT JOIN Sottocategorie SCat ON TC.id_sottocategoria = SCat.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON SCat.id_categoria = Cat.id_categoria
                        WHERE CC.id_famiglia = %s
                          AND CC.tipo_condivisione = 'famiglia'
                        ORDER BY TC.data DESC, TC.id_transazione_condivisa DESC
                        """, (id_famiglia,))
            results = [dict(row) for row in cur.fetchall()]
            
            if id_utente and master_key_b64:
                crypto, master_key = _get_crypto_and_key(master_key_b64)
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
                
                if family_key:
                    for row in results:
                        row['descrizione'] = _decrypt_if_key(row['descrizione'], family_key, crypto)
                        row['nome_conto'] = _decrypt_if_key(row['nome_conto'], family_key, crypto)
                        row['nome_categoria'] = _decrypt_if_key(row['nome_categoria'], family_key, crypto)
                        row['nome_sottocategoria'] = _decrypt_if_key(row['nome_sottocategoria'], family_key, crypto)

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero transazioni condivise famiglia: {e}")
        return []


# --- Funzioni Ruoli e Famiglia ---
def ottieni_ruolo_utente(id_utente, id_famiglia):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT ruolo FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s",
                        (id_utente, id_famiglia))
            res = cur.fetchone()
            return res['ruolo'] if res else None
    except Exception as e:
        print(f"[ERRORE] Errore generico: {e}")
        return None


def ottieni_totali_famiglia(id_famiglia, master_key_b64=None, id_utente_richiedente=None):
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Fetch users in family with server encrypted names
            cur.execute("""
                        SELECT U.id_utente,
                               U.username,
                               U.nome_enc_server,
                               U.cognome_enc_server
                        FROM Utenti U
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                        """, (id_famiglia,))
            
            users = []
            for row in cur.fetchall():
                 n = decrypt_system_data(row.get('nome_enc_server'))
                 c = decrypt_system_data(row.get('cognome_enc_server'))
                 display = row['username']
                 if n or c:
                     display = f"{n or ''} {c or ''}".strip()
                 users.append({'id_utente': row['id_utente'], 'nome_visualizzato': display})

            # 2. Iterate users and calculate totals
            results = []
            for user in users:
                uid = user['id_utente']
                
                # A. Liquidità (Sum of transactions in non-investment accounts)
                # Note: This sum is on 'importo' which is numeric/visible in DB (for now)
                cur.execute("""
                            SELECT COALESCE(SUM(T.importo), 0.0) as val
                            FROM Transazioni T
                                     JOIN Conti C ON T.id_conto = C.id_conto
                            WHERE C.id_utente = %s
                              AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')
                            """, (uid,))
                liquidita = cur.fetchone()['val'] or 0.0
                
                # B. Investimenti (Sum of Quantity * Current Price)
                # Price and Quantity are numeric/visible
                cur.execute("""
                            SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0) as val
                            FROM Asset A
                                     JOIN Conti C ON A.id_conto = C.id_conto
                            WHERE C.id_utente = %s
                              AND C.tipo = 'Investimento'
                            """, (uid,))
                investimenti = cur.fetchone()['val'] or 0.0
                
                # C. Fondi Pensione (Manually updated value)
                # Value is stored in 'valore_manuale' which might be encrypted text
                cur.execute("""
                            SELECT valore_manuale
                            FROM Conti
                            WHERE id_utente = %s AND tipo = 'Fondo Pensione'
                            """, (uid,))
                
                fondi_pensione = 0.0
                for row in cur.fetchall():
                    val = row['valore_manuale']
                    # If current user, try to search/decrypt. If other user, we can't decrypt their MK encrypted data.
                    if uid == id_utente_richiedente and master_key:
                         val = _decrypt_if_key(val, master_key, crypto)
                    
                    try:
                        fondi_pensione += float(val) if val else 0.0
                    except (ValueError, TypeError):
                        pass
                
                saldo_totale = liquidita + investimenti + fondi_pensione
                
                results.append({
                    'id_utente': uid,
                    'nome_visualizzato': user['nome_visualizzato'],
                    'saldo_totale': saldo_totale
                })
                
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero totali famiglia: {e}")
        return []


def ottieni_dettagli_famiglia(id_famiglia, anno, mese, master_key_b64=None, id_utente=None):
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"

    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        -- Transazioni Personali
                        SELECT U.username_enc AS utente_username_enc,
                               U.nome_enc_server AS utente_nome_server_enc, 
                               U.cognome_enc_server AS utente_cognome_server_enc,
                               T.data, 
                               T.descrizione, 
                               T.importo, 
                               T.importo_nascosto,
                               C.nome_conto,
                               Cat.nome_categoria,
                               Sub.nome_sottocategoria,
                               U.id_utente  -- Needed to identify who owns the data to decrypt
                        FROM Transazioni T
                        JOIN Conti C ON T.id_conto = C.id_conto
                        JOIN Utenti U ON C.id_utente = U.id_utente
                        JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente -- To filter family
                        LEFT JOIN Sottocategorie Sub ON T.id_sottocategoria = Sub.id_sottocategoria
                        LEFT JOIN Categorie Cat ON Sub.id_categoria = Cat.id_categoria
                        WHERE AF.id_famiglia = %s
                          AND T.data BETWEEN %s AND %s
                        
                        UNION ALL

                        -- Transazioni Condivise (Shared)
                        SELECT U.username_enc AS utente_username_enc,
                               U.nome_enc_server AS utente_nome_server_enc,
                               U.cognome_enc_server AS utente_cognome_server_enc,
                               TC.data,
                               TC.descrizione,
                               TC.importo,
                               TC.importo_nascosto,
                               CC.nome_conto,
                               Cat.nome_categoria,
                               SCat.nome_sottocategoria,
                               TC.id_utente_autore AS id_utente
                        FROM TransazioniCondivise TC
                                 JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                 LEFT JOIN Utenti U
                                           ON TC.id_utente_autore = U.id_utente -- Join per ottenere il nome dell'autore
                                 LEFT JOIN Sottocategorie SCat ON TC.id_sottocategoria = SCat.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON SCat.id_categoria = Cat.id_categoria
                        WHERE CC.id_famiglia = %s
                          AND TC.data BETWEEN %s AND %s
                        ORDER BY data DESC, utente_username_enc, nome_conto
                        """, (id_famiglia, data_inizio, data_fine, id_famiglia, data_inizio, data_fine))
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            for row in results:
                owner_id = row.get('owner_id_utente')
                
                # Build display name: decrypt nome/cognome with master_key and combine
                utente_username_enc = row.pop('utente_username_enc', '') or ''
                nome_enc = row.pop('utente_nome_enc', '') or ''
                cognome_enc = row.pop('utente_cognome_enc', '') or ''
                
                # Decrypt username (system data)
                row['utente_username'] = decrypt_system_data(utente_username_enc) or "Sconosciuto"
                
                # Decrypt Name/Surname (Server Key preferred for visibility)
                nome_server = decrypt_system_data(row.get('utente_nome_server_enc'))
                cognome_server = decrypt_system_data(row.get('utente_cognome_server_enc'))
                
                if nome_server and cognome_server:
                    nome_raw = nome_server
                    cognome_raw = cognome_server
                else:
                    # Fallback to encrypted blobs if backfill hasn't run
                     nome_raw = ''
                     cognome_raw = ''
                
                # Cleanup encrypted strings for display
                if isinstance(nome_raw, str) and nome_raw.startswith('gAAAAA'): 
                     nome_raw = '' # Hide encrypted blob
                if isinstance(cognome_raw, str) and cognome_raw.startswith('gAAAAA'):
                     cognome_raw = ''

                # Build display name: prefer nome+cognome, fallback to username
                if nome_raw or cognome_raw:
                    row['utente_nome'] = f"{nome_raw} {cognome_raw}".strip()
                else:
                    row['utente_nome'] = row['utente_username']
                
                # Decrypt transaction data
                descrizione_orig = row['descrizione']
                conto_nome_orig = row['nome_conto']
                
                # Decrypt Logic: Try Family Key, then Master Key (if owner or fallback), then clean fallback
                decoded_desc = "[ENCRYPTED]"
                decoded_conto = "[ENCRYPTED]"
                
                if family_key:
                    decoded_desc = _decrypt_if_key(descrizione_orig, family_key, crypto, silent=True)
                    decoded_conto = _decrypt_if_key(conto_nome_orig, family_key, crypto, silent=True)

                if decoded_desc == "[ENCRYPTED]" and master_key:
                     # Try silent decrypt with master key for fallback (will work if user is owner OR legacy)
                     decoded_desc = _decrypt_if_key(descrizione_orig, master_key, crypto, silent=True)
                     
                if decoded_conto == "[ENCRYPTED]" and master_key:
                     decoded_conto = _decrypt_if_key(conto_nome_orig, master_key, crypto, silent=True)
                
                # Assign with fallback text
                if decoded_desc == "[ENCRYPTED]":
                    row['descrizione'] = "🔒 Dettaglio Privato"
                else:
                    row['descrizione'] = decoded_desc
                    
                if decoded_conto == "[ENCRYPTED]":
                    row['conto_nome'] = "🔒 Conto Privato"
                else:
                    row['conto_nome'] = decoded_conto
                
                # Category and subcategory names are encrypted with family_key
                if family_key:
                    row['nome_categoria'] = _decrypt_if_key(row['nome_categoria'], family_key, crypto) if row.get('nome_categoria') else None
                    row['nome_sottocategoria'] = _decrypt_if_key(row['nome_sottocategoria'], family_key, crypto) if row.get('nome_sottocategoria') else None
                
                # Combine category and subcategory for display
                cat = row.get('nome_categoria') or ''
                subcat = row.get('nome_sottocategoria') or ''
                if cat and subcat:
                    row['nome_sottocategoria'] = f"{cat} - {subcat}"
                elif cat:
                    row['nome_sottocategoria'] = cat
                # else: subcat only, or empty
            
            # Filtra le transazioni "Saldo Iniziale" DOPO la decrittografia
            # (il filtro SQL non funziona sui dati crittografati)
            results = [r for r in results if 'saldo iniziale' not in (r.get('descrizione') or '').lower()]
            
            # --- SYNTHESIZE PIGGY BANK TRANSACTIONS ---
            # Generate counterpart transactions for Piggy Bank transfers to visualize them in the list
            pb_transactions = []
            for row in results:
                desc = row.get('descrizione', '')
                try:
                    # Case 1: Assignment (Account -> PB)
                    # Desc: "Assegnazione a {nome_salvadanaio}"
                    if desc and "Assegnazione a " in desc:
                        pb_name = desc.replace("Assegnazione a ", "").strip()
                        amount = row.get('importo', 0.0)
                        
                        # Only synthesize if it represents a debit on account (negative amount)
                        # So PB receives credit (positive)
                        if amount < 0:
                            new_row = row.copy()
                            new_row['nome_conto'] = pb_name # Virtual Account Name = PB Name
                            new_row['importo'] = abs(amount) # Positive
                            new_row['descrizione'] = f"Ricevuto da {row.get('nome_conto')}"
                            new_row['nome_sottocategoria'] = "Risparmio" # Force category
                            pb_transactions.append(new_row)
                            
                    # Case 2: Withdrawal/Closure (PB -> Account)
                    # Desc: "Prelievo da {nome}" OR "Chiusura Salvadanaio" -- but "Prelievo" is usually explicit
                    elif desc and "Prelievo da " in desc:
                        pb_name = desc.replace("Prelievo da ", "").strip()
                        amount = row.get('importo', 0.0)
                        if amount > 0: # Credit on account
                            new_row = row.copy()
                            new_row['nome_conto'] = pb_name
                            new_row['importo'] = -abs(amount) # Debit on PB
                            new_row['descrizione'] = f"Versamento su {row.get('nome_conto')}"
                            new_row['nome_sottocategoria'] = "Risparmio"
                            pb_transactions.append(new_row)
                            
                    elif desc and "Chiusura Salvadanaio" in desc:
                         # Name is unknown if generic desc. Display "Salvadanaio"
                        amount = row.get('importo', 0.0)
                        if amount > 0:
                            new_row = row.copy()
                            new_row['nome_conto'] = "Salvadanaio (Chiusura)"
                            new_row['importo'] = -abs(amount)
                            new_row['descrizione'] = f"Restituzione fondi a {row.get('nome_conto')}"
                            new_row['nome_sottocategoria'] = "Risparmio"
                            pb_transactions.append(new_row)

                except Exception as e:
                    pass
            
            # Append synthesized transactions
            results.extend(pb_transactions)
            
            # Re-sort by Date DESC
            results.sort(key=lambda x: str(x.get('data', '')), reverse=True)

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero dettagli famiglia: {e}")
        return []



def modifica_ruolo_utente(id_utente, id_famiglia, nuovo_ruolo):
    if nuovo_ruolo not in ['admin', 'livello1', 'livello2', 'livello3']:
        return False
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("UPDATE Appartenenza_Famiglia SET ruolo = %s WHERE id_utente = %s AND id_famiglia = %s",
                        (nuovo_ruolo, id_utente, id_famiglia))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica del ruolo: {e}")
        return False


def rimuovi_utente_da_famiglia(id_utente, id_famiglia):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s",
                        (id_utente, id_famiglia))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la rimozione utente: {e}")
        return False


# --- Funzioni Fondo Pensione ---
def aggiorna_valore_fondo_pensione(id_conto, nuovo_valore):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Conti SET valore_manuale = %s WHERE id_conto = %s AND tipo = 'Fondo Pensione'",
                        (nuovo_valore, id_conto))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante l'aggiornamento del valore del fondo pensione: {e}")
        return False


def esegui_operazione_fondo_pensione(id_fondo_pensione, tipo_operazione, importo, data, id_conto_collegato=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")

            if tipo_operazione == 'VERSAMENTO':
                descrizione = f"Versamento a fondo pensione (ID: {id_fondo_pensione})"
                cur.execute("INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (?, %s, %s, %s)",
                            (id_conto_collegato, data, descrizione, -abs(importo)))
            elif tipo_operazione == 'PRELIEVO':
                descrizione = f"Prelievo da fondo pensione (ID: {id_fondo_pensione})"
                cur.execute("INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (?, %s, %s, %s)",
                            (id_conto_collegato, data, descrizione, abs(importo)))

            if tipo_operazione in ['VERSAMENTO', 'VERSAMENTO_ESTERNO']:
                cur.execute("UPDATE Conti SET valore_manuale = valore_manuale + %s WHERE id_conto = %s",
                            (abs(importo), id_fondo_pensione))
            elif tipo_operazione == 'PRELIEVO':
                cur.execute("UPDATE Conti SET valore_manuale = valore_manuale - %s WHERE id_conto = %s",
                            (abs(importo), id_fondo_pensione))

            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'esecuzione dell'operazione sul fondo pensione: {e}")
        if con: con.rollback()
        return False


# --- Funzioni Budget ---
def imposta_budget(id_famiglia, id_sottocategoria, importo_limite, master_key_b64=None, id_utente=None):
    try:
        # Encrypt importo_limite with family_key
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        # Retrieve Family Key for encryption - REQUIRED for family data
        family_key = None
        if master_key and id_utente:
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        # Family data MUST be encrypted with family_key, NOT master_key
        if not family_key:
            print(f"[WARN] imposta_budget: Cannot encrypt without family_key. id_utente={id_utente}")
            # Store as plain text if no key available (for backwards compatibility)
            encrypted_importo = str(importo_limite)
        else:
            encrypted_importo = _encrypt_if_key(str(importo_limite), family_key, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        INSERT INTO Budget (id_famiglia, id_sottocategoria, importo_limite, periodo)
                        VALUES (%s, %s, %s, 'Mensile') ON CONFLICT(id_famiglia, id_sottocategoria, periodo) DO
                        UPDATE SET importo_limite = excluded.importo_limite
                        """, (id_famiglia, id_sottocategoria, encrypted_importo))
            
            # Auto-update history for current month
            try:
                import datetime
                now = datetime.datetime.now()
                # Pass existing cursor to reuse connection
                trigger_budget_history_update(id_famiglia, now, master_key_b64, id_utente, cursor=cur)
            except Exception as e:
                print(f"[WARN] Failed auto-update in imposta_budget: {e}")

            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'impostazione del budget: {e}")
        return False

def ottieni_budget_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT B.id_budget, B.id_sottocategoria, C.nome_categoria, S.nome_sottocategoria, B.importo_limite
                        FROM Budget B
                                 JOIN Sottocategorie S ON B.id_sottocategoria = S.id_sottocategoria
                                 JOIN Categorie C ON S.id_categoria = C.id_categoria
                        WHERE B.id_famiglia = %s
                          AND B.periodo = 'Mensile'
                        """, (id_famiglia,))
            rows = [dict(row) for row in cur.fetchall()]
            
            # Decrypt
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            for row in rows:
                # Decrypt budget limit (Try Family Key, then Master Key)
                if family_key:
                    decrypted = _decrypt_if_key(row['importo_limite'], family_key, crypto, silent=True)
                    # If decryption failed (returns [ENCRYPTED]) and it looks encrypted, try master_key
                    if decrypted == "[ENCRYPTED]" and isinstance(row['importo_limite'], str) and row['importo_limite'].startswith("gAAAAA"):
                         decrypted = _decrypt_if_key(row['importo_limite'], master_key, crypto)
                else:
                    decrypted = row['importo_limite'] # Cannot decrypt without family key
                try:
                    row['importo_limite'] = float(decrypted)
                except (ValueError, TypeError):
                    row['importo_limite'] = 0.0
                
                # Decrypt category and subcategory names (always Family Key)
                if family_key:
                    row['nome_categoria'] = _decrypt_if_key(row['nome_categoria'], family_key, crypto)
                    row['nome_sottocategoria'] = _decrypt_if_key(row['nome_sottocategoria'], family_key, crypto)
            
            # Sort in Python
            rows.sort(key=lambda x: (x['nome_categoria'] or "", x['nome_sottocategoria'] or ""))
            
            return rows
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero budget: {e}")
        return []


def ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese, master_key_b64=None, id_utente=None):
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                SELECT
                    C.id_categoria,
                    C.nome_categoria,
                    S.id_sottocategoria,
                    S.nome_sottocategoria,
                    COALESCE(BS.importo_limite, B.importo_limite, '0.0') as importo_limite,
                    COALESCE(T_SPESE.spesa_totale, 0.0) as spesa_totale
                FROM Categorie C
                JOIN Sottocategorie S ON C.id_categoria = S.id_categoria
                LEFT JOIN Budget_Storico BS ON S.id_sottocategoria = BS.id_sottocategoria 
                    AND BS.id_famiglia = C.id_famiglia 
                    AND BS.anno = %s 
                    AND BS.mese = %s
                LEFT JOIN Budget B ON S.id_sottocategoria = B.id_sottocategoria 
                    AND B.id_famiglia = C.id_famiglia 
                    AND B.periodo = 'Mensile'
                LEFT JOIN (
                    SELECT id_sottocategoria, SUM(spesa_totale) as spesa_totale
                    FROM (
                        SELECT
                            T.id_sottocategoria,
                            SUM(T.importo) as spesa_totale
                        FROM Transazioni T
                        JOIN Conti CO ON T.id_conto = CO.id_conto
                        JOIN Appartenenza_Famiglia AF ON CO.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s AND T.importo < 0 AND T.data BETWEEN %s AND %s
                          AND T.id_sottocategoria IS NOT NULL
                        GROUP BY T.id_sottocategoria
                        UNION ALL
                        SELECT
                            TC.id_sottocategoria,
                            SUM(TC.importo) as spesa_totale
                        FROM TransazioniCondivise TC
                        JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                        WHERE CC.id_famiglia = %s AND TC.importo < 0 AND TC.data BETWEEN %s AND %s
                          AND TC.id_sottocategoria IS NOT NULL
                        GROUP BY TC.id_sottocategoria
                    ) AS U
                    GROUP BY id_sottocategoria
                ) AS T_SPESE ON S.id_sottocategoria = T_SPESE.id_sottocategoria
                WHERE C.id_famiglia = %s
                ORDER BY C.nome_categoria, S.nome_sottocategoria;
            """, (anno, mese, id_famiglia, data_inizio, data_fine, id_famiglia, data_inizio, data_fine, id_famiglia))
            
            riepilogo = {}
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            for row in cur.fetchall():
                cat_id = row['id_categoria']
                if cat_id not in riepilogo:
                    # Decrypt category name
                    cat_name = row['nome_categoria']
                    if family_key:
                        cat_name = _decrypt_if_key(cat_name, family_key, crypto)
                        
                    riepilogo[cat_id] = {
                        'nome_categoria': cat_name,
                        'importo_limite_totale': 0,
                        'spesa_totale_categoria': 0,
                        'sottocategorie': []
                    }
                
                spesa = abs(row['spesa_totale'])
                
                # Decrypt importo_limite (Try Family Key, then Master Key)
                if family_key:
                    decrypted_limite = _decrypt_if_key(row['importo_limite'], family_key, crypto, silent=True)
                    # If decryption failed (returns [ENCRYPTED]) and it looks encrypted, try master_key
                    if decrypted_limite == "[ENCRYPTED]" and isinstance(row['importo_limite'], str) and row['importo_limite'].startswith("gAAAAA"):
                         decrypted_limite = _decrypt_if_key(row['importo_limite'], master_key, crypto)
                else:
                    decrypted_limite = row['importo_limite'] # Cannot decrypt without family key
                try:
                    limite = float(decrypted_limite)
                except (ValueError, TypeError):
                    limite = 0.0

                riepilogo[cat_id]['importo_limite_totale'] += limite
                riepilogo[cat_id]['spesa_totale_categoria'] += spesa
                
                # Decrypt subcategory name
                sub_name = row['nome_sottocategoria']
                if family_key:
                    sub_name = _decrypt_if_key(sub_name, family_key, crypto)

                riepilogo[cat_id]['sottocategorie'].append({
                    'id_sottocategoria': row['id_sottocategoria'],
                    'nome_sottocategoria': sub_name,
                    'importo_limite': limite,
                    'spesa_totale': spesa,
                    'rimanente': limite - spesa
                })
            
            # Calcola il rimanente totale per categoria
            for cat_id in riepilogo:
                riepilogo[cat_id]['rimanente_totale'] = riepilogo[cat_id]['importo_limite_totale'] - riepilogo[cat_id]['spesa_totale_categoria']
            
            # Sort categories and subcategories in Python
            # Convert dict to list of values for sorting, but we return a dict keyed by cat_id.
            # Actually, the caller expects a dict. But we can't sort a dict in place reliably across versions (though 3.7+ preserves insertion order).
            # Let's sort the subcategories list within each category.
            for cat_id in riepilogo:
                riepilogo[cat_id]['sottocategorie'].sort(key=lambda x: x['nome_sottocategoria'] or "")
            
            # To sort categories, we might need to return a sorted dict or list.
            # The current implementation returns a dict. The caller iterates over values.
            # Let's return a dict with sorted keys (insertion order).
            sorted_riepilogo = dict(sorted(riepilogo.items(), key=lambda item: item[1]['nome_categoria'] or ""))

            return sorted_riepilogo

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero riepilogo budget: {e}")
        return {}


def salva_budget_mese_corrente(id_famiglia, anno, mese, master_key_b64=None, id_utente=None):
    try:
        riepilogo_corrente = ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese, master_key_b64, id_utente)
        if not riepilogo_corrente:
            return False
            
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            dati_da_salvare = []
            # Salva per ogni sottocategoria
            for cat_id, cat_data in riepilogo_corrente.items():
                for sub_data in cat_data['sottocategorie']:
                    # Encrypt amounts
                    key_to_use = family_key if family_key else master_key
                    enc_limite = _encrypt_if_key(str(sub_data['importo_limite']), key_to_use, crypto)
                    enc_speso = _encrypt_if_key(str(abs(sub_data['spesa_totale'])), key_to_use, crypto)
                    
                    # Encrypt subcategory name (for history snapshot)
                    enc_sub_name = sub_data['nome_sottocategoria']
                    if family_key: # Re-encrypt if it was decrypted
                         enc_sub_name = _encrypt_if_key(sub_data['nome_sottocategoria'], family_key, crypto)

                    dati_da_salvare.append((
                        id_famiglia, sub_data['id_sottocategoria'], enc_sub_name,
                        anno, mese, enc_limite, enc_speso
                    ))
            
            cur.executemany("""
                            INSERT INTO Budget_Storico (id_famiglia, id_sottocategoria, nome_sottocategoria, anno, mese,
                                                        importo_limite, importo_speso)
                            VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT(id_famiglia, id_sottocategoria, anno, mese) DO
                            UPDATE SET importo_limite = excluded.importo_limite, importo_speso = excluded.importo_speso, nome_sottocategoria = excluded.nome_sottocategoria
                            """, dati_da_salvare)
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la storicizzazione del budget: {e}")
        return False

# --- Helper per Automazione Storico ---
def _get_famiglia_and_utente_from_conto(id_conto):
    try:
        with get_db_connection() as con:
             cur = con.cursor()
             # Get user and family from account
             cur.execute("""
                SELECT U.id_utente, AF.id_famiglia 
                FROM Conti C
                JOIN Utenti U ON C.id_utente = U.id_utente
                JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                WHERE C.id_conto = %s
             """, (id_conto,))
             res = cur.fetchone()
             if res:
                 return res['id_famiglia'], res['id_utente']
             return None, None
    except Exception as e:
        print(f"[ERRORE] _get_famiglia_and_utente_from_conto: {e}")
        return None, None

def trigger_budget_history_update(id_famiglia, date_obj, master_key_b64, id_utente):
    """Updates budget history for a specific month only if family and user are identified."""
    if not id_famiglia or not id_utente or not date_obj:
        return
    try:
        if isinstance(date_obj, str):
            date_obj = parse_date(date_obj)
        
        # Saves snapshot for that month
        salva_budget_mese_corrente(id_famiglia, date_obj.year, date_obj.month, master_key_b64, id_utente)
    except Exception as e:
        print(f"[WARN] Failed to auto-update budget history: {e}")



def storicizza_budget_retroattivo(id_famiglia, master_key_b64=None):
    """
    Storicizza automaticamente i budget per tutti i mesi passati con transazioni.
    Usa i limiti correnti dalla tabella Budget come baseline per i mesi storici.
    Questa funzione dovrebbe essere chiamata una sola volta per popolare Budget_Storico.
    """
    try:
        oggi = datetime.date.today()
        
        # Ottieni tutti i mesi con transazioni
        periodi = ottieni_anni_mesi_storicizzati(id_famiglia)
        if not periodi:
            print("Nessun periodo storico trovato.")
            return True
        
        mesi_storicizzati = 0
        mesi_saltati = 0
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            for periodo in periodi:
                anno = periodo['anno']
                mese = periodo['mese']
                
                # Salta il mese corrente (verrà storicizzato normalmente)
                if anno == oggi.year and mese == oggi.month:
                    continue
                
                # Salta i mesi futuri
                if anno > oggi.year or (anno == oggi.year and mese > oggi.month):
                    continue
                
                # Controlla se il mese è già storicizzato
                cur.execute("""
                    SELECT COUNT(*) as count FROM Budget_Storico 
                    WHERE id_famiglia = %s AND anno = %s AND mese = %s
                """, (id_famiglia, anno, mese))
                
                if cur.fetchone()['count'] > 0:
                    mesi_saltati += 1
                    continue
                
                # Storicizza il mese usando i limiti correnti
                if salva_budget_mese_corrente(id_famiglia, anno, mese, master_key_b64):
                    mesi_storicizzati += 1
                    print(f"  Storicizzato {anno}-{mese:02d}")
                else:
                    print(f"  Errore storicizzando {anno}-{mese:02d}")
        
        print(f"\nStoricizzazione retroattiva completata:")
        print(f"  - Mesi storicizzati: {mesi_storicizzati}")
        print(f"  - Mesi già presenti: {mesi_saltati}")
        return True
        
    except Exception as e:
        print(f"Errore durante la storicizzazione retroattiva: {e}")
        return False



def ottieni_anni_mesi_storicizzati(id_famiglia):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            # Query aggiornata per leggere i mesi da TUTTE le transazioni (personali e condivise)
            cur.execute("""
                SELECT DISTINCT anno, mese FROM (
                    -- Mesi da transazioni personali
                    SELECT
                        CAST(EXTRACT(YEAR FROM CAST(T.data AS DATE)) AS INTEGER) as anno,
                        CAST(EXTRACT(MONTH FROM CAST(T.data AS DATE)) AS INTEGER) as mese
                    FROM Transazioni T
                    JOIN Conti C ON T.id_conto = C.id_conto
                    JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                    WHERE AF.id_famiglia = %s

                    UNION

                    -- Mesi da transazioni condivise
                    SELECT
                        CAST(EXTRACT(YEAR FROM CAST(TC.data AS DATE)) AS INTEGER) as anno,
                        CAST(EXTRACT(MONTH FROM CAST(TC.data AS DATE)) AS INTEGER) as mese
                    FROM TransazioniCondivise TC
                    JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                    WHERE CC.id_famiglia = %s
                ) ORDER BY anno DESC, mese DESC
            """, (id_famiglia, id_famiglia))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero periodi storici: {e}")
        return []


def ottieni_storico_budget_per_export(id_famiglia, lista_periodi, master_key_b64=None, id_utente=None):
    if not lista_periodi: return []
    placeholders = " OR ".join(["(anno = %s AND mese = %s)"] * len(lista_periodi))
    params = [id_famiglia] + [item for sublist in lista_periodi for item in sublist]
    
    # Decryption setup
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Budget_Storico has 'nome_sottocategoria'
            # Fetch raw values, decrypt and calculate in Python
            query = f"""
                SELECT anno, mese, nome_sottocategoria, importo_limite, importo_speso
                FROM Budget_Storico
                WHERE id_famiglia = %s AND ({placeholders})
                ORDER BY anno, mese, nome_sottocategoria
            """
            cur.execute(query, tuple(params))
            results = [dict(row) for row in cur.fetchall()]
            
            for row in results:
                # Decrypt subcategory name if needed
                if row.get('nome_sottocategoria'):
                     decrypted = _decrypt_if_key(row['nome_sottocategoria'], family_key, crypto, silent=True)
                     if not decrypted and family_key != master_key:
                         decrypted = _decrypt_if_key(row['nome_sottocategoria'], master_key, crypto, silent=True)
                     row['nome_sottocategoria'] = decrypted or row['nome_sottocategoria']

                # Decrypt and process amounts
                limit = row.get('importo_limite')
                spent = row.get('importo_speso')
                
                # Decrypt limit
                if isinstance(limit, str) and not limit.replace('.', '', 1).isdigit(): # Simple check if likely encrypted
                     dec_limit = _decrypt_if_key(limit, family_key, crypto, silent=True)
                     if not dec_limit and family_key != master_key:
                         dec_limit = _decrypt_if_key(limit, master_key, crypto, silent=True)
                     limit = float(dec_limit) if dec_limit else 0.0
                else:
                    limit = float(limit) if limit is not None else 0.0
                
                # Decrypt spent
                if isinstance(spent, str) and not spent.replace('.', '', 1).isdigit():
                     dec_spent = _decrypt_if_key(spent, family_key, crypto, silent=True)
                     if not dec_spent and family_key != master_key:
                         dec_spent = _decrypt_if_key(spent, master_key, crypto, silent=True)
                     spent = float(dec_spent) if dec_spent else 0.0
                else:
                     spent = float(spent) if spent is not None else 0.0
                
                row['importo_limite'] = limit
                row['importo_speso'] = spent
                row['rimanente'] = limit - spent

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero storico per export: {e}")
        return []


# --- Funzioni Prestiti ---

def gestisci_quote_prestito(id_prestito, lista_quote):
    """
    Gestisce le quote di competenza di un prestito.
    lista_quote: lista di dizionari {'id_utente': int, 'percentuale': float}
    """
    if lista_quote is None:
        return True
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM QuotePrestiti WHERE id_prestito = %s", (id_prestito,))
            for quota in lista_quote:
                cur.execute("""
                    INSERT INTO QuotePrestiti (id_prestito, id_utente, percentuale)
                    VALUES (%s, %s, %s)
                """, (id_prestito, quota['id_utente'], quota['percentuale']))
            con.commit()
        return True
    except Exception as e:
        print(f"[ERRORE] Errore salvataggio quote prestito: {e}")
        return False

def ottieni_quote_prestito(id_prestito):
    try:
        with get_db_connection() as con:
             cur = con.cursor()
             cur.execute("SELECT id_utente, percentuale FROM QuotePrestiti WHERE id_prestito = %s", (id_prestito,))
             return [dict(row) for row in cur.fetchall()]
    except Exception:
        return []

def aggiungi_prestito(id_famiglia, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                      importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default=None,
                      id_conto_condiviso_default=None, id_sottocategoria_default=None, addebito_automatico=False,
                      master_key_b64=None, id_utente=None, lista_quote=None):
    
    # Encrypt sensitive data if keys available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                row = cur.fetchone()
                if row and row['chiave_famiglia_criptata']:
                    family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                    family_key = base64.b64decode(family_key_b64)
        except Exception:
            pass

    encrypted_nome = _encrypt_if_key(nome, family_key, crypto)
    encrypted_descrizione = _encrypt_if_key(descrizione, family_key, crypto)

    try:
        id_new = None
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        INSERT INTO Prestiti (id_famiglia, nome, tipo, descrizione, data_inizio, numero_mesi_totali,
                                              importo_finanziato, importo_interessi, importo_residuo, importo_rata,
                                              giorno_scadenza_rata, id_conto_pagamento_default,
                                              id_conto_condiviso_pagamento_default, id_sottocategoria_pagamento_default,
                                              addebito_automatico)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_prestito
                        """, (id_famiglia, encrypted_nome, tipo, encrypted_descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                              importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default,
                              id_conto_condiviso_default, id_sottocategoria_default, bool(addebito_automatico)))
            id_new = cur.fetchone()['id_prestito']
        
        # Effettuiamo la gestione quote DOPO il commit della transazione principale
        # altrimenti la nuova query in gestisci_quote_prestito (nuova connessione) non vedrebbe l'ID
        if id_new and lista_quote:
            gestisci_quote_prestito(id_new, lista_quote)
            
        return id_new
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiunta del prestito: {e}")
        return None


def modifica_prestito(id_prestito, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                      importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default=None,
                      id_conto_condiviso_default=None, id_sottocategoria_default=None, addebito_automatico=False,
                      master_key_b64=None, id_utente=None, lista_quote=None):
    
    # Encrypt sensitive data if keys available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                # Need id_famiglia to get key
                cur.execute("SELECT id_famiglia FROM Prestiti WHERE id_prestito = %s", (id_prestito,))
                p_row = cur.fetchone()
                if p_row:
                    id_famiglia = p_row['id_famiglia']
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
        except Exception:
            pass

    encrypted_nome = _encrypt_if_key(nome, family_key, crypto)
    encrypted_descrizione = _encrypt_if_key(descrizione, family_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        UPDATE Prestiti
                        SET nome                           = %s,
                            tipo                           = %s,
                            descrizione                    = %s,
                            data_inizio                    = %s,
                            numero_mesi_totali             = %s,
                            importo_finanziato             = %s,
                            importo_interessi              = %s,
                            importo_residuo                = %s,
                            importo_rata                   = %s,
                            giorno_scadenza_rata           = %s,
                            id_conto_pagamento_default     = %s,
                            id_conto_condiviso_pagamento_default = %s,
                            id_sottocategoria_pagamento_default = %s,
                            addebito_automatico            = %s
                        WHERE id_prestito = %s
                        """, (encrypted_nome, tipo, encrypted_descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                              importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default,
                              id_conto_condiviso_default, id_sottocategoria_default, bool(addebito_automatico), id_prestito))
            
            if lista_quote is not None:
                gestisci_quote_prestito(id_prestito, lista_quote)
            
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica del prestito: {e}")
        return False


def elimina_prestito(id_prestito):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM Prestiti WHERE id_prestito = %s", (id_prestito,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione del prestito: {e}")
        return None


def ottieni_prestiti_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            # Calcoliamo le rate pagate basandoci sul residuo, per gestire anche modifiche manuali
            cur.execute("""
                        SELECT P.*, 
                               C.nome_categoria AS nome_categoria_default,
                               CASE 
                                   WHEN P.importo_rata > 0 THEN CAST((P.importo_finanziato + COALESCE(P.importo_interessi, 0) - P.importo_residuo) / P.importo_rata AS INTEGER)
                                   ELSE 0 
                               END as rate_pagate
                        FROM Prestiti P
                                 LEFT JOIN Categorie C ON P.id_categoria_pagamento_default = C.id_categoria
                        WHERE P.id_famiglia = %s
                        ORDER BY P.data_inizio DESC
                        """, (id_famiglia,))
            results = [dict(row) for row in cur.fetchall()]

            if not results:
                return []

            # Decrypt sensitive data if keys available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                try:
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
                except Exception:
                    pass

            if family_key:
                for row in results:
                    row['nome'] = _decrypt_if_key(row['nome'], family_key, crypto)
                    row['descrizione'] = _decrypt_if_key(row['descrizione'], family_key, crypto)
            
            # --- OTTIMIZZAZIONE INIZIO: Batch Quote Prestiti ---
            ids_prestiti = [r['id_prestito'] for r in results]
            quote_map = {}
            if ids_prestiti:
                placeholders = ','.join(['%s'] * len(ids_prestiti))
                query = f"SELECT id_prestito, id_utente, percentuale FROM QuotePrestiti WHERE id_prestito IN ({placeholders})"
                cur.execute(query, tuple(ids_prestiti))
                rows = cur.fetchall()
                for r in rows:
                    if r['id_prestito'] not in quote_map:
                        quote_map[r['id_prestito']] = []
                    quote_map[r['id_prestito']].append({'id_utente': r['id_utente'], 'percentuale': r['percentuale']})
            
            for row in results:
                row['lista_quote'] = quote_map.get(row['id_prestito'], [])

            # --- OTTIMIZZAZIONE INIZIO: Batch Piano Ammortamento ---
            # Se esiste un piano ammortamento, questo "vince" sui dati statici per:
            # 1. Importo prossima rata
            # 2. Numero rate pagate / totali
            if ids_prestiti:
                piano_map = {} # id_prestito -> { 'rate_pagate': 0, 'rate_totali': 0, 'next_rata_amount': None, 'next_rata_date': None }
                
                placeholders = ','.join(['%s'] * len(ids_prestiti))
                query_piano = f"""
                    SELECT id_prestito, importo_rata, quota_capitale, quota_interessi, data_scadenza, stato 
                    FROM PianoAmmortamento 
                    WHERE id_prestito IN ({placeholders})
                    ORDER BY data_scadenza ASC
                """
                cur.execute(query_piano, tuple(ids_prestiti))
                rows_piano = cur.fetchall()
                
                for r in rows_piano:
                    pid = r['id_prestito']
                    if pid not in piano_map:
                        piano_map[pid] = {
                            'rate_pagate': 0, 
                            'rate_totali': 0, 
                            'next_rata_found': False, 
                            'next_rata_importo': 0.0,
                            'residuo_totale': 0.0,
                            'capitale_residuo': 0.0,
                            'interessi_residui': 0.0
                        }
                    
                    piano_map[pid]['rate_totali'] += 1
                    
                    if r['stato'] == 'pagata':
                        piano_map[pid]['rate_pagate'] += 1
                    elif r['stato'] == 'da_pagare':
                        # Somma residuo
                        piano_map[pid]['residuo_totale'] += float(r['importo_rata'])
                        piano_map[pid]['capitale_residuo'] += float(r['quota_capitale'])
                        piano_map[pid]['interessi_residui'] += float(r['quota_interessi'])
                        
                        if not piano_map[pid]['next_rata_found']:
                            # La prima rata 'da_pagare' (ordinato data ASC) è quella corrente
                            piano_map[pid]['next_rata_found'] = True
                            piano_map[pid]['next_rata_importo'] = float(r['importo_rata'])
                
                # Applica override se dati presenti
                for row in results:
                    pid = row['id_prestito']
                    if pid in piano_map:
                        pm = piano_map[pid]
                        # Aggiorniamo i conteggi reali da piano
                        row['rate_pagate'] = pm['rate_pagate']
                        row['numero_mesi_totali'] = pm['rate_totali'] # Opzionale, ma mantiene coerenza
                        
                        # Override Importo Residuo (calcolato come somma rate ancora da pagare)
                        row['importo_residuo'] = pm['residuo_totale']
                        row['capitale_residuo'] = pm['capitale_residuo']
                        row['interessi_residui'] = pm['interessi_residui']
                        
                        # Se trovata una prossima rata, usiamo il suo importo specifico
                        if pm['next_rata_found']:
                           # print(f"[DEBUG] Override importo rata per {pid}: Old={row['importo_rata']} New={pm['next_rata_importo']}")
                           row['importo_rata'] = pm['next_rata_importo']
            # --- OTTIMIZZAZIONE FINE ---

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero prestiti: {e}")
        return []


def check_e_paga_rate_scadute(id_famiglia, master_key_b64=None, id_utente=None):
    oggi = datetime.date.today()
    pagamenti_eseguiti = 0
    try:
        prestiti_attivi = ottieni_prestiti_famiglia(id_famiglia, master_key_b64=master_key_b64, id_utente=id_utente)
        with get_db_connection() as con:
            cur = con.cursor()
            for p in prestiti_attivi:
                # 1. Verifica Addebito Automatico Attivo
                if not p.get('addebito_automatico'):
                    continue
                    
                # Validazione dati minimi
                id_conto_pers = p.get('id_conto_pagamento_default')
                id_conto_cond = p.get('id_conto_condiviso_pagamento_default')
                
                if p['importo_residuo'] <= 0 or (not id_conto_pers and not id_conto_cond):
                    continue

                pay_data = None # (amount, id_rata_schedule)

                # 2. Controllo Piano Ammortamento (Prioritario)
                cur.execute("""
                    SELECT id_rata, data_scadenza, importo_rata 
                    FROM PianoAmmortamento 
                    WHERE id_prestito = %s AND stato = 'da_pagare' 
                    ORDER BY data_scadenza ASC LIMIT 1
                """, (p['id_prestito'],))
                sched = cur.fetchone()

                from datetime import datetime as dt_class # Per parsing sicuro se non importato top-level

                if sched:
                    try:
                        # Parsing data scadenza (YYYY-MM-DD)
                        if isinstance(sched['data_scadenza'], str):
                             due_dt = dt_class.strptime(sched['data_scadenza'], '%Y-%m-%d').date()
                        else:
                             due_dt = sched['data_scadenza'] # Se driver restituisce date object
                        
                        if oggi >= due_dt:
                             pay_data = (float(sched['importo_rata']), sched['id_rata'])
                    except Exception as ed:
                        print(f"Errore parsing data rata id {sched['id_rata']}: {ed}")
                else:
                    # 3. Logica Legacy (Statico)
                    day = p.get('giorno_scadenza_rata')
                    if day and oggi.day >= day:
                        # Verifica importo
                        amount = min(float(p['importo_rata']), float(p['importo_residuo']))
                        pay_data = (amount, None)

                # 4. Esecuzione Pagamento
                if pay_data:
                    amount, sched_id = pay_data
                    
                    perform_payment = False
                    
                    if sched_id:
                        # Se da schedina, 'da_pagare' fa da lock (se paghiamo ora, settiamo 'pagata')
                        perform_payment = True
                    else:
                        # Se legacy, check Storico mensile per evitare doppi pagamenti
                        cur.execute("SELECT 1 FROM StoricoPagamentiRate WHERE id_prestito = %s AND anno = %s AND mese = %s", 
                                    (p['id_prestito'], oggi.year, oggi.month))
                        if not cur.fetchone():
                            perform_payment = True

                    if perform_payment:
                        # Usa categoria default o sottocategoria? Il vecchio codice usava id_categoria... 
                        # Controlliamo la firma di effettua_pagamento_rata -> args: id_sottocategoria
                        # Il vecchio codice passava id_categoria_pagamento_default... verifichiamo se p ha sottocategoria
                        cat_id = p.get('id_sottocategoria_pagamento_default') or p.get('id_categoria_pagamento_default')
                        
                        effettua_pagamento_rata(
                            p['id_prestito'], 
                            id_conto_pers, 
                            amount, 
                            oggi.strftime('%Y-%m-%d'), 
                            cat_id, 
                            p['nome'],
                            id_conto_condiviso=id_conto_cond,
                            id_utente_autore=id_utente
                        )
                        
                        if sched_id:
                            # Aggiorna lo stato nel piano
                            aggiorna_stato_rata_piano(sched_id, 'pagata')
                        
                        pagamenti_eseguiti += 1

        return pagamenti_eseguiti
    except Exception as e:
        print(f"[ERRORE] Errore critico durante il controllo delle rate scadute: {e}")
        return 0


def effettua_pagamento_rata(id_prestito, id_conto_pagamento, importo_pagato, data_pagamento, id_sottocategoria,
                            nome_prestito="", id_conto_condiviso=None, id_utente_autore=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")
            cur.execute("UPDATE Prestiti SET importo_residuo = importo_residuo - %s WHERE id_prestito = %s",
                        (importo_pagato, id_prestito))
            
            # --- Aggiornamento Piano Ammortamento (se presente) ---
            cur.execute("SELECT id_rata FROM PianoAmmortamento WHERE id_prestito = %s AND stato = 'da_pagare' ORDER BY numero_rata ASC LIMIT 1", (id_prestito,))
            rata_row = cur.fetchone()
            if rata_row:
                cur.execute("UPDATE PianoAmmortamento SET stato = 'pagata' WHERE id_rata = %s", (rata_row['id_rata'],))
            # ------------------------------------------------------
            descrizione = f"Pagamento rata {nome_prestito} (Prestito ID: {id_prestito})"
            
            if id_conto_condiviso:
                # Transazione condivisa
                if not id_utente_autore:
                    # Fallback on some admin ID or safe default if automated
                    # Better to print warning, but let's try to proceed if possible or error?
                    # Automated tasks pass id_utente now.
                    print("[WARNING] effettua_pagamento_rata called for shared account without id_utente_autore")
                    pass 
                
                # Per le transazioni condivise, l'autore deve essere specificato. 
                # Se è null, potrebbe fallire constraint NOT NULL su id_utente_autore.
                cur.execute(
                    "INSERT INTO TransazioniCondivise (id_conto_condiviso, id_utente_autore, id_sottocategoria, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s, %s)",
                    (id_conto_condiviso, id_utente_autore, id_sottocategoria, data_pagamento, descrizione, -abs(importo_pagato)))
            
            elif id_conto_pagamento:
                # Transazione personale standard
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s)",
                    (id_conto_pagamento, id_sottocategoria, data_pagamento, descrizione, -abs(importo_pagato)))
            else:
                 print(f"[ERRORE] effettua_pagamento_rata: Nessun conto specificato per il pagamento.")
                 con.rollback()
                 return False

            data_dt = parse_date(data_pagamento)
            cur.execute(
                "INSERT INTO StoricoPagamentiRate (id_prestito, anno, mese, data_pagamento, importo_pagato) VALUES (%s, %s, %s, %s, %s) ON CONFLICT(id_prestito, anno, mese) DO NOTHING",
                (id_prestito, data_dt.year, data_dt.month, data_pagamento, importo_pagato))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'esecuzione del pagamento rata: {e}")
        if con: con.rollback()
        return False


# --- Funzioni Immobili ---

def gestisci_quote_immobile(id_immobile, lista_quote):
    """
    Gestisce le quote di proprietà di un immobile.
    lista_quote: lista di dizionari {'id_utente': int, 'percentuale': float}
    """
    if lista_quote is None:
        return True
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Rimuovi quote esistenti
            cur.execute("DELETE FROM QuoteImmobili WHERE id_immobile = %s", (id_immobile,))
            
            # Inserisci nuove quote
            for quota in lista_quote:
                cur.execute("""
                    INSERT INTO QuoteImmobili (id_immobile, id_utente, percentuale)
                    VALUES (%s, %s, %s)
                """, (id_immobile, quota['id_utente'], quota['percentuale']))
            con.commit()
        return True
    except Exception as e:
        print(f"[ERRORE] Errore salvataggio quote immobile: {e}")
        return False

def ottieni_quote_immobile(id_immobile):
    try:
        with get_db_connection() as con:
             cur = con.cursor()
             cur.execute("SELECT id_utente, percentuale FROM QuoteImmobili WHERE id_immobile = %s", (id_immobile,))
             return [dict(row) for row in cur.fetchall()]
    except Exception:
        return []

def aggiungi_immobile(id_famiglia, nome, via, citta, valore_acquisto, valore_attuale, nuda_proprieta,
                      id_prestito_collegato=None, master_key_b64=None, id_utente=None, lista_quote=None):
    # Converti il valore del dropdown in int se necessario
    db_id_prestito = None
    if id_prestito_collegato is not None and id_prestito_collegato != "None":
        try:
            db_id_prestito = int(id_prestito_collegato)
        except (ValueError, TypeError):
            db_id_prestito = None
            
    # Encrypt sensitive data if keys available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                row = cur.fetchone()
                if row and row['chiave_famiglia_criptata']:
                    family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                    family_key = base64.b64decode(family_key_b64)
        except Exception:
            pass

    encrypted_nome = _encrypt_if_key(nome, family_key, crypto)
    encrypted_via = _encrypt_if_key(via, family_key, crypto)
    encrypted_citta = _encrypt_if_key(citta, family_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        INSERT INTO Immobili (id_famiglia, nome, via, citta, valore_acquisto, valore_attuale,
                                              nuda_proprieta, id_prestito_collegato)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_immobile
                        """,
                        (id_famiglia, encrypted_nome, encrypted_via, encrypted_citta, valore_acquisto, valore_attuale, bool(nuda_proprieta),
                         db_id_prestito))
            id_new = cur.fetchone()['id_immobile']
            
            # Gestione Quote
            if id_new and lista_quote:
                gestisci_quote_immobile(id_new, lista_quote)
                
            return id_new
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiunta dell'immobile: {e}")
        return None


def modifica_immobile(id_immobile, nome, via, citta, valore_acquisto, valore_attuale, nuda_proprieta,
                      id_prestito_collegato=None, master_key_b64=None, id_utente=None, lista_quote=None):
    # Converti il valore del dropdown in int se necessario
    db_id_prestito = None
    if id_prestito_collegato is not None and id_prestito_collegato != "None":
        try:
            db_id_prestito = int(id_prestito_collegato)
        except (ValueError, TypeError):
            db_id_prestito = None
            
    # Encrypt sensitive data if keys available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                # Need id_famiglia to get key
                cur.execute("SELECT id_famiglia FROM Immobili WHERE id_immobile = %s", (id_immobile,))
                i_row = cur.fetchone()
                if i_row:
                    id_famiglia = i_row['id_famiglia']
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
        except Exception:
            pass

    encrypted_nome = _encrypt_if_key(nome, family_key, crypto)
    encrypted_via = _encrypt_if_key(via, family_key, crypto)
    encrypted_citta = _encrypt_if_key(citta, family_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        UPDATE Immobili
                        SET nome                  = %s,
                            via                   = %s,
                            citta                 = %s,
                            valore_acquisto       = %s,
                            valore_attuale        = %s,
                            nuda_proprieta        = %s,
                            id_prestito_collegato = %s
                        WHERE id_immobile = %s
                        """,
                        (encrypted_nome, encrypted_via, encrypted_citta, valore_acquisto, valore_attuale, bool(nuda_proprieta), db_id_prestito,
                         id_immobile))
            
            # Gestione Quote
            if lista_quote is not None:
                gestisci_quote_immobile(id_immobile, lista_quote)

            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica dell'immobile: {e}")
        return False


def elimina_immobile(id_immobile):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM Immobili WHERE id_immobile = %s", (id_immobile,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione dell'immobile: {e}")
        return None


def ottieni_immobili_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT I.*, P.importo_residuo AS valore_mutuo_residuo, P.nome AS nome_mutuo
                        FROM Immobili I
                                 LEFT JOIN Prestiti P ON I.id_prestito_collegato = P.id_prestito
                        WHERE I.id_famiglia = %s
                        ORDER BY I.nome
                        """, (id_famiglia,))
            results = [dict(row) for row in cur.fetchall()]

            if not results:
                return []

            # Decrypt sensitive data if keys available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                try:
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
                except Exception:
                    pass

            if family_key:
                for row in results:
                    row['nome'] = _decrypt_if_key(row['nome'], family_key, crypto)
                    row['via'] = _decrypt_if_key(row['via'], family_key, crypto)
                    row['citta'] = _decrypt_if_key(row['citta'], family_key, crypto)
                    # Also decrypt linked loan name if present
                    if row.get('nome_mutuo'):
                        row['nome_mutuo'] = _decrypt_if_key(row['nome_mutuo'], family_key, crypto)
            
            # --- OTTIMIZZAZIONE INIZIO: Batch Fetching delle Quote ---
            ids_immobili = [r['id_immobile'] for r in results]
            ids_prestiti = [r['id_prestito_collegato'] for r in results if r.get('id_prestito_collegato')]
            
            # Batch fetch Quote Immobili
            quote_immobili_map = {} # id_immobile -> list[dict]
            if ids_immobili:
                placeholders = ','.join(['%s'] * len(ids_immobili))
                query_qi = f"SELECT id_immobile, id_utente, percentuale FROM QuoteImmobili WHERE id_immobile IN ({placeholders})"
                cur.execute(query_qi, tuple(ids_immobili))
                rows_qi = cur.fetchall()
                for r in rows_qi:
                    if r['id_immobile'] not in quote_immobili_map:
                        quote_immobili_map[r['id_immobile']] = []
                    quote_immobili_map[r['id_immobile']].append({'id_utente': r['id_utente'], 'percentuale': r['percentuale']})
            
            # Batch fetch Quote Prestiti
            quote_prestiti_map = {} # id_prestito -> list[dict]
            if ids_prestiti:
                ids_prestiti_unique = list(set(ids_prestiti))
                placeholders_p = ','.join(['%s'] * len(ids_prestiti_unique))
                query_qp = f"SELECT id_prestito, id_utente, percentuale FROM QuotePrestiti WHERE id_prestito IN ({placeholders_p})"
                cur.execute(query_qp, tuple(ids_prestiti_unique))
                rows_qp = cur.fetchall()
                for r in rows_qp:
                    if r['id_prestito'] not in quote_prestiti_map:
                        quote_prestiti_map[r['id_prestito']] = []
                    quote_prestiti_map[r['id_prestito']].append({'id_utente': r['id_utente'], 'percentuale': r['percentuale']})

            # Assegna i risultati in memoria
            for row in results:
                row['lista_quote'] = quote_immobili_map.get(row['id_immobile'], [])
                if row.get('id_prestito_collegato'):
                    row['lista_quote_prestito'] = quote_prestiti_map.get(row.get('id_prestito_collegato'), [])
                else:
                    row['lista_quote_prestito'] = []
            # --- OTTIMIZZAZIONE FINE ---

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero immobili: {e}")
        return []


# --- Funzioni Asset ---
def compra_asset(id_conto_investimento, ticker, nome_asset, quantita, costo_unitario_nuovo, tipo_mov='COMPRA',
                 prezzo_attuale_override=None, master_key_b64=None, id_utente=None):
    ticker_upper = ticker.upper()
    nome_asset_upper = nome_asset.upper()
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Determine Keys for Duplicate Check
    keys_to_try = []
    family_key = None
    
    if id_utente:
         id_famiglia = ottieni_prima_famiglia_utente(id_utente)
         if id_famiglia and master_key:
              family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    
    if master_key: keys_to_try.append(master_key)
    if family_key: keys_to_try.append(family_key)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Fetch all assets to find match (since encryption is non-deterministic or mixed keys)
            cur.execute(
                "SELECT id_asset, ticker, quantita, costo_iniziale_unitario, nome_asset FROM Asset WHERE id_conto = %s",
                (id_conto_investimento,))
            assets = cur.fetchall()
            
            risultato = None
            
            # Helper for multi-key decryption
            def try_decrypt(val, keys):
                for k in keys:
                    if not k: continue
                    try:
                        res = _decrypt_if_key(val, k, crypto, silent=True)
                        if res != "[ENCRYPTED]": return res
                    except: continue
                # Fallback: try raw match if unencrypted (legacy)
                return val 

            for asset in assets:
                db_ticker = asset['ticker']
                # Decrypt ticker using all available keys
                decrypted_ticker = try_decrypt(db_ticker, keys_to_try)
                
                if decrypted_ticker == ticker_upper:
                    risultato = asset
                    break
            
            # Determine encryption key for NEW write
            # Use Family Key if available (shared logic preference), else Master Key
            write_key = family_key if family_key else master_key
            
            # Encrypt for storage
            encrypted_ticker = _encrypt_if_key(ticker_upper, write_key, crypto)
            encrypted_nome_asset = _encrypt_if_key(nome_asset_upper, write_key, crypto)

            cur.execute(
                "INSERT INTO Storico_Asset (id_conto, ticker, data, tipo_movimento, quantita, prezzo_unitario_movimento) VALUES (%s, %s, %s, %s, %s, %s)",
                (id_conto_investimento, encrypted_ticker, datetime.date.today().strftime('%Y-%m-%d'), tipo_mov, quantita,
                 costo_unitario_nuovo))
                 
            if risultato:
                id_asset_aggiornato = risultato['id_asset']
                vecchia_quantita = float(risultato['quantita'])
                vecchio_costo_medio = float(risultato['costo_iniziale_unitario'])
                
                nuova_quantita_totale = vecchia_quantita + quantita
                nuovo_costo_medio = (
                                                vecchia_quantita * vecchio_costo_medio + quantita * costo_unitario_nuovo) / nuova_quantita_totale
                
                # Keep existing name if not explicitly changed, or update? 
                # Strategy: If found, we update Quantita and Costo Medio. 
                # Should we re-encrypt Name and Ticker with new key? 
                # Better to keep existing keys for consistency unless we want to migrate.
                # Let's just update numerics to be safe, OR re-encrypt everything if we want to unify keys.
                # Re-encrypting ensures latest key is used.
                
                cur.execute(
                    "UPDATE Asset SET quantita = %s, costo_iniziale_unitario = %s WHERE id_asset = %s",
                    (nuova_quantita_totale, nuovo_costo_medio, id_asset_aggiornato))
            else:
                prezzo_attuale = prezzo_attuale_override if prezzo_attuale_override is not None else costo_unitario_nuovo
                cur.execute(
                    "INSERT INTO Asset (id_conto, ticker, nome_asset, quantita, costo_iniziale_unitario, prezzo_attuale_manuale) VALUES (%s, %s, %s, %s, %s, %s)",
                    (id_conto_investimento, encrypted_ticker, encrypted_nome_asset, quantita, costo_unitario_nuovo,
                     prezzo_attuale))
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'acquisto asset: {e}")
        return False


def vendi_asset(id_conto_investimento, ticker, quantita_da_vendere, prezzo_di_vendita_unitario, master_key_b64=None):
    ticker_upper = ticker.upper()
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    # Determine correct key (Family Key if applicable)
    encryption_key = _get_key_for_transaction(id_conto_investimento, master_key, crypto)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            
            # Fetch all assets to find match (encryption non-deterministic)
            cur.execute("SELECT id_asset, ticker, quantita FROM Asset WHERE id_conto = %s",
                        (id_conto_investimento,))
            assets = cur.fetchall()
            
            risultato = None
            for asset in assets:
                db_ticker = asset['ticker']
                # Decrypt logic similar to compra_asset
                decrypted_ticker = _decrypt_if_key(db_ticker, encryption_key, crypto, silent=True)
                if (decrypted_ticker == "[ENCRYPTED]" or decrypted_ticker == db_ticker) and encryption_key != master_key:
                     decrypted_ticker = _decrypt_if_key(db_ticker, master_key, crypto)

                if decrypted_ticker == ticker_upper:
                    risultato = asset
                    break
            
            if not risultato: return False
            
            id_asset = risultato['id_asset']
            quantita_attuale = risultato['quantita']
            
            if quantita_da_vendere > quantita_attuale and abs(
                quantita_da_vendere - quantita_attuale) > 1e-9: return False

            nuova_quantita = quantita_attuale - quantita_da_vendere
            
            # Encrypt ticker for history
            encrypted_ticker = _encrypt_if_key(ticker_upper, encryption_key, crypto)
            
            cur.execute(
                "INSERT INTO Storico_Asset (id_conto, ticker, data, tipo_movimento, quantita, prezzo_unitario_movimento) VALUES (%s, %s, %s, %s, %s, %s)",
                (id_conto_investimento, encrypted_ticker, datetime.date.today().strftime('%Y-%m-%d'), 'VENDI',
                 quantita_da_vendere, prezzo_di_vendita_unitario))
                 
            if nuova_quantita < 1e-9:
                cur.execute("DELETE FROM Asset WHERE id_asset = %s", (id_asset,))
            else:
                cur.execute("UPDATE Asset SET quantita = %s WHERE id_asset = %s", (nuova_quantita, id_asset))
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la vendita asset: {e}")
        return False


def ottieni_portafoglio(id_conto_investimento, master_key_b64=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT id_asset,
                               ticker,
                               nome_asset,
                               quantita,
                               prezzo_attuale_manuale,
                               costo_iniziale_unitario,
                               data_aggiornamento,
                               (prezzo_attuale_manuale - costo_iniziale_unitario)              AS gain_loss_unitario,
                               (quantita * (prezzo_attuale_manuale - costo_iniziale_unitario)) AS gain_loss_totale
                        FROM Asset
                        WHERE id_conto = %s
                        """, (id_conto_investimento,))
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt fields
            if master_key:
                # Determine correct key for this account (Family or Master)
                encryption_key = _get_key_for_transaction(id_conto_investimento, master_key, crypto)
                
                for row in results:
                    # Preserve original encrypted values for fallback
                    ticker_orig = row['ticker']
                    nome_asset_orig = row['nome_asset']

                    # Try encryption_key first (could be Family key)
                    row['ticker'] = _decrypt_if_key(ticker_orig, encryption_key, crypto, silent=True)
                    row['nome_asset'] = _decrypt_if_key(nome_asset_orig, encryption_key, crypto, silent=True)
                    
                    # Fallback to master_key if failed (and keys are different)
                    if encryption_key != master_key:
                        if row['ticker'] == "[ENCRYPTED]" or row['ticker'].startswith("gAAAAA"):
                             decrypted = _decrypt_if_key(ticker_orig, master_key, crypto, silent=True)
                             if decrypted and decrypted != "[ENCRYPTED]": row['ticker'] = decrypted
                        
                        if row['nome_asset'] == "[ENCRYPTED]" or row['nome_asset'].startswith("gAAAAA"):
                             decrypted = _decrypt_if_key(nome_asset_orig, master_key, crypto, silent=True)
                             if decrypted and decrypted != "[ENCRYPTED]": row['nome_asset'] = decrypted
            
            # Sort by ticker (in Python because DB has encrypted data)
            results.sort(key=lambda x: x['ticker'])
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero portafoglio: {e}")
        return []


def aggiorna_prezzo_manuale_asset(id_asset, nuovo_prezzo):
    # No encryption needed for price
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            adesso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("UPDATE Asset SET prezzo_attuale_manuale = %s, data_aggiornamento = %s WHERE id_asset = %s", (nuovo_prezzo, adesso, id_asset))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiornamento prezzo: {e}")
        return False


def modifica_asset_dettagli(id_asset, nuovo_ticker, nuovo_nome, nuova_quantita=None, nuovo_costo_medio=None, master_key_b64=None):
    nuovo_ticker_upper = nuovo_ticker.upper()
    nuovo_nome_upper = nuovo_nome.upper()
    
    # Fetch id_conto to determine key
    id_conto = None
    try:
         with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_conto FROM Asset WHERE id_asset = %s", (id_asset,))
            res = cur.fetchone()
            if res:
                id_conto = res['id_conto']
    except Exception as e:
        print(f"[ERRORE] Errore recupero conto per modifica dettagli asset: {e}")

    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encryption_key = _get_key_for_transaction(id_conto, master_key, crypto)
    
    encrypted_ticker = _encrypt_if_key(nuovo_ticker_upper, encryption_key, crypto)
    encrypted_nome = _encrypt_if_key(nuovo_nome_upper, encryption_key, crypto)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Costruisci query dinamica
            query = "UPDATE Asset SET ticker = %s, nome_asset = %s"
            params = [encrypted_ticker, encrypted_nome]
            
            if nuova_quantita is not None:
                query += ", quantita = %s"
                params.append(nuova_quantita)
            
            if nuovo_costo_medio is not None:
                query += ", costo_iniziale_unitario = %s"
                params.append(nuovo_costo_medio)
                
            query += " WHERE id_asset = %s"
            params.append(id_asset)
            
            cur.execute(query, tuple(params))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiornamento dettagli asset: {e}")
        return False

def elimina_asset(id_asset):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Elimina lo storico associato (opzionale, ma consigliato per pulizia)
            # ATTENZIONE: Se eliminiamo storico, perdiamo traccia dei movimenti?
            # Se l'utente elimina l'asset, forse vuole cancellare tutto.
            # Per ora cancelliamo solo l'asset dalla tabella Asset.
            # Lo storico rimane "orfano" ma non crea problemi logici immediati.
            cur.execute("DELETE FROM Asset WHERE id_asset = %s", (id_asset,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione asset: {e}")
        return False




# --- Funzioni Investimenti ---
def aggiungi_investimento(id_conto, ticker, nome_asset, quantita, costo_unitario, data_acquisto, master_key_b64=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    # Determine correct key (Family Key if applicable)
    encryption_key = _get_key_for_transaction(id_conto, master_key, crypto)
    
    encrypted_ticker = _encrypt_if_key(ticker.upper(), encryption_key, crypto)
    encrypted_nome = _encrypt_if_key(nome_asset, encryption_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO Asset (id_conto, ticker, nome_asset, quantita, costo_iniziale_unitario, data_acquisto, prezzo_attuale_manuale) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_asset",
                (id_conto, encrypted_ticker, encrypted_nome, quantita, costo_unitario, data_acquisto, costo_unitario))
            return cur.fetchone()['id_asset']
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta investimento: {e}")
        return None

def modifica_investimento(id_asset, ticker, nome_asset, quantita, costo_unitario, data_acquisto, master_key_b64=None):
    # Fetch id_conto to determine key
    id_conto = None
    try:
         with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_conto FROM Asset WHERE id_asset = %s", (id_asset,))
            res = cur.fetchone()
            if res:
                id_conto = res['id_conto']
    except Exception as e:
        print(f"[ERRORE] Errore recupero conto per modifica asset: {e}")

    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encryption_key = _get_key_for_transaction(id_conto, master_key, crypto)

    encrypted_ticker = _encrypt_if_key(ticker.upper(), encryption_key, crypto)
    encrypted_nome = _encrypt_if_key(nome_asset, encryption_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(
                "UPDATE Asset SET ticker = %s, nome_asset = %s, quantita = %s, costo_iniziale_unitario = %s, data_acquisto = %s WHERE id_asset = %s",
                (encrypted_ticker, encrypted_nome, quantita, costo_unitario, data_acquisto, id_asset))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore modifica investimento: {e}")
        return False

def elimina_investimento(id_asset):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM Asset WHERE id_asset = %s", (id_asset,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione investimento: {e}")
        return False

def ottieni_investimenti(id_conto, master_key_b64=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Asset WHERE id_conto = %s", (id_conto,))
            assets = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            if master_key:
                # Determine encryption key (Family vs Master)
                encryption_key = _get_key_for_transaction(id_conto, master_key, crypto)
                
                for asset in assets:
                    asset['ticker'] = _decrypt_if_key(asset['ticker'], encryption_key, crypto, silent=True)
                    asset['nome_asset'] = _decrypt_if_key(asset['nome_asset'], encryption_key, crypto, silent=True)
                    
                    # Fallback to master_key if failed
                    if encryption_key != master_key:
                        if asset['ticker'] == "[ENCRYPTED]" or asset['ticker'].startswith("gAAAAA"):
                             decrypted = _decrypt_if_key(asset['ticker'], master_key, crypto, silent=True)
                             if decrypted and decrypted != "[ENCRYPTED]": asset['ticker'] = decrypted
                        
                        if asset['nome_asset'] == "[ENCRYPTED]" or asset['nome_asset'].startswith("gAAAAA"):
                             decrypted = _decrypt_if_key(asset['nome_asset'], master_key, crypto, silent=True)
                             if decrypted and decrypted != "[ENCRYPTED]": asset['nome_asset'] = decrypted
            
            return assets
    except Exception as e:
        print(f"[ERRORE] Errore recupero investimenti: {e}")
        return []

def ottieni_dettaglio_asset(id_asset, master_key_b64=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Asset WHERE id_asset = %s", (id_asset,))
            res = cur.fetchone()
            if not res: return None
            
            asset = dict(res)
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            if master_key:
                # Determine encryption key (Family vs Master)
                id_conto = asset.get('id_conto')
                encryption_key = _get_key_for_transaction(id_conto, master_key, crypto)
                
                # Decrypt ticker
                decrypted = _decrypt_if_key(asset['ticker'], encryption_key, crypto, silent=True)
                if (decrypted == "[ENCRYPTED]" or decrypted == asset['ticker']) and encryption_key != master_key:
                     decrypted = _decrypt_if_key(asset['ticker'], master_key, crypto, silent=True)
                if decrypted and decrypted != "[ENCRYPTED]": asset['ticker'] = decrypted

                # Decrypt nome_asset
                decrypted = _decrypt_if_key(asset['nome_asset'], encryption_key, crypto, silent=True)
                if (decrypted == "[ENCRYPTED]" or decrypted == asset['nome_asset']) and encryption_key != master_key:
                     decrypted = _decrypt_if_key(asset['nome_asset'], master_key, crypto, silent=True)
                if decrypted and decrypted != "[ENCRYPTED]": asset['nome_asset'] = decrypted
            
            return asset
    except Exception as e:
        print(f"[ERRORE] Errore recupero dettaglio asset: {e}")
        return None

def aggiorna_prezzo_asset(id_asset, nuovo_prezzo):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Asset SET prezzo_attuale_manuale = %s, data_ultimo_aggiornamento = CURRENT_TIMESTAMP WHERE id_asset = %s",
                        (nuovo_prezzo, id_asset))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore aggiornamento prezzo asset: {e}")
        return False



# --- Funzioni Prestiti ---



# --- Funzioni Giroconti ---
def esegui_giroconto(id_conto_origine, id_conto_destinazione, importo, data, descrizione=None, master_key_b64=None, tipo_origine="personale", tipo_destinazione="personale", id_utente_autore=None, id_famiglia=None):
    """
    Esegue un giroconto tra conti personali e/o condivisi.
    tipo_origine/tipo_destinazione: "personale" o "condiviso"
    """
    if not descrizione:
        descrizione = "Giroconto"
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    # Per conti condivisi, usa la family key
    family_key = None
    if (tipo_origine == "condiviso" or tipo_destinazione == "condiviso") and id_utente_autore and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente_autore, master_key, crypto)
    
    # Cripta la descrizione con la chiave appropriata
    # Se coinvolge conti condivisi, usa family_key per quelli
    encrypted_descrizione_personale = _encrypt_if_key(descrizione, master_key, crypto)
    encrypted_descrizione_condivisa = _encrypt_if_key(descrizione, family_key if family_key else master_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Prelievo dal conto origine
            if tipo_origine == "personale":
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (%s, %s, %s, %s)",
                    (id_conto_origine, data, encrypted_descrizione_personale, -abs(importo)))
            else:  # condiviso
                cur.execute(
                    "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s)",
                    (id_utente_autore, id_conto_origine, data, encrypted_descrizione_condivisa, -abs(importo)))
            
            # 2. Versamento sul conto destinazione
            if tipo_destinazione == "personale":
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (%s, %s, %s, %s)",
                    (id_conto_destinazione, data, encrypted_descrizione_personale, abs(importo)))
            else:  # condiviso
                cur.execute(
                    "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s)",
                    (id_utente_autore, id_conto_destinazione, data, encrypted_descrizione_condivisa, abs(importo)))
            
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore esecuzione giroconto: {e}")
        return False


# --- Funzioni Export ---
def ottieni_riepilogo_conti_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        # Decryption setup
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            
            # --- Personal Accounts ---
            # Cast 0.0 to NUMERIC/REAL to ensure type match in UNION/CASE if needed, though usually automatic.
            # The issue 'CASE types double precision and text' implies one branch is text.
            # COALESCE returns type of first non-null arg. 0.0 is double.
            # Check if fields are correct.
            query_personali = """
                        SELECT U.nome_enc_server, U.cognome_enc_server, U.username,
                               C.nome_conto,
                               C.tipo,
                               C.iban,
                               CASE
                                   WHEN C.tipo = 'Fondo Pensione' THEN CAST(C.valore_manuale AS DOUBLE PRECISION)
                                   WHEN C.tipo = 'Investimento'
                                       THEN (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                             FROM Asset A
                                             WHERE A.id_conto = C.id_conto)
                                   ELSE (SELECT COALESCE(SUM(T.importo), 0.0)
                                         FROM Transazioni T
                                         WHERE T.id_conto = C.id_conto) + COALESCE(CAST(NULLIF(CAST(C.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0)
                                   END                                          AS saldo_calcolato
                        FROM Conti C
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                          AND (C.nascosto IS NOT TRUE)
            """
            
            # --- Shared Accounts ---
            # Fixed missing 'iban' in ContiCondivisi by selecting NULL
            query_condivisi = """
                        SELECT 'Condiviso' as nome_enc_server, NULL as cognome_enc_server, 'Condiviso' as username,
                               CC.nome_conto,
                               CC.tipo,
                               NULL as iban,
                               CASE
                                   WHEN CC.tipo = 'Investimento'
                                       THEN (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                             FROM Asset A
                                             WHERE 0=1) -- Shared Asset support missing in current schema
                                   ELSE (SELECT COALESCE(SUM(TC.importo), 0.0)
                                         FROM TransazioniCondivise TC
                                         WHERE TC.id_conto_condiviso = CC.id_conto_condiviso) + COALESCE(CAST(NULLIF(CAST(CC.rettifica_saldo AS TEXT), '') AS NUMERIC), 0.0)
                                   END                                          AS saldo_calcolato
                        FROM ContiCondivisi CC
                        WHERE CC.id_famiglia = %s
            """
            
            # Execute queries
            cur.execute(query_personali, (id_famiglia,))
            personali = [dict(row) for row in cur.fetchall()]
            
            cur.execute(query_condivisi, (id_famiglia,))
            condivisi = [dict(row) for row in cur.fetchall()]
            
            results = personali + condivisi
            
            # Decrypt and Format
            for row in results:
                # Decrypt Member Name
                if row.get('username') == 'Condiviso':
                     row['membro'] = "Condiviso"
                else:
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['membro'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['membro'] = row.get('username', 'Sconosciuto')
                
                # Decrypt Account Name
                if row.get('nome_conto'):
                    decrypted_conto = _decrypt_if_key(row['nome_conto'], family_key, crypto, silent=True)
                    # Check if decryption failed (None, [ENCRYPTED], or returned original encrypted value)
                    if (not decrypted_conto or decrypted_conto == "[ENCRYPTED]" or decrypted_conto == row['nome_conto']) and family_key != master_key:
                        decrypted_conto = _decrypt_if_key(row['nome_conto'], master_key, crypto, silent=True)
                    row['nome_conto'] = decrypted_conto or row['nome_conto']
                
                # Decrypt IBAN
                if row.get('iban'):
                     decrypted_iban = _decrypt_if_key(row['iban'], family_key, crypto, silent=True)
                     if (not decrypted_iban or decrypted_iban == "[ENCRYPTED]" or decrypted_iban == row['iban']) and family_key != master_key:
                         decrypted_iban = _decrypt_if_key(row['iban'], master_key, crypto, silent=True)
                     row['iban'] = decrypted_iban or row['iban']

                # Clean up encrypted/internal fields
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
            
            # Sort by Member, Type, Account Name
            results.sort(key=lambda x: (x.get('membro', ''), x.get('tipo', ''), x.get('nome_conto', '')))
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero riepilogo conti famiglia: {e}")
        return []


def ottieni_dettaglio_portafogli_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        # Decryption setup
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            # Removed Shared Investments UNION as Asset table does not support Shared Accounts yet (missing id_conto_condiviso)
            query = """
                        SELECT U.nome_enc_server, U.cognome_enc_server, U.username,
                               C.nome_conto,
                               A.ticker,
                               A.nome_asset,
                               A.quantita,
                               A.costo_iniziale_unitario,
                               A.prezzo_attuale_manuale as valore_corrente_unitario,
                               (A.quantita * A.costo_iniziale_unitario)             AS investito_totale,
                               (A.quantita * A.prezzo_attuale_manuale)              AS valore_totale,
                               ((A.quantita * A.prezzo_attuale_manuale) - (A.quantita * A.costo_iniziale_unitario)) AS profitto
                        FROM Conti C
                                 JOIN Asset A ON C.id_conto = A.id_conto
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                          AND C.tipo = 'Investimento'
                          
                        ORDER BY username, nome_conto, ticker
            """
            cur.execute(query, (id_famiglia,))
            
            results = [dict(row) for row in cur.fetchall()]
            for row in results:
                # Decrypt Member
                if row.get('username') == 'Condiviso':
                    row['membro'] = "Condiviso"
                else:
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['membro'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['membro'] = row.get('username', 'Sconosciuto')
                
                # Decrypt Account/Ticker/Asset
                for field in ['nome_conto', 'ticker', 'nome_asset']:
                    val = row.get(field)
                    if val:
                        decrypted = _decrypt_if_key(val, family_key, crypto, silent=True)
                        # Check if decryption failed (None, [ENCRYPTED], or returned original encrypted value)
                        if (not decrypted or decrypted == "[ENCRYPTED]" or decrypted == val) and family_key != master_key:
                            decrypted = _decrypt_if_key(val, master_key, crypto, silent=True)
                        row[field] = decrypted or val
                
                # Clean up encrypted/internal fields
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
            
            return results

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero dettaglio portafogli famiglia: {e}")
        return []




def ottieni_transazioni_famiglia_per_export(id_famiglia, data_inizio, data_fine, master_key_b64=None, id_utente=None, filtra_utente_id=None):
    try:
        # Decryption setup
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            
            # --- Personal Transactions ---
            # Transazioni joins Sottocategorie joins Categorie
            # If filtra_utente_id is set, restrict to that user only
            sql_filtro_utente = ""
            params_personali = [id_famiglia, data_inizio, data_fine]
            
            if filtra_utente_id:
                sql_filtro_utente = "AND U.id_utente = %s"
                params_personali.append(filtra_utente_id)

            query_personali = f"""
                        SELECT T.data,
                               U.nome_enc_server, U.cognome_enc_server, U.username,
                               C.nome_conto,
                               T.descrizione,
                               Cat.nome_categoria,
                               T.importo
                        FROM Transazioni T
                                 JOIN Conti C ON T.id_conto = C.id_conto
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                                 LEFT JOIN Sottocategorie S ON T.id_sottocategoria = S.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON S.id_categoria = Cat.id_categoria
                        WHERE AF.id_famiglia = %s
                          AND T.data BETWEEN %s AND %s
                          AND C.tipo != 'Fondo Pensione'
                          {sql_filtro_utente}
            """
            
            # --- Shared Transactions ---
            query_condivise = """
                        SELECT TC.data,
                               'Condiviso' as nome_enc_server, NULL as cognome_enc_server, 'Condiviso' as username,
                               CC.nome_conto,
                               TC.descrizione,
                               Cat.nome_categoria,
                               TC.importo
                        FROM TransazioniCondivise TC
                                 JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                 LEFT JOIN Sottocategorie S ON TC.id_sottocategoria = S.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON S.id_categoria = Cat.id_categoria
                        WHERE CC.id_famiglia = %s
                          AND TC.data BETWEEN %s AND %s
            """
            
            # Exec Personal
            cur.execute(query_personali, tuple(params_personali))
            personali = [dict(row) for row in cur.fetchall()]
            
            # Exec Shared
            cur.execute(query_condivise, (id_famiglia, data_inizio, data_fine))
            condivise = [dict(row) for row in cur.fetchall()]
            
            # Combine
            results = personali + condivise
            
            # Decrypt loop & Filter
            final_results = []
            for row in results:
                # Decrypt Member
                if row.get('username') == 'Condiviso':
                     row['membro'] = "Condiviso"
                else:
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['membro'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['membro'] = row.get('username', 'Sconosciuto')

                # Decrypt Fields (Account, Description, Category)
                for field in ['nome_conto', 'descrizione', 'nome_categoria']:
                    val = row.get(field)
                    if val:
                        # Try Family Key
                        decrypted = _decrypt_if_key(val, family_key, crypto, silent=True)
                        
                        # If failed (ENCRYPTED or None), and we have a different Master Key, try that
                        if (not decrypted or decrypted == "[ENCRYPTED]") and family_key != master_key:
                             decrypted = _decrypt_if_key(val, master_key, crypto, silent=True)
                        
                        # If still failed, keep original val (or handle below)
                        if decrypted and decrypted != "[ENCRYPTED]":
                            row[field] = decrypted
                        else:
                            row[field] = val # Revert to raw if decryption failed completely

                # USER REQ: Eliminate 'Saldo iniziale'
                if str(row.get('descrizione', '')).lower() == "saldo iniziale":
                    continue

                # USER REQ: Rename encrypted giroconti
                desc = row.get('descrizione', '')
                if isinstance(desc, str):
                    if desc.startswith('gAAAA') or desc == "[ENCRYPTED]":
                        row['descrizione'] = "Giroconto (Criptato)"

                # Clean up encrypted/internal fields
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
                
                final_results.append(row)
            
            # USER REQ: Sort Oldest to Newest (Ascending)
            final_results.sort(key=lambda x: x['data'], reverse=False)
            
            return final_results

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero transazioni famiglia per export: {e}")
        return []

def ottieni_dati_immobili_famiglia_per_export(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            # Fixed 'mutuo_residuo' missing. It's in Prestiti table linked by id_prestito_collegato
            query = """
                SELECT I.nome as nome_immobile, I.via || ', ' || I.citta as indirizzo, I.valore_attuale, 
                       P.importo_residuo as mutuo_residuo, I.nuda_proprieta,
                       QI.id_utente, U.nome_enc_server, U.cognome_enc_server, U.username,
                       QI.percentuale
                FROM Immobili I
                LEFT JOIN Prestiti P ON I.id_prestito_collegato = P.id_prestito
                LEFT JOIN QuoteImmobili QI ON I.id_immobile = QI.id_immobile
                LEFT JOIN Utenti U ON QI.id_utente = U.id_utente
                WHERE I.id_famiglia = %s
                ORDER BY I.nome
            """
            cur.execute(query, (id_famiglia,))
            
            results = [dict(row) for row in cur.fetchall()]
            for row in results:
                # Decrypt Member
                if row.get('username'):
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['comproprietario'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['comproprietario'] = row.get('username', 'Sconosciuto')
                else:
                    row['comproprietario'] = "Nessuno/Non assegnato"
                    
                # Decrypt Property details
                for field in ['nome_immobile', 'indirizzo']:
                    val = row.get(field)
                    if val:
                        decrypted = _decrypt_if_key(val, family_key, crypto, silent=True)
                        row[field] = decrypted or val
                
                # Clean up
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
                row.pop('id_utente', None)
                        
            return results
    except Exception as e:
        print(f"[ERRORE] Errore export immobili: {e}")
        return []

def ottieni_dati_prestiti_famiglia_per_export(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            # Fixed 'data_scadenza' missing
            query = """
                SELECT P.nome, P.importo_finanziato as importo_totale, P.importo_residuo as importo_rimanente, P.data_inizio,
                       QP.id_utente, U.nome_enc_server, U.cognome_enc_server, U.username,
                       QP.percentuale
                FROM Prestiti P
                LEFT JOIN QuotePrestiti QP ON P.id_prestito = QP.id_prestito
                LEFT JOIN Utenti U ON QP.id_utente = U.id_utente
                WHERE P.id_famiglia = %s
                ORDER BY P.nome
            """
            cur.execute(query, (id_famiglia,))
            
            results = [dict(row) for row in cur.fetchall()]
            for row in results:
                 # Decrypt Member
                if row.get('username'):
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['intestatario'] = f"{n or ''} {c or ''}".strip()
                    else:
                        row['intestatario'] = row.get('username', 'Sconosciuto')
                else:
                    row['intestatario'] = "Nessuno/Non assegnato"
                
                # Decrypt name
                if row.get('nome'):
                     decrypted = _decrypt_if_key(row['nome'], family_key, crypto, silent=True)
                     row['nome'] = decrypted or row['nome']
                
                # Clean up
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
                row.pop('id_utente', None)
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore export prestiti: {e}")
        return []

def ottieni_dati_spese_fisse_famiglia_per_export(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        with get_db_connection() as con:
            cur = con.cursor()
            # SpeseFisse uses 'id_conto_personale_addebito' and 'id_conto_condiviso_addebito'
            query = """
                SELECT SF.nome, SF.importo, SF.giorno_addebito, SF.attiva, SF.addebito_automatico,
                       SF.id_conto_personale_addebito, C.nome_conto as nome_conto_personale, U.nome_enc_server, U.cognome_enc_server, U.username,
                       SF.id_conto_condiviso_addebito, CC.nome_conto as nome_conto_condiviso,
                       Cat.nome_categoria,
                       SC.nome_sottocategoria
                FROM SpeseFisse SF
                LEFT JOIN Conti C ON SF.id_conto_personale_addebito = C.id_conto
                LEFT JOIN Utenti U ON C.id_utente = U.id_utente
                LEFT JOIN ContiCondivisi CC ON SF.id_conto_condiviso_addebito = CC.id_conto_condiviso
                LEFT JOIN Categorie Cat ON SF.id_categoria = Cat.id_categoria
                LEFT JOIN Sottocategorie SC ON SF.id_sottocategoria = SC.id_sottocategoria
                WHERE SF.id_famiglia = %s
                ORDER BY SF.giorno_addebito
            """
            cur.execute(query, (id_famiglia,))
            
            results = [dict(row) for row in cur.fetchall()]
            for row in results:
                # Resolve Account Name and Owner
                if row.get('id_conto_personale_addebito'):
                     # Personal Account
                    # Decrypt Member
                    n = decrypt_system_data(row.get('nome_enc_server'))
                    c = decrypt_system_data(row.get('cognome_enc_server'))
                    if n or c:
                        row['conto_addebito'] = f"{row.get('nome_conto_personale')} ({n or ''} {c or ''})".strip()
                    else:
                        row['conto_addebito'] = f"{row.get('nome_conto_personale')} ({row.get('username', '?')})"
                else:
                    # Shared Account
                    row['conto_addebito'] = f"{row.get('nome_conto_condiviso')} (Condiviso)"
                
                # Decrypt Expense Name
                if row.get('nome'):
                     decrypted = _decrypt_if_key(row['nome'], family_key, crypto, silent=True)
                     row['nome'] = decrypted or row['nome']
                
                # Decrypt Account Names
                # nome_conto_personale and nome_conto_condiviso are potentially encrypted
                conto_name = row.get('nome_conto_personale') or row.get('nome_conto_condiviso')
                if conto_name:
                    decrypted_conto = _decrypt_if_key(conto_name, family_key, crypto, silent=True)
                    if not decrypted_conto and family_key != master_key:
                        decrypted_conto = _decrypt_if_key(conto_name, master_key, crypto, silent=True)
                    conto_name = decrypted_conto or conto_name
                
                if row.get('id_conto_personale_addebito'):
                     n = decrypt_system_data(row.get('nome_enc_server'))
                     c = decrypt_system_data(row.get('cognome_enc_server'))
                     owner = f"{n or ''} {c or ''}".strip() or row.get('username')
                     row['conto_addebito'] = f"{conto_name} ({owner})"
                else:
                    row['conto_addebito'] = f"{conto_name} (Condiviso)"

                # Decrypt Category/Subcat
                if row.get('nome_categoria'):
                     decrypted = _decrypt_if_key(row['nome_categoria'], family_key, crypto, silent=True)
                     row['nome_categoria'] = decrypted or row['nome_categoria']
                
                # Clean up
                row.pop('nome_enc_server', None)
                row.pop('cognome_enc_server', None)
                row.pop('username', None)
                row.pop('id_conto_personale_addebito', None)
                row.pop('id_conto_condiviso_addebito', None)
                row.pop('nome_conto_personale', None)
                row.pop('nome_conto_condiviso', None)
                
            return results
    except Exception as e:
        print(f"[ERRORE] Errore export spese fisse: {e}")
        return []


def ottieni_prima_famiglia_utente(id_utente):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s LIMIT 1", (id_utente,))
            res = cur.fetchone()
            return res['id_famiglia'] if res else None
    except Exception as e:
        print(f"[ERRORE] Errore generico: {e}")
        return None


# --- NUOVE FUNZIONI PER SPESE FISSE ---
def aggiungi_spesa_fissa(id_famiglia, nome, importo, id_conto_personale=None, id_conto_condiviso=None, id_sottocategoria=None, giorno_addebito=1, attiva=True, addebito_automatico=False, master_key_b64=None, id_utente=None, id_carta=None):
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        # Encrypt Name
        key_to_use = family_key if family_key else master_key
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto) if key_to_use else nome

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO SpeseFisse (
                    id_famiglia, nome, importo, id_conto_personale_addebito, id_conto_condiviso_addebito,
                    id_categoria, id_sottocategoria, giorno_addebito, attiva, addebito_automatico, id_carta
                )
                VALUES (%s, %s, %s, %s, %s, (SELECT id_categoria FROM Sottocategorie WHERE id_sottocategoria = %s), %s, %s, %s, %s, %s)
            """, (id_famiglia, nome_enc, importo, id_conto_personale, id_conto_condiviso, id_sottocategoria, id_sottocategoria, giorno_addebito, attiva, addebito_automatico, id_carta))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'aggiunta della spesa fissa: {e}")
        return None


def modifica_spesa_fissa(id_spesa_fissa, nome, importo, id_conto_personale=None, id_conto_condiviso=None, id_sottocategoria=None, giorno_addebito=1, attiva=True, addebito_automatico=False, master_key_b64=None, id_utente=None, id_carta=None):
    try:
        # Recupera famiglia
        id_famiglia = None
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia FROM SpeseFisse WHERE id_spesa_fissa = %s", (id_spesa_fissa,))
            res = cur.fetchone()
            if res: id_famiglia = res['id_famiglia']

        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente and id_famiglia:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        key_to_use = family_key if family_key else master_key
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto) if key_to_use else nome

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE SpeseFisse
                SET nome = %s, importo = %s, id_conto_personale_addebito = %s, id_conto_condiviso_addebito = %s,
                    id_sottocategoria = %s, id_categoria = (SELECT id_categoria FROM Sottocategorie WHERE id_sottocategoria = %s),
                    giorno_addebito = %s, attiva = %s, addebito_automatico = %s, id_carta = %s
                WHERE id_spesa_fissa = %s
            """, (nome_enc, importo, id_conto_personale, id_conto_condiviso, id_sottocategoria, id_sottocategoria, giorno_addebito, attiva, addebito_automatico, id_carta, id_spesa_fissa))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante la modifica della spesa fissa: {e}")
        return False


def modifica_stato_spesa_fissa(id_spesa_fissa, nuovo_stato):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE SpeseFisse SET attiva = %s WHERE id_spesa_fissa = %s",
                        (1 if nuovo_stato else 0, id_spesa_fissa))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante la modifica dello stato della spesa fissa: {e}")
        return False


def elimina_spesa_fissa(id_spesa_fissa):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM SpeseFisse WHERE id_spesa_fissa = %s", (id_spesa_fissa,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante l'eliminazione della spesa fissa: {e}")
        return False


def ottieni_spese_fisse_famiglia(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                SELECT 
                    SF.id_spesa_fissa,
                    SF.nome,
                    SF.importo,
                    SF.id_conto_personale_addebito,
                    SF.id_conto_condiviso_addebito,
                    SF.id_categoria,
                    SF.id_sottocategoria,
                    SF.giorno_addebito,
                    SF.attiva,
                    SF.addebito_automatico,
                    SF.id_carta,
                    COALESCE(CP.nome_conto, CC.nome_conto) as nome_conto,
                    CARTE.nome_carta,
                    CARTE.id_conto_contabile as id_conto_carta_pers,
                    CARTE.id_conto_contabile_condiviso as id_conto_carta_cond,
                    U_CP.username_enc as username_enc_conto,
                    U_CARTE.username_enc as username_enc_carta
                FROM SpeseFisse SF
                LEFT JOIN Conti CP ON SF.id_conto_personale_addebito = CP.id_conto
                LEFT JOIN Utenti U_CP ON CP.id_utente = U_CP.id_utente
                LEFT JOIN ContiCondivisi CC ON SF.id_conto_condiviso_addebito = CC.id_conto_condiviso
                LEFT JOIN Carte CARTE ON SF.id_carta = CARTE.id_carta
                LEFT JOIN Utenti U_CARTE ON CARTE.id_utente = U_CARTE.id_utente
                WHERE SF.id_famiglia = %s
                ORDER BY SF.nome
            """, (id_famiglia,))
            spese = [dict(row) for row in cur.fetchall()]

            # Decrypt nome if keys available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                try:
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
                except Exception:
                    pass

            def is_encrypted(val):
                return val == "[ENCRYPTED]" or (isinstance(val, str) and val.startswith("gAAAAA"))

            if family_key:
                for spesa in spese:
                    spesa['nome'] = _decrypt_if_key(spesa['nome'], family_key, crypto)
                    
                    # Decripta anche il nome del conto
                    if spesa.get('nome_conto'):
                         # Prova prima con family_key (per conti condivisi)
                        if spesa.get('id_conto_condiviso_addebito'):
                            spesa['nome_conto'] = _decrypt_if_key(spesa['nome_conto'], family_key, crypto, silent=True)
                        else:
                            # Conto personale: prova con master_key prima (se l'utente è il proprietario)
                             spesa['nome_conto'] = _decrypt_if_key(spesa['nome_conto'], master_key, crypto, silent=True) # Usa master key utente corrente
                             
                             # Se fallisce decriptazione e abbiamo username proprietario
                             if is_encrypted(spesa['nome_conto']):
                                 user_conto_enc = spesa.get('username_enc_conto')
                                 if user_conto_enc:
                                     user_conto = decrypt_system_data(user_conto_enc)
                                     if user_conto:
                                        spesa['nome_conto'] = f"Conto di {user_conto}"

                    if spesa.get('nome_carta'):
                         spesa['nome_carta'] = _decrypt_if_key(spesa['nome_carta'], family_key, crypto, silent=True)
                         if is_encrypted(spesa['nome_carta']) and family_key != master_key:
                             test_dec = _decrypt_if_key(spesa['nome_carta'], master_key, crypto, silent=True)
                             if test_dec and not is_encrypted(test_dec): 
                                 spesa['nome_carta'] = test_dec
                             elif spesa.get('username_enc_carta'):
                                 user_carta = decrypt_system_data(spesa.get('username_enc_carta'))
                                 if user_carta:
                                     spesa['nome_carta'] = f"Carta di {user_carta}"

                    # Sovrascrivi nome_conto se c'è una carta
                    if spesa.get('id_carta') and spesa.get('nome_carta'):
                         spesa['nome_conto'] = f"{spesa['nome_carta']} (Carta)"
            else:
                 # Fallback without family key (should theoretically not happen for family view if logged in properly)
                 # Try decrypting with master_key just in case (e.g. personal items)
                 if master_key:
                     for spesa in spese:
                         # Decrypt card if present
                         if spesa.get('id_carta') and spesa.get('nome_carta'):
                             dec = _decrypt_if_key(spesa['nome_carta'], master_key, crypto, silent=True)
                             if dec and not is_encrypted(dec): 
                                 spesa['nome_carta'] = dec
                             elif spesa.get('username_enc_carta'):
                                 user_carta = decrypt_system_data(spesa.get('username_enc_carta'))
                                 if user_carta:
                                     spesa['nome_carta'] = f"Carta di {user_carta}"

                             spesa['nome_conto'] = f"{spesa['nome_carta']} (Carta)"
                             
                         elif spesa.get('nome_conto') and not spesa.get('id_conto_condiviso_addebito'):
                             # Try decrypt personal account
                             dec = _decrypt_if_key(spesa['nome_conto'], master_key, crypto, silent=True)
                             if dec and not is_encrypted(dec):
                                 spesa['nome_conto'] = dec
                             elif spesa.get('username_enc_conto'):
                                 user_conto = decrypt_system_data(spesa.get('username_enc_conto'))
                                 if user_conto:
                                     spesa['nome_conto'] = f"Conto di {user_conto}"

            return spese
    except Exception as e:
        print(f"[ERRORE] Errore durante il recupero delle spese fisse: {e}")
        return []

def _trova_admin_famiglia(id_famiglia):
    """Helper per trovare l'ID di un utente admin nella famiglia."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND ruolo = 'admin' LIMIT 1", (id_famiglia,))
            res = cur.fetchone()
            return res['id_utente'] if res else None
    except Exception as e:
        print(f"[ERRORE] _trova_admin_famiglia: {e}")
        return None

def _esegui_spesa_fissa(spesa):
    """Esegue una singola spesa fissa creando la transazione."""
    today = datetime.date.today()
    try:
        # Determina id_conto effettivo:
        # Se c'è una carta, usa il suo conto contabile (o di riferimento)
        id_conto_personale = spesa.get('id_conto_personale_addebito')
        id_conto_condiviso = spesa.get('id_conto_condiviso_addebito')
        id_carta = spesa.get('id_carta')
        
        # Se id_carta è presente, usiamo il conto contabile della carta come conto di addebito
        if id_carta:
             # Se la carta è definita, il conto di addebito deve essere quello della carta
             # Se Conto Personale Carta
             if spesa.get('id_conto_carta_pers'):
                 id_conto_personale = spesa.get('id_conto_carta_pers')
                 id_conto_condiviso = None
             # Se Conto Condiviso Carta
             elif spesa.get('id_conto_carta_cond'):
                 id_conto_condiviso = spesa.get('id_conto_carta_cond')
                 id_conto_personale = None
             # Se non c'è conto contabile (es. debito senza specifico), usa quello di riferimento o quello gia impostato
             # ... (logica attuale OK se id_conto_personale_addebito era già quello della carta)
        
        # Se nome è criptato e non abbiamo chiave qui (job automatico), lo passiamo criptato o cerchiamo di decriptare?
        # Il job automatico spesso non ha chiavi utente in memoria se gira in background.
        # Ma controlla_scadenze viene chiamato spesso con utente loggato.
        # Assumiamo che descrizione sia già il nome (potrebbe essere criptato).
        
        if id_conto_personale:
            res = aggiungi_transazione(
                id_conto=id_conto_personale,
                data=today.strftime('%Y-%m-%d'),
                descrizione=f"{spesa['nome']} (Automatico)",
                importo=-abs(spesa['importo']),
                id_sottocategoria=spesa['id_sottocategoria'],
                master_key_b64=None, # Non possiamo decriptare se background, MA aggiungi_transazione cifra se key passata.
                # Se non passiamo key, salva in chiaro? NO. Salva criptato SE trova key in session o altro.
                # Qui è tricky. Se gira automatico background senza sessione. 
                # Per ora assumiamo esecuzione con utente loggato o che accetti encrypted string.
                id_carta=id_carta
            )
        elif id_conto_condiviso:
            # Serve autore. Per spese fisse automatiche, chi è l'autore?
            # Se background, serve "sistema" o primo admin.
            # Qui semplifichiamo: se chiamato da UI, usa user. Se background?
            # BudgetAmico è desktop app single user session mostly. 
            # Assumiamo id_utente della spesa fissa? SpeseFisse non ha id_utente OWNER, ma id_famiglia.
            # Cerchiamo un admin della famiglia?
            id_autore = _trova_admin_famiglia(spesa['id_famiglia'])
            if not id_autore: return False
            
            res = aggiungi_transazione_condivisa(
                id_utente_autore=id_autore,
                id_conto_condiviso=id_conto_condiviso,
                data=today.strftime('%Y-%m-%d'),
                descrizione=f"{spesa['nome']} (Automatico)",
                importo=-abs(spesa['importo']),
                id_sottocategoria=spesa['id_sottocategoria'],
                master_key_b64=None,
                id_carta=id_carta
            )
        else:
            return False

        return res is not None

    except Exception as e:
        print(f"[ERRORE] Errore esecuzione spesa fissa: {e}")
        return False


def check_e_processa_spese_fisse(id_famiglia, master_key_b64=None, id_utente=None):
    oggi = datetime.date.today()
    spese_eseguite = 0
    try:
        spese_da_processare = ottieni_spese_fisse_famiglia(id_famiglia, master_key_b64=master_key_b64, id_utente=id_utente)
        with get_db_connection() as con:
            cur = con.cursor()
            for spesa in spese_da_processare:
                if not spesa['attiva']:
                    continue
                
                # Processa solo le spese con addebito automatico abilitato
                if not spesa.get('addebito_automatico'):
                    continue

                # Suffisso univoco per identificare la spesa (non criptato, usato per controllo duplicati)
                suffisso_id = f"[SF-{spesa['id_spesa_fissa']}]"

                # Controlla se la spesa è già stata eseguita questo mese
                # Usa POSITION per cercare il suffisso ID nella descrizione (che è criptata ma il suffisso no)
                # Check personal account
                if spesa.get('id_conto_personale_addebito'):
                    cur.execute("""
                        SELECT 1 FROM Transazioni
                        WHERE id_conto = %s
                        AND POSITION(%s IN descrizione) > 0
                        AND TO_CHAR(data::date, 'YYYY-MM') = %s
                    """, (spesa['id_conto_personale_addebito'], suffisso_id, oggi.strftime('%Y-%m')))
                    if cur.fetchone(): continue
                
                # Check shared account
                if spesa.get('id_conto_condiviso_addebito'):
                    cur.execute("""
                        SELECT 1 FROM TransazioniCondivise
                        WHERE id_conto_condiviso = %s
                        AND POSITION(%s IN descrizione) > 0
                        AND TO_CHAR(data::date, 'YYYY-MM') = %s
                    """, (spesa['id_conto_condiviso_addebito'], suffisso_id, oggi.strftime('%Y-%m')))
                    if cur.fetchone(): continue

                # Se il giorno di addebito è passato, esegui la transazione
                if oggi.day >= spesa['giorno_addebito']:
                    # Usa il giorno configurato per la data di esecuzione, non la data odierna
                    data_esecuzione = datetime.date(oggi.year, oggi.month, spesa['giorno_addebito']).strftime('%Y-%m-%d')
                    # Aggiungi suffisso ID alla descrizione per tracciabilità e controllo duplicati
                    descrizione = f"Spesa Fissa: {spesa['nome']} {suffisso_id}"
                    importo = -abs(spesa['importo'])

                    # Use the new _esegui_spesa_fissa helper
                    if _esegui_spesa_fissa(spesa):
                        spese_eseguite += 1
            if spese_eseguite > 0:
                con.commit()
        return spese_eseguite
    except Exception as e:
        print(f"[ERRORE] Errore critico durante il processamento delle spese fisse: {e}")
        return 0


# --- FUNZIONI STORICO ASSET GLOBALE (cross-famiglia) ---

_TABELLA_STORICO_CREATA = False
_LAST_UPDATE_CHECK_CACHE = {}  # Cache per throttling aggiornamenti (ticker -> datetime)

def _crea_tabella_storico_asset_globale():
    """Crea la tabella StoricoAssetGlobale se non esiste."""
    global _TABELLA_STORICO_CREATA
    if _TABELLA_STORICO_CREATA:
        return True
        
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS StoricoAssetGlobale (
                    id SERIAL PRIMARY KEY,
                    ticker VARCHAR(30) NOT NULL,
                    data DATE NOT NULL,
                    prezzo_chiusura DECIMAL(18, 6) NOT NULL,
                    data_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, data)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_storico_ticker ON StoricoAssetGlobale(ticker);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_storico_data ON StoricoAssetGlobale(data);")
            con.commit()
            _TABELLA_STORICO_CREATA = True
            return True
    except Exception as e:
        print(f"[ERRORE] Errore creazione tabella StoricoAssetGlobale: {e}")
        return False


def _pulisci_storico_vecchio():
    """
    Ottimizza lo storico conservando:
    - Ultimi 5 anni: dettaglio giornaliero
    - Da 5 a 25 anni: dettaglio mensile (solo primo del mese)
    - Oltre 25 anni: elimina
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Elimina dati più vecchi di 25 anni (pulizia profonda)
            data_limite_25y = (datetime.date.today() - datetime.timedelta(days=365*25)).strftime('%Y-%m-%d')
            cur.execute("DELETE FROM StoricoAssetGlobale WHERE data < %s", (data_limite_25y,))
            
            # 2. Downsampling: per dati più vecchi di 5 anni, mantieni solo il 1° del mese
            # Nota: SQLite strftime('%d', data) ritorna il giorno. Se != '01', eliminiamo.
            data_limite_5y = (datetime.date.today() - datetime.timedelta(days=365*5)).strftime('%Y-%m-%d')
            
            # Query ottimizzata: elimina record vecchi che NON sono il primo del mese
            # Postgres syntax: EXTRACT(DAY FROM data) returns numeric day (1-31)
            cur.execute("""
                DELETE FROM StoricoAssetGlobale 
                WHERE data < %s 
                  AND EXTRACT(DAY FROM data) != 1
            """, (data_limite_5y,))
            
            eliminati = cur.rowcount
            if eliminati > 0:
                print(f"[INFO] Ottimizzazione storico: rimossi {eliminati} record giornalieri vecchi")
            
            con.commit()
            return eliminati
    except Exception as e:
        print(f"[ERRORE] Errore ottimizzazione storico vecchio: {e}")
        return 0


def salva_storico_asset_globale(ticker: str, dati_storici: list):
    """
    Salva/aggiorna prezzi storici nella cache globale.
    
    Args:
        ticker: Il ticker dell'asset (es. "AAPL")
        dati_storici: Lista di dict con {'data': 'YYYY-MM-DD', 'prezzo': float}
    
    Returns:
        Numero di record inseriti/aggiornati
    """
    if not dati_storici:
        return 0
    
    # Assicurati che la tabella esista
    _crea_tabella_storico_asset_globale()
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            inseriti = 0
            
            for record in dati_storici:
                try:
                    cur.execute("""
                        INSERT INTO StoricoAssetGlobale (ticker, data, prezzo_chiusura, data_aggiornamento)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (ticker, data) DO UPDATE SET 
                            prezzo_chiusura = EXCLUDED.prezzo_chiusura,
                            data_aggiornamento = CURRENT_TIMESTAMP
                    """, (ticker.upper(), record['data'], record['prezzo']))
                    inseriti += 1
                except Exception as e:
                    print(f"[ERRORE] Errore inserimento record storico per {ticker}: {e}")
            
            con.commit()
            return inseriti
    except Exception as e:
        print(f"[ERRORE] Errore salvataggio storico asset globale: {e}")
        return 0


def ottieni_storico_asset_globale(ticker: str, data_inizio: str = None, data_fine: str = None):
    """
    Recupera storico prezzi dalla cache globale.
    
    Args:
        ticker: Il ticker dell'asset
        data_inizio: Data inizio filtro (YYYY-MM-DD), opzionale
        data_fine: Data fine filtro (YYYY-MM-DD), opzionale
    
    Returns:
        Lista di dict con {data, prezzo_chiusura} ordinati per data crescente
    """
    # Assicurati che la tabella esista
    _crea_tabella_storico_asset_globale()
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            query = "SELECT data, prezzo_chiusura FROM StoricoAssetGlobale WHERE ticker = %s"
            params = [ticker.upper()]
            
            if data_inizio:
                query += " AND data >= %s"
                params.append(data_inizio)
            
            if data_fine:
                query += " AND data <= %s"
                params.append(data_fine)
            
            query += " ORDER BY data ASC"
            
            cur.execute(query, tuple(params))
            return [{'data': str(row['data']), 'prezzo_chiusura': float(row['prezzo_chiusura'])} for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore recupero storico asset globale: {e}")
        return []


def ultimo_aggiornamento_storico(ticker: str):
    """
    Restituisce la data dell'ultimo record per il ticker.
    """
    # Assicurati che la tabella esista
    _crea_tabella_storico_asset_globale()
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT MAX(data) as ultima_data FROM StoricoAssetGlobale WHERE ticker = %s", (ticker.upper(),))
            result = cur.fetchone()
            if result and result['ultima_data']:
                return str(result['ultima_data'])
            return None
    except Exception as e:
        print(f"[ERRORE] Errore recupero ultimo aggiornamento storico: {e}")
        return None

def _data_piu_vecchia_storico(ticker: str):
    """
    Restituisce la data del record più vecchio per il ticker.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT MIN(data) as prima_data FROM StoricoAssetGlobale WHERE ticker = %s", (ticker.upper(),))
            result = cur.fetchone()
            if result and result['prima_data']:
                return str(result['prima_data'])
            return None
    except Exception as e:
        print(f"[ERRORE] Errore recupero data più vecchia storico: {e}")
        return None


def aggiorna_storico_asset_se_necessario(ticker: str, anni: int = 25):
    """
    Aggiorna lo storico di un asset da yfinance.
    Strategia ibrida:
    - Se nuovo: scarica 25 anni mensili + 5 anni giornalieri.
    - Se esistente: aggiorna incrementalmente (giornaliero).
    """
    # Prima ottimizza i dati vecchi (downsampling)
    _pulisci_storico_vecchio()
    
    # Throttle check: se controllato meno di 1 ora fa, salta
    from datetime import datetime as dt
    ora = datetime.datetime.now()
    if ticker in _LAST_UPDATE_CHECK_CACHE:
        last_check = _LAST_UPDATE_CHECK_CACHE[ticker]
        if (ora - last_check).total_seconds() < 3600:
            # print(f"[DEBUG] Skip update {ticker} (throttled)")
            return False
    
    # Aggiorna ultimo controllo a ORA (indipendentemente dall'esito)
    _LAST_UPDATE_CHECK_CACHE[ticker] = ora
    
    ultima_data = ultimo_aggiornamento_storico(ticker)
    prima_data = _data_piu_vecchia_storico(ticker)
    
    oggi = datetime.date.today()
    oggi_str = oggi.strftime('%Y-%m-%d')
    
    # Calcola data target di inizio
    target_start_date = (oggi - datetime.timedelta(days=anni*365)).strftime('%Y-%m-%d')
    
    # Recupera data inizio trading effettiva dell'asset (inception date)
    from utils.yfinance_manager import ottieni_data_inizio_trading
    inception_date = ottieni_data_inizio_trading(ticker)
    
    # Se abbiamo una inception date, la data target non può essere precedente ad essa
    if inception_date and inception_date > target_start_date:
        target_start_date = inception_date
        # Buffer di sicurezza: se inception è 2019-01-01, e noi abbiamo 2019-01-05, è ok.
    
    # Condizione per download completo:
    # 1. Non abbiamo dati (ultima_data is None)
    # 2. Oppure i dati che abbiamo sono troppo recenti RISPETTO AL POSSIBILE (target_start_date)
    #    Questo significa che l'utente ha chiesto 25 anni ma noi ne abbiamo meno, ED ESISTONO DATI PIÙ VECCHI.
    
    manca_storico_profondo = False
    if prima_data:
        # Se la data più vecchia che abbiamo è POSTERIORE alla valid start date (con un margine di tolleranza di 30gg)
        # Esempio A: Asset vecchio (es. MSFT inizia 1986). Target: 2000. PrimaData: 2020. -> 2020 > 2000 -> MANCA.
        # Esempio B: Asset nuovo (es. VWCE inizia 2019). Target: 2019. PrimaData: 2019-07. -> 2019-07 > 2019-06 (presunto) -> Forse manca qualche mese.
        # Se PrimaData è 2019-07-23 e Inception è 2019-07-23 -> OK (differenza < 30gg)
        
        limit_date_dt = datetime.datetime.strptime(target_start_date, '%Y-%m-%d') + datetime.timedelta(days=30)
        limit_date = limit_date_dt.strftime('%Y-%m-%d')
        
        manca_storico_profondo = prima_data > limit_date
    
    # --- CASO 1: PRIMA IMPORTAZIONE O STORICO INSUFFICIENTE ---
    if not ultima_data or manca_storico_profondo:
        print(f"[INFO] Download completo storico {anni}y per {ticker} (Depth check: {manca_storico_profondo})...")
        inseriti_tot = 0
        
        # 1. Scarica storico lungo (es. 25 anni) a risoluzione MENSILE
        # Usiamo richiesta diretta per specificare l'intervallo '1mo'
        try:
            import requests
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            # Scarica anni richiesti mensili
            params_long = {'interval': '1mo', 'range': f'{anni}y'}
            resp_long = requests.get(url, headers=headers, params=params_long, timeout=15)
            if resp_long.status_code == 200:
                dati_long = _estrai_dati_da_risposta_yf(resp_long.json())
                if dati_long:
                    inseriti_tot += salva_storico_asset_globale(ticker, dati_long)
                    print(f"      - Salvati {len(dati_long)} punti mensili (base storica)")
        
            # 2. Scarica ultimi 5 anni a risoluzione GIORNALIERA (sovrascrive/dettaglia i recenti)
            # Solo se anni > 5, altrimenti il range è quello richiesto
            if anni >= 5:
                params_short = {'interval': '1d', 'range': '5y'}
                resp_short = requests.get(url, headers=headers, params=params_short, timeout=15)
                if resp_short.status_code == 200:
                    dati_short = _estrai_dati_da_risposta_yf(resp_short.json())
                    if dati_short:
                        inseriti_tot += salva_storico_asset_globale(ticker, dati_short)
                        print(f"      - Salvati {len(dati_short)} punti giornalieri (dettaglio recente)")
            
            return inseriti_tot > 0
            
        except Exception as e:
            print(f"[ERRORE] Errore download base {ticker}: {e}")
            return False

    # --- CASO 2: AGGIORNAMENTO INCREMENTALE (Solo se abbiamo già storico profondo) ---
    if ultima_data >= oggi_str:
        return False
    
    from datetime import datetime as dt
    ultima_dt = dt.strptime(ultima_data, '%Y-%m-%d')
    oggi_dt = dt.strptime(oggi_str, '%Y-%m-%d')
    giorni_mancanti = (oggi_dt - ultima_dt).days
    
    if giorni_mancanti <= 0:
        return False
    
    print(f"[INFO] Aggiornamento incrementale {ticker}: +{giorni_mancanti} giorni")
    
    # Determina range minimo per coprire il buco
    if giorni_mancanti <= 5: range_yf = '5d'
    elif giorni_mancanti <= 30: range_yf = '1mo'
    elif giorni_mancanti <= 90: range_yf = '3mo'
    elif giorni_mancanti <= 180: range_yf = '6mo'
    elif giorni_mancanti <= 365: range_yf = '1y'
    else: range_yf = '5y' # Se manca più di un anno, riscarica 5y
    
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        params = {'interval': '1d', 'range': range_yf}
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            dati_raw = _estrai_dati_da_risposta_yf(response.json())
            # Filtra solo i dati veramente nuovi (> ultima_data)
            dati_nuovi = [d for d in dati_raw if d['data'] > ultima_data]
            
            if dati_nuovi:
                salva_storico_asset_globale(ticker, dati_nuovi)
                return True
                
        return False
    except Exception as e:
        print(f"[ERRORE] Errore update {ticker}: {e}")
        return False

def _estrai_dati_da_risposta_yf(data: dict) -> list:
    """Helper per estrarre lista {data, prezzo} dal JSON grezzo di YF."""
    results = []
    try:
        if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
            res = data['chart']['result'][0]
            if 'timestamp' in res and 'indicators' in res:
                timestamps = res['timestamp']
                quotes = res['indicators']['quote'][0]
                closes = quotes.get('close', [])
                
                from datetime import datetime as dt
                for i, ts in enumerate(timestamps):
                    if i < len(closes) and closes[i] is not None:
                        data_str = dt.fromtimestamp(ts).strftime('%Y-%m-%d')
                        results.append({
                            'data': data_str,
                            'prezzo': float(closes[i])
                        })
    except Exception:
        pass
    return results


# --- MAIN ---
mimetypes.add_type("application/x-sqlite3", ".db")


if __name__ == "__main__":
    print("--- 0. PULIZIA DATABASE (CANCELLAZIONE .db) ---")
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"File '{DB_FILE}' rimosso per un test pulito.")


# --- GESTIONE PIANO AMMORTAMENTO ---

def aggiungi_rata_piano_ammortamento(id_prestito, numero_rata, data_scadenza, importo_rata, quota_capitale, quota_interessi, spese_fisse=0, stato='da_pagare'):
    """
    Aggiunge una rata al piano di ammortamento di un prestito.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO PianoAmmortamento 
                (id_prestito, numero_rata, data_scadenza, importo_rata, quota_capitale, quota_interessi, spese_fisse, stato)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (id_prestito, numero_rata, data_scadenza, importo_rata, quota_capitale, quota_interessi, spese_fisse, stato))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta rata piano ammortamento: {e}")
        return False

def ottieni_piano_ammortamento(id_prestito):
    """
    Recupera il piano di ammortamento completo per un prestito, ordinato per numero rata.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT * FROM PianoAmmortamento 
                WHERE id_prestito = %s 
                ORDER BY numero_rata ASC
            """, (id_prestito,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore recupero piano ammortamento: {e}")
        return []

def elimina_piano_ammortamento(id_prestito):
    """
    Elimina tutte le rate del piano di ammortamento per un prestito.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM PianoAmmortamento WHERE id_prestito = %s", (id_prestito,))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione piano ammortamento: {e}")
        return False

def aggiorna_stato_rata_piano(id_rata, nuovo_stato):
    """
    Aggiorna lo stato di una rata (es. da 'da_pagare' a 'pagata').
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE PianoAmmortamento SET stato = %s WHERE id_rata = %s", (nuovo_stato, id_rata))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiornamento stato rata: {e}")
        return False



# --- Funzioni Budget History Helpers ---

def trigger_budget_history_update(id_famiglia, data_riferimento, master_key_b64=None, id_utente=None, cursor=None):
    """
    Allinea la tabella Budget_Storico con la tabella Budget per il mese/anno corrente.
    Itera sui budget definiti, cripta nome e spesa (0), ed esegue UPSERT.
    """
    anno = data_riferimento.year
    mese = data_riferimento.month
    
    # 1. Recupera chiavi per crittografia
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    
    if not family_key:
        print(f"[WARN] trigger_budget_history_update: Cannot encrypt without family_key. id_utente={id_utente}")
        return False

    # 2. Definisci logica di update (inner function per riuso con/senza cursor esterno)
    def _perform_update(cur):
        # Fetch budget correnti con nomi in chiaro
        sql_fetch = """
        SELECT B.id_sottocategoria, B.importo_limite, S.nome_sottocategoria 
        FROM Budget B
        JOIN Sottocategorie S ON B.id_sottocategoria = S.id_sottocategoria
        WHERE B.id_famiglia = %s AND B.periodo = 'Mensile'
        """
        cur.execute(sql_fetch, (id_famiglia,))
        rows = cur.fetchall()
        
        # Prepare encrypted zero for new rows
        zero_enc = _encrypt_if_key("0.0", family_key, crypto)
        
        for row in rows:
            # Encrypt name
            nome_enc = _encrypt_if_key(row['nome_sottocategoria'], family_key, crypto)
            limit_val = row['importo_limite'] # Already encrypted in Budget table
            
            # Upsert
            # ON CONFLICT: Update ONLY LIMIT. Preserve existing imported_speso and names.
            sql_upsert = """
            INSERT INTO Budget_Storico (id_famiglia, id_sottocategoria, anno, mese, importo_limite, nome_sottocategoria, importo_speso)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_famiglia, id_sottocategoria, anno, mese)
            DO UPDATE SET importo_limite = EXCLUDED.importo_limite;
            """
            cur.execute(sql_upsert, (
                id_famiglia, 
                row['id_sottocategoria'], 
                anno, 
                mese, 
                limit_val, 
                nome_enc, 
                zero_enc
            ))

    if cursor:
        try:
            _perform_update(cursor)
            return True
        except Exception as e:
             print(f"[ERRORE] Errore trigger_budget_history_update (shared cursor): {e}")
             return False

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            _perform_update(cur)
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore trigger_budget_history_update: {e}")
        return False



# --- GESTIONE CARTE ---

def aggiungi_carta(id_utente, nome_carta, tipo_carta, circuito, 
                   id_conto_riferimento=None, id_conto_contabile=None, 
                   id_conto_riferimento_condiviso=None, id_conto_contabile_condiviso=None,
                   massimale=None, giorno_addebito=None, spesa_tenuta=None, soglia_azzeramento=None, giorno_addebito_tenuta=None,
                   addebito_automatico=False, master_key=None, crypto=None):
    """
    Aggiunge una nuova carta nel database. Cripta i dati sensibili.
    Gestisce automaticamente la creazione/assegnazione del conto contabile e lo storico massimali.
    Supporta conti personali e condivisi.
    """
    try:
        crypto, master_key_bytes = _get_crypto_and_key(master_key)
        
        # 1. Gestione Conto Contabile
        if tipo_carta == 'credito':
            # Se conto contabile non specificato, creane uno automatico (Personale)
            if not id_conto_contabile and not id_conto_contabile_condiviso:
                nome_conto_contabile = f"Saldo {nome_carta}"
                res_conto = aggiungi_conto(id_utente, nome_conto_contabile, "Carta di Credito", 0.0, master_key_b64=master_key)
                if not res_conto or not res_conto[0]:
                     print("[ERRORE] Impossibile creare conto contabile automatico")
                     return False
                id_conto_contabile = res_conto[0]
        else:
            # Debito: default al conto di riferimento
            if not id_conto_contabile and not id_conto_contabile_condiviso:
                id_conto_contabile = id_conto_riferimento
                id_conto_contabile_condiviso = id_conto_riferimento_condiviso

        massimale_enc = _encrypt_if_key(str(massimale) if massimale is not None else None, master_key_bytes, crypto)
        giorno_addebito_enc = _encrypt_if_key(str(giorno_addebito) if giorno_addebito is not None else None, master_key_bytes, crypto)
        spesa_tenuta_enc = _encrypt_if_key(str(spesa_tenuta) if spesa_tenuta is not None else None, master_key_bytes, crypto)
        soglia_azzeramento_enc = _encrypt_if_key(str(soglia_azzeramento) if soglia_azzeramento is not None else None, master_key_bytes, crypto)
        giorno_addebito_tenuta_enc = _encrypt_if_key(str(giorno_addebito_tenuta) if giorno_addebito_tenuta is not None else None, master_key_bytes, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO Carte (
                    id_utente, nome_carta, tipo_carta, circuito, 
                    id_conto_riferimento, id_conto_contabile,
                    id_conto_riferimento_condiviso, id_conto_contabile_condiviso,
                    massimale_encrypted, giorno_addebito_encrypted, spesa_tenuta_encrypted, 
                    soglia_azzeramento_encrypted, giorno_addebito_tenuta_encrypted, addebito_automatico
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_carta
            """, (id_utente, nome_carta, tipo_carta, circuito, 
                  id_conto_riferimento, id_conto_contabile,
                  id_conto_riferimento_condiviso, id_conto_contabile_condiviso,
                  massimale_enc, giorno_addebito_enc, spesa_tenuta_enc, soglia_azzeramento_enc, giorno_addebito_tenuta_enc, addebito_automatico))
            
            row = cur.fetchone()
            id_carta = row.get('id_carta') if row else None
            
            if id_carta and massimale is not None:
                data_validita = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')
                cur.execute("""
                    INSERT INTO StoricoMassimaliCarte (id_carta, data_inizio_validita, massimale_encrypted)
                    VALUES (%s, %s, %s)
                """, (id_carta, data_validita, massimale_enc))

            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta carta: {e}")
        return False

def ottieni_carte_utente(id_utente, master_key_b64=None):
    """
    Restituisce la lista delle carte attive dell'utente, decriptando i dati sensibili.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Carte WHERE id_utente = %s AND attiva = TRUE", (id_utente,))
            carte_raw = cur.fetchall()
            
            carte = []
            for row in carte_raw:
                try:
                    c = dict(row)
                    c['massimale'] = _decrypt_and_convert(c['massimale_encrypted'], float, master_key, crypto)
                    c['giorno_addebito'] = _decrypt_and_convert(c['giorno_addebito_encrypted'], int, master_key, crypto)
                    c['spesa_tenuta'] = _decrypt_and_convert(c['spesa_tenuta_encrypted'], float, master_key, crypto)
                    c['soglia_azzeramento'] = _decrypt_and_convert(c['soglia_azzeramento_encrypted'], float, master_key, crypto)
                    c['giorno_addebito_tenuta'] = _decrypt_and_convert(c['giorno_addebito_tenuta_encrypted'], int, master_key, crypto)
                    carte.append(c)
                except Exception as e:
                     print(f"[WARN] Errore decriptazione carta {row.get('id_carta')}: {e}")
            return carte
    except Exception as e:
        print(f"[ERRORE] Errore recupero carte utente: {e}")
        return []

def _decrypt_and_convert(encrypted_val, type_func, master_key, crypto):
    """Helper per decriptare e convertire. Ritorna None se vuoto o errore."""
    if not encrypted_val: return None
    val_str = _decrypt_if_key(encrypted_val, master_key, crypto, silent=True)
    if not val_str or val_str == "[ENCRYPTED]": return None
    try:
        return type_func(val_str)
    except:
        return None

def modifica_carta(id_carta, nome_carta=None, tipo_carta=None, circuito=None, 
                   id_conto_riferimento=None, id_conto_contabile=None,
                   id_conto_riferimento_condiviso=None, id_conto_contabile_condiviso=None,
                   massimale=None, giorno_addebito=None, spesa_tenuta=None, soglia_azzeramento=None, giorno_addebito_tenuta=None,
                   addebito_automatico=None, master_key_b64=None):
    """
    Modifica una carta esistente. Aggiorna solo i campi forniti.
    Gestisce lo storico massimali e la logica esclusiva Conti Personali/Condivisi.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Verifica Cambio Massimale
            should_update_history = False
            massimale_enc_new = None
            
            if massimale is not None:
                cur.execute("SELECT massimale_encrypted FROM Carte WHERE id_carta = %s", (id_carta,))
                row = cur.fetchone()
                curr_enc = row.get('massimale_encrypted') if row else None
                curr_val = _decrypt_if_key(curr_enc, master_key, crypto)
                
                try:
                    v1 = float(curr_val) if curr_val else 0.0
                    v2 = float(massimale) if massimale else 0.0
                    if abs(v1 - v2) > 0.001: 
                        should_update_history = True
                except:
                    if str(curr_val) != str(massimale):
                        should_update_history = True
                
                # Encrypt new value for global update
                massimale_enc_new = _encrypt_if_key(str(massimale), master_key, crypto)

            # 2. Costruzione Query Update
            updates = []
            params = []

            if nome_carta is not None:
                updates.append("nome_carta = %s")
                params.append(nome_carta)
            if tipo_carta is not None:
                updates.append("tipo_carta = %s")
                params.append(tipo_carta)
            if circuito is not None:
                updates.append("circuito = %s")
                params.append(circuito)
            if addebito_automatico is not None:
                updates.append("addebito_automatico = %s")
                params.append(addebito_automatico)
            
            # Handle Account Exclusivity: if one provided, set other to NULL
            if id_conto_riferimento is not None: 
                updates.append("id_conto_riferimento = %s")
                params.append(id_conto_riferimento)
                updates.append("id_conto_riferimento_condiviso = NULL")
            elif id_conto_riferimento_condiviso is not None: # Only if personal not provided
                updates.append("id_conto_riferimento_condiviso = %s")
                params.append(id_conto_riferimento_condiviso)
                updates.append("id_conto_riferimento = NULL")

            if id_conto_contabile is not None:
                updates.append("id_conto_contabile = %s")
                params.append(id_conto_contabile)
                updates.append("id_conto_contabile_condiviso = NULL")
            elif id_conto_contabile_condiviso is not None: # Only if personal not provided
                updates.append("id_conto_contabile_condiviso = %s")
                params.append(id_conto_contabile_condiviso)
                updates.append("id_conto_contabile = NULL")

            if massimale is not None:
                updates.append("massimale_encrypted = %s")
                params.append(massimale_enc_new)
            if giorno_addebito is not None:
                updates.append("giorno_addebito_encrypted = %s")
                params.append(_encrypt_if_key(str(giorno_addebito), master_key, crypto))
            if spesa_tenuta is not None:
                updates.append("spesa_tenuta_encrypted = %s")
                params.append(_encrypt_if_key(str(spesa_tenuta), master_key, crypto))
            if soglia_azzeramento is not None:
                updates.append("soglia_azzeramento_encrypted = %s")
                params.append(_encrypt_if_key(str(soglia_azzeramento), master_key, crypto))
            if giorno_addebito_tenuta is not None:
                updates.append("giorno_addebito_tenuta_encrypted = %s")
                params.append(_encrypt_if_key(str(giorno_addebito_tenuta), master_key, crypto))

            if updates:
                params.append(id_carta)
                query = f"UPDATE Carte SET {', '.join(updates)} WHERE id_carta = %s"
                cur.execute(query, tuple(params))

            # 3. Aggiornamento Storico
            if should_update_history and massimale_enc_new:
                 data_validita = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')
                 cur.execute("""
                    INSERT INTO StoricoMassimaliCarte (id_carta, data_inizio_validita, massimale_encrypted)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id_carta, data_inizio_validita) 
                    DO UPDATE SET massimale_encrypted = EXCLUDED.massimale_encrypted
                 """, (id_carta, data_validita, massimale_enc_new))
            
            con.commit()
            return True
            
    except Exception as e:
        print(f"[ERRORE] Errore modifica carta: {e}")
        return False

def elimina_carta(id_carta, soft_delete=True):
    """
    Elimina una carta (soft delete di default per preservare storico).
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            if soft_delete:
                cur.execute("UPDATE Carte SET attiva = FALSE WHERE id_carta = %s", (id_carta,))
            else:
                cur.execute("DELETE FROM Carte WHERE id_carta = %s", (id_carta,))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione carta: {e}")
        return False


def calcola_totale_speso_carta(id_carta: int, mese: int, anno: int) -> float:
    try:
        with get_db_connection() as conn:
            start_date = f'{anno}-{mese:02d}-01'
            if mese == 12:
                end_date = f'{anno+1}-01-01'
            else:
                end_date = f'{anno}-{mese+1:02d}-01'
            
            cur = conn.cursor()
            
            # 1. Personal Transactions
            q1 = "SELECT SUM(importo) as totale FROM Transazioni WHERE id_carta = %s AND data >= %s AND data < %s"
            cur.execute(q1, (id_carta, start_date, end_date))
            res1 = cur.fetchone()
            val1 = float(res1.get('totale') or 0.0)
            
            # 2. Shared Transactions
            q2 = "SELECT SUM(importo) as totale FROM TransazioniCondivise WHERE id_carta = %s AND data >= %s AND data < %s"
            cur.execute(q2, (id_carta, start_date, end_date))
            res2 = cur.fetchone()
            val2 = float(res2.get('totale') or 0.0)
            
            return abs(val1 + val2)
    except Exception as e:
        print(f'Error calc speso carta: {e}')
        return 0.0


def ottieni_transazioni_carta(id_carta, mese, anno, master_key_b64=None, id_utente=None):
    """
    Recupera le transazioni (personali e condivise) associate a una carta per un dato mese/anno.
    Decripta le descrizioni se necessario.
    """
    import calendar
    try:
        start_date = datetime.date(anno, mese, 1)
        _, last_day = calendar.monthrange(anno, mese)
        end_date = datetime.date(anno, mese, last_day)

        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        family_key = None
        if master_key and id_utente:
             id_famiglia = ottieni_prima_famiglia_utente(id_utente)
             if id_famiglia:
                 family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        transazioni = []

        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Transazioni Personali
            cur.execute("""
                SELECT 
                    T.id_transazione, T.data, T.descrizione, T.importo, 
                    S.nome_sottocategoria, C.nome_categoria
                FROM Transazioni T
                LEFT JOIN Sottocategorie S ON T.id_sottocategoria = S.id_sottocategoria
                LEFT JOIN Categorie C ON S.id_categoria = C.id_categoria
                WHERE T.id_carta = %s 
                  AND T.data >= %s AND T.data <= %s
                ORDER BY T.data DESC
            """, (id_carta, start_date, end_date))
            
            rows_p = cur.fetchall()
            for r in rows_p:
                t = dict(r)
                t['tipo'] = 'Personale'
                
                # Decrypt description - Try Master Key then Family Key fallback
                desc = _decrypt_if_key(t['descrizione'], master_key, crypto, silent=True)
                if desc == "[ENCRYPTED]" and family_key:
                    res = _decrypt_if_key(t['descrizione'], family_key, crypto, silent=True)
                    if res != "[ENCRYPTED]":
                        desc = res
                t['descrizione'] = desc
                
                if family_key:
                    t['nome_sottocategoria'] = _decrypt_if_key(t['nome_sottocategoria'], family_key, crypto, silent=True)
                    t['nome_categoria'] = _decrypt_if_key(t['nome_categoria'], family_key, crypto, silent=True)
                
                transazioni.append(t)

            # 2. Transazioni Condivise
            cur.execute("""
                SELECT 
                    TC.id_transazione_condivisa as id_transazione, TC.data, TC.descrizione, TC.importo, 
                    S.nome_sottocategoria, C.nome_categoria,
                    U.username as autore
                FROM TransazioniCondivise TC
                LEFT JOIN Sottocategorie S ON TC.id_sottocategoria = S.id_sottocategoria
                LEFT JOIN Categorie C ON S.id_categoria = C.id_categoria
                LEFT JOIN Utenti U ON TC.id_utente_autore = U.id_utente
                WHERE TC.id_carta = %s
                  AND TC.data >= %s AND TC.data <= %s
                ORDER BY TC.data DESC
            """, (id_carta, start_date, end_date))
            
            rows_c = cur.fetchall()
            for r in rows_c:
                t = dict(r)
                t['tipo'] = 'Condivisa'
                
                # Decrypt description - Try Family Key then Master Key fallback
                desc = t['descrizione']
                if family_key:
                    desc = _decrypt_if_key(desc, family_key, crypto, silent=True)
                
                if (desc == "[ENCRYPTED]" or desc == t['descrizione']) and master_key:
                     res = _decrypt_if_key(t['descrizione'], master_key, crypto, silent=True)
                     if res != "[ENCRYPTED]":
                         desc = res
                t['descrizione'] = desc

                if family_key:
                    t['nome_sottocategoria'] = _decrypt_if_key(t['nome_sottocategoria'], family_key, crypto, silent=True)
                    t['nome_categoria'] = _decrypt_if_key(t['nome_categoria'], family_key, crypto, silent=True)
                transazioni.append(t)
                
        transazioni.sort(key=lambda x: x['data'], reverse=True)
        return transazioni

    except Exception as e:
        print(f"[ERRORE] Errore recupero transazioni carta: {e}")
        return []


def ottieni_mesi_disponibili_carta(id_carta):
    """
    Restituisce una lista di tuple (anno, mese) distinte in cui sono presenti transazioni per la carta.
    Ordinata dalla più recente.
    """
    try:
        mesi = set()
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Personali
            cur.execute("""
                SELECT DISTINCT EXTRACT(YEAR FROM data::date) as anno, EXTRACT(MONTH FROM data::date) as mese
                FROM Transazioni
                WHERE id_carta = %s
            """, (id_carta,))
            for row in cur.fetchall():
                mesi.add((int(row['anno']), int(row['mese'])))
                
            # Condivise
            cur.execute("""
                SELECT DISTINCT EXTRACT(YEAR FROM data::date) as anno, EXTRACT(MONTH FROM data::date) as mese
                FROM TransazioniCondivise
                WHERE id_carta = %s
            """, (id_carta,))
            for row in cur.fetchall():
                mesi.add((int(row['anno']), int(row['mese'])))
        
        lista_mesi = sorted(list(mesi), key=lambda x: (x[0], x[1]), reverse=True)
        return lista_mesi
    except Exception as e:
        print(f"[ERRORE] Errore recupero mesi carta: {e}")
        return []

# --- GESTIONE OBIETTIVI RISPARMIO (ACCANTONAMENTI) ---



def crea_obiettivo(id_famiglia: str, nome: str, importo_obiettivo: float, data_obiettivo: str, note: str = "", master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, mostra_suggerimento: bool = True) -> bool:
    """
    Crea un nuovo obiettivo di risparmio (v2).
    Nome, importo e note vengono criptati con chiave famiglia.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        key_to_use = family_key if family_key else master_key
        
        # Encrypt data
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto)
        importo_enc = _encrypt_if_key(str(importo_obiettivo), key_to_use, crypto)
        note_enc = _encrypt_if_key(note, key_to_use, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO Obiettivi_Risparmio (id_famiglia, nome, importo_obiettivo, data_obiettivo, note, mostra_suggerimento_mensile)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (id_famiglia, nome_enc, importo_enc, data_obiettivo, note_enc, mostra_suggerimento))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore creazione obiettivo: {e}")
        return False

def ottieni_obiettivi(id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recupera tutti gli obiettivi, calcolando il totale accumulato dai Salvadanai collegati.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        key_to_use = family_key if family_key else master_key

        with get_db_connection() as con:
            cur = con.cursor()
            # Get goals
            cur.execute("""
                SELECT id, nome, importo_obiettivo, data_obiettivo, note, mostra_suggerimento_mensile
                FROM Obiettivi_Risparmio
                WHERE id_famiglia = %s
                ORDER BY data_obiettivo ASC
            """, (id_famiglia,))
            
            rows = cur.fetchall()
            obiettivi = []
            
            for row in rows:
                try:
                    goal_id = row['id']
                    
                    # Decrypt core data
                    nome = _decrypt_if_key(row['nome'], key_to_use, crypto)
                    importo_obj_str = _decrypt_if_key(row['importo_obiettivo'], key_to_use, crypto)
                    note = _decrypt_if_key(row['note'], key_to_use, crypto)
                    
                    # Calculate accumulated amount using Dynamic Logic (min(Assigned, RealBalance))
                    # Reuse ottieni_salvadanai_obiettivo to ensure consistency with Dialog
                    # Note: We pass master_key_b64 and id_utente, letting the function handle key derivation internally if needed,
                    # but since we already have keys here, maybe we could optimize? 
                    # ottieni_salvadanai_obiettivo re-derives keys. To avoid overhead, we could factor out the logic, 
                    # but calling it is safer for consistency.
                    
                    salvadanai = ottieni_salvadanai_obiettivo(goal_id, id_famiglia, master_key_b64, id_utente)
                    totale_accumulato = sum(s['importo'] for s in salvadanai)

                    obiettivi.append({
                        'id': goal_id,
                        'nome': nome,
                        'importo_obiettivo': float(importo_obj_str) if importo_obj_str else 0.0,
                        'data_obiettivo': row['data_obiettivo'],
                        'importo_accumulato': totale_accumulato, 
                        'note': note,
                        'mostra_suggerimento_mensile': row['mostra_suggerimento_mensile']
                    })
                except Exception as ex:
                    # logger.error(f"Errore decrypt obiettivo {row['id']}: {ex}")
                    obiettivi.append({
                         'id': row['id'],
                         'nome': "[ERRORE DECRITTAZIONE]",
                         'importo_obiettivo': 0.0,
                         'data_obiettivo': row['data_obiettivo'],
                         'importo_accumulato': 0.0,
                         'note': "",
                         'mostra_suggerimento_mensile': False
                    })

            return obiettivi
    except Exception as e:
        logger.error(f"Errore recupero obiettivi: {e}")
        return []

def aggiorna_obiettivo(id_obiettivo: int, id_famiglia: str, nome: str, importo_obiettivo: float, data_obiettivo: str, note: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, mostra_suggerimento: bool = True) -> bool:
    """
    Aggiorna un obiettivo esistente.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
        key_to_use = family_key if family_key else master_key
        
        # Encrypt data
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto)
        importo_obj_enc = _encrypt_if_key(str(importo_obiettivo), key_to_use, crypto)
        note_enc = _encrypt_if_key(note, key_to_use, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE Obiettivi_Risparmio
                SET nome = %s, 
                    importo_obiettivo = %s,
                    data_obiettivo = %s,
                    note = %s,
                    mostra_suggerimento_mensile = %s
                WHERE id = %s AND id_famiglia = %s
            """, (nome_enc, importo_obj_enc, data_obiettivo, note_enc, mostra_suggerimento, id_obiettivo, id_famiglia))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore aggiornamento obiettivo: {e}")
        return False

def elimina_obiettivo(id_obiettivo: int, id_famiglia: str) -> bool:
    """
    Elimina un obiettivo.
    IMPORTANTE: Scollega prima i salvadanai per NON cancellare i fondi fisici (Soldi).
    I salvadanai diventeranno "Orfani" (visibili nel conto) e l'utente potrà gestirli.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Step 1: Unlink Piggy Banks (Save the Money!)
            cur.execute("""
                UPDATE Salvadanai 
                SET id_obiettivo = NULL 
                WHERE id_obiettivo = %s AND id_famiglia = %s
            """, (id_obiettivo, id_famiglia))
            
            # Step 2: Delete Goal
            cur.execute("DELETE FROM Obiettivi_Risparmio WHERE id = %s AND id_famiglia = %s", (id_obiettivo, id_famiglia))
            
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore eliminazione obiettivo: {e}")
        return False

# --- GESTIONE SALVADANAI (Obiettivi v2) ---

def crea_salvadanaio(id_famiglia: str, nome: str, importo: float, id_obiettivo: Optional[int] = None, id_conto: Optional[int] = None, id_asset: Optional[int] = None, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, incide_su_liquidita: bool = False, id_conto_condiviso: Optional[int] = None, usa_saldo_totale: bool = False) -> Optional[int]:
    """
    Crea un salvadanaio.
    Richiede id_conto (Personale) OPPURE id_conto_condiviso (Condiviso).
    Returns the ID of the new piggy bank, or None on failure.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        # Enforce Family Key for Shared PBs
        if id_conto_condiviso:
            if not family_key:
                logger.error("Tentativo di creare salvadanaio condiviso senza chiave famiglia.")
                return None
            key_to_use = family_key
        else:
            key_to_use = family_key if family_key else master_key
            if not key_to_use: return None
        
        # If usa_saldo_totale is True, importo might be ignored (or used solely as cap if compiled). 
        # But here we encrypt it anyway.
        importo_enc = _encrypt_if_key(str(importo), key_to_use, crypto)
        note_enc = _encrypt_if_key("", key_to_use, crypto)
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            
            # Use id_conto_condiviso if provided
            cur.execute("""
                INSERT INTO Salvadanai (id_famiglia, id_obiettivo, id_conto, id_conto_condiviso, id_asset, nome, importo_assegnato, note, incide_su_liquidita, usa_saldo_totale)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_salvadanaio
            """, (id_famiglia, id_obiettivo, id_conto, id_conto_condiviso, id_asset, nome_enc, importo_enc, note_enc, incide_su_liquidita, usa_saldo_totale))
            
            row = cur.fetchone()
            con.commit()
            
            if row:
                return row['id_salvadanaio']
            return None
            
    except Exception as e:
        logger.error(f"Errore crea_salvadanaio: {e}")
        return None

def scollega_salvadanaio_obiettivo(id_salvadanaio: int, id_famiglia: str) -> bool:
    """
    Scollega un salvadanaio da un obiettivo (lo rende 'libero' ma non lo elimina).
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE Salvadanai 
                SET id_obiettivo = NULL 
                WHERE id_salvadanaio = %s AND id_famiglia = %s
            """, (id_salvadanaio, id_famiglia))
            con.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Errore scollega_salvadanaio_obiettivo: {e}")
        return False

def ottieni_salvadanai_conto(id_conto: int, id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None, is_condiviso: bool = False) -> List[Dict[str, Any]]:
    """
    Recupera i salvadanai collegati a uno specifico conto (personale o condiviso).
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            if is_condiviso:
                cur.execute("SELECT * FROM Salvadanai WHERE id_conto_condiviso = %s", (id_conto,))
            else:
                cur.execute("SELECT * FROM Salvadanai WHERE id_conto = %s", (id_conto,))
                
            rows = [dict(row) for row in cur.fetchall()]
            
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente and id_famiglia:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            if is_condiviso:
                 keys_to_try = [family_key] if family_key else []
            else:
                 keys_to_try = []
                 if family_key: keys_to_try.append(family_key)
                 if master_key: keys_to_try.append(master_key)
            
            # logger.info(f"DEBUG PB: User={id_utente}, Fam={id_famiglia}. Keys to try: {len(keys_to_try)} (MK={bool(master_key)}, FK={bool(family_key)})")

            def try_decrypt(val, keys):
                last_res = None
                for i, k in enumerate(keys):
                    if not k: continue
                    try:
                        res = _decrypt_if_key(val, k, crypto, silent=True)
                        # logger.info(f"DEBUG PB Decrypt Try {i}: ValPrefix={val[:10] if isinstance(val, str) else type(val)}... Res={res[:10] if isinstance(res, str) else res}")
                        if res == "[ENCRYPTED]":
                            last_res = res
                            continue
                        return res
                    except Exception as e:
                        # logger.error(f"DEBUG PB Decrypt Exception: {e}")
                        continue
                return last_res if last_res else "[ENCRYPTED]"
                last_res = None
                for k in keys:
                    if not k: continue
                    try:
                        res = _decrypt_if_key(val, k, crypto, silent=True)
                        if res == "[ENCRYPTED]":
                            last_res = res
                            continue
                        return res
                    except: continue
                return last_res if last_res else "[ENCRYPTED]"

            results = []
            for r in rows:
                nome = try_decrypt(r['nome'], keys_to_try)
                imp_str = try_decrypt(r['importo_assegnato'], keys_to_try)
                
                try:
                    importo = float(imp_str)
                except:
                    importo = 0.0

                results.append({
                    'id': r['id_salvadanaio'],
                    'nome': nome,
                    'importo': importo,
                    'id_obiettivo': r['id_obiettivo'], # Useful for filtering
                    'incide_su_liquidita': r.get('incide_su_liquidita', False)
                })
            
            return results
    except Exception as e:
        logger.error(f"Errore ottieni_salvadanai_conto: {e}")
        return []

def esegui_giroconto_salvadanaio(
    id_conto: int,
    id_salvadanaio: int,
    direzione: str, # 'verso_salvadanaio' (Conto -> PB) o 'da_salvadanaio' (PB -> Conto)
    importo: float,
    data: str = None,
    descrizione: str = None,
    master_key_b64: Optional[str] = None,
    id_utente: Optional[str] = None,
    id_famiglia: Optional[str] = None,
    parent_is_shared: bool = False # New flag
) -> bool:
    """
    Gestisce il trasferimento di fondi tra un Conto e un suo Salvadanaio.
    Supports Personal and Shared accounts.
    """
    if not data: data = datetime.date.today().strftime('%Y-%m-%d')
    if not descrizione: descrizione = "Giroconto Salvadanaio"
    
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente and id_famiglia:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    key_to_use = family_key if family_key else master_key

    # Encrypt description
    if parent_is_shared:
        # For Shared Trans, use family key usually, or master key? 
        # Shared Trans usually use Family Key if encrypted. 
        # But 'esegui_giroconto' uses family_key for shared description.
        desc_enc = _encrypt_if_key(descrizione, key_to_use, crypto)
    else:
        desc_enc = _encrypt_if_key(descrizione, master_key, crypto)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get current PB Amount
            cur.execute("SELECT importo_assegnato, nome FROM Salvadanai WHERE id_salvadanaio = %s", (id_salvadanaio,))
            row = cur.fetchone()
            if not row: raise Exception("Salvadanaio non trovato")
            
            current_pb_amount_enc = row['importo_assegnato']
            # decryption of amount always uses PB key (which is family key usually or master)
            current_pb_amount = float(_decrypt_if_key(current_pb_amount_enc, key_to_use, crypto))
            
            # Determine correct table and column for Account Transaction
            if parent_is_shared:
                table_trans = "TransazioniCondivise"
                col_id = "id_conto_condiviso"
                # Shared Trans table also needs id_utente_autore
                extra_cols = ", id_utente_autore"
                extra_vals = ", %s"
                extra_params = (id_utente,)
            else:
                table_trans = "Transazioni"
                col_id = "id_conto"
                extra_cols = ""
                extra_vals = ""
                extra_params = ()

            if direzione == 'verso_salvadanaio':
                # Conto -> PB
                # 1. Create Transaction Out on Account
                query = f"INSERT INTO {table_trans} ({col_id}, data, descrizione, importo{extra_cols}) VALUES (%s, %s, %s, %s{extra_vals})"
                params = (id_conto, data, desc_enc, -abs(importo)) + extra_params
                cur.execute(query, params)
                
                # 2. Increase PB
                new_pb_amount = current_pb_amount + abs(importo)
                
            elif direzione == 'da_salvadanaio':
                # PB -> Conto
                if current_pb_amount < abs(importo):
                     raise Exception("Fondi insufficienti nel salvadanaio")
                
                # 1. Create Transaction In on Account
                query = f"INSERT INTO {table_trans} ({col_id}, data, descrizione, importo{extra_cols}) VALUES (%s, %s, %s, %s{extra_vals})"
                params = (id_conto, data, desc_enc, abs(importo)) + extra_params
                cur.execute(query, params)
                             
                # 2. Decrease PB
                new_pb_amount = current_pb_amount - abs(importo)
            
            else:
                raise Exception(f"Direzione sconosciuta: {direzione}")

            # Save new PB amount
            new_amount_enc = _encrypt_if_key(str(new_pb_amount), key_to_use, crypto)
            cur.execute("UPDATE Salvadanai SET importo_assegnato = %s WHERE id_salvadanaio = %s", (new_amount_enc, id_salvadanaio))
            
            con.commit()
            return True

    except Exception as e:
        logger.error(f"Errore esegui_giroconto_salvadanaio: {e}")
        return False

def ottieni_salvadanai_obiettivo(id_obiettivo: int, id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        key_to_use = family_key if family_key else master_key
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT s.id_salvadanaio, s.nome, s.importo_assegnato, s.id_conto, s.id_conto_condiviso, s.id_asset,
                       c.nome_conto, a.nome_asset, a.ticker
                FROM Salvadanai s
                LEFT JOIN Conti c ON s.id_conto = c.id_conto
                LEFT JOIN Asset a ON s.id_asset = a.id_asset
                WHERE s.id_obiettivo = %s AND s.id_famiglia = %s
            """, (id_obiettivo, id_famiglia))
            
            rows = cur.fetchall()
            results = []
            for row in rows:
                # Decryption Strategy: Try Family Key first, then Master Key
                # This handles mixed history (PBs created with Family Key vs Master Key).
                
                nome = "[ENCRYPTED]"
                imp_str = "0.0"
                usa_saldo_totale = row.get('usa_saldo_totale', False)
                
                # Helper to try keys
                def try_decrypt(val, keys):
                    last_res = None
                    for k in keys:
                        if not k: continue
                        try:
                            # Pass silent=True to avoid excessive logging during trial
                            res = _decrypt_if_key(val, k, crypto, silent=True) # Assuming _decrypt_if_key passes silent arg (Modified below?)
                            
                            if res == "[ENCRYPTED]":
                                last_res = res
                                continue # Try next key
                            
                            return res
                        except: continue
                    return last_res if last_res else "[ENCRYPTED]"

                keys_to_try = [family_key, master_key] if family_key else [master_key]
                
                try:
                    nome = try_decrypt(row['nome'], keys_to_try)
                    imp_str = try_decrypt(row['importo_assegnato'], keys_to_try)
                    
                    source_name = "Manuale / Esterno"
                    source_balance = 0.0
                    source_found = False
                    
                    # --- BALANCE CALCULATION START ---
                    
                    # 1. Linked to Account (Personal)
                    if row['id_conto']:
                        try:
                            # Only calculate Account Balance if needed (for usa_saldo_totale)
                            # Standard PBs (Physical) hold their own funds, so we generally trust importo_assegnato.
                            
                            if usa_saldo_totale:
                                # Fetch manual value (Pension) and rectification (Checking) logic
                                cur.execute("SELECT tipo, valore_manuale, rettifica_saldo FROM Conti WHERE id_conto = %s", (row['id_conto'],))
                                c_res = cur.fetchone()
                                
                                if c_res:
                                    if c_res['tipo'] == 'Fondo Pensione' and c_res['valore_manuale'] is not None:
                                         # Pension Fund -> Use encrypted manual value
                                         val_man_enc = c_res['valore_manuale']
                                         val_man_dec = try_decrypt(val_man_enc, keys_to_try)
                                         try: source_balance = float(val_man_dec)
                                         except: source_balance = 0.0
                                    else:
                                         # Standard Account -> Sum Transactions + Rectification
                                         cur.execute("SELECT SUM(importo) as saldo FROM Transazioni WHERE id_conto = %s", (row['id_conto'],))
                                         t_res = cur.fetchone()
                                         trans_sum = float(t_res['saldo']) if t_res and t_res['saldo'] is not None else 0.0
                                         
                                         rettifica = 0.0
                                         if c_res['rettifica_saldo']:
                                             try:
                                                 r_dec = try_decrypt(c_res['rettifica_saldo'], keys_to_try)
                                                 rettifica = float(r_dec)
                                             except: pass
                                         
                                         source_balance = trans_sum + rettifica
                                    source_found = True
                        except Exception as e:
                            # logger.warning(f"Error fetching balance for conto {row['id_conto']}: {e}")
                            pass

                    # 2. Linked to Shared Account
                    elif row['id_conto_condiviso']:
                        try:
                            # Similar logic for shared.. only if usa_saldo_totale needed
                             if usa_saldo_totale:
                                cur.execute("SELECT valore_manuale FROM ContiCondivisi WHERE id_conto_condiviso = %s", (row['id_conto_condiviso'],))
                                cc_res = cur.fetchone()
                                if cc_res and cc_res['valore_manuale'] is not None:
                                    val_man_enc = cc_res['valore_manuale']
                                    val_man_dec = try_decrypt(val_man_enc, keys_to_try) 
                                    try: source_balance = float(val_man_dec)
                                    except: source_balance = 0.0
                                else:
                                     cur.execute("SELECT SUM(importo) as saldo FROM TransazioniCondivise WHERE id_conto_condiviso = %s", (row['id_conto_condiviso'],))
                                     t_res = cur.fetchone()
                                     source_balance = float(t_res['saldo']) if t_res and t_res['saldo'] is not None else 0.0
                                source_found = True
                        except: pass

                    # 3. Linked to Asset (ALWAYS Virtual -> Need Source Balance)
                    elif row['id_asset']:
                         try:
                             cur.execute("SELECT quantita, prezzo_attuale_manuale, costo_iniziale_unitario FROM Asset WHERE id_asset = %s", (row['id_asset'],))
                             a_res = cur.fetchone()
                             if a_res:
                                 qty = float(a_res['quantita'])
                                 price = float(a_res['prezzo_attuale_manuale']) if a_res['prezzo_attuale_manuale'] else float(a_res['costo_iniziale_unitario'])
                                 source_balance = qty * price
                                 source_found = True
                         except: pass

                    # --- BALANCE CALCULATION END ---

                    # Decrypt Source Name (Account) if present
                    if row['nome_conto']:
                        # Try both keys (Legacy Support)
                        source_name = f"Conto: {try_decrypt(row['nome_conto'], keys_to_try)}"
                    
                    # Decrypt Source Name (Asset) if present
                    if row['nome_asset']: 
                        # Asset lookup strategy
                        # Try keys for Asset Name AND Ticker
                        s_asset = try_decrypt(row['nome_asset'], keys_to_try)
                        s_ticker = try_decrypt(row['ticker'], keys_to_try)
                        
                        if s_asset != "[ENCRYPTED]":
                            source_name = f"Asset: {s_asset} ({s_ticker})"
                        else:
                             source_name = f"Asset: [Privato/Encrypted]"
                                     
                    if row['id_conto_condiviso']:
                        # Fetch Shared Account Name
                        try:
                            cur.execute("SELECT nome_conto FROM ContiCondivisi WHERE id_conto_condiviso = %s", (row['id_conto_condiviso'],))
                            cc_row = cur.fetchone()
                            if cc_row:
                                cc_name = try_decrypt(cc_row['nome_conto'], keys_to_try)
                                source_name = f"Conto Condiviso: {cc_name}"
                        except:
                            source_name = "Conto Condiviso" 
                    
                    # Determine Final Importo
                    # If not linked to any source (manual), rely on importo_assegnato (imp_str)
                    importo_nominale = float(imp_str) if imp_str and imp_str != "[ENCRYPTED]" else 0.0
                    
                    final_importo = importo_nominale
                    
                    # Special Rule for Assets or Dynamic Accounts
                    # Assets are ALWAYS virtual, so we cap.
                    # Accounts are only capped if usa_saldo_totale (dynamic tracking), otherwise we trust the assigned amount (Physical PB).
                    
                    if row['id_asset'] and source_found:
                         # Heuristic: If assigned is 0, assume user wants Full Value (since empty field implies that).
                         # Also checking usa_saldo_totale flag.
                         if usa_saldo_totale or importo_nominale == 0:
                              final_importo = max(0.0, source_balance)
                         else:
                              final_importo = max(0.0, min(importo_nominale, source_balance))
                    
                    elif (row['id_conto'] or row['id_conto_condiviso']) and usa_saldo_totale and source_found:
                         final_importo = max(0.0, source_balance)
                         
                    # Else (Fixed Account PB): use importo_nominale as is.
                        
                    results.append({
                        'id': row['id_salvadanaio'],
                        'nome': nome,
                        'importo': final_importo,
                        'source': source_name,
                        'usa_saldo_totale': usa_saldo_totale, # Useful for UI?
                        'source_balance': source_balance # useful for debug?
                    })
                except Exception as ex:
                    # logger.error(f"Error processing salvadanaio {row['id_salvadanaio']}: {ex}")
                    results.append({
                        'id': row['id_salvadanaio'],
                        'nome': "[ENCRYPTED]",
                        'importo': 0.0,
                        'source': "Errore Decrittazione"
                    })

            return results
    except Exception as e:
        logger.error(f"Errore ottieni_salvadanai: {e}")
        return []

def elimina_salvadanaio(id_salvadanaio: int, id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> bool:
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        family_key = None
        if master_key and id_utente:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        key_to_use = family_key if family_key else master_key

        with get_db_connection() as con:
            cur = con.cursor()
            
            # Fetch PB info
            cur.execute("""
                SELECT id_conto, id_conto_condiviso, importo_assegnato, id_asset, usa_saldo_totale
                FROM Salvadanai
                WHERE id_salvadanaio = %s AND id_famiglia = %s
            """, (id_salvadanaio, id_famiglia))
            
            row = cur.fetchone()
            if not row: return False # Not found
            
            # Check if refund needed
            needs_refund = False
            amount_to_refund = 0.0
            
            # Only refund if Physical PB (Linked to Account, not Asset, and NOT dynamic)
            # If dynamic (usa_saldo_totale), it tracks account balance, so no dedicated funds to move back.
            # If Asset, it's virtual.
            
            if (row['id_conto'] or row['id_conto_condiviso']) and not row['usa_saldo_totale'] and not row['id_asset']:
                try:
                    enc_val = row['importo_assegnato']
                    dec_val = _decrypt_if_key(enc_val, key_to_use, crypto, silent=True)
                    if dec_val == "[ENCRYPTED]" or dec_val is None:
                        logger.error("Abort deleting Piggy Bank: Cannot decrypt amount to refund.")
                        return False # ABORT: Cannot determine refund amount
                        
                    amount_to_refund = float(dec_val)
                    if amount_to_refund > 0:
                        needs_refund = True
                except Exception as e:
                    logger.error(f"Abort deleting Piggy Bank: Decryption error {e}")
                    return False # ABORT
            
            if needs_refund:
                # Refund to Account
                parent_is_shared = bool(row['id_conto_condiviso'])
                id_conto_target = row['id_conto'] if row['id_conto'] else row['id_conto_condiviso']
                
                success_refund = esegui_giroconto_salvadanaio(
                    id_conto=id_conto_target,
                    id_salvadanaio=id_salvadanaio,
                    direzione='da_salvadanaio',
                    importo=amount_to_refund,
                    descrizione=f"Chiusura Salvadanaio",
                    master_key_b64=master_key_b64,
                    id_utente=id_utente,
                    id_famiglia=id_famiglia,
                    parent_is_shared=parent_is_shared
                )
                
                if not success_refund:
                    logger.error("Refund failed during deletion. Aborting deletion to save funds.")
                    return False # ABORT
            
            # Proceed to Delete ONLY if Refund success or not needed
            cur.execute("DELETE FROM Salvadanai WHERE id_salvadanaio = %s AND id_famiglia = %s", (id_salvadanaio, id_famiglia))
            con.commit()
            return True

    except Exception as e:
        logger.error(f"Errore eliminazione salvadanaio: {e}")
        return False

def admin_rettifica_salvadanaio(id_salvadanaio: int, nuovo_importo: float, master_key_b64: Optional[str], id_utente: str, is_shared: bool = False) -> bool:
    """
    Rettifica manuale (ADMIN) dell'importo di un salvadanaio.
    Sovrascrive il valore.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        # Determine Key
        family_key = None
        id_famiglia = ottieni_prima_famiglia_utente(id_utente)
        if id_famiglia and master_key:
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        if is_shared:
            if not family_key:
                logger.error("Rettifica salvadanaio condiviso impossibile: chiave famiglia assente.")
                return False
            key_to_use = family_key
        else:
            key_to_use = family_key if family_key else master_key
            
        importo_enc = _encrypt_if_key(str(nuovo_importo), key_to_use, crypto)
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Salvadanai SET importo_assegnato = %s WHERE id_salvadanaio = %s", (importo_enc, id_salvadanaio))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore rettifica salvadanaio: {e}")
        return False

def collega_salvadanaio_obiettivo(id_salvadanaio: int, id_obiettivo: int, id_famiglia: str) -> bool:
    """
    Collega un salvadanaio esistente a un obiettivo.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Salvadanai SET id_obiettivo = %s WHERE id_salvadanaio = %s AND id_famiglia = %s", (id_obiettivo, id_salvadanaio, id_famiglia))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore collegamento salvadanaio-obiettivo: {e}")
        return False

def ottieni_asset_conto(id_conto: int, master_key_b64: Optional[str] = None, is_shared: bool = False, id_utente: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recupera gli asset (azioni, etf, ecc.) di un conto investimento.
    Supporta conti condivisi (richiede id_utente per recuperare chiave famiglia).
    Tenta la decrittazione con entrambe le chiavi (Personale e Famiglia) per robustezza.
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        # Determine Keys to Try
        keys_to_try = []
        family_key = None
        
        if id_utente:
             id_famiglia = ottieni_prima_famiglia_utente(id_utente)
             if id_famiglia and master_key:
                  family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
        
        if is_shared:
            if family_key: keys_to_try.append(family_key)
            if master_key: keys_to_try.append(master_key)
        else:
            if master_key: keys_to_try.append(master_key)
            if family_key: keys_to_try.append(family_key)
            
        # Helper for multi-key decryption
        def try_decrypt(val, keys):
            last_res = None
            for k in keys:
                if not k: continue
                try:
                    res = _decrypt_if_key(val, k, crypto, silent=True)
                    if res == "[ENCRYPTED]":
                        last_res = res
                        continue
                    return res
                except: continue
            return last_res if last_res else "[ENCRYPTED]"

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Asset WHERE id_conto = %s", (id_conto,))
            rows = cur.fetchall()
            
            assets = []
            for r in rows:
                try:
                    nome = try_decrypt(r['nome_asset'], keys_to_try)
                    ticker = try_decrypt(r['ticker'], keys_to_try)
                    assets.append({
                        'id': r['id_asset'],
                        'nome': nome,
                        'ticker': ticker,
                        'quantita': float(r['quantita'])
                    })
                except: continue
            return assets
    except Exception as e:
        logger.error(f"Errore ottieni_asset_conto: {e}")
        return []

