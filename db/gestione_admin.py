"""
Funzioni admin: utenti, famiglie, statistiche, sicurezza
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

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code,
    hash_password, verify_password_hash,
    valida_iban_semplice,
    SERVER_SECRET_KEY,
    crypto as _crypto_instance
)

# Importazioni da altri moduli
from db.gestione_config import get_configurazione, save_system_config
from db.gestione_utenti import verifica_login, imposta_password_temporanea

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


def aggiorna_ultimo_accesso(id_utente: int) -> bool:
    """Aggiorna il timestamp di ultimo accesso/attività dell'utente."""
    if not id_utente:
        return False
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Utenti SET ultimo_accesso = CURRENT_TIMESTAMP WHERE id_utente = %s", (id_utente,))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore aggiorna_ultimo_accesso per utente {id_utente}: {e}")
        return False


def ottieni_statistiche_accessi() -> Dict[str, Any]:
    """
    Calcola le statistiche degli accessi basandoci sui log di sistema.
    Restituisce: { 
        'attivi_ora': int, 
        'lista_attivi': [str],
        '24h': {'unici': int, 'totali': int},
        '48h': {'unici': int, 'totali': int},
        '72h': {'unici': int, 'totali': int},
        '7d':  {'unici': int, 'totali': int},
        '30d': {'unici': int, 'totali': int},
        '1y':  {'unici': int, 'totali': int},
        'sempre': {'unici': int, 'totali': int}
    }
    """
    stats = {
        'attivi_ora': 0, 
        'lista_attivi': [],
        '24h': {'unici': 0, 'totali': 0},
        '48h': {'unici': 0, 'totali': 0},
        '72h': {'unici': 0, 'totali': 0},
        '7d':  {'unici': 0, 'totali': 0},
        '30d': {'unici': 0, 'totali': 0},
        '1y':  {'unici': 0, 'totali': 0},
        'sempre': {'unici': 0, 'totali': 0}
    }
    try:
        from db.gestione_db import decrypt_system_data
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Attivi ora (qualsiasi attività negli ultimi 15 minuti) + Recupero nomi
            # Usiamo la nuova colonna ultimo_accesso per maggiore precisione
            cur.execute("""
                SELECT id_utente, username as user_plain, username_enc as user_enc
                FROM Utenti
                WHERE ultimo_accesso > CURRENT_TIMESTAMP - INTERVAL '15 minutes'
            """)
            
            attivi_nomi = []
            for row in cur.fetchall():
                name = row['user_plain']
                if not name and row['user_enc']:
                    name = decrypt_system_data(row['user_enc'])
                
                if name:
                    attivi_nomi.append(name)
                else:
                    attivi_nomi.append(f"User #{row['id_utente']}")

            stats['attivi_ora'] = len(attivi_nomi)
            stats['lista_attivi'] = attivi_nomi[:5]
            
            # Funzione helper per le query dei periodi
            def get_period_stats(hours=None, all_time=False):
                if all_time:
                    cur.execute("""
                        SELECT COUNT(DISTINCT id_utente) as unici, COUNT(*) as totali
                        FROM Log_Sistema 
                        WHERE (messaggio LIKE 'LOGIN RIUSCITO%' OR messaggio LIKE '[NAV]%')
                    """)
                else:
                    cur.execute("""
                        SELECT COUNT(DISTINCT id_utente) as unici, COUNT(*) as totali
                        FROM Log_Sistema 
                        WHERE (messaggio LIKE 'LOGIN RIUSCITO%' OR messaggio LIKE '[NAV]%') 
                        AND timestamp > CURRENT_TIMESTAMP - (INTERVAL '1 hour' * %s)
                    """, (hours,))
                res = cur.fetchone()
                
                # fallback unici dalla colonna ultimo_accesso per periodi recenti (se i log sono disattivati)
                if not all_time and (hours and hours <= 72):
                    cur.execute("""
                        SELECT COUNT(*) as unici_from_table
                        FROM Utenti
                        WHERE ultimo_accesso > CURRENT_TIMESTAMP - (INTERVAL '1 hour' * %s)
                    """, (hours,))
                    res_alt = cur.fetchone()
                    unici_db = res_alt['unici_from_table'] or 0
                    if unici_db > (res['unici'] or 0):
                        return {'unici': unici_db, 'totali': max(res['totali'] or 0, unici_db)}

                return {'unici': res['unici'] or 0, 'totali': res['totali'] or 0}

            # 2. Accessi varie finestre temporali
            stats['24h'] = get_period_stats(24)
            stats['48h'] = get_period_stats(48)
            stats['72h'] = get_period_stats(72)
            stats['7d'] = get_period_stats(24 * 7)
            stats['30d'] = get_period_stats(24 * 30)
            stats['1y'] = get_period_stats(24 * 365)
            stats['sempre'] = get_period_stats(all_time=True)
            
        return stats
    except Exception as e:
        logger.error(f"Errore in ottieni_statistiche_accessi: {e}")
        return stats


