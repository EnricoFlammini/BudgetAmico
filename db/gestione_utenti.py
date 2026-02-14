"""
Funzioni utenti: login, registrazione, profilo, password
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
from utils.logger import setup_logger
from utils.crypto_manager import CryptoManager
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
import os

logger = setup_logger(__name__)
import hashlib
import secrets
import string
import base64
from utils.cache_manager import cache_manager

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code, verify_password_hash,
    SERVER_SECRET_KEY,
    crypto as _crypto_instance
)

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
            
            export_data = {
                'versione_export': '1.0',
                'data_export': datetime.datetime.now().isoformat(),
                'id_famiglia': id_famiglia,
                'nome_famiglia': nome_famiglia,
                'family_key_b64': family_key_b64,
                'configurazioni': {}
            }
            
            return export_data, None
            
    except Exception as e:
        print(f"[ERRORE] Errore durante l'esportazione: {e}")
        return None, str(e)

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
            # Fetch also password_algo with fallback
            cur.execute("""
                SELECT id_utente, password_hash, password_algo, nome, cognome, username, email, 
                       forza_cambio_password, salt, encrypted_master_key, 
                       username_enc, email_enc, nome_enc_server, cognome_enc_server,
                       failed_login_attempts, lockout_until, sospeso, codice_utente_enc
                FROM Utenti 
                WHERE username_bindex = %s OR email_bindex = %s
            """, (u_bindex, u_bindex))
            risultato = cur.fetchone()
            
            # Fallback removed - we rely on migration
            if False: pass # Placeholder to minimize diff changes if needed, or simply remove


            # Fallback removed - we rely on migration
            if False: pass # Placeholder to minimize diff changes if needed, or simply remove


            if risultato:
                # --- RATE LIMITING CHECK ---
                if risultato.get('sospeso'):
                    return None, "Account sospeso. Contatta il supporto."
                
                if risultato.get('lockout_until'):
                    lockout_until = risultato['lockout_until']
                    # Ensure lockout_until is offset-aware or consistent with datetime.now()
                    # Supabase/Postgres returns TZ-aware datetime if column is TIMESTAMP WITH TIME ZONE
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if lockout_until > now:
                         minutes_left = int((lockout_until - now).total_seconds() / 60) + 1
                         return None, f"Account temporaneamente bloccato. Riprova tra {minutes_left} minuti."

                # --- PASSWORD VERIFICATION & LAZY MIGRATION ---
                stored_hash = risultato['password_hash']
                # Handle cases where password_algo might be NULL (if migration missed row or default issue)
                algo = risultato.get('password_algo') or 'sha256' 
                
                is_valid = verify_password_hash(password, stored_hash, algo)
                
                if not is_valid:
                     # --- HANDLE FAILED ATTEMPT ---
                     try:
                         attempts = (risultato.get('failed_login_attempts') or 0) + 1
                         now_utc = datetime.datetime.now(datetime.timezone.utc)
                         
                         updates = ["failed_login_attempts = %s", "last_failed_login = %s"]
                         params = [attempts, now_utc]
                         
                         error_msg = "Password errata."
                         
                         # Check capabilities
                         if attempts >= 15:
                             updates.append("sospeso = TRUE")
                             error_msg = "Account sospeso per troppi tentativi falliti. Controlla la tua email."
                             
                             # Send Email
                             try:
                                 from utils.email_sender import send_email
                                 email_dest = decrypt_system_data(risultato.get('email_enc')) or risultato.get('email')
                                 if email_dest:
                                     subject = "BudgetAmico - Avviso di Sicurezza: Account Sospeso"
                                     body = f"""
                                     <h2>Account Sospeso</h2>
                                     <p>Il tuo account è stato sospeso dopo {attempts} tentativi di accesso falliti consecutivi.</p>
                                     <p>Se non sei stato tu, qualcuno potrebbe non autorizzato sta provando ad accedere.</p>
                                     <p>Per riattivare l'account, contatta il supporto o l'amministratore di sistema.</p>
                                     """
                                     # Run email sending in background or just try-catch to not block DB op too long?
                                     # Blocking for simplicity here.
                                     send_email(email_dest, subject, body)
                             except Exception as e_mail:
                                 logger.error(f"Failed to send suspension email: {e_mail}")
                                 
                         elif attempts == 5 or attempts == 10:
                             lockout_duration = datetime.timedelta(minutes=5)
                             lockout_time = now_utc + lockout_duration
                             updates.append("lockout_until = %s")
                             params.append(lockout_time)
                             error_msg = f"Troppi tentativi falliti. Account bloccato per 5 minuti."
                         
                         params.append(risultato['id_utente'])
                         
                         with get_db_connection() as con_fail:
                             cur_fail = con_fail.cursor()
                             sql = f"UPDATE Utenti SET {', '.join(updates)} WHERE id_utente = %s"
                             cur_fail.execute(sql, tuple(params))
                             con_fail.commit()
                             
                         return None, error_msg

                     except Exception as e_fail:
                         logger.error(f"Error handling failed login: {e_fail}")
                         return None, "Errore durante login."

                     return None # return None implicit for verify_login usually means valid=False

                # --- SUCCESSFUL LOGIN ---
                # Reset counters if needed
                if (risultato.get('failed_login_attempts') or 0) > 0:
                    try:
                        with get_db_connection() as con_succ:
                            cur_succ = con_succ.cursor()
                            cur_succ.execute("UPDATE Utenti SET failed_login_attempts = 0, lockout_until = NULL WHERE id_utente = %s", (risultato['id_utente'],))
                            con_succ.commit()
                    except Exception as e_succ:
                        logger.error(f"Error resetting login counters: {e_succ}")

                # LAZY MIGRATION: If user is still on SHA256, upgrade to PBKDF2

                # LAZY MIGRATION: If user is still on SHA256, upgrade to PBKDF2
                if algo == 'sha256':
                    logger.info(f"LAZY MIGRATION: Upgrading password for user {risultato['id_utente']} to PBKDF2")
                    new_hash = hash_password(password, algo='pbkdf2')
                    try:
                        with get_db_connection() as con_up:
                            cur_up = con_up.cursor()
                            cur_up.execute("UPDATE Utenti SET password_hash = %s, password_algo = 'pbkdf2' WHERE id_utente = %s", 
                                          (new_hash, risultato['id_utente']))
                            con_up.commit()
                    except Exception as e:
                        logger.error(f"Failed to migrate password for user {risultato['id_utente']}: {e}")

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
                        return None, "Errore decriptazione dati protetti."

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
                    'codice_utente': decrypt_system_data(risultato.get('codice_utente_enc')) or "-",
                    'master_key': master_key.decode() if master_key else None,
                    'forza_cambio_password': risultato['forza_cambio_password'],
                    'sospeso': risultato.get('sospeso', False)
                }, None
            
            print("[DEBUG] Login fallito o password errata.")
            return None, "Username o password errati."
    except Exception as e:
        print(f"[ERRORE] Errore generico durante il login: {e}")
        return None, f"Errore di sistema: {str(e)}"



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
            codice_utente = generate_unique_code()
            cod_u_enc = encrypt_system_data(codice_utente)
            
            cur.execute("""
                INSERT INTO Utenti (username, email, password_hash, nome, cognome, forza_cambio_password, salt, encrypted_master_key, recovery_key_hash, encrypted_master_key_recovery, encrypted_master_key_backup, username_bindex, email_bindex, username_enc, email_enc, nome_enc_server, cognome_enc_server, codice_utente_enc)
                VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_utente
            """, (None, None, password_hash, None, None,
                  base64.urlsafe_b64encode(temp_salt).decode(),
                  base64.urlsafe_b64encode(encrypted_temp_mk).decode(),
                  recovery_key_hash,
                  base64.urlsafe_b64encode(encrypted_mk_recovery).decode(),
                  encrypted_mk_backup_b64,
                  u_bindex, e_bindex, u_enc, e_enc, n_enc_srv, c_enc_srv, cod_u_enc))
            
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
        enc_nome = crypto.encrypt_data(nome.title(), master_key)
        enc_cognome = crypto.encrypt_data(cognome.title(), master_key)
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
            u_bindex = compute_blind_index(username)
            e_bindex = compute_blind_index(email)
            
            # Pulisci eventuali tentativi precedenti non verificati
            cur.execute("DELETE FROM Utenti WHERE (username_bindex = %s OR email_bindex = %s) AND email_verificata = FALSE", (u_bindex, e_bindex))
            
            # NOTA: username e email legacy sono NULL - usiamo solo le versioni _bindex e _enc
            codice_utente = generate_unique_code()
            cod_u_enc = encrypt_system_data(codice_utente)

            cur.execute("""
                INSERT INTO Utenti (nome, cognome, username, password_hash, password_algo, email, data_nascita, codice_fiscale, indirizzo, salt, encrypted_master_key, recovery_key_hash, encrypted_master_key_recovery, encrypted_master_key_backup, username_bindex, email_bindex, username_enc, email_enc, nome_enc_server, cognome_enc_server, email_verificata, codice_utente_enc)
                VALUES (%s, %s, %s, %s, 'pbkdf2', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
                RETURNING id_utente
            """, (enc_nome, enc_cognome, None, password_hash, None, data_nascita, enc_cf, enc_indirizzo, 
                  base64.urlsafe_b64encode(salt).decode(), 
                  base64.urlsafe_b64encode(encrypted_mk).decode(),
                  recovery_key_hash,
                  base64.urlsafe_b64encode(encrypted_mk_recovery).decode(),
                  encrypted_mk_backup_b64,
                  u_bindex, e_bindex,
                  encrypt_system_data(username), encrypt_system_data(email),
                  encrypt_system_data(nome.title()), encrypt_system_data(cognome.title()), cod_u_enc))

            
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
                    password_algo = 'pbkdf2',
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

def cambia_password_e_username(id_utente: str, password_raw: str, nuovo_username: Optional[str] = None, nome: Optional[str] = None, cognome: Optional[str] = None, vecchia_password: Optional[str] = None) -> Dict[str, Any]:
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

        # Fetch current data if needed
        current_data = None
        if not nuovo_username or not nome or not cognome:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT username_enc, nome, cognome, nome_enc_server, cognome_enc_server FROM Utenti WHERE id_utente = %s", (id_utente,))
                current_data = cur.fetchone()

        # 2. Hash password
        password_hash = hash_password(password_raw)
        
        # 3. Handle PII (Nome/Cognome/Username)
        # Se non abbiamo i nuovi, proviamo a recuperare i vecchi
        if not nuovo_username and current_data:
            nuovo_username = decrypt_system_data(current_data['username_enc'])
        
        if not nome and current_data:
            if old_master_key and current_data['nome']:
                nome = crypto.decrypt_data(current_data['nome'], old_master_key)
            elif current_data['nome_enc_server']:
                nome = decrypt_system_data(current_data['nome_enc_server'])
        
        if not cognome and current_data:
            if old_master_key and current_data['cognome']:
                cognome = crypto.decrypt_data(current_data['cognome'], old_master_key)
            elif current_data['cognome_enc_server']:
                cognome = decrypt_system_data(current_data['cognome_enc_server'])

        # Se ancora non abbiamo i nomi (es. primo setup assoluto senza backup), usiamo placeholder o lasciamo None
        
        # 3.b Encrypt User PII for the new (or preserved) Master Key
        enc_nome = None
        enc_cognome = None
        if nome: enc_nome = crypto.encrypt_data(nome, master_key)
        if cognome: enc_cognome = crypto.encrypt_data(cognome, master_key)
        
        # 3.c Secure Username (Blind Index + Enc System)
        if not nuovo_username:
            raise ValueError("Username non disponibile e non fornito.")
            
        u_bindex = compute_blind_index(nuovo_username)
        u_enc = encrypt_system_data(nuovo_username)
        
        # 3.d Encrypt Server-Side Display Names (for Family Visibility)
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
                "master_key": base64.urlsafe_b64encode(master_key).decode(), # Return b64 string
                "username": nuovo_username
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
                    password_algo = 'pbkdf2',
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
            valore_da_salvare = valore.title() if campo in ['nome', 'cognome'] else valore
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
                            enc_server = encrypt_system_data(valore.title())
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
                nome = dati_profilo.get('nome', '') if 'nome' in dati_profilo else ''
                cognome = dati_profilo.get('cognome', '') if 'cognome' in dati_profilo else ''
                
                # If one is missing from update but we need it for display name, we'd need to fetch old.
                # However, Flet Settings view sends all fields. 
                # To be generic, let's title it.
                display_name = f"{nome.title()} {cognome.title()}".strip()
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

