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


# --- Helper Functions for Encryption ---
def _get_crypto_and_key(master_key_b64=None):
    """
    Returns CryptoManager instance and master_key.
    If master_key_b64 is None, returns (crypto, None) for legacy support.
    """
    crypto = CryptoManager()
    if master_key_b64:
        try:
            master_key = base64.urlsafe_b64decode(master_key_b64.encode())
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

def _decrypt_if_key(encrypted_data, master_key, crypto=None):
    """Decrypts data if master_key is available, otherwise returns data as-is."""
    if not master_key or not encrypted_data:
        return encrypted_data
    if not crypto:
        crypto = CryptoManager()
    return crypto.decrypt_data(encrypted_data, master_key)


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
def get_configurazione(chiave, id_famiglia=None):
    """
    Recupera il valore di una configurazione.
    Se id_famiglia è None, cerca una configurazione globale.
    Se id_famiglia è specificato, cerca una configurazione per quella famiglia.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            if id_famiglia is None:
                cur.execute("SELECT valore FROM Configurazioni WHERE chiave = %s AND id_famiglia IS NULL", (chiave,))
            else:
                cur.execute("SELECT valore FROM Configurazioni WHERE chiave = %s AND id_famiglia = %s", (chiave, id_famiglia))
            
            res = cur.fetchone()
            return res['valore'] if res else None
    except Exception as e:
        print(f"[ERRORE] Errore recupero configurazione {chiave}: {e}")
        return None

def set_configurazione(chiave, valore, id_famiglia=None):
    """
    Imposta o aggiorna una configurazione.
    Se id_famiglia è None, imposta una configurazione globale.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            if id_famiglia is None:
                cur.execute("""
                    INSERT INTO Configurazioni (chiave, valore, id_famiglia) 
                    VALUES (%s, %s, NULL)
                    ON CONFLICT (chiave, id_famiglia) WHERE id_famiglia IS NULL
                    DO UPDATE SET valore = EXCLUDED.valore
                """, (chiave, valore))
            else:
                cur.execute("""
                    INSERT INTO Configurazioni (chiave, valore, id_famiglia) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (chiave, id_famiglia) 
                    DO UPDATE SET valore = EXCLUDED.valore
                """, (chiave, valore, id_famiglia))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore salvataggio configurazione {chiave}: {e}")
        return False

def get_smtp_config(id_famiglia=None):
    """Recupera la configurazione SMTP completa."""
    return {
        'server': get_configurazione('smtp_server', id_famiglia),
        'port': get_configurazione('smtp_port', id_famiglia),
        'user': get_configurazione('smtp_user', id_famiglia),
        'password': get_configurazione('smtp_password', id_famiglia),
        'provider': get_configurazione('smtp_provider', id_famiglia)
    }