def get_all_users() -> List[Dict[str, Any]]:
    """Recupera la lista di tutti gli utenti."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # USE ENCRYPTED SHADOW COLUMNS
            # USE ENCRYPTED SHADOW COLUMNS and JOIN for Families
            cur.execute("""
                SELECT u.id_utente, u.username_enc, u.email_enc, u.nome_enc_server, u.cognome_enc_server, u.sospeso,
                       u.password_algo, u.codice_utente_enc,
                       string_agg(f.codice_famiglia_enc, '|') as codici_famiglie_enc
                FROM Utenti u
                LEFT JOIN Appartenenza_Famiglia af ON u.id_utente = af.id_utente
                LEFT JOIN Famiglie f ON af.id_famiglia = f.id_famiglia
                GROUP BY u.id_utente, u.password_algo, u.codice_utente_enc
                ORDER BY u.id_utente
            """)
            rows = []
            for row in cur.fetchall():
                d = {}
                d['id_utente'] = row['id_utente']
                
                # Decrittazione Codici Famiglia
                codici_lista = []
                if row.get('codici_famiglie_enc'):
                    for c_enc in row['codici_famiglie_enc'].split('|'):
                        dec = decrypt_system_data(c_enc)
                        if dec: codici_lista.append(dec)
                
                d['famiglie'] = ", ".join(codici_lista) if codici_lista else "-"
                
                d['sospeso'] = row.get('sospeso', False)
                d['algo'] = row.get('password_algo', 'sha256') # Default to sha256 (legacy) if null
                d['codice_utente'] = decrypt_system_data(row.get('codice_utente_enc')) or "-"
                
                # Decrypt sensitive fields using System Key
                # Nota: usiamo .get() perché potrebbero essere NULL
                d['username'] = decrypt_system_data(row.get('username_enc')) or row.get('username_enc', '-')
                d['email'] = decrypt_system_data(row.get('email_enc')) or row.get('email_enc', '-')
                d['nome'] = decrypt_system_data(row.get('nome_enc_server')) or row.get('nome_enc_server', '-')
                d['cognome'] = decrypt_system_data(row.get('cognome_enc_server')) or row.get('cognome_enc_server', '-')
                rows.append(d)
            return rows
    except Exception as e:
        logger.error(f"Errore get_all_users: {e}")
        return []


def delete_user(user_id: int) -> tuple[bool, str]:
    """Elimina un utente dal database e tutti i dati correlati."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Rimuovi appartenenza famiglie e partecipazioni conti condivisi
            cur.execute("DELETE FROM Appartenenza_Famiglia WHERE id_utente = %s", (user_id,))
            cur.execute("DELETE FROM PartecipazioneContoCondiviso WHERE id_utente = %s", (user_id,))
            
            # 2. Elimina transazioni condivise di cui è autore
            cur.execute("DELETE FROM TransazioniCondivise WHERE id_utente_autore = %s", (user_id,))

            # 3. Elimina Carte dell'utente
            cur.execute("DELETE FROM Carte WHERE id_utente = %s", (user_id,))

            # 4. Elimina Contatti dell'utente (e relative condivisioni)
            # CondivisioneContatto ha FK su id_utente e id_contatto (entrambi cascade teoricamente, ma meglio esplicito)
            cur.execute("DELETE FROM CondivisioneContatto WHERE id_utente = %s", (user_id,))
            cur.execute("DELETE FROM Contatti WHERE id_utente = %s", (user_id,))
            
            # 5. Elimina Quote Immobili e Prestiti
            cur.execute("DELETE FROM QuoteImmobili WHERE id_utente = %s", (user_id,))
            cur.execute("DELETE FROM QuotePrestiti WHERE id_utente = %s", (user_id,))

            # 6. Elimina dati finanziari personali (Conti e cascata)
            # Recupera conti dell'utente
            cur.execute("SELECT id_conto FROM Conti WHERE id_utente = %s", (user_id,))
            res = cur.fetchall()
            conti_ids = [r['id_conto'] for r in res] if res else []
            
            if conti_ids:
                # Transazioni
                cur.execute("DELETE FROM Transazioni WHERE id_conto = ANY(%s)", (conti_ids,))
                # Saldi/Salvadanaio
                cur.execute("DELETE FROM Salvadanai WHERE id_conto = ANY(%s)", (conti_ids,))
                # Asset / Storico Asset
                cur.execute("DELETE FROM Asset WHERE id_conto = ANY(%s)", (conti_ids,))
                cur.execute("DELETE FROM Storico_Asset WHERE id_conto = ANY(%s)", (conti_ids,))
                # Infine i Conti
                cur.execute("DELETE FROM Conti WHERE id_utente = %s", (user_id,))

            # 7. Elimina Log relativi all'utente
            cur.execute("DELETE FROM Log_Sistema WHERE id_utente = %s", (user_id,))

            # 8. Infine elimina l'utente
            cur.execute("DELETE FROM Utenti WHERE id_utente = %s", (user_id,))
            
            con.commit()
            return True, "Utente eliminato con successo."
    except Exception as e:
        logger.error(f"Errore delete_user {user_id}: {e}")
        return False, str(e)

