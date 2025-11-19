import sqlite3
import hashlib
import datetime
import os
import sys
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse as parse_date
import mimetypes
import secrets
import string

# --- BLOCCO DI CODICE PER CORREGGERE IL PERCORSO ---
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
# --- FINE BLOCCO DI CODICE ---

from db.crea_database import setup_database

# --- GESTIONE PERCORSI PER ESEGUIBILE ---
APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), 'BudgetFamiliare')
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR)
DB_FILE = os.path.join(APP_DATA_DIR, 'budget_familiare.db')
# --- FINE GESTIONE PERCORSI ---


# --- Funzioni di Versioning ---
def ottieni_versione_db(db_path=DB_FILE):
    """Legge la versione dello schema dal PRAGMA user_version del database."""
    try:
        with sqlite3.connect(db_path) as con:
            cur = con.cursor()
            cur.execute("PRAGMA user_version;")
            return cur.fetchone()[0]
    except Exception as e:
        print(f"❌ Errore durante la lettura della versione del DB ({db_path}): {e}")
        return 0


# --- Funzioni di Utilità ---
def generate_token(length=32):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def get_user_count():
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM Utenti")
            return cur.fetchone()[0]
    except Exception as e:
        print(f"❌ Errore in get_user_count: {e}")
        return -1


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def valida_iban_semplice(iban):
    if not iban:
        return True
    iban_pulito = iban.strip().upper()
    return iban_pulito.startswith("IT") and len(iban_pulito) == 27 and iban_pulito[2:].isalnum()


# --- Funzioni Utenti & Login ---
def registra_utente(username, email, password, nome, cognome):
    hashed_pass = hash_password(password)
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("INSERT INTO Utenti (username, email, password_hash, nome, cognome) VALUES (?, ?, ?, ?, ?)",
                        (username, email.lower(), hashed_pass, nome, cognome))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        print(f"❌ Errore generico durante la registrazione: {e}")
        return None


def verifica_login(login_identifier, password):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT id_utente, password_hash, nome, cognome, username, email, forza_cambio_password FROM Utenti WHERE username = ? OR email = ?",
                        (login_identifier, login_identifier.lower()))
            risultato = cur.fetchone()
            if risultato and risultato['password_hash'] == hash_password(password):
                return {"id": risultato['id_utente'], "username": risultato['username'], "forza_cambio_password": risultato['forza_cambio_password'], "nome": risultato['nome'],
                        "cognome": risultato['cognome']}
            return None
    except Exception as e:
        print(f"❌ Errore generico durante il login: {e}")
        return None


def imposta_conto_default_utente(id_utente, id_conto_personale=None, id_conto_condiviso=None):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")

            if id_conto_personale:
                # Imposta il conto personale e annulla quello condiviso
                cur.execute(
                    "UPDATE Utenti SET id_conto_condiviso_default = NULL, id_conto_default = ? WHERE id_utente = ?",
                    (id_conto_personale, id_utente))
            elif id_conto_condiviso:
                # Imposta il conto condiviso e annulla quello personale
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_conto_condiviso_default = ? WHERE id_utente = ?",
                    (id_conto_condiviso, id_utente))
            else:  # Se entrambi sono None, annulla entrambi
                cur.execute(
                    "UPDATE Utenti SET id_conto_default = NULL, id_conto_condiviso_default = NULL WHERE id_utente = ?",
                    (id_utente,))

            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore durante l'impostazione del conto di default: {e}")
        return False


def ottieni_conto_default_utente(id_utente):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT id_conto_default, id_conto_condiviso_default FROM Utenti WHERE id_utente = ?",
                        (id_utente,))
            result = cur.fetchone()
            if result:
                if result['id_conto_default'] is not None:
                    return {'id': result['id_conto_default'], 'tipo': 'personale'}
                elif result['id_conto_condiviso_default'] is not None:
                    return {'id': result['id_conto_condiviso_default'], 'tipo': 'condiviso'}
            return None
    except Exception as e:
        print(f"❌ Errore durante il recupero del conto di default: {e}")
        return None


# --- Funzioni Onboarding & Admin ---
def crea_famiglia_e_admin(nome_famiglia, id_admin):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("INSERT INTO Famiglie (nome_famiglia) VALUES (?)", (nome_famiglia,))
            new_family_id = cur.lastrowid
            cur.execute("INSERT INTO Appartenenza_Famiglia (id_utente, id_famiglia, ruolo) VALUES (?, ?, ?)",
                        (id_admin, new_family_id, 'admin'))
            return new_family_id
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        print(f"❌ Errore generico durante la creazione famiglia: {e}")
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
        "ENTRATE": ["STIPENDIO", "BONUS", "REGALI"],
        "SPESE": ["CIBO", "AFFITTO/MUTUO", "UTENZE", "TRASPORTI", "SVAGO", "VIAGGI", "SALUTE"],
        "FINANZA": ["RISPARMI", "INVESTIMENTI", "TASSE"]
    }
    for nome_cat, sottocategorie in categorie_base.items():
        id_cat = aggiungi_categoria(id_famiglia, nome_cat)
        if id_cat:
            for nome_sottocat in sottocategorie:
                aggiungi_sottocategoria(id_cat, nome_sottocat)


def aggiungi_utente_a_famiglia(id_famiglia, id_utente, ruolo):
    if ruolo not in ['admin', 'livello1', 'livello2', 'livello3']:
        return False
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("INSERT INTO Appartenenza_Famiglia (id_utente, id_famiglia, ruolo) VALUES (?, ?, ?)",
                        (id_utente, id_famiglia, ruolo))
            return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"❌ Errore generico: {e}")
        return None


def cerca_utente_per_username(username):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        SELECT U.id_utente,
                               U.username,
                               COALESCE(U.nome || ' ' || U.cognome, U.username) AS nome_visualizzato
                        FROM Utenti U
                                 LEFT JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE U.username = ?
                          AND AF.id_famiglia IS NULL
                        """, (username,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"❌ Errore generico durante la ricerca utente: {e}")
        return None

def trova_utente_per_email(email):
    """Trova un utente dal suo username (che è l'email)."""
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM Utenti WHERE email = ?", (email.lower(),))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"❌ Errore in trova_utente_per_email: {e}")
        return None

def imposta_password_temporanea(id_utente, temp_password_hash):
    """Imposta una password temporanea e forza il cambio al prossimo login."""
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("UPDATE Utenti SET password_hash = ?, forza_cambio_password = 1 WHERE id_utente = ?",
                        (temp_password_hash, id_utente))
            return True
    except Exception as e:
        print(f"❌ Errore durante l'impostazione della password temporanea: {e}")
        return False

def cambia_password(id_utente, nuovo_password_hash):
    """Cambia la password di un utente e rimuove il flag di cambio forzato."""
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("UPDATE Utenti SET password_hash = ?, forza_cambio_password = 0 WHERE id_utente = ?",
                        (nuovo_password_hash, id_utente))
            return True
    except Exception as e:
        print(f"❌ Errore durante il cambio password: {e}")
        return False

def ottieni_dettagli_utente(id_utente):
    """Recupera tutti i dettagli di un utente dal suo ID."""
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM Utenti WHERE id_utente = ?", (id_utente,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"❌ Errore in ottieni_dettagli_utente: {e}")
        return None

def aggiorna_profilo_utente(id_utente, dati_profilo):
    """Aggiorna i campi del profilo di un utente."""
    campi_da_aggiornare = []
    valori = []
    campi_validi = ['username', 'email', 'nome', 'cognome', 'data_nascita', 'codice_fiscale', 'indirizzo']

    for campo, valore in dati_profilo.items():
        if campo in campi_validi:
            campi_da_aggiornare.append(f"{campo} = ?")
            valori.append(valore)

    if not campi_da_aggiornare:
        return True # Nessun campo da aggiornare

    valori.append(id_utente)
    query = f"UPDATE Utenti SET {', '.join(campi_da_aggiornare)} WHERE id_utente = ?"

    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute(query, tuple(valori))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore durante l'aggiornamento del profilo: {e}")
        return False

# --- Funzioni Gestione Inviti ---
def crea_invito(id_famiglia, email, ruolo):
    token = generate_token()
    if ruolo not in ['admin', 'livello1', 'livello2', 'livello3']:
        return None
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("INSERT INTO Inviti (id_famiglia, email_invitato, ruolo_assegnato, token) VALUES (?, ?, ?, ?)",
                        (id_famiglia, email.lower(), ruolo, token))
            return token
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        print(f"❌ Errore durante la creazione dell'invito: {e}")
        return None


def ottieni_invito_per_token(token):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")
            cur.execute("SELECT id_famiglia, email_invitato, ruolo_assegnato FROM Inviti WHERE token = ?", (token,))
            invito = cur.fetchone()
            if invito:
                cur.execute("DELETE FROM Inviti WHERE token = ?", (token,))
                con.commit()
                return dict(invito)
            else:
                con.rollback()
                return None
    except Exception as e:
        print(f"❌ Errore durante l'ottenimento/eliminazione dell'invito: {e}")
        if con: con.rollback()
        return None


# --- Funzioni Conti Personali ---
def aggiungi_conto(id_utente, nome_conto, tipo_conto, iban=None):
    if not valida_iban_semplice(iban):
        return None
    iban_pulito = iban.strip().upper() if iban else None
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("INSERT INTO Conti (id_utente, nome_conto, tipo, iban) VALUES (?, ?, ?, ?)",
                        (id_utente, nome_conto, tipo_conto, iban_pulito))
            return cur.lastrowid
    except sqlite3.IntegrityError as e:
        print(f"❌ Errore di integrità: {e}")
        return None
    except Exception as e:
        print(f"❌ Errore generico: {e}")
        return None


def ottieni_conti_utente(id_utente):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT id_conto, nome_conto, tipo FROM Conti WHERE id_utente = ?", (id_utente,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero conti: {e}")
        return []


