from db.supabase_manager import get_db_connection
import hashlib
import datetime
import os
import sys
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse as parse_date
import mimetypes
import secrets
import string
import base64
from utils.crypto_manager import CryptoManager

# --- BLOCCO DI CODICE PER CORREGGERE IL PERCORSO ---
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
# --- FINE BLOCCO DI CODICE ---

from db.crea_database import setup_database

# Load Server Key
SERVER_SECRET_KEY = os.getenv("SERVER_SECRET_KEY")
if not SERVER_SECRET_KEY:
    print("[WARNING] SERVER_SECRET_KEY not found in .env. Password recovery via email will not work for new encrypted data.")

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



# --- Helper Functions for Encryption ---
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
            print(f"[ERRORE] Errore decodifica master_key: {e}")
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
        print(f"[ERRORE] Errore durante la lettura della versione del DB: {repr(e)}")
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
        print(f"[ERRORE] Errore in get_user_count: {e}")
        return -1


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def valida_iban_semplice(iban):
    if not iban:
        return True
    iban_pulito = iban.strip().upper()
    return iban_pulito.startswith("IT") and len(iban_pulito) == 27 and iban_pulito[2:].isalnum()



# --- Funzioni Configurazioni ---
def get_configurazione(chiave, id_famiglia=None, master_key_b64=None, id_utente=None):
    """
    Recupera il valore di una configurazione.
    Se id_famiglia è None, cerca una configurazione globale.
    Se id_famiglia è specificato, cerca una configurazione per quella famiglia.
    I valori SMTP vengono decriptati con family_key.
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
                if id_famiglia and master_key_b64 and id_utente:
                     # Decrypt Family Config
                    crypto, master_key = _get_crypto_and_key(master_key_b64)
                    if master_key:
                        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
                        if family_key:
                            valore = _decrypt_if_key(valore, family_key, crypto)
                        else:
                            print(f"[DEBUG] get_configurazione - family_key non trovata per id_famiglia={id_famiglia}, id_utente={id_utente}")
                    else:
                        print("[DEBUG] get_configurazione - master_key non valida")
                elif id_famiglia is None:
                    # Decrypt Global Config (System Key)
                    try:
                        decrypted = decrypt_system_data(valore)
                        if decrypted:
                            valore = decrypted
                    except Exception as e:
                        print(f"[WARN] Failed to system-decrypt {chiave}: {e}")
            
            return valore
    except Exception as e:
        print(f"[ERRORE] Errore recupero configurazione {chiave}: {e}")
        return None

def set_configurazione(chiave, valore, id_famiglia=None, master_key_b64=None, id_utente=None):
    """
    Imposta o aggiorna una configurazione.
    Se id_famiglia è None, imposta una configurazione globale.
    I valori SMTP vengono criptati con family_key.
    """
    try:
        # Encrypt sensitive config values
        encrypted_valore = valore
        sensitive_keys = ['smtp_server', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from_email']
        
        if chiave in sensitive_keys:
            if id_famiglia and master_key_b64 and id_utente:
                # Encrypt with Family Key (User Data)
                crypto, master_key = _get_crypto_and_key(master_key_b64)
                if master_key:
                    family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
                    if family_key:
                        encrypted_valore = _encrypt_if_key(valore, family_key, crypto)
            elif id_famiglia is None and SERVER_SECRET_KEY:
                # Encrypt with System Key (Global Config accessible by Server)
                # Used for SMTP credentials needed for Password Reset
                try:
                    encrypted_valore = encrypt_system_data(valore)
                except Exception as e:
                    print(f"[WARN] Failed to system-encrypt {chiave}: {e}")
        
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
        print(f"[ERRORE] Errore salvataggio configurazione {chiave}: {e}")
        return False

def get_smtp_config(id_famiglia=None, master_key_b64=None, id_utente=None):
    """Recupera la configurazione SMTP completa. Tutti i valori vengono decriptati automaticamente."""
    print(f"[DEBUG] get_smtp_config called with id_famiglia={id_famiglia}, id_utente={id_utente}, master_key_present={bool(master_key_b64)}")
    return {
        'server': get_configurazione('smtp_server', id_famiglia, master_key_b64, id_utente),
        'port': get_configurazione('smtp_port', id_famiglia, master_key_b64, id_utente),
        'user': get_configurazione('smtp_user', id_famiglia, master_key_b64, id_utente),
        'password': get_configurazione('smtp_password', id_famiglia, master_key_b64, id_utente),
        'provider': get_configurazione('smtp_provider', id_famiglia)  # provider is not sensitive
    }

def save_smtp_config(settings, id_famiglia=None, master_key_b64=None, id_utente=None):
    """Salva la configurazione SMTP. Tutti i valori sensibili vengono criptati automaticamente."""
    try:
        set_configurazione('smtp_server', settings.get('server'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_port', settings.get('port'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_user', settings.get('user'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_password', settings.get('password'), id_famiglia, master_key_b64, id_utente)
        set_configurazione('smtp_provider', settings.get('provider'), id_famiglia)  # provider is not sensitive
        return True
    except Exception as e:
        print(f"[ERRORE] Errore salvataggio SMTP config: {e}")
        return False


# --- Funzioni Gestione Budget Famiglia ---

def get_impostazioni_budget_famiglia(id_famiglia):
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

def set_impostazioni_budget_famiglia(id_famiglia, entrate_mensili, risparmio_tipo, risparmio_valore):
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
        print(f"[ERRORE] Errore salvataggio impostazioni budget: {e}")
        return False

def calcola_entrate_mensili_famiglia(id_famiglia, anno, mese, master_key_b64=None, id_utente=None):
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
        print(f"[ERRORE] Errore calcolo entrate mensili: {e}")
        return 0.0

def ottieni_totale_budget_allocato(id_famiglia, master_key_b64=None, id_utente=None):
    """
    Ritorna il totale dei budget assegnati alle sottocategorie.
    """
    try:
        budget_list = ottieni_budget_famiglia(id_famiglia, master_key_b64, id_utente)
        return sum(b.get('importo_limite', 0) for b in budget_list)
    except Exception as e:
        print(f"[ERRORE] Errore calcolo totale budget allocato: {e}")
        return 0.0

def salva_impostazioni_budget_storico(id_famiglia, anno, mese, entrate_mensili, risparmio_tipo, risparmio_valore):
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
        print(f"[ERRORE] Errore salvataggio storico impostazioni budget: {e}")
        return False

def ottieni_impostazioni_budget_storico(id_famiglia, anno, mese):
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

def ottieni_dati_analisi_mensile(id_famiglia, anno, mese, master_key_b64, id_utente):
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
            cur.execute("""
                SELECT T.id_sottocategoria, SUM(T.importo) as totale
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND T.data BETWEEN %s AND %s
                  AND T.importo < 0
                GROUP BY T.id_sottocategoria
            """, (id_famiglia, data_inizio, data_fine))
            spese_personali = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}

            # Query UNICA per spese condivise raggruppate per sottocategoria
            cur.execute("""
                SELECT TC.id_sottocategoria, SUM(TC.importo) as totale
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND TC.data BETWEEN %s AND %s
                  AND TC.importo < 0
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
        print(f"[ERRORE] ottieni_dati_analisi_mensile: {e}")
        return None