def elimina_account_utente(id_utente: str, password_raw: str) -> tuple[bool, str]:
    """
    Elimina definitivamente l'account utente previa verifica della password.
    """
    try:
        # 1. Recupera username per verifica_login
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT username_enc FROM Utenti WHERE id_utente = %s", (id_utente,))
            res = cur.fetchone()
            if not res:
                return False, "Utente non trovato."
            
            username = decrypt_system_data(res['username_enc'])
            if not username:
                return False, "Impossibile recuperare i dati utente per la verifica."

        # 2. Verifica password
        utente_loggato, errore = verifica_login(username, password_raw)
        if not utente_loggato:
            return False, errore or "Password errata."

        # 3. Esegue eliminazione (delete_user usa int ID)
        return delete_user(int(id_utente))

    except Exception as e:
        logger.error(f"Errore elimina_account_utente {id_utente}: {e}")
        return False, f"Errore durante l'eliminazione dell'account: {e}"

def get_all_families() -> List[Dict[str, Any]]:
    """Recupera la lista di tutte le famiglie, tentando di decriptare il nome."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT f.id_famiglia, f.nome_famiglia, f.server_encrypted_key, f.codice_famiglia_enc,
                       COUNT(af.id_utente) as num_membri
                FROM Famiglie f
                LEFT JOIN Appartenenza_Famiglia af ON f.id_famiglia = af.id_famiglia
                GROUP BY f.id_famiglia, f.nome_famiglia, f.server_encrypted_key, f.codice_famiglia_enc
                ORDER BY f.id_famiglia
            """)
            families = cur.fetchall()
            
            rows = []
            crypto = CryptoManager()
            
            for row in families:
                d = {}
                d['id_famiglia'] = row['id_famiglia']
                d['num_membri'] = row['num_membri']
                d['codice_famiglia'] = decrypt_system_data(row.get('codice_famiglia_enc')) or "-"
                encrypted_name = row['nome_famiglia']
                srv_key_enc = row.get('server_encrypted_key')
                
                nome_decrypted = encrypted_name
                family_key = None
                
                # METODO 1: Uso chiave server diretta (Automazione attiva)
                if srv_key_enc:
                    try:
                         family_key_b64 = decrypt_system_data(srv_key_enc)
                         if family_key_b64:
                             if isinstance(family_key_b64, str):
                                 family_key = family_key_b64.encode()
                             else:
                                 family_key = family_key_b64
                    except Exception:
                        pass

                # METODO 2: Fallback tramite utenti della famiglia (Recovery/Backup Key)
                if not family_key:
                    try:
                        # Cerchiamo un utente di questa famiglia che abbia il backup server della master key
                        cur.execute("""
                            SELECT u.encrypted_master_key_backup, af.chiave_famiglia_criptata 
                            FROM Appartenenza_Famiglia af
                            JOIN Utenti u ON af.id_utente = u.id_utente
                            WHERE af.id_famiglia = %s AND u.encrypted_master_key_backup IS NOT NULL
                            LIMIT 1
                        """, (row['id_famiglia'],))
                        user_row = cur.fetchone()
                        
                        if user_row:
                            # 1. Decrypt User Master Key using System Key
                            user_mk_backup_enc = user_row['encrypted_master_key_backup']
                            # encrypted_master_key_backup è cifrata con Fernet(SystemKey)
                            # Quindi usiamo decrypt_system_data ma attenzione:
                            # In crea_utente: encrypted_mk_backup = crypto.encrypt_master_key(master_key, srv_fernet_key)
                            # encrypt_master_key usa Fernet.
                            # Quindi decrypt_system_data (che usa Fernet(SYSTEM_FERNET_KEY)) dovrebbe funzionare se srv_fernet_key == SYSTEM_FERNET_KEY.
                            # Verifichiamo _get_system_keys: Sì, è la stessa chiave.
                            
                            user_mk_bytes = None
                            try:
                                # decrypt_system_data ritorna stringa, ma qui ci aspettiamo bytes (la master key raw) oppure stringa b64?
                                # crypto.encrypt_master_key ritorna bytes. decrypt_system_data fa .decode().
                                # Quindi otteniamo la stringa b64 della chiave o i bytes raw?
                                # Fernet.encrypt ritorna bytes. decrypt_system_data fa .decode() -> Ritorna stringa.
                                # Ma encrypt_master_key potrebbe ritornare i bytes del contenuto cifrato.
                                # Vediamo crea_utente: encrypted_mk_backup_b64 = base64.urlsafe_b64encode(encrypted_mk_backup).decode()
                                # Quindi nel DB c'è B64(Fernet(MK)). 
                                # decrypt_system_data fa: Fernet.decrypt(value.encode()).decode()
                                # Se passiamo la stringa B64 dal DB, decrypt_system_data fallirà perché si aspetta Token Fernet (gAAAA...), non B64(Token).
                                # WAIT. encrypted_mk_backup è IL token fernet (bytes).
                                # encrypted_mk_backup_b64 è il base64 di tale token.
                                # decrypt_system_data si aspetta una stringa che sia un token Fernet valido.
                                # Se nel DB ho salvato B64(Token), devo prima fare b64decode per ottenere il Token stringa?
                                # Fernet token è url-safe base64 per definizione.
                                # Se ho fatto base64.urlsafe_b64encode su un token fernet, ho fatto doppio encoding?
                                # crypto.encrypt_master_key(master_key, key) -> f.encrypt(data) -> ritorna bytes (il token).
                                # base64.urlsafe_b64encode(...) -> bytes.
                                # .decode() -> stringa.
                                # QUINDI nel DB c'è B64(Token).
                                # decrypt_system_data prende stringa, fa .encode() -> bytes. E lo passa a decrypt().
                                # decrypt() vuole il Token bytes.
                                # Se passo B64(Token), non è un Token valido.
                                
                                # FIX: Dobbiamo decodificare il B64 esterno per ottenere il Token Fernet.
                                token_fernet_b64 = user_row['encrypted_master_key_backup']
                                token_fernet_bytes = base64.urlsafe_b64decode(token_fernet_b64)
                                # Ora token_fernet_bytes è il token fernet vero e proprio.
                                # Usiamo la chiave di sistema per decifrarlo.
                                from cryptography.fernet import Fernet
                                cipher = Fernet(SYSTEM_FERNET_KEY)
                                user_mk_bytes = cipher.decrypt(token_fernet_bytes)
                                # Ora user_mk_bytes è la Master Key dell'utente (bytes).
                                
                                # 2. Decrypt Family Key using User Master Key
                                fk_encrypted_b64 = user_row['chiave_famiglia_criptata']
                                # decrypt_data vuole: encrypted_data (str o bytes), key (bytes)
                                try:
                                    # decrypt_data gestisce input b64
                                    family_key_b64 = crypto.decrypt_data(fk_encrypted_b64, user_mk_bytes)
                                    if family_key_b64:
                                         family_key = family_key_b64.encode() if isinstance(family_key_b64, str) else family_key_b64
                                except:
                                    pass
                            except Exception as e_inner:
                                # logger.warning(f"Decryption fallback failed step 1: {e_inner}")
                                pass
                    except Exception as e_outer:
                        # logger.warning(f"Decryption fallback failed: {e_outer}")
                        pass
                
                # Se abbiamo la chiave famiglia (da Metodo 1 o 2), decriptiamo il nome
                if family_key:
                    try:
                        nome_decrypted = crypto.decrypt_data(encrypted_name, family_key, silent=True)
                    except:
                        pass
                
                d['nome_famiglia'] = nome_decrypted
                d['cloud_enabled'] = bool(row.get('server_encrypted_key'))
                rows.append(d)
                
            return rows
    except Exception as e:
        logger.error(f"Errore get_all_families: {e}")
        return []
    except Exception as e:
        logger.error(f"Errore get_all_families: {e}")
        return []