def ottieni_dettagli_conti_utente(id_utente):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        SELECT C.id_conto,
                               C.nome_conto,
                               C.tipo,
                               C.iban,
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
                        WHERE C.id_utente = ?
                        ORDER BY C.nome_conto
                        """, (id_utente,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero dettagli conti: {e}")
        return []


def modifica_conto(id_conto, id_utente, nome_conto, tipo_conto, iban=None):
    if not valida_iban_semplice(iban):
        return False
    iban_pulito = iban.strip().upper() if iban else None
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("UPDATE Conti SET nome_conto = ?, tipo = ?, iban = ? WHERE id_conto = ? AND id_utente = ?",
                        (nome_conto, tipo_conto, iban_pulito, id_conto, id_utente))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico: {e}")
        return False


def elimina_conto(id_conto, id_utente):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("SELECT tipo, valore_manuale FROM Conti WHERE id_conto = ? AND id_utente = ?", (id_conto, id_utente))
            res = cur.fetchone()
            if not res: return False
            tipo, valore_manuale = res

            saldo = 0.0
            num_transazioni = 0

            if tipo == 'Fondo Pensione':
                saldo = valore_manuale if valore_manuale else 0
            elif tipo == 'Investimento':
                cur.execute(
                    "SELECT COALESCE(SUM(quantita * prezzo_attuale_manuale), 0.0), COUNT(*) FROM Asset WHERE id_conto = ?",
                    (id_conto,))
                saldo, num_transazioni = cur.fetchone()
            else:
                cur.execute("SELECT COALESCE(SUM(importo), 0.0), COUNT(*) FROM Transazioni T WHERE T.id_conto = ?", (id_conto,))
                saldo, num_transazioni = cur.fetchone()

            if abs(saldo) > 1e-9:
                return "SALDO_NON_ZERO"
            
            # Nuovo controllo: impedisce la cancellazione se ci sono transazioni/asset, anche se il saldo è zero.
            if num_transazioni > 0:
                return "CONTO_NON_VUOTO"

            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("DELETE FROM Conti WHERE id_conto = ? AND id_utente = ?", (id_conto, id_utente))
            return cur.rowcount > 0
    except Exception as e:
        error_message = f"Errore generico durante l'eliminazione del conto: {e}"
        print(f"❌ {error_message}")
        return False, error_message

def admin_imposta_saldo_conto_corrente(id_conto, nuovo_saldo):
    """
    [SOLO ADMIN] Calcola e imposta la rettifica per forzare un nuovo saldo, senza cancellare le transazioni.
    """
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            # Calcola il saldo corrente basato solo sulle transazioni
            cur.execute("SELECT COALESCE(SUM(importo), 0.0) FROM Transazioni WHERE id_conto = ?", (id_conto,))
            saldo_transazioni = cur.fetchone()[0]
            # La rettifica è la differenza tra il nuovo saldo desiderato e il saldo delle transazioni
            rettifica = nuovo_saldo - saldo_transazioni
            cur.execute("UPDATE Conti SET rettifica_saldo = ? WHERE id_conto = ?", (rettifica, id_conto))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore in admin_imposta_saldo_conto_corrente: {e}")
        return False

# --- Funzioni Conti Condivisi ---
def crea_conto_condiviso(id_famiglia, nome_conto, tipo_conto, tipo_condivisione, lista_utenti_ids=None):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")

            cur.execute(
                "INSERT INTO ContiCondivisi (id_famiglia, nome_conto, tipo, tipo_condivisione) VALUES (?, ?, ?, ?)",
                (id_famiglia, nome_conto, tipo_conto, tipo_condivisione))
            id_nuovo_conto_condiviso = cur.lastrowid

            if tipo_condivisione == 'utenti' and lista_utenti_ids:
                for id_utente in lista_utenti_ids:
                    cur.execute(
                        "INSERT INTO PartecipazioneContoCondiviso (id_conto_condiviso, id_utente) VALUES (?, ?)",
                        (id_nuovo_conto_condiviso, id_utente))

            return id_nuovo_conto_condiviso
    except sqlite3.IntegrityError as e:
        print(f"❌ Errore di integrità durante la creazione conto condiviso: {e}")
        return None
    except Exception as e:
        print(f"❌ Errore generico durante la creazione conto condiviso: {e}")
        return None


def modifica_conto_condiviso(id_conto_condiviso, nome_conto, tipo_conto, lista_utenti_ids=None):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")

            cur.execute("UPDATE ContiCondivisi SET nome_conto = ?, tipo = ? WHERE id_conto_condiviso = ?",
                        (nome_conto, tipo_conto, id_conto_condiviso))

            cur.execute("SELECT tipo_condivisione FROM ContiCondivisi WHERE id_conto_condiviso = ?",
                        (id_conto_condiviso,))
            tipo_condivisione = cur.fetchone()[0]

            if tipo_condivisione == 'utenti':
                cur.execute("DELETE FROM PartecipazioneContoCondiviso WHERE id_conto_condiviso = ?",
                            (id_conto_condiviso,))
                if lista_utenti_ids:
                    for id_utente in lista_utenti_ids:
                        cur.execute(
                            "INSERT INTO PartecipazioneContoCondiviso (id_conto_condiviso, id_utente) VALUES (?, ?)",
                            (id_conto_condiviso, id_utente))

            return True
    except Exception as e:
        print(f"❌ Errore generico durante la modifica conto condiviso: {e}")
        return False


def elimina_conto_condiviso(id_conto_condiviso):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("DELETE FROM ContiCondivisi WHERE id_conto_condiviso = ?", (id_conto_condiviso,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante l'eliminazione conto condiviso: {e}")
        return None


def ottieni_conti_condivisi_utente(id_utente):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        -- Recupera l'elenco dei conti condivisi a cui l'utente partecipa, includendo il saldo calcolato.
                        SELECT CC.id_conto_condiviso         AS id_conto,
                               CC.nome_conto,
                               CC.tipo,
                               CC.tipo_condivisione,
                               1                             AS is_condiviso,
                               COALESCE(SUM(T.importo), 0.0) AS saldo_calcolato
                        FROM ContiCondivisi CC
                                 LEFT JOIN PartecipazioneContoCondiviso PCC
                                           ON CC.id_conto_condiviso = PCC.id_conto_condiviso
                                 LEFT JOIN TransazioniCondivise T ON CC.id_conto_condiviso = T.id_conto_condiviso -- Join per calcolare il saldo
                        WHERE (PCC.id_utente = ? AND CC.tipo_condivisione = 'utenti')
                           OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = ?) AND
                               CC.tipo_condivisione = 'famiglia')
                        GROUP BY CC.id_conto_condiviso, CC.nome_conto, CC.tipo,
                                 CC.tipo_condivisione -- GROUP BY per tutte le colonne non aggregate
                        ORDER BY CC.nome_conto
                        """, (id_utente, id_utente))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero conti condivisi utente: {e}")
        return []