def ottieni_dati_analisi_annuale(id_famiglia, anno, master_key_b64, id_utente, include_prev_year=True):
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
            # Personali
            cur.execute("""
                SELECT T.id_sottocategoria, SUM(T.importo) as totale
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND T.data BETWEEN %s AND %s
                  AND T.importo < 0
                GROUP BY T.id_sottocategoria
            """, (id_famiglia, data_inizio_anno, data_fine_anno))
            spese_personali = {row['id_sottocategoria']: abs(row['totale']) for row in cur.fetchall()}
            
            # Condivise
            cur.execute("""
                SELECT TC.id_sottocategoria, SUM(TC.importo) as totale
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND TC.data BETWEEN %s AND %s
                  AND TC.importo < 0
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
            
            budget_totale_periodo += budget_mensile_corrente 

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

def esporta_dati_famiglia(id_famiglia, id_utente, master_key_b64):
    """
    Esporta family_key e configurazioni base per backup.
    Solo admin può esportare questi dati.
    Ritorna un dizionario con tutti i dati oppure None in caso di errore.
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


def ottieni_utenti_senza_famiglia():
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


def verifica_login(login_identifier, password):
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



def crea_utente_invitato(email, ruolo, id_famiglia, id_admin=None, master_key_b64=None):
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
                INSERT INTO Utenti (username, email, password_hash, nome, cognome, forza_cambio_password, salt, encrypted_master_key, username_bindex, email_bindex, username_enc, email_enc, nome_enc_server, cognome_enc_server)
                VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_utente
            """, (temp_username, email, password_hash, "Nuovo", "Utente",
                  base64.urlsafe_b64encode(temp_salt).decode(),
                  base64.urlsafe_b64encode(encrypted_temp_mk).decode(),
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


def registra_utente(nome, cognome, username, password, email, data_nascita, codice_fiscale, indirizzo):
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
                 import hashlib
                 srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
                 srv_fernet_key = base64.urlsafe_b64encode(srv_key_bytes)
                 encrypted_mk_backup = crypto.encrypt_master_key(master_key, srv_fernet_key)
                 encrypted_mk_backup_b64 = base64.urlsafe_b64encode(encrypted_mk_backup).decode()
             except Exception as e_bk:
                 print(f"[WARNING] Failed to generate server backup key: {e_bk}")

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO Utenti (nome, cognome, username, password_hash, email, data_nascita, codice_fiscale, indirizzo, salt, encrypted_master_key, recovery_key_hash, encrypted_master_key_recovery, encrypted_master_key_backup, username_bindex, email_bindex, username_enc, email_enc, nome_enc_server, cognome_enc_server)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_utente
            """, (enc_nome, enc_cognome, username, password_hash, email, data_nascita, enc_cf, enc_indirizzo, 
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

def cambia_password(id_utente, vecchia_password_hash, nuova_password_hash):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Utenti SET password_hash = %s WHERE id_utente = %s AND password_hash = %s",
                        (nuova_password_hash, id_utente, vecchia_password_hash))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore cambio password: {e}")
        return False

def imposta_password_temporanea(id_utente, temp_password_raw):
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

def trova_utente_per_email(email):
    try:
        e_bindex = compute_blind_index(email)
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente, nome, email, email_enc FROM Utenti WHERE email_bindex = %s", (e_bindex,))
            res = cur.fetchone()
            # Fallback removed

            
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
                 'email': real_email
             }
            return None
    except Exception as e:
        print(f"[ERRORE] Errore ricerca utente per email: {e}")
        return None

def cambia_password_e_username(id_utente, password_raw, nuovo_username, nome=None, cognome=None, vecchia_password=None):
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
        master_key = crypto.generate_master_key()
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

def aggiungi_utente_a_famiglia(id_utente, id_famiglia, ruolo='user'):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("INSERT INTO Appartenenza_Famiglia (id_utente, id_famiglia, ruolo) VALUES (%s, %s, %s)",
                        (id_utente, id_famiglia, ruolo))
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta utente a famiglia: {e}")
        return False

def rimuovi_utente_da_famiglia(id_utente, id_famiglia):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s",
                        (id_utente, id_famiglia))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore rimozione utente da famiglia: {e}")
        return False