def get_family_summary(id_famiglia):
    """Restituisce un riassunto (nome e codice decriptati) per una famiglia."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT nome_famiglia, server_encrypted_key, codice_famiglia_enc FROM Famiglie WHERE id_famiglia = %s", (id_famiglia,))
            row = cur.fetchone()
            if not row:
                return None
            
            d = {}
            # Decrypt Name
            srv_key_enc = row.get('server_encrypted_key')
            enc_name = row['nome_famiglia']
            if srv_key_enc:
                try:
                    fk_b64 = decrypt_system_data(srv_key_enc)
                    if fk_b64:
                        fk_bytes = base64.b64decode(fk_b64.encode())
                        crypto = CryptoManager()
                        d['nome'] = _decrypt_if_key(enc_name, fk_bytes, crypto, silent=True)
                    else:
                        d['nome'] = enc_name
                except:
                    d['nome'] = enc_name
            else:
                d['nome'] = enc_name
                
            # Decrypt Code
            cod_enc = row.get('codice_famiglia_enc')
            d['codice'] = decrypt_system_data(cod_enc) or "-"
            
            return d
    except Exception as e:
        logger.error(f"Errore get_family_summary: {e}")
        return None


def delete_family(family_id: int) -> Tuple[bool, str]:
    """Elimina una famiglia dal database. Impedisce cancellazione se ci sono utenti."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Check for existing users
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM Appartenenza_Famiglia 
                WHERE id_famiglia = %s
            """, (family_id,))
            count = cur.fetchone()['count']
            
            if count > 0:
                return False, f"Impossibile eliminare: ci sono {count} utenti associati."
            
            # Delete related data first (cascade should handle most, but safer to be explicit if needed)
            # Assuming cascade handles it or manual cleanup
            
            cur.execute("DELETE FROM Famiglie WHERE id_famiglia = %s", (family_id,))
            con.commit()
            return True, "Famiglia eliminata con successo."
    except Exception as e:
        logger.error(f"Errore delete_family {family_id}: {e}")
        return False, f"Errore interno: {e}" 

def toggle_user_suspension(user_id: int, suspend: bool) -> bool:
    """Attiva o sospende un utente."""
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE Utenti SET sospeso = %s WHERE id_utente = %s", (suspend, user_id))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore toggle_user_suspension {user_id}: {e}")
        return False


def verify_admin_password(password: str) -> bool:
    """Verifica se la password fornita corrisponde alla password admin."""
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        return False
    return password == admin_password

def reset_user_password(user_id: int) -> Tuple[bool, str]:
    """
    Resetta la password dell'utente e invia un'email con la nuova password.
    
    Returns:
        Tuple[bool, str]: (Successo, Messaggio di errore o conferma)
    """
    from utils.email_sender import send_email
    
    try:
        # Recupera email utente (usando campi di sistema criptati)
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT email_enc, username_enc FROM Utenti WHERE id_utente = %s", (user_id,))
            user_data = cur.fetchone()
            
        if not user_data:
            return False, "Utente non trovato."
            
        # Decrypt system data
        email = decrypt_system_data(user_data.get('email_enc'))
        username = decrypt_system_data(user_data.get('username_enc'))
        
        if not email:
             return False, "Email utente non disponibile (crittografia mancante o errore)."
             
        if not username:
             username = "Utente"
        
        # Genera nuova password
        new_password = generate_token(12)
        
        # Aggiorna DB usando la logica di recupero master key (v0.48)
        success_recovery = imposta_password_temporanea(user_id, new_password)
        
        recovery_note = ""
        if not success_recovery:
            # Fallback a solo reset hash se il recupero fallisce (es. backup mancante o errore)
            # Ma informiamo che i dati non saranno accessibili direttamente.
            password_hash = hash_password(new_password)
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("""
                    UPDATE Utenti 
                    SET password_hash = %s, password_algo = 'pbkdf2', forza_cambio_password = TRUE 
                    WHERE id_utente = %s
                """, (password_hash, user_id))
                con.commit()
            recovery_note = """
            <p style='color: #d32f2f; font-weight: bold;'>⚠️ NOTA IMPORTANTE SULLA SICUREZZA:</p>
            <p>Il backup della tua chiave master non è stato trovato sul server. Per motivi di sicurezza, i tuoi dati criptati esistenti (conti, transazioni, ecc.) 
            <b>non saranno accessibili</b> fino a quando non userai la tua <b>Chiave di Recupero</b> personale per ripristinarli al primo accesso.</p>
            """
        else:
            recovery_note = "<p><i>I tuoi dati sono stati recuperati con successo grazie al backup di sicurezza del server.</i></p>"
        
        # Invia Email
        subject = "BudgetAmico - Reset Password"
        body = f"""
        <h2>Ciao {username},</h2>
        <p>Un amministratore ha richiesto il reset della tua password.</p>
        <p>Ecco le tue nuove credenziali temporanee:</p>
        <ul>
            <li><b>Username:</b> {username}</li>
            <li><b>Nuova Password:</b> {new_password}</li>
        </ul>
        <p>Ti verrà chiesto di cambiare questa password al primo accesso.</p>
        <br>
        {recovery_note}
        <br>
        <p>Saluti,<br>Team BudgetAmico</p>
        """
        
        success_email, error_msg = send_email(email, subject, body)
        if success_email:
            return True, f"Password resettata e email inviata a {email}"
        else:
            return False, f"Password resettata ma errore invio email: {error_msg}"

    except Exception as e:
        logger.error(f"Errore reset_user_password: {e}")
        return False, f"Errore generico: {e}"



def get_database_statistics() -> Dict[str, Any]:
    """
    Recupera statistiche sulle tabelle del database (righe, dimensioni).
    Utilizza pg_stat_user_tables e pg_class.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Total Database Size
            cur.execute("SELECT pg_database_size(current_database()) as total_size")
            total_size = cur.fetchone()['total_size']
            
            # 2. Table Stats (Row count estimation & Size)
            # n_live_tup is an estimate but much faster than COUNT(*)
            # pg_total_relation_size includes indexes and toasted data
            cur.execute("""
                SELECT 
                    stat.relname as table_name,
                    stat.n_live_tup as row_count,
                    pg_total_relation_size(c.oid) as size_bytes
                FROM pg_stat_user_tables stat
                JOIN pg_class c ON stat.relid = c.oid
                ORDER BY size_bytes DESC
            """)
            tables = cur.fetchall()
            
            return {
                "total_size_bytes": total_size,
                "tables": tables
            }
            
    except Exception as e:
        logger.error(f"Errore get_database_statistics: {e}")
        return {"total_size_bytes": 0, "tables": []}

            
    except Exception as e:
        logger.error(f"Errore calcolo entrate mensili: {e}")
        return 0.0