def ottieni_dettagli_conto_condiviso(id_conto_condiviso):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        SELECT CC.id_conto_condiviso,
                               CC.id_famiglia,
                               CC.nome_conto,
                               CC.tipo,
                               CC.tipo_condivisione,
                               COALESCE(SUM(T.importo), 0.0) AS saldo_calcolato
                        FROM ContiCondivisi CC
                                 LEFT JOIN TransazioniCondivise T ON CC.id_conto_condiviso = T.id_conto_condiviso
                        WHERE CC.id_conto_condiviso = ?
                        GROUP BY CC.id_conto_condiviso, CC.id_famiglia, CC.nome_conto, CC.tipo, CC.tipo_condivisione
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
                                WHERE PCC.id_conto_condiviso = ?
                                """, (id_conto_condiviso,))
                    conto_dict['partecipanti'] = [dict(row) for row in cur.fetchall()]
                else:
                    conto_dict['partecipanti'] = []
                return conto_dict
            return None
    except Exception as e:
        print(f"❌ Errore generico durante il recupero dettagli conto condiviso: {e}")
        return []


def ottieni_utenti_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        SELECT U.id_utente, COALESCE(U.nome || ' ' || U.cognome, U.username) AS nome_visualizzato
                        FROM Utenti U
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = ?
                        ORDER BY nome_visualizzato
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore recupero utenti famiglia: {e}")
        return []


def ottieni_tutti_i_conti_utente(id_utente):
    """
    Restituisce una lista unificata di conti personali e conti condivisi a cui l'utente partecipa.
    Ogni conto avrà un flag 'is_condiviso'.
    """
    conti_personali = ottieni_dettagli_conti_utente(id_utente)  # Usa dettagli per avere saldo
    conti_condivisi = ottieni_conti_condivisi_utente(id_utente)

    risultato_unificato = []
    for conto in conti_personali:
        conto['is_condiviso'] = False
        risultato_unificato.append(conto)
    for conto in conti_condivisi:
        conto['is_condiviso'] = True
        risultato_unificato.append(conto)

    return risultato_unificato


def ottieni_tutti_i_conti_famiglia(id_famiglia):
    """
    Restituisce una lista unificata di TUTTI i conti (personali e condivisi)
    di una data famiglia, escludendo quelli di investimento.
    """
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            # Conti Personali di tutti i membri della famiglia
            cur.execute("""
                        SELECT C.id_conto, C.nome_conto, C.tipo, 0 as is_condiviso, U.nome as proprietario
                        FROM Conti C
                                 JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                 JOIN Utenti U ON C.id_utente = U.id_utente
                        WHERE AF.id_famiglia = ?
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
                        WHERE id_famiglia = ?
                        """, (id_famiglia,))
            conti_condivisi = [dict(row) for row in cur.fetchall()]

            return conti_personali + conti_condivisi

    except Exception as e:
        print(f"❌ Errore generico durante il recupero di tutti i conti famiglia: {e}")
        return []


def esegui_giroconto(id_sorgente, tipo_sorgente, id_destinazione, tipo_destinazione, importo, data, descrizione,
                     id_utente_autore):
    """
    Esegue un giroconto tra due conti (personali o condivisi).
    Crea due transazioni opposte in modo atomico.
    """
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")

            desc_sorgente = f"Giroconto Uscita: {descrizione}"
            desc_destinazione = f"Giroconto Entrata: {descrizione}"

            # Debito sul conto sorgente
            if tipo_sorgente == 'P':
                aggiungi_transazione(id_sorgente, data, desc_sorgente, -abs(importo), cursor=cur)
            elif tipo_sorgente == 'C':
                aggiungi_transazione_condivisa(id_utente_autore, id_sorgente, data, desc_sorgente, -abs(importo),
                                               cursor=cur)

            # Credito sul conto destinazione
            if tipo_destinazione == 'P':
                aggiungi_transazione(id_destinazione, data, desc_destinazione, abs(importo), cursor=cur)
            elif tipo_destinazione == 'C':
                aggiungi_transazione_condivisa(id_utente_autore, id_destinazione, data, desc_destinazione, abs(importo),
                                               cursor=cur)

            con.commit()
            return True
    except Exception as e:
        print(f"❌ Errore durante l'esecuzione del giroconto: {e}")
        if con: con.rollback()
        return False


# --- Funzioni Categorie ---
def aggiungi_categoria(id_famiglia, nome_categoria):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("INSERT INTO Categorie (id_famiglia, nome_categoria) VALUES (?, ?)",
                        (id_famiglia, nome_categoria.upper()))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        print(f"❌ Errore generico: {e}")
        return None


def modifica_categoria(id_categoria, nuovo_nome):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("UPDATE Categorie SET nome_categoria = ? WHERE id_categoria = ?",
                        (nuovo_nome.upper(), id_categoria))
            return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"❌ Errore generico durante la modifica della categoria: {e}")
        return False


def elimina_categoria(id_categoria):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("DELETE FROM Categorie WHERE id_categoria = ?", (id_categoria,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante l'eliminazione della categoria: {e}")
        return False


def ottieni_categorie(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT id_categoria, nome_categoria FROM Categorie WHERE id_famiglia = ?", (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero categorie: {e}")
        return []

# --- Funzioni Sottocategorie ---
def aggiungi_sottocategoria(id_categoria, nome_sottocategoria):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("INSERT INTO Sottocategorie (id_categoria, nome_sottocategoria) VALUES (?, ?)",
                        (id_categoria, nome_sottocategoria.upper()))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        print(f"❌ Errore durante l'aggiunta della sottocategoria: {e}")
        return None

def modifica_sottocategoria(id_sottocategoria, nuovo_nome):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("UPDATE Sottocategorie SET nome_sottocategoria = ? WHERE id_sottocategoria = ?",
                        (nuovo_nome.upper(), id_sottocategoria))
            return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"❌ Errore durante la modifica della sottocategoria: {e}")
        return False

def elimina_sottocategoria(id_sottocategoria):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("DELETE FROM Sottocategorie WHERE id_sottocategoria = ?", (id_sottocategoria,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore durante l'eliminazione della sottocategoria: {e}")
        return False

def ottieni_sottocategorie(id_categoria):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT id_sottocategoria, nome_sottocategoria FROM Sottocategorie WHERE id_categoria = ?", (id_categoria,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore durante il recupero sottocategorie: {e}")
        return []

def ottieni_categorie_e_sottocategorie(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                SELECT C.id_categoria, C.nome_categoria, S.id_sottocategoria, S.nome_sottocategoria
                FROM Categorie C
                LEFT JOIN Sottocategorie S ON C.id_categoria = S.id_categoria
                WHERE C.id_famiglia = ?
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
        print(f"❌ Errore durante il recupero di categorie e sottocategorie: {e}")
        return {}


# --- Funzioni Transazioni Personali ---
def aggiungi_transazione(id_conto, data, descrizione, importo, id_sottocategoria=None, cursor=None):
    # Permette di passare un cursore esistente per le transazioni atomiche
    if cursor:
        cursor.execute(
            "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo) VALUES (?, ?, ?, ?, ?)",
            (id_conto, id_sottocategoria, data, descrizione, importo))
        return cursor.lastrowid
    else:
        try:
            with sqlite3.connect(DB_FILE) as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo) VALUES (?, ?, ?, ?, ?)",
                    (id_conto, id_sottocategoria, data, descrizione, importo))
                return cur.lastrowid
        except Exception as e:
            print(f"❌ Errore generico: {e}")
            return None


def modifica_transazione(id_transazione, data, descrizione, importo, id_sottocategoria=None, id_conto=None):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            if id_conto is not None:
                cur.execute(
                    "UPDATE Transazioni SET data = ?, descrizione = ?, importo = ?, id_sottocategoria = ?, id_conto = ? WHERE id_transazione = ?",
                    (data, descrizione, importo, id_sottocategoria, id_conto, id_transazione))
            else:
                cur.execute(
                    "UPDATE Transazioni SET data = ?, descrizione = ?, importo = ?, id_sottocategoria = ? WHERE id_transazione = ?",
                    (data, descrizione, importo, id_sottocategoria, id_transazione))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante la modifica: {e}")
        return False


def elimina_transazione(id_transazione):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("DELETE FROM Transazioni WHERE id_transazione = ?", (id_transazione,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante l'eliminazione: {e}")
        return None


def ottieni_transazioni_utente(id_utente, anno, mese):
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"

    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
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
                        WHERE C.id_utente = ?
                          AND C.tipo != 'Fondo Pensione' AND T.data BETWEEN ? AND ?

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
                        WHERE (PCC.id_utente = ? AND CC.tipo_condivisione = 'utenti')
                           OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = ?) AND
                               CC.tipo_condivisione = 'famiglia') AND TC.data BETWEEN ? AND ?

                        ORDER BY data DESC, id_transazione DESC, id_transazione_condivisa DESC
                        """, (id_utente, data_inizio, data_fine, id_utente, id_utente, data_inizio, data_fine))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero transazioni: {e}")
        return []