def ottieni_membri_famiglia(id_famiglia, master_key_b64=None, id_utente_current=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT U.id_utente, U.username, U.email, AF.ruolo, 
                       U.nome_enc_server, U.cognome_enc_server
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

            return or_rows
    except Exception as e:
        print(f"[ERRORE] Errore recupero membri famiglia: {e}")
        return []


def ottieni_ruolo_utente(id_utente, id_famiglia):
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

def ensure_family_key(id_utente, id_famiglia, master_key_b64):
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
def ottieni_conti(id_utente, master_key_b64=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_conto, nome_conto, tipo, iban, valore_manuale, rettifica_saldo FROM Conti WHERE id_utente = %s", (id_utente,))
            conti = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            if master_key:
                for conto in conti:
                    conto['nome_conto'] = _decrypt_if_key(conto['nome_conto'], master_key, crypto)
                    conto['tipo'] = _decrypt_if_key(conto['tipo'], master_key, crypto)
                    if 'iban' in conto:
                        conto['iban'] = _decrypt_if_key(conto['iban'], master_key, crypto)
                    
                    # Handle numeric fields that might be encrypted
                    for field in ['valore_manuale', 'rettifica_saldo']:
                        if field in conto and conto[field] is not None:
                            decrypted = _decrypt_if_key(conto[field], master_key, crypto)
                            try:
                                conto[field] = float(decrypted)
                            except (ValueError, TypeError):
                                conto[field] = decrypted # Keep as is if not a number
            
            return conti
            
            return conti
    except Exception as e:
        print(f"[ERRORE] Errore recupero conti: {e}")
        return []

def aggiungi_conto(id_utente, nome_conto, tipo, saldo_iniziale=0.0, data_saldo_iniziale=None, master_key_b64=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_nome = _encrypt_if_key(nome_conto, master_key, crypto)
    encrypted_tipo = _encrypt_if_key(tipo, master_key, crypto)
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

def modifica_conto(id_conto, nome_conto, tipo, saldo_iniziale, data_saldo_iniziale, master_key_b64=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_nome = _encrypt_if_key(nome_conto, master_key, crypto)
    encrypted_tipo = _encrypt_if_key(tipo, master_key, crypto)
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


def elimina_conto(id_conto):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM Conti WHERE id_conto = %s", (id_conto,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione conto: {e}")
        return False

# --- Funzioni Categorie ---
def ottieni_categorie(id_famiglia, master_key_b64=None, id_utente=None):
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
            return cur.fetchone()['id_categoria']
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
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore modifica categoria: {e}")
        return False

def elimina_categoria(id_categoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            return cur.rowcount > 0
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
            return cur.fetchone()['id_sottocategoria']
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
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore modifica sottocategoria: {e}")
        return False

def elimina_sottocategoria(id_sottocategoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM Sottocategorie WHERE id_sottocategoria = %s", (id_sottocategoria,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione sottocategoria: {e}")
        return False

def ottieni_categorie_e_sottocategorie(id_famiglia, master_key_b64=None, id_utente=None):
    try:
        categorie = ottieni_categorie(id_famiglia, master_key_b64, id_utente)
        for cat in categorie:
            cat['sottocategorie'] = ottieni_sottocategorie(cat['id_categoria'], master_key_b64, id_utente)
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


def imposta_conto_default_utente(id_utente, id_conto_personale=None, id_conto_condiviso=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase

            if id_conto_personale:
                # Imposta il conto personale e annulla quello condiviso
                cur.execute(
                    "UPDATE Utenti SET id_conto_condiviso_default = NULL, id_conto_default = %s WHERE id_utente = %s",
                    (id_conto_personale, id_utente))
            elif id_conto_condiviso:
                # Imposta il conto condiviso e annulla quello personale
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_conto_condiviso_default = %s WHERE id_utente = %s",
                    (id_conto_condiviso, id_utente))
            else:  # Se entrambi sono None, annulla entrambi
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_conto_condiviso_default = NULL WHERE id_utente = %s",
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
            cur.execute("SELECT id_conto_default, id_conto_condiviso_default FROM Utenti WHERE id_utente = %s",
                        (id_utente,))
            result = cur.fetchone()
            if result:
                if result['id_conto_default'] is not None:
                    return {'id': result['id_conto_default'], 'tipo': 'personale'}
                elif result['id_conto_condiviso_default'] is not None:
                    return {'id': result['id_conto_condiviso_default'], 'tipo': 'condiviso'}
            return None
    except Exception as e:
        print(f"[ERRORE] Errore durante il recupero del conto di default: {e}")
        return None


def registra_utente(nome, cognome, username, password, email, data_nascita, codice_fiscale, indirizzo):
    try:
        crypto = CryptoManager()
        
        # Generate encryption keys
        salt = crypto.generate_salt()
        kek = crypto.derive_key(password, salt)
        master_key = crypto.generate_master_key()
        encrypted_master_key = crypto.encrypt_master_key(master_key, kek)
        recovery_key = crypto.generate_recovery_key()
        recovery_key_hash = crypto.hash_recovery_key(recovery_key)
        
        # Encrypt PII
        encrypted_nome = crypto.encrypt_data(nome, master_key)
        encrypted_cognome = crypto.encrypt_data(cognome, master_key)
        encrypted_codice_fiscale = crypto.encrypt_data(codice_fiscale, master_key)
        encrypted_indirizzo = crypto.encrypt_data(indirizzo, master_key)
        
        # --- BLIND INDEX & SYSTEM ENCRYPTION ---
        # Calculate blind index for login
        username_bindex = compute_blind_index(username)
        email_bindex = compute_blind_index(email)
        
        # Encrypt for system visibility (display)
        username_enc = encrypt_system_data(username)
        email_enc = encrypt_system_data(email)
        
        # Encrypt name/surname for server visibility (family display)
        nome_enc_server = encrypt_system_data(nome)
        cognome_enc_server = encrypt_system_data(cognome)
        
        # Backup Master Key with Server Key (for Password Recovery)
        # Encrypt the Master Key with the Server Fernet Key
        srv_key_bytes = hashlib.sha256(SERVER_SECRET_KEY.encode()).digest()
        srv_fernet_key = base64.urlsafe_b64encode(srv_key_bytes)
        encrypted_mk_backup = crypto.encrypt_master_key(master_key, srv_fernet_key)

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                        INSERT INTO Utenti (
                            nome, cognome, password_hash, data_nascita, codice_fiscale, indirizzo, 
                            salt, encrypted_master_key, recovery_key_hash, 
                            username_bindex, email_bindex, username_enc, email_enc,
                            nome_enc_server, cognome_enc_server, encrypted_master_key_backup
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                        RETURNING id_utente
                        """, (
                            encrypted_nome, 
                            encrypted_cognome, 
                            hash_password(password), 
                            data_nascita, 
                            encrypted_codice_fiscale, 
                            encrypted_indirizzo,
                            base64.urlsafe_b64encode(salt).decode(),
                            base64.urlsafe_b64encode(encrypted_master_key).decode(),
                            recovery_key_hash,
                            username_bindex, email_bindex, username_enc, email_enc,
                            nome_enc_server, cognome_enc_server, 
                            base64.urlsafe_b64encode(encrypted_mk_backup).decode()
                        ))
            id_utente = cur.fetchone()['id_utente']
            return {"id_utente": id_utente, "recovery_key": recovery_key}
    except Exception as e:
        print(f"[ERRORE] Errore durante la registrazione: {e}")
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
        "SOPRAVVIVENZA": ["MUTUO", "FINANZIAMENTO", "ASSICURAZIONI", "UTENZE", "ALIMENTI","AUTO 1", "AUTO 2","SCUOLA", "CONDOMINIO", "SALUTE"],
        "SPESE": ["TELEFONI", "INTERNET", "TELEVISIONE", "SERVIZI", "ATTIVITA' BAMBINI", "RISTORAZIONE", "VESTITI", "ACQUISTI VARI", "SPESE PER LA CASA", "REGALI", "VACANZE", "CORSI ESTIVI"],
        "SVAGO": ["LIBRI", "SPETTACOLI"],
        "IMPREVISTI": ["IMPREVISTI"]
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



def trova_utente_per_email(email):
    """
    Trova un utente dal suo username (che è l'email) usando il Blind Index.
    Decripta i campi di sistema (username, email, nome) per l'uso interno (es. reset password).
    """
    try:
        bindex = compute_blind_index(email)
        if not bindex: return None

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Utenti WHERE email_bindex = %s", (bindex,))
            row = cur.fetchone()
            
            if not row: return None
            
            dati = dict(row)
            
            # Decrypt System Data
            dati['email'] = decrypt_system_data(dati.get('email_enc'))
            dati['username'] = decrypt_system_data(dati.get('username_enc'))
            
            # Decrypt Name/Surname from Server copy if available (for email greeting)
            n_srv = decrypt_system_data(dati.get('nome_enc_server'))
            c_srv = decrypt_system_data(dati.get('cognome_enc_server'))
            
            if n_srv: dati['nome'] = n_srv
            if c_srv: dati['cognome'] = c_srv
            
            return dati
    except Exception as e:
        print(f"[ERRORE] Errore in trova_utente_per_email: {e}")
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
def aggiungi_conto(id_utente, nome_conto, tipo_conto, iban=None, valore_manuale=0.0, borsa_default=None, master_key_b64=None):
    if not valida_iban_semplice(iban):
        return None, "IBAN non valido"
    iban_pulito = iban.strip().upper() if iban else None
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_nome = _encrypt_if_key(nome_conto, master_key, crypto)
    encrypted_iban = _encrypt_if_key(iban_pulito, master_key, crypto)
    
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
            cur.execute("SELECT id_conto, nome_conto, tipo FROM Conti WHERE id_utente = %s", (id_utente,))
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
                        WHERE C.id_utente = %s
                        ORDER BY C.nome_conto
                        """, (id_utente,))
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            
            for row in results:
                # Decrypt text fields
                if master_key:
                    row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
                    row['iban'] = _decrypt_if_key(row['iban'], master_key, crypto)
                
                # Handle saldo_calcolato
                saldo_str = row['saldo_calcolato']
                if row['tipo'] == 'Fondo Pensione':
                    if master_key:
                        saldo_str = _decrypt_if_key(saldo_str, master_key, crypto)
                
                try:
                    row['saldo_calcolato'] = float(saldo_str) if saldo_str else 0.0
                except (ValueError, TypeError):
                    row['saldo_calcolato'] = 0.0
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero dettagli conti: {e}")
        return []


def modifica_conto(id_conto, id_utente, nome_conto, tipo_conto, iban=None, valore_manuale=None, borsa_default=None, master_key_b64=None):
    if not valida_iban_semplice(iban):
        return False, "IBAN non valido"
    iban_pulito = iban.strip().upper() if iban else None
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_nome = _encrypt_if_key(nome_conto, master_key, crypto)
    encrypted_iban = _encrypt_if_key(iban_pulito, master_key, crypto)

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
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT tipo, valore_manuale FROM Conti WHERE id_conto = %s AND id_utente = %s", (id_conto, id_utente))
            res = cur.fetchone()
            if not res: return False
            tipo = res['tipo']
            valore_manuale = res['valore_manuale']

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
                cur.execute("SELECT COALESCE(SUM(importo), 0.0) AS saldo, COUNT(*) AS num_transazioni FROM Transazioni T WHERE T.id_conto = %s", (id_conto,))
                res = cur.fetchone()
                saldo = res['saldo']
                num_transazioni = res['num_transazioni']

            if abs(saldo) > 1e-9:
                return "SALDO_NON_ZERO"
            
            # Nuovo controllo: impedisce la cancellazione se ci sono transazioni/asset, anche se il saldo è zero.
            if num_transazioni > 0:
                return "CONTO_NON_VUOTO"

            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
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


def modifica_conto_condiviso(id_conto_condiviso, nome_conto, tipo=None, lista_utenti=None, id_utente=None, master_key_b64=None):
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
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase

            if tipo:
                cur.execute("UPDATE ContiCondivisi SET nome_conto = %s, tipo = %s WHERE id_conto_condiviso = %s",
                            (encrypted_nome, tipo, id_conto_condiviso))
            else:
                cur.execute("UPDATE ContiCondivisi SET nome_conto = %s WHERE id_conto_condiviso = %s",
                            (encrypted_nome, id_conto_condiviso))

            cur.execute("SELECT tipo_condivisione FROM ContiCondivisi WHERE id_conto_condiviso = %s",
                        (id_conto_condiviso,))
            tipo_condivisione = cur.fetchone()['tipo_condivisione']

            if tipo_condivisione == 'utenti' and lista_utenti is not None:
                cur.execute("DELETE FROM PartecipazioneContoCondiviso WHERE id_conto_condiviso = %s",
                            (id_conto_condiviso,))
                for uid in lista_utenti:
                    cur.execute(
                        "INSERT INTO PartecipazioneContoCondiviso (id_conto_condiviso, id_utente) VALUES (%s, %s)",
                        (id_conto_condiviso, uid))

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


def ottieni_dettagli_conto_condiviso(id_conto_condiviso):
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

            # Conti Personali di tutti i membri della famiglia
            cur.execute("""
                        SELECT C.id_conto, C.nome_conto, C.tipo, 0 as is_condiviso, U.username_enc as proprietario_enc, C.id_utente
                        FROM Conti C
                        JOIN Utenti U ON C.id_utente = U.id_utente
                        JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s AND C.tipo != 'Investimento'
                        
                        UNION ALL
                        
                        SELECT CC.id_conto_condiviso as id_conto, CC.nome_conto, CC.tipo, 1 as is_condiviso, 'Condiviso' as proprietario_enc, NULL as id_utente
                        FROM ContiCondivisi CC
                        WHERE CC.id_famiglia = %s AND CC.tipo != 'Investimento'
                        """, (id_famiglia, id_famiglia))
            
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt loop
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            for row in results:
                # Decrypt proprietario if it's a person
                if row.get('proprietario_enc') and row['proprietario_enc'] != 'Condiviso':
                     row['proprietario'] = decrypt_system_data(row['proprietario_enc']) or "Sconosciuto"
                else:
                     row['proprietario'] = row.get('proprietario_enc') # 'Condiviso'

                if row['is_condiviso']:
                    # Shared Account: Try Family Key, then Master Key
                    family_key = None
                    if master_key and id_utente:
                        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

                    if family_key:
                        row['nome_conto'] = _decrypt_if_key(row['nome_conto'], family_key, crypto, silent=True)
                        if row['nome_conto'] == "[ENCRYPTED]" and isinstance(row['nome_conto'], str) and row['nome_conto'].startswith("gAAAAA"):
                            row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
                    else:
                         # No family key, try master key (legacy/fallback)
                         row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
                else:
                    # Personal Account: Decrypt ONLY if it belongs to the current user
                    if id_utente and row.get('id_utente') == id_utente:
                        row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
                    # Else: Leave encrypted (or show placeholder if desired, but for now leave as is)
            
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
                if fk_b64 != "[ENCRYPTED]":
                    return base64.b64decode(fk_b64)
    except Exception as e:
        # Non bloccante, fallback a master_key
        pass
        
    return master_key

def aggiungi_transazione(id_conto, data, descrizione, importo, id_sottocategoria=None, cursor=None, master_key_b64=None):
    # Encrypt if key available using Family Key if possible (for shared visibility)
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encryption_key = _get_key_for_transaction(id_conto, master_key, crypto)
    encrypted_descrizione = _encrypt_if_key(descrizione, encryption_key, crypto)
    
    # Permette di passare un cursore esistente per le transazioni atomiche
    if cursor:
        cursor.execute(
            "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s) RETURNING id_transazione",
            (id_conto, id_sottocategoria, data, encrypted_descrizione, importo))
        return cursor.fetchone()['id_transazione']
    else:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s) RETURNING id_transazione",
                    (id_conto, id_sottocategoria, data, encrypted_descrizione, importo))
                return cur.fetchone()['id_transazione']
        except Exception as e:
            print(f"[ERRORE] Errore generico: {e}")
            return None


def modifica_transazione(id_transazione, data, descrizione, importo, id_sottocategoria=None, id_conto=None, master_key_b64=None):
    # Encrypt if key available using Family Key if possible (for shared visibility)
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encryption_key = _get_key_for_transaction(id_conto, master_key, crypto)
    encrypted_descrizione = _encrypt_if_key(descrizione, encryption_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            if id_conto is not None:
                cur.execute(
                    "UPDATE Transazioni SET data = %s, descrizione = %s, importo = %s, id_sottocategoria = %s, id_conto = %s WHERE id_transazione = %s",
                    (data, encrypted_descrizione, importo, id_sottocategoria, id_conto, id_transazione))
            else:
                cur.execute(
                    "UPDATE Transazioni SET data = %s, descrizione = %s, importo = %s, id_sottocategoria = %s WHERE id_transazione = %s",
                    (data, encrypted_descrizione, importo, id_sottocategoria, id_transazione))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica: {e}")
        return False


def elimina_transazione(id_transazione):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM Transazioni WHERE id_transazione = %s", (id_transazione,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione: {e}")
        return None


def ottieni_riepilogo_patrimonio_utente(id_utente, anno, mese, master_key_b64=None):
    try:
        data_limite = datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)
        data_limite_str = data_limite.strftime('%Y-%m-%d')
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Liquidità Personale (somma transazioni + rettifica)
            cur.execute("""
                SELECT COALESCE(SUM(T.importo), 0.0) as val
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                WHERE C.id_utente = %s
                  AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')
                  AND T.data <= %s
            """, (id_utente, data_limite_str))
            transazioni_personali = float(cur.fetchone()['val'] or 0.0)
            
            # 1.1 Rettifiche Conti Personali
            cur.execute("""
                SELECT COALESCE(SUM(CAST(NULLIF(CAST(C.rettifica_saldo AS TEXT), '') AS NUMERIC)), 0.0) as val
                FROM Conti C
                WHERE C.id_utente = %s
                  AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')
            """, (id_utente,))
            rettifica_personali = float(cur.fetchone()['val'] or 0.0)
            
            liquidita_personale = transazioni_personali + rettifica_personali

            # 1.2 Liquidità Condivisa (somma transazioni)
            cur.execute("""
                SELECT COALESCE(SUM(TC.importo), 0.0) as val
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                LEFT JOIN PartecipazioneContoCondiviso PCC ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                WHERE ((PCC.id_utente = %s AND CC.tipo_condivisione = 'utenti')
                   OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s) AND CC.tipo_condivisione = 'famiglia'))
                  AND TC.data <= %s
            """, (id_utente, id_utente, data_limite_str))
            transazioni_condivise = float(cur.fetchone()['val'] or 0.0)
            
            # 1.3 Rettifiche Conti Condivisi
            cur.execute("""
                SELECT COALESCE(SUM(CAST(NULLIF(CAST(CC.rettifica_saldo AS TEXT), '') AS NUMERIC)), 0.0) as val
                FROM ContiCondivisi CC
                LEFT JOIN PartecipazioneContoCondiviso PCC ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                WHERE (PCC.id_utente = %s AND CC.tipo_condivisione = 'utenti')
                   OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s) AND CC.tipo_condivisione = 'famiglia')
            """, (id_utente, id_utente))
            rettifica_condivisi = float(cur.fetchone()['val'] or 0.0)
            
            liquidita_condivisa = transazioni_condivise + rettifica_condivisi

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
            
            patrimonio_netto = liquidita + investimenti + fondi_pensione
            
            return {
                'patrimonio_netto': patrimonio_netto,
                'liquidita': liquidita,
                'investimenti': investimenti,
                'fondi_pensione': fondi_pensione,
                'risparmio': risparmio
            }
    except Exception as e:
        print(f"[ERRORE] Errore in ottieni_riepilogo_patrimonio_utente: {e}")
        return {'patrimonio_netto': 0.0, 'liquidita': 0.0, 'investimenti': 0.0, 'fondi_pensione': 0.0, 'risparmio': 0.0}


def ottieni_riepilogo_patrimonio_famiglia_aggregato(id_famiglia, anno, mese, master_key_b64=None):
    try:
        data_limite = datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)
        data_limite_str = data_limite.strftime('%Y-%m-%d')
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Liquidità Personale (Tutti i membri)
            cur.execute("""
                SELECT COALESCE(SUM(T.importo), 0.0) as val
                FROM Transazioni T
                JOIN Conti C ON T.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')
                  AND T.data <= %s
            """, (id_famiglia, data_limite_str))
            liquidita_personale = cur.fetchone()['val'] or 0.0
            
            # 1b. Liquidità Conti Condivisi
            cur.execute("""
                SELECT COALESCE(SUM(TC.importo), 0.0) as val
                FROM TransazioniCondivise TC
                JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                WHERE CC.id_famiglia = %s
                  AND CC.tipo NOT IN ('Investimento')
                  AND TC.data <= %s
            """, (id_famiglia, data_limite_str))
            liquidita_condivisa = cur.fetchone()['val'] or 0.0
            
            # Include rettifica_saldo for shared accounts
            cur.execute("""
                SELECT COALESCE(SUM(CAST(NULLIF(CAST(CC.rettifica_saldo AS TEXT), '') AS NUMERIC)), 0.0) as val
                FROM ContiCondivisi CC
                WHERE CC.id_famiglia = %s
                  AND CC.tipo NOT IN ('Investimento')
            """, (id_famiglia,))
            rettifica_condivisi = cur.fetchone()['val'] or 0.0
            
            liquidita = liquidita_personale + liquidita_condivisa + rettifica_condivisi
            
            # 2. Investimenti (Tutti i membri)
            cur.execute("""
                SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0) as val
                FROM Asset A
                JOIN Conti C ON A.id_conto = C.id_conto
                JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                WHERE AF.id_famiglia = %s
                  AND C.tipo = 'Investimento'
            """, (id_famiglia,))
            investimenti = cur.fetchone()['val'] or 0.0
            
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
            risparmio = cur.fetchone()['val'] or 0.0
            
            patrimonio_netto = liquidita + investimenti + fondi_pensione
            
            return {
                'patrimonio_netto': patrimonio_netto,
                'liquidita': liquidita,
                'investimenti': investimenti,
                'fondi_pensione': fondi_pensione,
                'risparmio': risparmio
            }
    except Exception as e:
        print(f"[ERRORE] Errore in ottieni_riepilogo_patrimonio_famiglia_aggregato: {e}")
        return {'patrimonio_netto': 0.0, 'liquidita': 0.0, 'investimenti': 0.0, 'fondi_pensione': 0.0, 'risparmio': 0.0}


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
                               0           AS id_transazione_condivisa -- Placeholder
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
                               TC.id_transazione_condivisa
                        FROM TransazioniCondivise TC
                                 JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                 LEFT JOIN PartecipazioneContoCondiviso PCC
                                           ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                                 LEFT JOIN Sottocategorie SCat ON TC.id_sottocategoria = SCat.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON SCat.id_categoria = Cat.id_categoria
                        WHERE (PCC.id_utente = %s AND CC.tipo_condivisione = 'utenti')
                           OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s) AND
                               CC.tipo_condivisione = 'famiglia') AND TC.data BETWEEN %s AND %s

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
                    
                    # Decrypt other fields
                    if row.get('tipo_transazione') == 'condivisa' and family_key:
                        key_conto = family_key
                    else:
                        key_conto = master_key

                    row['nome_conto'] = _decrypt_if_key(row['nome_conto'], key_conto, crypto)
                    
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