def save_smtp_config(settings, id_famiglia=None):
    """Salva la configurazione SMTP."""
    try:
        set_configurazione('smtp_server', settings.get('server'), id_famiglia)
        set_configurazione('smtp_port', settings.get('port'), id_famiglia)
        set_configurazione('smtp_user', settings.get('user'), id_famiglia)
        set_configurazione('smtp_password', settings.get('password'), id_famiglia)
        set_configurazione('smtp_provider', settings.get('provider'), id_famiglia)
        return True
    except Exception as e:
        print(f"[ERRORE] Errore salvataggio SMTP config: {e}")
        return False

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
                        SELECT username 
                        FROM Utenti 
                        WHERE id_utente NOT IN (SELECT id_utente FROM Appartenenza_Famiglia)
                        ORDER BY username
                        """)
            return [row['username'] for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore recupero utenti senza famiglia: {e}")
        return []


def verifica_login(login_identifier, password):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente, password_hash, nome, cognome, username, email, forza_cambio_password, salt, encrypted_master_key FROM Utenti WHERE username = %s OR email = %s",
                        (login_identifier, login_identifier.lower()))
            risultato = cur.fetchone()
            if risultato and risultato['password_hash'] == hash_password(password):
                # Decrypt master key if encryption is enabled
                master_key = None
                if risultato['salt'] and risultato['encrypted_master_key']:
                    try:
                        crypto = CryptoManager()
                        salt = base64.urlsafe_b64decode(risultato['salt'].encode())
                        kek = crypto.derive_key(password, salt)
                        encrypted_mk = base64.urlsafe_b64decode(risultato['encrypted_master_key'].encode())
                        master_key = crypto.decrypt_master_key(encrypted_mk, kek)
                        
                        # Decrypt nome and cognome for display
                        nome = crypto.decrypt_data(risultato['nome'], master_key)
                        cognome = crypto.decrypt_data(risultato['cognome'], master_key)
                    except Exception as e:
                        print(f"[ERRORE] Errore decryption: {e}")
                        return None
                else:
                    # Legacy user without encryption
                    nome = risultato['nome']
                    cognome = risultato['cognome']
                
                print(f"[DEBUG] Login verificato. Master Key recuperata: {bool(master_key)}")
                if master_key:
                    print(f"[DEBUG] Master Key type: {type(master_key)}")
                    print(f"[DEBUG] Master Key len: {len(master_key)}")
                    print(f"[DEBUG] Master Key content (partial): {master_key[:10]}")
                
                return {
                    "id": risultato['id_utente'], 
                    "username": risultato['username'], 
                    "forza_cambio_password": risultato['forza_cambio_password'], 
                    "nome": nome,
                    "cognome": cognome,
                    "master_key": master_key.decode() if master_key else None
                }
            print("[DEBUG] Login fallito o password errata.")
            return None
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il login: {e}")
        return None


def crea_utente_invitato(email, ruolo, id_famiglia):
    """
    Crea un nuovo utente invitato con credenziali temporanee.
    Restituisce un dizionario con le credenziali o None in caso di errore.
    """
    try:
        # Genera credenziali temporanee
        temp_password = secrets.token_urlsafe(10)
        temp_username = f"user_{secrets.token_hex(4)}"
        password_hash = hash_password(temp_password)
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Crea l'utente
            cur.execute("""
                INSERT INTO Utenti (username, email, password_hash, nome, cognome, forza_cambio_password)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                RETURNING id_utente
            """, (temp_username, email, password_hash, "Nuovo", "Utente"))
            
            id_utente = cur.fetchone()['id_utente']
            
            # 2. Aggiungi alla famiglia
            cur.execute("""
                INSERT INTO Appartenenza_Famiglia (id_utente, id_famiglia, ruolo)
                VALUES (%s, %s, %s)
            """, (id_utente, id_famiglia, ruolo))
            
            con.commit()
            
            return {
                "email": email,
                "username": temp_username,
                "password": temp_password
            }
            
    except Exception as e:
        print(f"[ERRORE] Errore creazione utente invitato: {e}")
        return None


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
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                        INSERT INTO Utenti (nome, cognome, username, password_hash, email, data_nascita, codice_fiscale, indirizzo, salt, encrypted_master_key, recovery_key_hash)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_utente
                        """, (
                            encrypted_nome, 
                            encrypted_cognome, 
                            username, 
                            hash_password(password), 
                            email.lower(), 
                            data_nascita, 
                            encrypted_codice_fiscale, 
                            encrypted_indirizzo,
                            base64.urlsafe_b64encode(salt).decode(),
                            base64.urlsafe_b64encode(encrypted_master_key).decode(),
                            recovery_key_hash
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
        if master_key_b64:
            try:
                crypto, master_key = _get_crypto_and_key(master_key_b64)
                if master_key:
                    chiave_famiglia_criptata = crypto.encrypt_data(family_key_b64, master_key)
            except Exception as e:
                print(f"[WARNING] Could not encrypt family key: {e}")
        
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("INSERT INTO Famiglie (nome_famiglia) VALUES (%s) RETURNING id_famiglia", (nome_famiglia,))
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
                               COALESCE(U.nome || ' ' || U.cognome, U.username) AS nome_visualizzato
                        FROM Utenti U
                                 LEFT JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE U.username = %s
                          AND AF.id_famiglia IS NULL
                        """, (username,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la ricerca utente: {e}")
        return None

def trova_utente_per_email(email):
    """Trova un utente dal suo username (che è l'email)."""
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("SELECT * FROM Utenti WHERE email = %s", (email.lower(),))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"[ERRORE] Errore in trova_utente_per_email: {e}")
        return None

def imposta_password_temporanea(id_utente, temp_password_hash):
    """Imposta una password temporanea e forza il cambio al prossimo login."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Utenti SET password_hash = %s, forza_cambio_password = %s WHERE id_utente = %s",
                        (temp_password_hash, True, id_utente))
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


def cambia_password_e_username(id_utente, nuovo_password_hash, nuovo_username):
    """Cambia password e username, rimuovendo il flag di cambio forzato."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE Utenti 
                SET password_hash = %s, username = %s, forza_cambio_password = FALSE 
                WHERE id_utente = %s
            """, (nuovo_password_hash, nuovo_username, id_utente))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore cambio password e username: {e}")
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
            
            # Decrypt PII if master key is provided
            if master_key_b64:
                print("[DEBUG] Decriptazione profilo con master key...")
                dati['nome'] = _decrypt_if_key(dati.get('nome'), master_key_b64)
                dati['cognome'] = _decrypt_if_key(dati.get('cognome'), master_key_b64)
                dati['codice_fiscale'] = _decrypt_if_key(dati.get('codice_fiscale'), master_key_b64)
                dati['indirizzo'] = _decrypt_if_key(dati.get('indirizzo'), master_key_b64)
            else:
                print("[DEBUG] Nessuna master key fornita per decriptazione profilo.")
                
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
            if master_key_b64 and campo in campi_sensibili:
                print(f"[DEBUG] Criptazione campo {campo}...")
                valore_da_salvare = _encrypt_if_key(valore, master_key_b64)
            
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
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante l'aggiornamento del profilo: {e}")
        return False

# --- Funzioni Gestione Inviti ---
def crea_invito(id_famiglia, email, ruolo):
    token = generate_token()
    if ruolo not in ['admin', 'livello1', 'livello2', 'livello3']:
        return None
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("INSERT INTO Inviti (id_famiglia, email_invitato, token, ruolo_assegnato) VALUES (%s, %s, %s, %s)",
                        (id_famiglia, email.lower(), token, ruolo))
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
                cur.execute("DELETE FROM Inviti WHERE token = %s", (token,))
                con.commit()
                return dict(invito)
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
                                   WHEN C.tipo = 'Fondo Pensione' THEN COALESCE(C.valore_manuale, 0.0)
                                   WHEN C.tipo = 'Investimento'
                                       THEN (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                             FROM Asset A
                                             WHERE A.id_conto = C.id_conto)
                                   ELSE (SELECT COALESCE(SUM(T.importo), 0.0) FROM Transazioni T WHERE T.id_conto = C.id_conto) +
                                        COALESCE(C.rettifica_saldo, 0.0)
                                   END AS saldo_calcolato
                        FROM Conti C
                        WHERE C.id_utente = %s
                        ORDER BY C.nome_conto
                        """, (id_utente,))
            results = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            if master_key:
                for row in results:
                    row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
                    row['iban'] = _decrypt_if_key(row['iban'], master_key, crypto)
            
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
                 # It seems if valore_manuale IS None, it did NOTHING? That looks like a bug or I missed something.
                 # Ah, looking at the original code:
                 # if valore_manuale is not None:
                 #    cur.execute(...)
                 # It implies that if valore_manuale is None, NO UPDATE happens? That seems wrong for a "modifica_conto" function.
                 # Let's assume I should handle the case where valore_manuale is None by NOT updating it, but updating others.
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
                 # Let's look at the original code again very carefully.
                 pass

            # RE-READING ORIGINAL CODE:
            # if valore_manuale is not None:
            #     cur.execute("UPDATE ...")
            # 
            # This means for normal accounts (where valore_manuale is None), the update is SKIPPED!
            # This looks like a bug in the existing code, or I am misinterpreting "valore_manuale is not None".
            # If I modify a "Corrente" account, valore_manuale is None. So the update is skipped?
            # User said "Ho modificato ula transazione...". Maybe they haven't modified accounts yet?
            # Or maybe I should fix this "bug" too?
            # Wait, let's check ContoDialog again.
            # Line 334: valore_manuale_modifica = saldo_iniziale if tipo == 'Fondo Pensione' else None
            # If I change the name of a checking account, valore_manuale is None.
            # So `modifica_conto` returns `cur.rowcount > 0` which will be False (initially 0? No, if execute is not called...).
            # Actually if execute is not called, it returns `UnboundLocalError` for `cur`? No, `cur` is defined.
            # But `cur.rowcount` would be -1 or 0.
            # So `modifica_conto` returns False.
            # So the user probably CANNOT modify normal accounts right now?
            # I should fix this logic to update other fields even if valore_manuale is None.
            
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
                               COALESCE(SUM(T.importo), 0.0) + COALESCE(CC.rettifica_saldo, 0.0) AS saldo_calcolato
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
                            row['nome_conto'] = _decrypt_if_key(row['nome_conto'], family_keys[fam_id], crypto)
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
                               COALESCE(SUM(T.importo), 0.0) + COALESCE(CC.rettifica_saldo, 0.0) AS saldo_calcolato
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
                        SELECT U.id_utente, COALESCE(U.nome || ' ' || U.cognome, U.username) AS nome_visualizzato
                        FROM Utenti U
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                        ORDER BY nome_visualizzato
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
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


