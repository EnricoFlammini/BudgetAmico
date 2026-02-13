"""
Funzioni famiglie: membri, ruoli, chiavi, totali
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
from utils.logger import setup_logger
from utils.crypto_manager import CryptoManager
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
import os

logger = setup_logger(__name__)
import base64
from utils.cache_manager import cache_manager
from dateutil.relativedelta import relativedelta

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code,
    SERVER_SECRET_KEY,
    crypto as _crypto_instance
)

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
    1. Se l'utente ha già la chiave, verifichiamo se è allineata con quella del server (se presente).
    2. Se l'utente non ha la chiave, proviamo a recuperarla dal backup del server (Automation Cloud).
    3. Se nessuno ha la chiave, ne genera una nuova (solo se admin o se la famiglia è nuova).
    """
    if not master_key_b64:
        return False

    crypto, master_key = _get_crypto_and_key(master_key_b64)
    if not master_key:
        return False

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # --- 1. Recupero Chiave di Sistema (Sorgente di verità se presente) ---
            cur.execute("SELECT server_encrypted_key FROM Famiglie WHERE id_famiglia = %s", (id_famiglia,))
            fam_row = cur.fetchone()
            server_fk_b64 = None
            if fam_row and fam_row['server_encrypted_key']:
                server_fk_b64 = decrypt_system_data(fam_row['server_encrypted_key'])

            # --- 2. Controlla chiave attuale dell'utente ---
            cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente, id_famiglia))
            row = cur.fetchone()
            
            user_has_correct_key = False
            if row and row['chiave_famiglia_criptata']:
                if not server_fk_b64:
                    return True # Nessun riferimento server, assumiamo che quella dell'utente sia ok
                
                # Se abbiamo una chiave server, verifichiamo coerenza
                try:
                    current_fk_b64 = crypto.decrypt_data(row['chiave_famiglia_criptata'], master_key)
                    if current_fk_b64 == server_fk_b64:
                        return True # Chiave allineata
                except:
                    pass # Chiave corrotta o master_key errata (improbabile qui)

            # --- 3. Recupero/Ripristino da Server ---
            if server_fk_b64:
                print(f"[INFO] Sincronizzazione chiave famiglia dal server per utente {id_utente}...")
                new_enc_key = crypto.encrypt_data(server_fk_b64, master_key)
                cur.execute("""
                    UPDATE Appartenenza_Famiglia 
                    SET chiave_famiglia_criptata = %s 
                    WHERE id_utente = %s AND id_famiglia = %s
                """, (new_enc_key, id_utente, id_famiglia))
                con.commit()
                return True

            # --- 4. Fallback: Recupero da altri membri (Solo se l'utente non ha nulla) ---
            if not (row and row['chiave_famiglia_criptata']):
                cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_famiglia = %s AND chiave_famiglia_criptata IS NOT NULL LIMIT 1", (id_famiglia,))
                existing_key_row = cur.fetchone()
                if existing_key_row:
                    print(f"[WARN] La famiglia {id_famiglia} ha già una chiave, ma non è possibile recuperarla senza l'intervento di un admin o Automazione Cloud.")
                    return False

                # --- 5. Generazione Nuova Chiave (Nessuno ha nulla) ---
                print(f"[INFO] Generazione nuova chiave famiglia per famiglia {id_famiglia}...")
                new_family_key = secrets.token_bytes(32)
                fk_b64_new = base64.b64encode(new_family_key).decode('utf-8')
                encrypted_family_key = crypto.encrypt_data(fk_b64_new, master_key)
                
                cur.execute("""
                    UPDATE Appartenenza_Famiglia 
                    SET chiave_famiglia_criptata = %s 
                    WHERE id_utente = %s AND id_famiglia = %s
                """, (encrypted_family_key, id_utente, id_famiglia))
                con.commit()
                return True

            return True

    except Exception as e:
        print(f"[ERRORE] Errore in ensure_family_key: {e}")
        return False

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
            
            codice_famiglia = generate_unique_code(prefix="FAM-", length=6)
            cod_f_enc = encrypt_system_data(codice_famiglia)

            cur.execute("INSERT INTO Famiglie (nome_famiglia, codice_famiglia_enc) VALUES (%s, %s) RETURNING id_famiglia", (encrypted_nome_famiglia, cod_f_enc))
            id_famiglia = cur.fetchone()['id_famiglia']
            cur.execute("INSERT INTO Appartenenza_Famiglia (id_utente, id_famiglia, ruolo, chiave_famiglia_criptata) VALUES (%s, %s, %s, %s)",
                        (id_admin, id_famiglia, 'admin', chiave_famiglia_criptata))
            
            con.commit() # Commit insertion first

            # Check Default Cloud Automation Setting
            try:
                default_cloud_auto = get_configurazione("system_default_cloud_automation")
                if default_cloud_auto == "true":
                     enable_server_automation(id_famiglia, master_key_b64, id_admin, forced_family_key=family_key_bytes)
            except Exception as e_auto:
                print(f"[WARNING] Failed to apply default cloud automation: {e_auto}")

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