# --- CONFIGURAZIONE SICUREZZA PASSWORD (v0.48) ---

def get_password_complexity_config():
    """Recupera la configurazione della complessità password, con fallback di sicurezza."""
    try:
        return {
            "min_length": int(get_configurazione("pwd_min_length") or 8),
            "require_special": get_configurazione("pwd_require_special") == "true",
            "require_digits": get_configurazione("pwd_require_digits") == "true",
            "require_uppercase": get_configurazione("pwd_require_uppercase") == "true"
        }
    except Exception as e:
        logger.warning(f"Errore caricamento config password (uso default): {e}")
        return {
            "min_length": 8,
            "require_special": False,
            "require_digits": False,
            "require_uppercase": False
        }

def save_password_complexity_config(config, id_utente=None):
    """Salva la configurazione della complessità password."""
    success = True
    success &= save_system_config("pwd_min_length", str(config.get("min_length", 8)), id_utente)
    success &= save_system_config("pwd_require_special", "true" if config.get("require_special") else "false", id_utente)
    success &= save_system_config("pwd_require_digits", "true" if config.get("require_digits") else "false", id_utente)
    success &= save_system_config("pwd_require_uppercase", "true" if config.get("require_uppercase") else "false", id_utente)
    return success

# --- VERIFICA EMAIL (v0.48) ---