def aggiungi_transazione_condivisa(id_utente_autore, id_conto_condiviso, data, descrizione, importo, id_sottocategoria=None, cursor=None, master_key_b64=None):
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
            "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_transazione_condivisa",
            (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, encrypted_descrizione, importo))
        return cursor.fetchone()['id_transazione_condivisa']
    else:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_transazione_condivisa",
                    (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, encrypted_descrizione, importo))
                return cur.fetchone()['id_transazione_condivisa']
        except Exception as e:
            print(f"[ERRORE] Errore generico durante l'aggiunta transazione condivisa: {e}")
            return None


def modifica_transazione_condivisa(id_transazione_condivisa, data, descrizione, importo, id_sottocategoria=None, master_key_b64=None, id_utente=None):
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
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        UPDATE TransazioniCondivise
                        SET data         = %s,
                            descrizione  = %s,
                            importo      = %s,
                            id_sottocategoria = %s
                        WHERE id_transazione_condivisa = %s
                        """, (data, encrypted_descrizione, importo, id_sottocategoria, id_transazione_condivisa))
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
                        GROUP BY T.id_sottocategoria
                        UNION ALL
                        SELECT
                            TC.id_sottocategoria,
                            SUM(TC.importo) as spesa_totale
                        FROM TransazioniCondivise TC
                        JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                        WHERE CC.id_famiglia = %s AND TC.importo < 0 AND TC.data BETWEEN %s AND %s
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


def ottieni_storico_budget_per_export(id_famiglia, lista_periodi):
    if not lista_periodi: return []
    placeholders = " OR ".join(["(anno = %s AND mese = %s)"] * len(lista_periodi))
    params = [id_famiglia] + [item for sublist in lista_periodi for item in sublist]
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            query = f"""
                SELECT anno, mese, nome_categoria, importo_limite, importo_speso, (importo_limite - importo_speso) AS rimanente
                FROM Budget_Storico
                WHERE id_famiglia = %s AND ({placeholders})
                ORDER BY anno, mese, nome_categoria
            """
            cur.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]
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
            # --- OTTIMIZZAZIONE FINE ---

            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero prestiti: {e}")
        return []


def check_e_paga_rate_scadute(id_famiglia):
    oggi = datetime.date.today()
    pagamenti_eseguiti = 0
    try:
        prestiti_attivi = ottieni_prestiti_famiglia(id_famiglia)
        with get_db_connection() as con:
            cur = con.cursor()
            for p in prestiti_attivi:
                if p['importo_residuo'] > 0 and p['id_conto_pagamento_default'] and p[
                    'id_categoria_pagamento_default'] and oggi.day >= p['giorno_scadenza_rata']:
                    cur.execute("SELECT 1 FROM StoricoPagamentiRate WHERE id_prestito = %s AND anno = %s AND mese = %s",
                                (p['id_prestito'], oggi.year, oggi.month))
                    if cur.fetchone() is None:
                        importo_da_pagare = min(p['importo_rata'], p['importo_residuo'])
                        effettua_pagamento_rata(p['id_prestito'], p['id_conto_pagamento_default'], importo_da_pagare,
                                                oggi.strftime('%Y-%m-%d'), p['id_categoria_pagamento_default'],
                                                p['nome'])
                        pagamenti_eseguiti += 1
        return pagamenti_eseguiti
    except Exception as e:
        print(f"[ERRORE] Errore critico durante il controllo delle rate scadute: {e}")
        return 0


def effettua_pagamento_rata(id_prestito, id_conto_pagamento, importo_pagato, data_pagamento, id_sottocategoria,
                            nome_prestito=""):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")
            cur.execute("UPDATE Prestiti SET importo_residuo = importo_residuo - %s WHERE id_prestito = %s",
                        (importo_pagato, id_prestito))
            descrizione = f"Pagamento rata {nome_prestito} (Prestito ID: {id_prestito})"
            cur.execute(
                "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo) VALUES (%s, %s, %s, %s, %s)",
                (id_conto_pagamento, id_sottocategoria, data_pagamento, descrizione, -abs(importo_pagato)))
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
                 prezzo_attuale_override=None, master_key_b64=None):
    ticker_upper = ticker.upper()
    nome_asset_upper = nome_asset.upper()
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Fetch all assets to find match (since encryption is non-deterministic)
            cur.execute(
                "SELECT id_asset, ticker, quantita, costo_iniziale_unitario FROM Asset WHERE id_conto = %s",
                (id_conto_investimento,))
            assets = cur.fetchall()
            
            risultato = None
            for asset in assets:
                db_ticker = asset['ticker']
                # Decrypt if possible
                decrypted_ticker = _decrypt_if_key(db_ticker, master_key, crypto)
                if decrypted_ticker == ticker_upper:
                    risultato = asset
                    break
            
            # Encrypt for storage
            encrypted_ticker = _encrypt_if_key(ticker_upper, master_key, crypto)
            encrypted_nome_asset = _encrypt_if_key(nome_asset_upper, master_key, crypto)

            cur.execute(
                "INSERT INTO Storico_Asset (id_conto, ticker, data, tipo_movimento, quantita, prezzo_unitario_movimento) VALUES (%s, %s, %s, %s, %s, %s)",
                (id_conto_investimento, encrypted_ticker, datetime.date.today().strftime('%Y-%m-%d'), tipo_mov, quantita,
                 costo_unitario_nuovo))
                 
            if risultato:
                id_asset_aggiornato = risultato['id_asset']
                vecchia_quantita = risultato['quantita']
                vecchio_costo_medio = risultato['costo_iniziale_unitario']
                
                nuova_quantita_totale = vecchia_quantita + quantita
                nuovo_costo_medio = (
                                                vecchia_quantita * vecchio_costo_medio + quantita * costo_unitario_nuovo) / nuova_quantita_totale
                cur.execute(
                    "UPDATE Asset SET quantita = %s, nome_asset = %s, costo_iniziale_unitario = %s WHERE id_asset = %s",
                    (nuova_quantita_totale, encrypted_nome_asset, nuovo_costo_medio, id_asset_aggiornato))
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
            encrypted_ticker = _encrypt_if_key(ticker_upper, master_key, crypto)
            
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
                for row in results:
                    row['ticker'] = _decrypt_if_key(row['ticker'], master_key, crypto)
                    row['nome_asset'] = _decrypt_if_key(row['nome_asset'], master_key, crypto)
            
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


def modifica_asset_dettagli(id_asset, nuovo_ticker, nuovo_nome, master_key_b64=None):
    nuovo_ticker_upper = nuovo_ticker.upper()
    nuovo_nome_upper = nuovo_nome.upper()
    
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_ticker = _encrypt_if_key(nuovo_ticker_upper, master_key, crypto)
    encrypted_nome = _encrypt_if_key(nuovo_nome_upper, master_key, crypto)
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("UPDATE Asset SET ticker = %s, nome_asset = %s WHERE id_asset = %s",
                        (encrypted_ticker, encrypted_nome, id_asset))
            return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiornamento dettagli asset: {e}")
        return False




# --- Funzioni Investimenti ---
def aggiungi_investimento(id_conto, ticker, nome_asset, quantita, costo_unitario, data_acquisto, master_key_b64=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_ticker = _encrypt_if_key(ticker.upper(), master_key, crypto)
    encrypted_nome = _encrypt_if_key(nome_asset, master_key, crypto)

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
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_ticker = _encrypt_if_key(ticker.upper(), master_key, crypto)
    encrypted_nome = _encrypt_if_key(nome_asset, master_key, crypto)

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
                for asset in assets:
                    asset['ticker'] = _decrypt_if_key(asset['ticker'], master_key, crypto)
                    asset['nome_asset'] = _decrypt_if_key(asset['nome_asset'], master_key, crypto)
            
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
                asset['ticker'] = _decrypt_if_key(asset['ticker'], master_key, crypto)
                asset['nome_asset'] = _decrypt_if_key(asset['nome_asset'], master_key, crypto)
            
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
def ottieni_riepilogo_conti_famiglia(id_famiglia):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT COALESCE(U.nome || ' ' || U.cognome, U.username) AS membro,
                               C.nome_conto,
                               C.tipo,
                               C.iban,
                               CASE
                                   WHEN C.tipo = 'Fondo Pensione' THEN C.valore_manuale
                                   WHEN C.tipo = 'Investimento'
                                       THEN (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                             FROM Asset A
                                             WHERE A.id_conto = C.id_conto)
                                   ELSE (SELECT COALESCE(SUM(T.importo), 0.0)
                                         FROM Transazioni T
                                         WHERE T.id_conto = C.id_conto)
                                   END                                          AS saldo_calcolato
                        FROM Conti C
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                        ORDER BY membro, C.tipo, C.nome_conto
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero riepilogo conti famiglia: {e}")
        return []


def ottieni_dettaglio_portafogli_famiglia(id_famiglia):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT U.username_enc                                       AS membro_enc,
                               C.nome_conto,
                               A.ticker,
                               A.nome_asset,
                               A.quantita,
                               A.costo_iniziale_unitario,
                               A.valore_corrente_unitario,
                               (A.quantita * A.costo_iniziale_unitario)             AS investito_totale,
                               (A.quantita * A.valore_corrente_unitario)            AS valore_totale,
                               ((A.quantita * A.valore_corrente_unitario) - (A.quantita * A.costo_iniziale_unitario)) AS profitto
                        FROM Conti C
                                 JOIN Asset A ON C.id_conto = A.id_conto
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                          AND C.tipo = 'Investimento'
                        
                        UNION ALL
                        
                        -- Shared Investments (if any? usually personal)
                        SELECT 'Condiviso' as membro_enc,
                               CC.nome_conto,
                               A.ticker,
                               A.nome_asset,
                               A.quantita,
                               A.costo_iniziale_unitario,
                               A.valore_corrente_unitario,
                               (A.quantita * A.costo_iniziale_unitario)             AS investito_totale,
                               (A.quantita * A.valore_corrente_unitario)            AS valore_totale,
                               ((A.quantita * A.valore_corrente_unitario) - (A.quantita * A.costo_iniziale_unitario)) AS profitto
                        FROM ContiCondivisi CC
                                 JOIN Asset A ON CC.id_conto_condiviso = A.id_conto_condiviso
                        WHERE CC.id_famiglia = %s
                          AND CC.tipo = 'Investimento'
                          
                        ORDER BY membro_enc, nome_conto, ticker
                        """, (id_famiglia, id_famiglia))
            
            results = [dict(row) for row in cur.fetchall()]
            for row in results:
                if row['membro_enc'] == 'Condiviso':
                    row['membro'] = 'Condiviso'
                else:
                    row['membro'] = decrypt_system_data(row['membro_enc']) or "Sconosciuto"
                # del row['membro_enc'] # Optional cleanup
            
            return results

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero dettaglio portafogli famiglia: {e}")
        return []