def ottieni_tutti_i_conti_famiglia(id_famiglia, master_key_b64=None):
    """
    Restituisce una lista unificata di TUTTI i conti (personali e condivisi)
    di una data famiglia, escludendo quelli di investimento.
    """
    try:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()

            # Conti Personali di tutti i membri della famiglia
            cur.execute("""
                        SELECT C.id_conto, C.nome_conto, C.tipo, 0 as is_condiviso, U.nome as proprietario
                        FROM Conti C
                                 JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                        WHERE AF.id_famiglia = %s
                        """, (id_famiglia,))
            conti_personali = [dict(row) for row in cur.fetchall()]

            # Conti Condivisi della famiglia
            cur.execute("""
                        SELECT id_conto_condiviso as id_conto,
                               nome_conto,
                               tipo,
                               1                  as is_condiviso,
                               'Condiviso'        as proprietario
                        FROM ContiCondivisi
                        WHERE id_famiglia = %s
                        """, (id_famiglia,))
            conti_condivisi = [dict(row) for row in cur.fetchall()]
            
            results = conti_personali + conti_condivisi
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            if master_key:
                for row in results:
                    row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)

            return results

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero di tutti i conti famiglia: {e}")
        return []


def esegui_giroconto(id_sorgente, tipo_sorgente, id_destinazione, tipo_destinazione, importo, data, descrizione,
                     id_utente_autore, master_key_b64=None):
    """
    Esegue un giroconto tra due conti (personali o condivisi).
    Crea due transazioni opposte in modo atomico.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")

            desc_sorgente = f"Giroconto Uscita: {descrizione}"
            desc_destinazione = f"Giroconto Entrata: {descrizione}"

            # Debito sul conto sorgente
            if tipo_sorgente == 'P':
                aggiungi_transazione(id_sorgente, data, desc_sorgente, -abs(importo), cursor=cur, master_key_b64=master_key_b64)
            elif tipo_sorgente == 'C':
                aggiungi_transazione_condivisa(id_utente_autore, id_sorgente, data, desc_sorgente, -abs(importo),
                                               cursor=cur, master_key_b64=master_key_b64)

            # Credito sul conto destinazione
            if tipo_destinazione == 'P':
                aggiungi_transazione(id_destinazione, data, desc_destinazione, abs(importo), cursor=cur, master_key_b64=master_key_b64)
            elif tipo_destinazione == 'C':
                aggiungi_transazione_condivisa(id_utente_autore, id_destinazione, data, desc_destinazione, abs(importo),
                                               cursor=cur, master_key_b64=master_key_b64)

            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'esecuzione del giroconto: {e}")
        if con: con.rollback()
        return False


# --- Funzioni Categorie ---
def aggiungi_categoria(id_famiglia, nome_categoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("INSERT INTO Categorie (id_famiglia, nome_categoria) VALUES (%s, %s) RETURNING id_categoria",
                        (id_famiglia, nome_categoria.upper()))
            return cur.fetchone()['id_categoria']
    except Exception:
        return None
    except Exception as e:
        print(f"[ERRORE] Errore generico: {e}")
        return None


def modifica_categoria(id_categoria, nuovo_nome):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("UPDATE Categorie SET nome_categoria = %s WHERE id_categoria = %s",
                        (nuovo_nome.upper(), id_categoria))
            return cur.rowcount > 0
    except Exception:
        return False
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la modifica della categoria: {e}")
        return False


def elimina_categoria(id_categoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione della categoria: {e}")
        return False


def ottieni_categorie(id_famiglia):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("SELECT id_categoria, nome_categoria FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero categorie: {e}")
        return []

# --- Funzioni Sottocategorie ---
def aggiungi_sottocategoria(id_categoria, nome_sottocategoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("INSERT INTO Sottocategorie (id_categoria, nome_sottocategoria) VALUES (%s, %s) RETURNING id_sottocategoria",
                        (id_categoria, nome_sottocategoria.upper()))
            return cur.fetchone()['id_sottocategoria']
    except Exception:
        return None
    except Exception as e:
        print(f"[ERRORE] Errore durante l'aggiunta della sottocategoria: {e}")
        return None

def modifica_sottocategoria(id_sottocategoria, nuovo_nome):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Sottocategorie SET nome_sottocategoria = %s WHERE id_sottocategoria = %s",
                        (nuovo_nome.upper(), id_sottocategoria))
            return cur.rowcount > 0
    except Exception:
        return False
    except Exception as e:
        print(f"[ERRORE] Errore durante la modifica della sottocategoria: {e}")
        return False

def elimina_sottocategoria(id_sottocategoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM Sottocategorie WHERE id_sottocategoria = %s", (id_sottocategoria,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore durante l'eliminazione della sottocategoria: {e}")
        return False

def ottieni_sottocategorie(id_categoria):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("SELECT id_sottocategoria, nome_sottocategoria FROM Sottocategorie WHERE id_categoria = %s", (id_categoria,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore durante il recupero sottocategorie: {e}")
        return []

def ottieni_categorie_e_sottocategorie(id_famiglia):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                SELECT C.id_categoria, C.nome_categoria, S.id_sottocategoria, S.nome_sottocategoria
                FROM Categorie C
                LEFT JOIN Sottocategorie S ON C.id_categoria = S.id_categoria
                WHERE C.id_famiglia = %s
                ORDER BY C.nome_categoria, S.nome_sottocategoria
            """, (id_famiglia,))
            
            categorie = {}
            for row in cur.fetchall():
                if row['id_categoria'] not in categorie:
                    categorie[row['id_categoria']] = {
                        'nome_categoria': row['nome_categoria'],
                        'sottocategorie': []
                    }
                if row['id_sottocategoria']:
                    categorie[row['id_categoria']]['sottocategorie'].append({
                        'id_sottocategoria': row['id_sottocategoria'],
                        'nome_sottocategoria': row['nome_sottocategoria'],
                        'id_categoria': row['id_categoria']
                    })
            return categorie
    except Exception as e:
        print(f"[ERRORE] Errore durante il recupero di categorie e sottocategorie: {e}")
        return {}