# --- Funzioni Transazioni Condivise ---
def aggiungi_transazione_condivisa(id_utente_autore, id_conto_condiviso, data, descrizione, importo, id_sottocategoria=None,
                                   cursor=None):
    # Permette di passare un cursore esistente per le transazioni atomiche
    if cursor:
        cursor.execute(
            "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, descrizione, importo) VALUES (?, ?, ?, ?, ?, ?)",
            (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, descrizione, importo))
        return cursor.lastrowid
    else:
        try:
            with sqlite3.connect(DB_FILE) as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO TransazioniCondivise (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, descrizione, importo) VALUES (?, ?, ?, ?, ?, ?)",
                    (id_utente_autore, id_conto_condiviso, id_sottocategoria, data, descrizione, importo))
                return cur.lastrowid
        except Exception as e:
            print(f"❌ Errore generico durante l'aggiunta transazione condivisa: {e}")
            return None


def modifica_transazione_condivisa(id_transazione_condivisa, data, descrizione, importo, id_sottocategoria=None):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("""
                        UPDATE TransazioniCondivise
                        SET data         = ?,
                            descrizione  = ?,
                            importo      = ?,
                            id_sottocategoria = ?
                        WHERE id_transazione_condivisa = ?
                        """, (data, descrizione, importo, id_sottocategoria, id_transazione_condivisa))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante la modifica transazione condivisa: {e}")
        return False