def generate_email_verification_code(email):
    """Genera e salva un codice di verifica email (6 cifre)."""
    import secrets
    code = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    # Salva in Configurazioni con prefisso e timestamp per scadenza (es. 15 min)
    # Chiave: email_verification_<code>_<email>
    # Valore: timestamp_scadenza
    import time
    expiry = int(time.time()) + 900 # 15 minuti
    save_system_config(f"verify_email_{email}", f"{code}|{expiry}")
    return code

def verify_email_code(email, code):
    """Verifica se il codice per l'email è corretto e non scaduto."""
    raw = get_configurazione(f"verify_email_{email}")
    if not raw: return False
    
    try:
        saved_code, expiry = raw.split("|")
        import time
        if int(time.time()) > int(expiry):
            return False
        return saved_code == code
    except:
        pass
    return False

def check_registration_availability(username, email):
    """Verifica se username o email sono già occupati da un utente VERIFICATO."""
    u_bindex = compute_blind_index(username)
    e_bindex = compute_blind_index(email)
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT id_utente FROM Utenti 
                WHERE (username_bindex = %s OR email_bindex = %s) AND email_verificata = TRUE
            """, (u_bindex, e_bindex))
            return cur.fetchone() is None
    except Exception as e:
        logger.error(f"Errore check_registration_availability: {e}")
        return False