def ottieni_transazioni_famiglia_per_export(id_famiglia, data_inizio, data_fine):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT T.data,
                               COALESCE(U.nome || ' ' || U.cognome, U.username) AS membro,
                               C.nome_conto,
                               T.descrizione,
                               Cat.nome_categoria,
                               T.importo
                        FROM Transazioni T
                                 JOIN Conti C ON T.id_conto = C.id_conto
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                                 LEFT JOIN Categorie Cat ON T.id_categoria = Cat.id_categoria
                        WHERE AF.id_famiglia = %s
                          AND T.data BETWEEN %s AND %s
                          AND C.tipo != 'Fondo Pensione'
                        ORDER BY T.data DESC, T.id_transazione DESC
                        """, (id_famiglia, data_inizio, data_fine))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero transazioni per export: {e}")
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
def aggiungi_spesa_fissa(id_famiglia, nome, importo, id_conto_personale, id_conto_condiviso, id_sottocategoria,
                        giorno_addebito, attiva, addebito_automatico=False, master_key_b64=None, id_utente=None):
    
    # Encrypt nome if keys available
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

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Ottieni id_categoria dalla sottocategoria
            cur.execute("SELECT id_categoria FROM Sottocategorie WHERE id_sottocategoria = %s", (id_sottocategoria,))
            result = cur.fetchone()
            id_categoria = result['id_categoria'] if result else None
            
            cur.execute("""
                INSERT INTO SpeseFisse (id_famiglia, nome, importo, id_conto_personale_addebito, id_conto_condiviso_addebito, id_categoria, id_sottocategoria, giorno_addebito, attiva, addebito_automatico)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_spesa_fissa
            """, (id_famiglia, encrypted_nome, importo, id_conto_personale, id_conto_condiviso, id_categoria, id_sottocategoria, giorno_addebito,
                  bool(attiva), bool(addebito_automatico)))
            return cur.fetchone()['id_spesa_fissa']
    except Exception as e:
        print(f"[ERRORE] Errore durante l'aggiunta della spesa fissa: {e}")
        return None


def modifica_spesa_fissa(id_spesa_fissa, nome, importo, id_conto_personale, id_conto_condiviso, id_sottocategoria,
                        giorno_addebito, attiva, addebito_automatico=False, master_key_b64=None, id_utente=None):
    
    # Encrypt nome if keys available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                # Need id_famiglia to get key
                cur.execute("SELECT id_famiglia FROM SpeseFisse WHERE id_spesa_fissa = %s", (id_spesa_fissa,))
                sf_row = cur.fetchone()
                if sf_row:
                    id_famiglia = sf_row['id_famiglia']
                    cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
                    row = cur.fetchone()
                    if row and row['chiave_famiglia_criptata']:
                        family_key_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                        family_key = base64.b64decode(family_key_b64)
        except Exception:
            pass

    encrypted_nome = _encrypt_if_key(nome, family_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Ottieni id_categoria dalla sottocategoria
            cur.execute("SELECT id_categoria FROM Sottocategorie WHERE id_sottocategoria = %s", (id_sottocategoria,))
            result = cur.fetchone()
            id_categoria = result['id_categoria'] if result else None
            
            cur.execute("""
                UPDATE SpeseFisse
                SET nome = %s, importo = %s, id_conto_personale_addebito = %s, id_conto_condiviso_addebito = %s, id_categoria = %s, id_sottocategoria = %s, giorno_addebito = %s, attiva = %s, addebito_automatico = %s
                WHERE id_spesa_fissa = %s
            """, (encrypted_nome, importo, id_conto_personale, id_conto_condiviso, id_categoria, id_sottocategoria, giorno_addebito,
                  bool(attiva), bool(addebito_automatico), id_spesa_fissa))
            return cur.rowcount > 0
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
                    COALESCE(CP.nome_conto, CC.nome_conto) as nome_conto
                FROM SpeseFisse SF
                LEFT JOIN Conti CP ON SF.id_conto_personale_addebito = CP.id_conto
                LEFT JOIN ContiCondivisi CC ON SF.id_conto_condiviso_addebito = CC.id_conto_condiviso
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

            if family_key:
                for spesa in spese:
                    spesa['nome'] = _decrypt_if_key(spesa['nome'], family_key, crypto)
                    # Decripta anche il nome del conto
                    if spesa.get('nome_conto'):
                        # Prova prima con family_key (per conti condivisi)
                        if spesa.get('id_conto_condiviso_addebito'):
                            spesa['nome_conto'] = _decrypt_if_key(spesa['nome_conto'], family_key, crypto, silent=True)
                        else:
                            # Conto personale: prova con master_key
                            spesa['nome_conto'] = _decrypt_if_key(spesa['nome_conto'], master_key, crypto, silent=True)

            return spese
    except Exception as e:
        print(f"[ERRORE] Errore durante il recupero delle spese fisse: {e}")
        return []


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

                # Controlla se la spesa è già stata eseguita questo mese
                cur.execute("""
                    SELECT 1 FROM Transazioni
                    WHERE (id_conto = %s AND descrizione = %s)
                    AND TO_CHAR(data::date, 'YYYY-MM') = %s
                """, (spesa['id_conto_personale_addebito'], f"Spesa Fissa: {spesa['nome']}", oggi.strftime('%Y-%m')))
                if cur.fetchone(): continue

                cur.execute("""
                    SELECT 1 FROM TransazioniCondivise
                    WHERE (id_conto_condiviso = %s AND descrizione = %s)
                    AND TO_CHAR(data::date, 'YYYY-MM') = %s
                """, (spesa['id_conto_condiviso_addebito'], f"Spesa Fissa: {spesa['nome']}", oggi.strftime('%Y-%m')))
                if cur.fetchone(): continue

                # Se il giorno di addebito è passato, esegui la transazione
                if oggi.day >= spesa['giorno_addebito']:
                    data_esecuzione = oggi.strftime('%Y-%m-%d')
                    descrizione = f"Spesa Fissa: {spesa['nome']}"
                    importo = -abs(spesa['importo'])

                    if spesa['id_conto_personale_addebito']:
                        aggiungi_transazione(
                            spesa['id_conto_personale_addebito'], data_esecuzione, descrizione, importo,
                            spesa['id_categoria'], cursor=cur
                        )
                    elif spesa['id_conto_condiviso_addebito']:
                        # L'autore è l'admin della famiglia (o il primo utente)
                        # Questa è un'approssimazione, si potrebbe migliorare
                        cur.execute("SELECT id_utente FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND ruolo = 'admin' LIMIT 1", (id_famiglia,))
                        admin_id = cur.fetchone()['id_utente']
                        aggiungi_transazione_condivisa(
                            admin_id, spesa['id_conto_condiviso_addebito'], data_esecuzione, descrizione, importo,
                            spesa['id_categoria'], cursor=cur
                        )
                    spese_eseguite += 1
            if spese_eseguite > 0:
                con.commit()
        return spese_eseguite
    except Exception as e:
        print(f"[ERRORE] Errore critico durante il processamento delle spese fisse: {e}")
        return 0


# --- MAIN ---
mimetypes.add_type("application/x-sqlite3", ".db")

if __name__ == "__main__":
    print("--- 0. PULIZIA DATABASE (CANCELLAZIONE .db) ---")
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"File '{DB_FILE}' rimosso per un test pulito.")