# --- Funzioni Transazioni Personali ---
def aggiungi_transazione(id_conto, data, descrizione, importo, id_sottocategoria=None, cursor=None, master_key_b64=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_descrizione = _encrypt_if_key(descrizione, master_key, crypto)
    
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
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_descrizione = _encrypt_if_key(descrizione, master_key, crypto)

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
                               COALESCE(Cat.nome_categoria || ' - ' || SCat.nome_sottocategoria, Cat.nome_categoria, SCat.nome_sottocategoria) AS nome_sottocategoria,
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
                               COALESCE(Cat.nome_categoria || ' - ' || SCat.nome_sottocategoria, Cat.nome_categoria, SCat.nome_sottocategoria) AS nome_sottocategoria,
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
            if master_key:
                for row in results:
                    row['descrizione'] = _decrypt_if_key(row['descrizione'], master_key, crypto)
                    row['nome_conto'] = _decrypt_if_key(row['nome_conto'], master_key, crypto)
            
            return results
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero transazioni: {e}")
        return []


# --- Funzioni Transazioni Condivise ---
def aggiungi_transazione_condivisa(id_utente_autore, id_conto_condiviso, data, descrizione, importo, id_sottocategoria=None,
                                   cursor=None, master_key_b64=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_descrizione = _encrypt_if_key(descrizione, master_key, crypto)
    
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


def modifica_transazione_condivisa(id_transazione_condivisa, data, descrizione, importo, id_sottocategoria=None, master_key_b64=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    encrypted_descrizione = _encrypt_if_key(descrizione, master_key, crypto)
    
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
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("DELETE FROM TransazioniCondivise WHERE id_transazione_condivisa = %s",
                        (id_transazione_condivisa,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'eliminazione transazione condivisa: {e}")
        return None


def ottieni_transazioni_condivise_utente(id_utente):
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
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero transazioni condivise utente: {e}")
        return []


def ottieni_transazioni_condivise_famiglia(id_famiglia):
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
            return [dict(row) for row in cur.fetchall()]
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


def ottieni_totali_famiglia(id_famiglia):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            # Query semplificata e più robusta per calcolare il patrimonio totale per membro.
            # Unisce i saldi dei conti personali, il valore degli investimenti e dei fondi pensione.
            # Il calcolo della quota dei conti condivisi è stato rimosso da qui per semplificare
            # e può essere gestito in una funzione separata se necessario per questa vista.
            cur.execute("""
                        SELECT U.id_utente,
                                COALESCE(U.nome || ' ' || U.cognome, U.username) AS nome_visualizzato,
                                (
                                    -- Somma della liquidità (conti correnti/risparmio)
                                    COALESCE((SELECT SUM(T.importo)
                                              FROM Transazioni T
                                                       JOIN Conti C ON T.id_conto = C.id_conto
                                              WHERE C.id_utente = U.id_utente
                                                AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')), 0.0)
                                        +
                                        -- Somma del valore degli investimenti
                                    COALESCE((SELECT SUM(A.quantita * A.prezzo_attuale_manuale)
                                              FROM Asset A
                                                       JOIN Conti C ON A.id_conto = C.id_conto
                                              WHERE C.id_utente = U.id_utente
                                                AND C.tipo = 'Investimento'), 0.0)
                                        +
                                        -- Somma del valore dei fondi pensione
                                    COALESCE((SELECT SUM(C.valore_manuale)
                                              FROM Conti C
                                              WHERE C.id_utente = U.id_utente AND C.tipo = 'Fondo Pensione'), 0.0)
                                    )                                            as saldo_totale
                        FROM Utenti U
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                        GROUP BY U.id_utente, nome_visualizzato
                        ORDER BY nome_visualizzato;
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero totali famiglia: {e}")
        return []


def ottieni_riepilogo_patrimonio_famiglia_aggregato(id_famiglia, anno, mese):
    """
    Calcola la liquidità totale, gli investimenti totali e il patrimonio netto per un'intera famiglia.
    """
    data_fine = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).strftime('%Y-%m-%d')

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            print(
                f"DEBUG (ottieni_riepilogo_patrimonio_famiglia_aggregato): Calcolo patrimonio per famiglia {id_famiglia}")

            # 1. Liquidità totale (Conti personali + Conti condivisi + Rettifiche personali)
            cur.execute("""
                        SELECT (SELECT COALESCE(SUM(T.importo), 0.0)
                                FROM Transazioni T
                                         JOIN Conti C ON T.id_conto = C.id_conto
                                         JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                WHERE AF.id_famiglia = %s
                                  AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')
                                  AND T.data <= %s)
                                   +
                               (SELECT COALESCE(SUM(TC.importo), 0.0)
                                FROM TransazioniCondivise TC
                                         JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                WHERE CC.id_famiglia = %s
                                  AND TC.data <= %s)
                                   +
                               (SELECT COALESCE(SUM(C.rettifica_saldo), 0.0)
                                FROM Conti C
                                         JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                WHERE AF.id_famiglia = %s
                                  AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')) AS liquidita_totale
                        """, (id_famiglia, data_fine, id_famiglia, data_fine, id_famiglia))
            liquidita_totale = cur.fetchone()['liquidita_totale'] or 0.0
            print(f"DEBUG (ottieni_riepilogo_patrimonio_famiglia_aggregato): Liquidità totale: {liquidita_totale}")

            # 2. Investimenti totali (Asset + Fondi Pensione di tutti gli utenti della famiglia)
            cur.execute("""
                        SELECT (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                FROM Asset A
                                         JOIN Conti C ON A.id_conto = C.id_conto
                                         JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                WHERE AF.id_famiglia = %s
                                  AND C.tipo = 'Investimento')
                                   +
                               (SELECT COALESCE(SUM(C.valore_manuale), 0.0)
                                FROM Conti C
                                         JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                WHERE AF.id_famiglia = %s
                                  AND C.tipo = 'Fondo Pensione') AS investimenti_totali
                        """, (id_famiglia, id_famiglia))
            investimenti_totali = cur.fetchone()['investimenti_totali'] or 0.0
            print(
                f"DEBUG (ottieni_riepilogo_patrimonio_famiglia_aggregato): Investimenti totali: {investimenti_totali}")

            patrimonio_netto = liquidita_totale + investimenti_totali
            print(f"DEBUG (ottieni_riepilogo_patrimonio_famiglia_aggregato): Patrimonio netto: {patrimonio_netto}")

            return {'liquidita': liquidita_totale, 'investimenti': investimenti_totali,
                    'patrimonio_netto': patrimonio_netto}
    except Exception as e:
        print(f"[ERRORE] Errore durante il calcolo del riepilogo patrimonio famiglia aggregato: {e}")
        return {'liquidita': 0, 'investimenti': 0, 'patrimonio_netto': 0}


def ottieni_riepilogo_patrimonio_utente(id_utente, anno, mese):
    """
    Calcola la liquidità, gli investimenti e il patrimonio netto per un singolo utente,
    includendo la sua quota dei conti condivisi.
    """
    data_fine = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).strftime('%Y-%m-%d')

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            print(f"DEBUG (ottieni_riepilogo_patrimonio_utente): Calcolo patrimonio per utente {id_utente}")

            # 1. Liquidità personale (conti non di investimento)
            cur.execute("""
                        SELECT COALESCE(SUM(T.importo), 0.0) as liquidita_transazioni
                        FROM Transazioni T
                                 JOIN Conti C ON T.id_conto = C.id_conto
                        WHERE C.id_utente = %s
                          AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')
                          AND T.data <= %s
                        """, (id_utente, data_fine))
            liquidita_transazioni = cur.fetchone()['liquidita_transazioni'] or 0.0

            cur.execute("""
                        SELECT COALESCE(SUM(rettifica_saldo), 0.0) as rettifiche_personali
                        FROM Conti
                        WHERE id_utente = %s
                          AND tipo NOT IN ('Investimento', 'Fondo Pensione')
                        """, (id_utente,))
            rettifiche_personali = cur.fetchone()['rettifiche_personali'] or 0.0
            liquidita_personale = liquidita_transazioni + rettifiche_personali
            print(
                f"DEBUG (ottieni_riepilogo_patrimonio_utente): Liquidità personale (solo conti privati): {liquidita_personale}")

            # 2. Investimenti personali (Asset + Fondi Pensione)
            cur.execute("""
                        SELECT (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                FROM Asset A
                                         JOIN Conti C ON A.id_conto = C.id_conto
                                WHERE C.id_utente = %s
                                  AND C.tipo = 'Investimento')
                                   +
                               (SELECT COALESCE(SUM(C.valore_manuale), 0.0)
                                FROM Conti C
                                WHERE C.id_utente = %s
                                  AND C.tipo = 'Fondo Pensione') as investimenti_personali
                        """, (id_utente, id_utente))
            investimenti_personali = cur.fetchone()['investimenti_personali'] or 0.0
            print(
                f"DEBUG (ottieni_riepilogo_patrimonio_utente): Investimenti personali (solo conti privati): {investimenti_personali}")

            # 3. Quota parte dei conti condivisi (Logica rivista per maggiore robustezza)
            quota_condivisa = 0.0

            # Ottiene tutti i conti condivisi a cui l'utente partecipa e il numero di partecipanti per ciascuno
            cur.execute("""
                        SELECT CC.id_conto_condiviso,
                               (SELECT COALESCE(SUM(importo), 0.0)
                                FROM TransazioniCondivise
                                WHERE id_conto_condiviso = CC.id_conto_condiviso
                                  AND data <= %s) as saldo_conto,
                               CASE
                                   WHEN CC.tipo_condivisione = 'famiglia' THEN (SELECT COUNT(*)
                                                                                FROM Appartenenza_Famiglia
                                                                                WHERE id_famiglia = CC.id_famiglia)
                                   ELSE (SELECT COUNT(*)
                                         FROM PartecipazioneContoCondiviso
                                         WHERE id_conto_condiviso = CC.id_conto_condiviso)
                                   END           as num_partecipanti
                        FROM ContiCondivisi CC
                        WHERE CC.id_conto_condiviso IN (
                            -- Conti a cui partecipo direttamente
                            SELECT id_conto_condiviso
                            FROM PartecipazioneContoCondiviso
                            WHERE id_utente = %s
                            UNION
                            -- Conti della mia famiglia
                            SELECT id_conto_condiviso
                            FROM ContiCondivisi
                            WHERE tipo_condivisione = 'famiglia'
                              AND id_famiglia = (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s))
                        """, (data_fine, id_utente, id_utente))

            conti_condivisi_da_calcolare = cur.fetchall()
            print(
                f"DEBUG (ottieni_riepilogo_patrimonio_utente): Conti condivisi da calcolare: {conti_condivisi_da_calcolare}")

            for row in conti_condivisi_da_calcolare:
                id_conto_cond = row['id_conto_condiviso']
                saldo_conto = float(row['saldo_conto']) if row['saldo_conto'] is not None else 0.0
                num_partecipanti = int(row['num_partecipanti']) if row['num_partecipanti'] is not None else 0
                
                if num_partecipanti > 0:
                    quota_condivisa += (saldo_conto / num_partecipanti)
                    print(
                        f"DEBUG (ottieni_riepilogo_patrimonio_utente):   Conto ID {id_conto_cond}, Saldo: {saldo_conto}, Partecipanti: {num_partecipanti}, Quota: {saldo_conto / num_partecipanti}")
                else:
                    print(
                        f"DEBUG (ottieni_riepilogo_patrimonio_utente):   Conto ID {id_conto_cond} saltato (0 partecipanti).")

            print(f"DEBUG (ottieni_riepilogo_patrimonio_utente): Quota condivisa totale: {quota_condivisa}")

            liquidita_totale = liquidita_personale + quota_condivisa
            patrimonio_netto = liquidita_totale + investimenti_personali

            return {'liquidita': liquidita_totale, 'investimenti': investimenti_personali,
                    'patrimonio_netto': patrimonio_netto}
    except Exception as e:
        print(f"[ERRORE] Errore durante il calcolo del riepilogo patrimonio utente: {e}")
        return {'liquidita': 0, 'investimenti': 0, 'patrimonio_netto': 0}


def ottieni_dettagli_famiglia(id_famiglia, anno, mese):
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"

    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        -- Transazioni Personali
                        SELECT COALESCE(U.nome || ' ' || U.cognome, U.username) AS utente_nome,
                               T.data,
                               T.descrizione,
                               COALESCE(Cat.nome_categoria || ' - ' || SCat.nome_sottocategoria, Cat.nome_categoria, SCat.nome_sottocategoria) AS nome_sottocategoria,
                               C.nome_conto                                     AS conto_nome,
                               T.importo
                        FROM Transazioni T
                                 JOIN Conti C ON T.id_conto = C.id_conto
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                                 LEFT JOIN Sottocategorie SCat ON T.id_sottocategoria = SCat.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON SCat.id_categoria = Cat.id_categoria
                        WHERE AF.id_famiglia = %s
                          AND C.tipo != 'Fondo Pensione' AND T.data BETWEEN %s AND %s AND UPPER(T.descrizione) NOT LIKE '%%SALDO INIZIALE%%'
                        UNION ALL
                        -- Transazioni Condivise
                        SELECT COALESCE(U.nome || ' ' || U.cognome, U.username) AS utente_nome,
                               TC.data,
                               TC.descrizione,
                               COALESCE(Cat.nome_categoria || ' - ' || SCat.nome_sottocategoria, Cat.nome_categoria, SCat.nome_sottocategoria) AS nome_sottocategoria,
                               CC.nome_conto                                    AS conto_nome,
                               TC.importo
                        FROM TransazioniCondivise TC
                                 JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                 LEFT JOIN Utenti U
                                           ON TC.id_utente_autore = U.id_utente -- Join per ottenere il nome dell'autore
                                 LEFT JOIN Sottocategorie SCat ON TC.id_sottocategoria = SCat.id_sottocategoria
                                 LEFT JOIN Categorie Cat ON SCat.id_categoria = Cat.id_categoria
                        WHERE CC.id_famiglia = %s
                          AND TC.data BETWEEN %s AND %s
                          AND UPPER(TC.descrizione) NOT LIKE '%%SALDO INIZIALE%%' -- Include tutti i conti condivisi della famiglia
                        ORDER BY data DESC, utente_nome, conto_nome
                        """, (id_famiglia, data_inizio, data_fine, id_famiglia, data_inizio, data_fine))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero dettagli famiglia: {e}")
        return []


def ottieni_membri_famiglia(id_famiglia):
    try:
        with get_db_connection() as con:
            # con.row_factory = sqlite3.Row # Removed for Supabase
            cur = con.cursor()
            cur.execute("""
                        SELECT U.id_utente,
                               U.username,
                               COALESCE(U.nome || ' ' || U.cognome, U.username) AS nome_visualizzato,
                               AF.ruolo
                        FROM Utenti U
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                        ORDER BY nome_visualizzato
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero membri: {e}")
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
def imposta_budget(id_famiglia, id_sottocategoria, importo_limite):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        INSERT INTO Budget (id_famiglia, id_sottocategoria, importo_limite, periodo)
                        VALUES (?, %s, %s, 'Mensile') ON CONFLICT(id_famiglia, id_sottocategoria, periodo) DO
                        UPDATE SET importo_limite = excluded.importo_limite
                        """, (id_famiglia, id_sottocategoria, importo_limite))
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'impostazione del budget: {e}")
        return False

def ottieni_budget_famiglia(id_famiglia):
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
                        ORDER BY C.nome_categoria, S.nome_sottocategoria
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero budget: {e}")
        return []


def ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese):
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
                    COALESCE(BS.importo_limite, B.importo_limite, 0.0) as importo_limite,
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
                ) AS T_SPESE ON S.id_sottocategoria = T_SPESE.id_sottocategoria
                WHERE C.id_famiglia = %s
                ORDER BY C.nome_categoria, S.nome_sottocategoria;
            """, (anno, mese, id_famiglia, data_inizio, data_fine, id_famiglia, data_inizio, data_fine, id_famiglia))
            
            riepilogo = {}
            for row in cur.fetchall():
                cat_id = row['id_categoria']
                if cat_id not in riepilogo:
                    riepilogo[cat_id] = {
                        'nome_categoria': row['nome_categoria'],
                        'importo_limite_totale': 0,
                        'spesa_totale_categoria': 0,
                        'sottocategorie': []
                    }
                
                spesa = abs(row['spesa_totale'])
                limite = row['importo_limite']
                riepilogo[cat_id]['importo_limite_totale'] += limite
                riepilogo[cat_id]['spesa_totale_categoria'] += spesa
                
                riepilogo[cat_id]['sottocategorie'].append({
                    'id_sottocategoria': row['id_sottocategoria'],
                    'nome_sottocategoria': row['nome_sottocategoria'],
                    'importo_limite': limite,
                    'spesa_totale': spesa,
                    'rimanente': limite - spesa
                })
            
            # Calcola il rimanente totale per categoria
            for cat_id in riepilogo:
                riepilogo[cat_id]['rimanente_totale'] = riepilogo[cat_id]['importo_limite_totale'] - riepilogo[cat_id]['spesa_totale_categoria']

            return riepilogo

    except Exception as e:
        print(f"[ERRORE] Errore generico durante il recupero riepilogo budget: {e}")
        return {}


def salva_budget_mese_corrente(id_famiglia, anno, mese):
    try:
        riepilogo_corrente = ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese)
        if not riepilogo_corrente:
            return False
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            dati_da_salvare = []
            # Salva per ogni sottocategoria
            for cat_id, cat_data in riepilogo_corrente.items():
                for sub_data in cat_data['sottocategorie']:
                    dati_da_salvare.append((
                        id_famiglia, sub_data['id_sottocategoria'], sub_data['nome_sottocategoria'],
                        anno, mese, sub_data['importo_limite'], abs(sub_data['spesa_totale'])
                    ))
            
            cur.executemany("""
                            INSERT INTO Budget_Storico (id_famiglia, id_sottocategoria, nome_sottocategoria, anno, mese,
                                                        importo_limite, importo_speso)
                            VALUES (?, %s, %s, %s, %s, %s, %s) ON CONFLICT(id_famiglia, id_sottocategoria, anno, mese) DO
                            UPDATE SET importo_limite = excluded.importo_limite, importo_speso = excluded.importo_speso, nome_sottocategoria = excluded.nome_sottocategoria
                            """, dati_da_salvare)
            return True
    except Exception as e:
        print(f"[ERRORE] Errore generico durante la storicizzazione del budget: {e}")
        return False


def storicizza_budget_retroattivo(id_famiglia):
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
                if salva_budget_mese_corrente(id_famiglia, anno, mese):
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
def aggiungi_prestito(id_famiglia, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                      importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default=None,
                      id_conto_condiviso_default=None, id_sottocategoria_default=None, addebito_automatico=False):
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
                        """, (id_famiglia, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                              importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default,
                              id_conto_condiviso_default, id_sottocategoria_default, addebito_automatico))
            return cur.fetchone()['id_prestito']
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiunta del prestito: {e}")
        return None


def modifica_prestito(id_prestito, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                      importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default=None,
                      id_conto_condiviso_default=None, id_sottocategoria_default=None, addebito_automatico=False):
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
                        """, (nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                              importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default,
                              id_conto_condiviso_default, id_sottocategoria_default, addebito_automatico, id_prestito))
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


def ottieni_prestiti_famiglia(id_famiglia):
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
            return [dict(row) for row in cur.fetchall()]
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
                "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo) VALUES (?, %s, %s, %s, %s)",
                (id_conto_pagamento, id_sottocategoria, data_pagamento, descrizione, -abs(importo_pagato)))
            data_dt = parse_date(data_pagamento)
            cur.execute(
                "INSERT INTO StoricoPagamentiRate (id_prestito, anno, mese, data_pagamento, importo_pagato) VALUES (?, %s, %s, %s, %s) ON CONFLICT(id_prestito, anno, mese) DO NOTHING",
                (id_prestito, data_dt.year, data_dt.month, data_pagamento, importo_pagato))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'esecuzione del pagamento rata: {e}")
        if con: con.rollback()
        return False


# --- Funzioni Immobili ---
def aggiungi_immobile(id_famiglia, nome, via, citta, valore_acquisto, valore_attuale, nuda_proprieta,
                      id_prestito_collegato=None):
    # Converti il valore del dropdown in int se necessario
    db_id_prestito = None
    if id_prestito_collegato is not None and id_prestito_collegato != "None":
        try:
            db_id_prestito = int(id_prestito_collegato)
        except (ValueError, TypeError):
            db_id_prestito = None
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # cur.execute("PRAGMA foreign_keys = ON;") # Removed for Supabase
            cur.execute("""
                        INSERT INTO Immobili (id_famiglia, nome, via, citta, valore_acquisto, valore_attuale,
                                              nuda_proprieta, id_prestito_collegato)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_immobile
                        """,
                        (id_famiglia, nome, via, citta, valore_acquisto, valore_attuale, 1 if nuda_proprieta else 0,
                         db_id_prestito))
            return cur.fetchone()['id_immobile']
    except Exception as e:
        print(f"[ERRORE] Errore generico durante l'aggiunta dell'immobile: {e}")
        return None


def modifica_immobile(id_immobile, nome, via, citta, valore_acquisto, valore_attuale, nuda_proprieta,
                      id_prestito_collegato=None):
    # Converti il valore del dropdown in int se necessario
    db_id_prestito = None
    if id_prestito_collegato is not None and id_prestito_collegato != "None":
        try:
            db_id_prestito = int(id_prestito_collegato)
        except (ValueError, TypeError):
            db_id_prestito = None
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
                        (nome, via, citta, valore_acquisto, valore_attuale, 1 if nuda_proprieta else 0, db_id_prestito,
                         id_immobile))
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


def ottieni_immobili_famiglia(id_famiglia):
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
            return [dict(row) for row in cur.fetchall()]
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
                        SELECT COALESCE(U.nome || ' ' || U.cognome, U.username)                      AS membro,
                               C.nome_conto,
                               A.ticker,
                               A.nome_asset,
                               A.quantita,
                               A.costo_iniziale_unitario,
                               A.prezzo_attuale_manuale,
                               (A.prezzo_attuale_manuale - A.costo_iniziale_unitario)                AS gain_loss_unitario,
                               (A.quantita * (A.prezzo_attuale_manuale - A.costo_iniziale_unitario)) AS gain_loss_totale,
                               (A.quantita * A.prezzo_attuale_manuale)                               AS valore_totale
                        FROM Asset A
                                 JOIN Conti C ON A.id_conto = C.id_conto
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s
                          AND C.tipo = 'Investimento'
                        ORDER BY membro, C.nome_conto, A.ticker
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
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
                        giorno_addebito, attiva, addebito_automatico=False):
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
            """, (id_famiglia, nome, importo, id_conto_personale, id_conto_condiviso, id_categoria, id_sottocategoria, giorno_addebito,
                  1 if attiva else 0, 1 if addebito_automatico else 0))
            return cur.fetchone()['id_spesa_fissa']
    except Exception as e:
        print(f"[ERRORE] Errore durante l'aggiunta della spesa fissa: {e}")
        return None


def modifica_spesa_fissa(id_spesa_fissa, nome, importo, id_conto_personale, id_conto_condiviso, id_sottocategoria,
                        giorno_addebito, attiva, addebito_automatico=False):
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
            """, (nome, importo, id_conto_personale, id_conto_condiviso, id_categoria, id_sottocategoria, giorno_addebito,
                  1 if attiva else 0, 1 if addebito_automatico else 0, id_spesa_fissa))
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


def ottieni_spese_fisse_famiglia(id_famiglia):
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
                    COALESCE(CP.nome_conto, CC.nome_conto) as nome_conto
                FROM SpeseFisse SF
                LEFT JOIN Conti CP ON SF.id_conto_personale_addebito = CP.id_conto
                LEFT JOIN ContiCondivisi CC ON SF.id_conto_condiviso_addebito = CC.id_conto_condiviso
                WHERE SF.id_famiglia = %s
                ORDER BY SF.nome
            """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore durante il recupero delle spese fisse: {e}")
        return []


def check_e_processa_spese_fisse(id_famiglia):
    oggi = datetime.date.today()
    spese_eseguite = 0
    try:
        spese_da_processare = ottieni_spese_fisse_famiglia(id_famiglia)
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