def ottieni_utenti_famiglia(id_famiglia):
    id_famiglia = _valida_id_int(id_famiglia)
    if not id_famiglia: return []
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


# --- Helper Functions for Encryption (Family) ---

# Cache per le chiavi famiglia per evitare continue query al DB
# {(id_famiglia, id_utente): family_key_bytes}
_family_key_cache = {}

def _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto):
    id_famiglia = _valida_id_int(id_famiglia)
    id_utente = _valida_id_int(id_utente)
    if not id_famiglia or not id_utente: return None

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


def get_family_summary(id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Restituisce un riassunto (nome e codice decriptati) per una famiglia.
    Tenta di decriptare il nome usando:
    1. Server Key (se disponibile e decriptabile con chiave di sistema)
    2. User Family Key (se master_key_b64 e id_utente sono forniti)
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT nome_famiglia, server_encrypted_key, codice_famiglia_enc FROM Famiglie WHERE id_famiglia = %s", (id_famiglia,))
            row = cur.fetchone()
            if not row:
                return None
            
            d = {}
            crypto = CryptoManager()
            
            # --- Decrypt Name ---
            enc_name = row['nome_famiglia']
            decrypted_nome = None
            
            # 1. Try via Server Key (System Key)
            srv_key_enc = row.get('server_encrypted_key')
            if srv_key_enc:
                try:
                    fk_b64 = decrypt_system_data(srv_key_enc)
                    if fk_b64:
                        fk_bytes = base64.b64decode(fk_b64.encode())
                        decrypted_nome = _decrypt_if_key(enc_name, fk_bytes, crypto, silent=True)
                except Exception as e:
                    # logger.debug(f"Server Key decryption failed: {e}")
                    pass
            
            # 2. Try via User Family Key (if Server Key failed/missing and we have context)
            if (not decrypted_nome or decrypted_nome == enc_name or CryptoManager.is_encrypted(decrypted_nome)) and master_key_b64 and id_utente:
                try:
                    _, master_key = _get_crypto_and_key(master_key_b64)
                    if master_key:
                        family_key_bytes = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
                        if family_key_bytes:
                            decrypted_nome = _decrypt_if_key(enc_name, family_key_bytes, crypto, silent=True)
                except Exception as e_user:
                     logger.warning(f"User Key decryption for family name failed: {e_user}")
            
            # Fallback
            d['nome'] = decrypted_nome if decrypted_nome else enc_name
                
            # --- Decrypt Code ---
            cod_enc = row.get('codice_famiglia_enc')
            d['codice'] = decrypt_system_data(cod_enc) or "-"
            
            return d
    except Exception as e:
        logger.error(f"Errore get_family_summary: {e}")
        return None

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
                if CryptoManager.is_encrypted(nome_raw): 
                     nome_raw = '' # Hide encrypted blob
                if CryptoManager.is_encrypted(cognome_raw):
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

def ottieni_prima_famiglia_utente(id_utente):
    id_utente = _valida_id_int(id_utente)
    if not id_utente: return None
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s LIMIT 1", (id_utente,))
            res = cur.fetchone()
            return res['id_famiglia'] if res else None
    except Exception as e:
        print(f"[ERRORE] Errore generico: {e}")
        return None

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