def elimina_transazione_condivisa(id_transazione_condivisa):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("DELETE FROM TransazioniCondivise WHERE id_transazione_condivisa = ?",
                        (id_transazione_condivisa,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante l'eliminazione transazione condivisa: {e}")
        return None


def ottieni_transazioni_condivise_utente(id_utente):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
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
                        WHERE (PCC.id_utente = ? AND CC.tipo_condivisione = 'utenti')
                           OR (CC.id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = ?) AND
                               CC.tipo_condivisione = 'famiglia')
                        ORDER BY TC.data DESC, TC.id_transazione_condivisa DESC
                        """, (id_utente, id_utente))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero transazioni condivise utente: {e}")
        return []


def ottieni_transazioni_condivise_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
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
                        WHERE CC.id_famiglia = ?
                          AND CC.tipo_condivisione = 'famiglia'
                        ORDER BY TC.data DESC, TC.id_transazione_condivisa DESC
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero transazioni condivise famiglia: {e}")
        return []


# --- Funzioni Ruoli e Famiglia ---
def ottieni_ruolo_utente(id_utente, id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("SELECT ruolo FROM Appartenenza_Famiglia WHERE id_utente = ? AND id_famiglia = ?",
                        (id_utente, id_famiglia))
            res = cur.fetchone()
            return res[0] if res else None
    except Exception as e:
        print(f"❌ Errore generico: {e}")
        return None


def ottieni_totali_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
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
                        WHERE AF.id_famiglia = ?
                        GROUP BY U.id_utente, nome_visualizzato
                        ORDER BY nome_visualizzato;
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero totali famiglia: {e}")
        return []


def ottieni_riepilogo_patrimonio_famiglia_aggregato(id_famiglia, anno, mese):
    """
    Calcola la liquidità totale, gli investimenti totali e il patrimonio netto per un'intera famiglia.
    """
    data_fine = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).strftime('%Y-%m-%d')

    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            print(
                f"DEBUG (ottieni_riepilogo_patrimonio_famiglia_aggregato): Calcolo patrimonio per famiglia {id_famiglia}")

            # 1. Liquidità totale (Conti personali + Conti condivisi + Rettifiche personali)
            cur.execute("""
                        SELECT (SELECT COALESCE(SUM(T.importo), 0.0)
                                FROM Transazioni T
                                         JOIN Conti C ON T.id_conto = C.id_conto
                                         JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                WHERE AF.id_famiglia = ?
                                  AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')
                                  AND T.data <= ?)
                                   +
                               (SELECT COALESCE(SUM(TC.importo), 0.0)
                                FROM TransazioniCondivise TC
                                         JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                                WHERE CC.id_famiglia = ?
                                  AND TC.data <= ?)
                                   +
                               (SELECT COALESCE(SUM(C.rettifica_saldo), 0.0)
                                FROM Conti C
                                         JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                WHERE AF.id_famiglia = ?
                                  AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')) AS liquidita_totale
                        """, (id_famiglia, data_fine, id_famiglia, data_fine, id_famiglia))
            liquidita_totale = cur.fetchone()[0] or 0.0
            print(f"DEBUG (ottieni_riepilogo_patrimonio_famiglia_aggregato): Liquidità totale: {liquidita_totale}")

            # 2. Investimenti totali (Asset + Fondi Pensione di tutti gli utenti della famiglia)
            cur.execute("""
                        SELECT (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                FROM Asset A
                                         JOIN Conti C ON A.id_conto = C.id_conto
                                         JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                WHERE AF.id_famiglia = ?
                                  AND C.tipo = 'Investimento')
                                   +
                               (SELECT COALESCE(SUM(C.valore_manuale), 0.0)
                                FROM Conti C
                                         JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                                WHERE AF.id_famiglia = ?
                                  AND C.tipo = 'Fondo Pensione') AS investimenti_totali
                        """, (id_famiglia, id_famiglia))
            investimenti_totali = cur.fetchone()[0] or 0.0
            print(
                f"DEBUG (ottieni_riepilogo_patrimonio_famiglia_aggregato): Investimenti totali: {investimenti_totali}")

            patrimonio_netto = liquidita_totale + investimenti_totali
            print(f"DEBUG (ottieni_riepilogo_patrimonio_famiglia_aggregato): Patrimonio netto: {patrimonio_netto}")

            return {'liquidita': liquidita_totale, 'investimenti': investimenti_totali,
                    'patrimonio_netto': patrimonio_netto}
    except Exception as e:
        print(f"❌ Errore durante il calcolo del riepilogo patrimonio famiglia aggregato: {e}")
        return {'liquidita': 0, 'investimenti': 0, 'patrimonio_netto': 0}


def ottieni_riepilogo_patrimonio_utente(id_utente, anno, mese):
    """
    Calcola la liquidità, gli investimenti e il patrimonio netto per un singolo utente,
    includendo la sua quota dei conti condivisi.
    """
    data_fine = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).strftime('%Y-%m-%d')

    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            print(f"DEBUG (ottieni_riepilogo_patrimonio_utente): Calcolo patrimonio per utente {id_utente}")

            # 1. Liquidità personale (conti non di investimento)
            cur.execute("""
                        SELECT COALESCE(SUM(T.importo), 0.0)
                        FROM Transazioni T
                                 JOIN Conti C ON T.id_conto = C.id_conto
                        WHERE C.id_utente = ?
                          AND C.tipo NOT IN ('Investimento', 'Fondo Pensione')
                          AND T.data <= ?
                        """, (id_utente, data_fine))
            liquidita_transazioni = cur.fetchone()[0] or 0.0

            cur.execute("""
                        SELECT COALESCE(SUM(rettifica_saldo), 0.0)
                        FROM Conti
                        WHERE id_utente = ?
                          AND tipo NOT IN ('Investimento', 'Fondo Pensione')
                        """, (id_utente,))
            rettifiche_personali = cur.fetchone()[0] or 0.0
            liquidita_personale = liquidita_transazioni + rettifiche_personali
            print(
                f"DEBUG (ottieni_riepilogo_patrimonio_utente): Liquidità personale (solo conti privati): {liquidita_personale}")

            # 2. Investimenti personali (Asset + Fondi Pensione)
            cur.execute("""
                        SELECT (SELECT COALESCE(SUM(A.quantita * A.prezzo_attuale_manuale), 0.0)
                                FROM Asset A
                                         JOIN Conti C ON A.id_conto = C.id_conto
                                WHERE C.id_utente = ?
                                  AND C.tipo = 'Investimento')
                                   +
                               (SELECT COALESCE(SUM(C.valore_manuale), 0.0)
                                FROM Conti C
                                WHERE C.id_utente = ?
                                  AND C.tipo = 'Fondo Pensione')
                        """, (id_utente, id_utente))
            investimenti_personali = cur.fetchone()[0] or 0.0
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
                                  AND data <= ?) as saldo_conto,
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
                            WHERE id_utente = ?
                            UNION
                            -- Conti della mia famiglia
                            SELECT id_conto_condiviso
                            FROM ContiCondivisi
                            WHERE tipo_condivisione = 'famiglia'
                              AND id_famiglia = (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = ?))
                        """, (data_fine, id_utente, id_utente))

            conti_condivisi_da_calcolare = cur.fetchall()
            print(
                f"DEBUG (ottieni_riepilogo_patrimonio_utente): Conti condivisi da calcolare: {conti_condivisi_da_calcolare}")

            for row in conti_condivisi_da_calcolare:
                id_conto_cond, saldo_conto, num_partecipanti = row
                if num_partecipanti and num_partecipanti > 0:
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
        print(f"❌ Errore durante il calcolo del riepilogo patrimonio utente: {e}")
        return {'liquidita': 0, 'investimenti': 0, 'patrimonio_netto': 0}


def ottieni_dettagli_famiglia(id_famiglia, anno, mese):
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"

    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
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
                        WHERE AF.id_famiglia = ?
                          AND C.tipo != 'Fondo Pensione' AND T.data BETWEEN ? AND ? AND UPPER(T.descrizione) NOT LIKE '%SALDO INIZIALE%'
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
                        WHERE CC.id_famiglia = ?
                          AND TC.data BETWEEN ? AND ?
                          AND UPPER(TC.descrizione) NOT LIKE '%SALDO INIZIALE%' -- Include tutti i conti condivisi della famiglia
                        ORDER BY data DESC, utente_nome, conto_nome
                        """, (id_famiglia, data_inizio, data_fine, id_famiglia, data_inizio, data_fine))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero dettagli famiglia: {e}")
        return []


def ottieni_membri_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        SELECT U.id_utente,
                               U.username,
                               COALESCE(U.nome || ' ' || U.cognome, U.username) AS nome_visualizzato,
                               AF.ruolo
                        FROM Utenti U
                                 JOIN Appartenenza_Famiglia AF ON U.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = ?
                        ORDER BY nome_visualizzato
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero membri: {e}")
        return []


def modifica_ruolo_utente(id_utente, id_famiglia, nuovo_ruolo):
    if nuovo_ruolo not in ['admin', 'livello1', 'livello2', 'livello3']:
        return False
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("UPDATE Appartenenza_Famiglia SET ruolo = ? WHERE id_utente = ? AND id_famiglia = ?",
                        (nuovo_ruolo, id_utente, id_famiglia))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante la modifica del ruolo: {e}")
        return False


def rimuovi_utente_da_famiglia(id_utente, id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("DELETE FROM Appartenenza_Famiglia WHERE id_utente = ? AND id_famiglia = ?",
                        (id_utente, id_famiglia))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante la rimozione utente: {e}")
        return False


# --- Funzioni Fondo Pensione ---
def aggiorna_valore_fondo_pensione(id_conto, nuovo_valore):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("UPDATE Conti SET valore_manuale = ? WHERE id_conto = ? AND tipo = 'Fondo Pensione'",
                        (nuovo_valore, id_conto))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore durante l'aggiornamento del valore del fondo pensione: {e}")
        return False


def esegui_operazione_fondo_pensione(id_fondo_pensione, tipo_operazione, importo, data, id_conto_collegato=None):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")

            if tipo_operazione == 'VERSAMENTO':
                descrizione = f"Versamento a fondo pensione (ID: {id_fondo_pensione})"
                cur.execute("INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (?, ?, ?, ?)",
                            (id_conto_collegato, data, descrizione, -abs(importo)))
            elif tipo_operazione == 'PRELIEVO':
                descrizione = f"Prelievo da fondo pensione (ID: {id_fondo_pensione})"
                cur.execute("INSERT INTO Transazioni (id_conto, data, descrizione, importo) VALUES (?, ?, ?, ?)",
                            (id_conto_collegato, data, descrizione, abs(importo)))

            if tipo_operazione in ['VERSAMENTO', 'VERSAMENTO_ESTERNO']:
                cur.execute("UPDATE Conti SET valore_manuale = valore_manuale + ? WHERE id_conto = ?",
                            (abs(importo), id_fondo_pensione))
            elif tipo_operazione == 'PRELIEVO':
                cur.execute("UPDATE Conti SET valore_manuale = valore_manuale - ? WHERE id_conto = ?",
                            (abs(importo), id_fondo_pensione))

            con.commit()
            return True
    except Exception as e:
        print(f"❌ Errore durante l'esecuzione dell'operazione sul fondo pensione: {e}")
        if con: con.rollback()
        return False


# --- Funzioni Budget ---
def imposta_budget(id_famiglia, id_sottocategoria, importo_limite):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("""
                        INSERT INTO Budget (id_famiglia, id_sottocategoria, importo_limite, periodo)
                        VALUES (?, ?, ?, 'Mensile') ON CONFLICT(id_famiglia, id_sottocategoria, periodo) DO
                        UPDATE SET importo_limite = excluded.importo_limite
                        """, (id_famiglia, id_sottocategoria, importo_limite))
            return True
    except Exception as e:
        print(f"❌ Errore generico durante l'impostazione del budget: {e}")
        return False


def ottieni_budget_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        SELECT B.id_budget, B.id_sottocategoria, C.nome_categoria, S.nome_sottocategoria, B.importo_limite
                        FROM Budget B
                                 JOIN Sottocategorie S ON B.id_sottocategoria = S.id_sottocategoria
                                 JOIN Categorie C ON S.id_categoria = C.id_categoria
                        WHERE B.id_famiglia = ?
                          AND B.periodo = 'Mensile'
                        ORDER BY C.nome_categoria, S.nome_sottocategoria
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero budget: {e}")
        return []


def ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese):
    data_inizio = f"{anno}-{mese:02d}-01"
    ultimo_giorno = (datetime.date(anno, mese, 1) + relativedelta(months=1) - relativedelta(days=1)).day
    data_fine = f"{anno}-{mese:02d}-{ultimo_giorno}"
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                SELECT
                    C.id_categoria,
                    C.nome_categoria,
                    S.id_sottocategoria,
                    S.nome_sottocategoria,
                    COALESCE(B.importo_limite, 0.0) as importo_limite,
                    COALESCE(T_SPESE.spesa_totale, 0.0) as spesa_totale
                FROM Categorie C
                JOIN Sottocategorie S ON C.id_categoria = S.id_categoria
                LEFT JOIN Budget B ON S.id_sottocategoria = B.id_sottocategoria AND B.id_famiglia = C.id_famiglia AND B.periodo = 'Mensile'
                LEFT JOIN (
                    SELECT
                        T.id_sottocategoria,
                        SUM(T.importo) as spesa_totale
                    FROM Transazioni T
                    JOIN Conti CO ON T.id_conto = CO.id_conto
                    JOIN Appartenenza_Famiglia AF ON CO.id_utente = AF.id_utente
                    WHERE AF.id_famiglia = ? AND T.importo < 0 AND T.data BETWEEN ? AND ?
                    GROUP BY T.id_sottocategoria
                    UNION ALL
                    SELECT
                        TC.id_sottocategoria,
                        SUM(TC.importo) as spesa_totale
                    FROM TransazioniCondivise TC
                    JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                    WHERE CC.id_famiglia = ? AND TC.importo < 0 AND TC.data BETWEEN ? AND ?
                    GROUP BY TC.id_sottocategoria
                ) AS T_SPESE ON S.id_sottocategoria = T_SPESE.id_sottocategoria
                WHERE C.id_famiglia = ?
                ORDER BY C.nome_categoria, S.nome_sottocategoria;
            """, (id_famiglia, data_inizio, data_fine, id_famiglia, data_inizio, data_fine, id_famiglia))
            
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
        print(f"❌ Errore generico durante il recupero riepilogo budget: {e}")
        return {}


def salva_budget_mese_corrente(id_famiglia, anno, mese):
    try:
        riepilogo_corrente = ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese)
        if not riepilogo_corrente:
            return False
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            dati_da_salvare = []
            for cat_id, cat_data in riepilogo_corrente.items():
                for sub_data in cat_data['sottocategorie']:
                    dati_da_salvare.append((
                        id_famiglia, sub_data['id_sottocategoria'], sub_data['nome_sottocategoria'],
                        anno, mese, sub_data['importo_limite'], abs(sub_data['spesa_totale'])
                    ))
            
            cur.executemany("""
                            INSERT INTO Budget_Storico (id_famiglia, id_sottocategoria, nome_sottocategoria, anno, mese,
                                                        importo_limite, importo_speso)
                            VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id_famiglia, id_sottocategoria, anno, mese) DO
                            UPDATE SET importo_limite = excluded.importo_limite, importo_speso = excluded.importo_speso, nome_sottocategoria = excluded.nome_sottocategoria
                            """, dati_da_salvare)
            return True
    except Exception as e:
        print(f"❌ Errore generico durante la storicizzazione del budget: {e}")
        return False


def ottieni_anni_mesi_storicizzati(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            # Query aggiornata per leggere i mesi da TUTTE le transazioni (personali e condivise)
            cur.execute("""
                SELECT DISTINCT anno, mese FROM (
                    -- Mesi da transazioni personali
                    SELECT
                        CAST(strftime('%Y', T.data) AS INTEGER) as anno,
                        CAST(strftime('%m', T.data) AS INTEGER) as mese
                    FROM Transazioni T
                    JOIN Conti C ON T.id_conto = C.id_conto
                    JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                    WHERE AF.id_famiglia = ?

                    UNION

                    -- Mesi da transazioni condivise
                    SELECT
                        CAST(strftime('%Y', TC.data) AS INTEGER) as anno,
                        CAST(strftime('%m', TC.data) AS INTEGER) as mese
                    FROM TransazioniCondivise TC
                    JOIN ContiCondivisi CC ON TC.id_conto_condiviso = CC.id_conto_condiviso
                    WHERE CC.id_famiglia = ?
                ) ORDER BY anno DESC, mese DESC
            """, (id_famiglia, id_famiglia))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero periodi storici: {e}")
        return []


def ottieni_storico_budget_per_export(id_famiglia, lista_periodi):
    if not lista_periodi: return []
    placeholders = " OR ".join(["(anno = ? AND mese = ?)"] * len(lista_periodi))
    params = [id_famiglia] + [item for sublist in lista_periodi for item in sublist]
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            query = f"""
                SELECT anno, mese, nome_categoria, importo_limite, importo_speso, (importo_limite - importo_speso) AS rimanente
                FROM Budget_Storico
                WHERE id_famiglia = ? AND ({placeholders})
                ORDER BY anno, mese, nome_categoria
            """
            cur.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero storico per export: {e}")
        return []


# --- Funzioni Prestiti ---
def aggiungi_prestito(id_famiglia, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                      importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default=None,
                      id_categoria_default=None):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("""
                        INSERT INTO Prestiti (id_famiglia, nome, tipo, descrizione, data_inizio, numero_mesi_totali,
                                              importo_finanziato, importo_interessi, importo_residuo, importo_rata,
                                              giorno_scadenza_rata, id_conto_pagamento_default,
                                              id_categoria_pagamento_default)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (id_famiglia, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                              importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default,
                              id_categoria_default))
            return cur.lastrowid
    except Exception as e:
        print(f"❌ Errore generico durante l'aggiunta del prestito: {e}")
        return None


def modifica_prestito(id_prestito, nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                      importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default=None,
                      id_categoria_default=None):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("""
                        UPDATE Prestiti
                        SET nome                           = ?,
                            tipo                           = ?,
                            descrizione                    = ?,
                            data_inizio                    = ?,
                            numero_mesi_totali             = ?,
                            importo_finanziato             = ?,
                            importo_interessi              = ?,
                            importo_residuo                = ?,
                            importo_rata                   = ?,
                            giorno_scadenza_rata           = ?,
                            id_conto_pagamento_default     = ?,
                            id_categoria_pagamento_default = ?
                        WHERE id_prestito = ?
                        """, (nome, tipo, descrizione, data_inizio, numero_mesi_totali, importo_finanziato,
                              importo_interessi, importo_residuo, importo_rata, giorno_scadenza_rata, id_conto_default,
                              id_categoria_default, id_prestito))
            return True
    except Exception as e:
        print(f"❌ Errore generico durante la modifica del prestito: {e}")
        return False


def elimina_prestito(id_prestito):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("DELETE FROM Prestiti WHERE id_prestito = ?", (id_prestito,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante l'eliminazione del prestito: {e}")
        return None


def ottieni_prestiti_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        SELECT P.*, 
                               C.nome_categoria AS nome_categoria_default,
                               (SELECT COUNT(*) FROM StoricoPagamentiRate WHERE id_prestito = P.id_prestito) as rate_pagate
                        FROM Prestiti P
                                 LEFT JOIN Categorie C ON P.id_categoria_pagamento_default = C.id_categoria
                        WHERE P.id_famiglia = ?
                        ORDER BY P.data_inizio DESC
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero prestiti: {e}")
        return []


def check_e_paga_rate_scadute(id_famiglia):
    oggi = datetime.date.today()
    pagamenti_eseguiti = 0
    try:
        prestiti_attivi = ottieni_prestiti_famiglia(id_famiglia)
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            for p in prestiti_attivi:
                if p['importo_residuo'] > 0 and p['id_conto_pagamento_default'] and p[
                    'id_categoria_pagamento_default'] and oggi.day >= p['giorno_scadenza_rata']:
                    cur.execute("SELECT 1 FROM StoricoPagamentiRate WHERE id_prestito = ? AND anno = ? AND mese = ?",
                                (p['id_prestito'], oggi.year, oggi.month))
                    if cur.fetchone() is None:
                        importo_da_pagare = min(p['importo_rata'], p['importo_residuo'])
                        effettua_pagamento_rata(p['id_prestito'], p['id_conto_pagamento_default'], importo_da_pagare,
                                                oggi.strftime('%Y-%m-%d'), p['id_categoria_pagamento_default'],
                                                p['nome'])
                        pagamenti_eseguiti += 1
        return pagamenti_eseguiti
    except Exception as e:
        print(f"❌ Errore critico durante il controllo delle rate scadute: {e}")
        return 0


def effettua_pagamento_rata(id_prestito, id_conto_pagamento, importo_pagato, data_pagamento, categoria_pagamento_id,
                            nome_prestito=""):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("BEGIN TRANSACTION;")
            cur.execute("UPDATE Prestiti SET importo_residuo = importo_residuo - ? WHERE id_prestito = ?",
                        (importo_pagato, id_prestito))
            descrizione = f"Pagamento rata {nome_prestito} (Prestito ID: {id_prestito})"
            cur.execute(
                "INSERT INTO Transazioni (id_conto, id_sottocategoria, data, descrizione, importo) VALUES (?, ?, ?, ?, ?)",
                (id_conto_pagamento, categoria_pagamento_id, data_pagamento, descrizione, -abs(importo_pagato)))
            data_dt = parse_date(data_pagamento)
            cur.execute(
                "INSERT INTO StoricoPagamentiRate (id_prestito, anno, mese, data_pagamento, importo_pagato) VALUES (?, ?, ?, ?, ?) ON CONFLICT(id_prestito, anno, mese) DO NOTHING",
                (id_prestito, data_dt.year, data_dt.month, data_pagamento, importo_pagato))
            con.commit()
            return True
    except Exception as e:
        print(f"❌ Errore durante l'esecuzione del pagamento rata: {e}")
        if con: con.rollback()
        return False


# --- Funzioni Immobili ---
def aggiungi_immobile(id_famiglia, nome, via, citta, valore_acquisto, valore_attuale, nuda_proprieta,
                      id_prestito_collegato=None):
    db_id_prestito = id_prestito_collegato if isinstance(id_prestito_collegato, int) else None
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("""
                        INSERT INTO Immobili (id_famiglia, nome, via, citta, valore_acquisto, valore_attuale,
                                              nuda_proprieta, id_prestito_collegato)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (id_famiglia, nome, via, citta, valore_acquisto, valore_attuale, 1 if nuda_proprieta else 0,
                         db_id_prestito))
            return cur.lastrowid
    except Exception as e:
        print(f"❌ Errore generico durante l'aggiunta dell'immobile: {e}")
        return None


def modifica_immobile(id_immobile, nome, via, citta, valore_acquisto, valore_attuale, nuda_proprieta,
                      id_prestito_collegato=None):
    db_id_prestito = id_prestito_collegato if isinstance(id_prestito_collegato, int) else None
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("""
                        UPDATE Immobili
                        SET nome                  = ?,
                            via                   = ?,
                            citta                 = ?,
                            valore_acquisto       = ?,
                            valore_attuale        = ?,
                            nuda_proprieta        = ?,
                            id_prestito_collegato = ?
                        WHERE id_immobile = ?
                        """,
                        (nome, via, citta, valore_acquisto, valore_attuale, 1 if nuda_proprieta else 0, db_id_prestito,
                         id_immobile))
            return True
    except Exception as e:
        print(f"❌ Errore generico durante la modifica dell'immobile: {e}")
        return False


def elimina_immobile(id_immobile):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("DELETE FROM Immobili WHERE id_immobile = ?", (id_immobile,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante l'eliminazione dell'immobile: {e}")
        return None


def ottieni_immobili_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        SELECT I.*, P.importo_residuo AS valore_mutuo_residuo, P.nome AS nome_mutuo
                        FROM Immobili I
                                 LEFT JOIN Prestiti P ON I.id_prestito_collegato = P.id_prestito
                        WHERE I.id_famiglia = ?
                        ORDER BY I.nome
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero immobili: {e}")
        return []


# --- Funzioni Asset ---
def compra_asset(id_conto_investimento, ticker, nome_asset, quantita, costo_unitario_nuovo, tipo_mov='COMPRA',
                 prezzo_attuale_override=None):
    ticker_upper = ticker.upper()
    nome_asset_upper = nome_asset.upper()
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute(
                "SELECT id_asset, quantita, costo_iniziale_unitario FROM Asset WHERE id_conto = ? AND ticker = ?",
                (id_conto_investimento, ticker_upper))
            risultato = cur.fetchone()
            cur.execute(
                "INSERT INTO Storico_Asset (id_conto, ticker, data, tipo_movimento, quantita, prezzo_unitario_movimento) VALUES (?, ?, ?, ?, ?, ?)",
                (id_conto_investimento, ticker_upper, datetime.date.today().strftime('%Y-%m-%d'), tipo_mov, quantita,
                 costo_unitario_nuovo))
            if risultato:
                id_asset_aggiornato, vecchia_quantita, vecchio_costo_medio = risultato
                nuova_quantita_totale = vecchia_quantita + quantita
                nuovo_costo_medio = (
                                                vecchia_quantita * vecchio_costo_medio + quantita * costo_unitario_nuovo) / nuova_quantita_totale
                cur.execute(
                    "UPDATE Asset SET quantita = ?, nome_asset = ?, costo_iniziale_unitario = ? WHERE id_asset = ?",
                    (nuova_quantita_totale, nome_asset_upper, nuovo_costo_medio, id_asset_aggiornato))
            else:
                prezzo_attuale = prezzo_attuale_override if prezzo_attuale_override is not None else costo_unitario_nuovo
                cur.execute(
                    "INSERT INTO Asset (id_conto, ticker, nome_asset, quantita, costo_iniziale_unitario, prezzo_attuale_manuale) VALUES (?, ?, ?, ?, ?, ?)",
                    (id_conto_investimento, ticker_upper, nome_asset_upper, quantita, costo_unitario_nuovo,
                     prezzo_attuale))
            return True
    except Exception as e:
        print(f"❌ Errore generico durante l'acquisto asset: {e}")
        return False


def vendi_asset(id_conto_investimento, ticker, quantita_da_vendere, prezzo_di_vendita_unitario):
    ticker_upper = ticker.upper()
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("SELECT id_asset, quantita FROM Asset WHERE id_conto = ? AND ticker = ?",
                        (id_conto_investimento, ticker_upper))
            risultato = cur.fetchone()
            if not risultato: return False
            id_asset, quantita_attuale = risultato
            if quantita_da_vendere > quantita_attuale and abs(
                quantita_da_vendere - quantita_attuale) > 1e-9: return False

            nuova_quantita = quantita_attuale - quantita_da_vendere
            cur.execute(
                "INSERT INTO Storico_Asset (id_conto, ticker, data, tipo_movimento, quantita, prezzo_unitario_movimento) VALUES (?, ?, ?, ?, ?, ?)",
                (id_conto_investimento, ticker_upper, datetime.date.today().strftime('%Y-%m-%d'), 'VENDI',
                 quantita_da_vendere, prezzo_di_vendita_unitario))
            if nuova_quantita < 1e-9:
                cur.execute("DELETE FROM Asset WHERE id_asset = ?", (id_asset,))
            else:
                cur.execute("UPDATE Asset SET quantita = ? WHERE id_asset = ?", (nuova_quantita, id_asset))
            return True
    except Exception as e:
        print(f"❌ Errore generico durante la vendita asset: {e}")
        return False


def ottieni_portafoglio(id_conto_investimento):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                        SELECT id_asset,
                               ticker,
                               nome_asset,
                               quantita,
                               prezzo_attuale_manuale,
                               costo_iniziale_unitario,
                               (prezzo_attuale_manuale - costo_iniziale_unitario)              AS gain_loss_unitario,
                               (quantita * (prezzo_attuale_manuale - costo_iniziale_unitario)) AS gain_loss_totale
                        FROM Asset
                        WHERE id_conto = ?
                        ORDER BY ticker
                        """, (id_conto_investimento,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero portafoglio: {e}")
        return []


def aggiorna_prezzo_manuale_asset(id_asset, nuovo_prezzo):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("UPDATE Asset SET prezzo_attuale_manuale = ? WHERE id_asset = ?", (nuovo_prezzo, id_asset))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore generico durante l'aggiornamento prezzo: {e}")
        return False


def modifica_asset_dettagli(id_asset, nuovo_ticker, nuovo_nome):
    nuovo_ticker_upper = nuovo_ticker.upper()
    nuovo_nome_upper = nuovo_nome.upper()
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")
            cur.execute("UPDATE Asset SET ticker = ?, nome_asset = ? WHERE id_asset = ?",
                        (nuovo_ticker_upper, nuovo_nome_upper, id_asset))
            return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"❌ Errore generico durante l'aggiornamento dettagli asset: {e}")
        return False


# --- Funzioni Export ---
def ottieni_riepilogo_conti_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
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
                        WHERE AF.id_famiglia = ?
                        ORDER BY membro, C.tipo, C.nome_conto
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero riepilogo conti famiglia: {e}")
        return []


def ottieni_dettaglio_portafogli_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
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
                        WHERE AF.id_famiglia = ?
                          AND C.tipo = 'Investimento'
                        ORDER BY membro, C.nome_conto, A.ticker
                        """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero dettaglio portafogli famiglia: {e}")
        return []


def ottieni_transazioni_famiglia_per_export(id_famiglia, data_inizio, data_fine):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
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
                        WHERE AF.id_famiglia = ?
                          AND T.data BETWEEN ? AND ?
                          AND C.tipo != 'Fondo Pensione'
                        ORDER BY T.data DESC, T.id_transazione DESC
                        """, (id_famiglia, data_inizio, data_fine))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore generico durante il recupero transazioni per export: {e}")
        return []


def ottieni_prima_famiglia_utente(id_utente):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = ? LIMIT 1", (id_utente,))
            res = cur.fetchone()
            return res[0] if res else None
    except Exception as e:
        print(f"❌ Errore generico: {e}")
        return None


# --- NUOVE FUNZIONI PER SPESE FISSE ---
def aggiungi_spesa_fissa(id_famiglia, nome, importo, id_conto_personale, id_conto_condiviso, id_categoria,
                        giorno_addebito, attiva):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO SpeseFisse (id_famiglia, nome, importo, id_conto_personale_addebito, id_conto_condiviso_addebito, id_categoria, giorno_addebito, attiva)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (id_famiglia, nome, importo, id_conto_personale, id_conto_condiviso, id_categoria, giorno_addebito,
                  1 if attiva else 0))
            return cur.lastrowid
    except Exception as e:
        print(f"❌ Errore durante l'aggiunta della spesa fissa: {e}")
        return None


def modifica_spesa_fissa(id_spesa_fissa, nome, importo, id_conto_personale, id_conto_condiviso, id_categoria,
                        giorno_addebito, attiva):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE SpeseFisse
                SET nome = ?, importo = ?, id_conto_personale_addebito = ?, id_conto_condiviso_addebito = ?, id_categoria = ?, giorno_addebito = ?, attiva = ?
                WHERE id_spesa_fissa = ?
            """, (nome, importo, id_conto_personale, id_conto_condiviso, id_categoria, giorno_addebito,
                  1 if attiva else 0, id_spesa_fissa))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore durante la modifica della spesa fissa: {e}")
        return False


def modifica_stato_spesa_fissa(id_spesa_fissa, nuovo_stato):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("UPDATE SpeseFisse SET attiva = ? WHERE id_spesa_fissa = ?",
                        (1 if nuovo_stato else 0, id_spesa_fissa))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore durante la modifica dello stato della spesa fissa: {e}")
        return False


def elimina_spesa_fissa(id_spesa_fissa):
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("DELETE FROM SpeseFisse WHERE id_spesa_fissa = ?", (id_spesa_fissa,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Errore durante l'eliminazione della spesa fissa: {e}")
        return False


def ottieni_spese_fisse_famiglia(id_famiglia):
    try:
        with sqlite3.connect(DB_FILE) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("""
                SELECT
                    SF.id_spesa_fissa,
                    SF.nome,
                    SF.importo,
                    SF.id_conto_personale_addebito,
                    SF.id_conto_condiviso_addebito,
                    SF.id_categoria,
                    SF.giorno_addebito,
                    SF.attiva,
                    COALESCE(CP.nome_conto, CC.nome_conto) as nome_conto
                FROM SpeseFisse SF
                LEFT JOIN Conti CP ON SF.id_conto_personale_addebito = CP.id_conto
                LEFT JOIN ContiCondivisi CC ON SF.id_conto_condiviso_addebito = CC.id_conto_condiviso
                WHERE SF.id_famiglia = ?
                ORDER BY SF.nome
            """, (id_famiglia,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Errore durante il recupero delle spese fisse: {e}")
        return []


def check_e_processa_spese_fisse(id_famiglia):
    oggi = datetime.date.today()
    spese_eseguite = 0
    try:
        spese_da_processare = ottieni_spese_fisse_famiglia(id_famiglia)
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            for spesa in spese_da_processare:
                if not spesa['attiva']:
                    continue

                # Controlla se la spesa è già stata eseguita questo mese
                cur.execute("""
                    SELECT 1 FROM Transazioni
                    WHERE (id_conto = ? AND descrizione = ?)
                      AND strftime('%Y-%m', data) = ?
                """, (spesa['id_conto_personale_addebito'], f"Spesa Fissa: {spesa['nome']}", oggi.strftime('%Y-%m')))
                if cur.fetchone(): continue

                cur.execute("""
                    SELECT 1 FROM TransazioniCondivise
                    WHERE (id_conto_condiviso = ? AND descrizione = ?)
                      AND strftime('%Y-%m', data) = ?
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
                        cur.execute("SELECT id_utente FROM Appartenenza_Famiglia WHERE id_famiglia = ? AND ruolo = 'admin' LIMIT 1", (id_famiglia,))
                        admin_id = cur.fetchone()[0]
                        aggiungi_transazione_condivisa(
                            admin_id, spesa['id_conto_condiviso_addebito'], data_esecuzione, descrizione, importo,
                            spesa['id_categoria'], cursor=cur
                        )
                    spese_eseguite += 1
            if spese_eseguite > 0:
                con.commit()
        return spese_eseguite
    except Exception as e:
        print(f"❌ Errore critico durante il processamento delle spese fisse: {e}")
        return 0


# --- MAIN ---
mimetypes.add_type("application/x-sqlite3", ".db")

if __name__ == "__main__":
    print("--- 0. PULIZIA DATABASE (CANCELLAZIONE .db) ---")
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"File '{DB_FILE}' rimosso per un test pulito.")
    setup_database()
    print("\n✅ Database vergine creato con successo.")