import sqlite3
import os

# --- GESTIONE PERCORSI ---
if os.name == 'nt':
    base_dir = os.getenv('APPDATA')
else:
    # Linux/Mac fallback - standard XDG path or home
    base_dir = os.path.join(os.path.expanduser("~"), ".local", "share")

APP_DATA_DIR = os.path.join(base_dir, 'BudgetAmico')
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR)
DB_FILE = os.path.join(APP_DATA_DIR, 'budget_amico.db')

# --- SCHEMA DATABASE ---
# Versione 23: Aggiunta email_verificata a Utenti
SCHEMA_VERSION = 23

TABLES = {
    "Utenti": """
        CREATE TABLE Utenti (
            id_utente INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nome TEXT,
            cognome TEXT,
            data_nascita TEXT,
            codice_fiscale TEXT,
            indirizzo TEXT,
            id_conto_default INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
            id_conto_condiviso_default INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL,
            id_carta_default INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL,
            forza_cambio_password BOOLEAN DEFAULT FALSE,
            email_verificata BOOLEAN DEFAULT FALSE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_utenti_username_bindex ON Utenti(username_bindex);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_utenti_email_bindex ON Utenti(email_bindex);
    """,
    "Famiglie": """
        CREATE TABLE Famiglie (
            id_famiglia INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_famiglia TEXT UNIQUE NOT NULL,
            server_encrypted_key TEXT
        );
    """,
    "Appartenenza_Famiglia": """
        CREATE TABLE Appartenenza_Famiglia (
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            ruolo TEXT NOT NULL CHECK(ruolo IN ('admin', 'livello1', 'livello2', 'livello3')),
            PRIMARY KEY (id_utente, id_famiglia)
        );
    """,
    "Inviti": """
        CREATE TABLE Inviti (
            id_invito INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            email_invitato TEXT NOT NULL UNIQUE,
            ruolo_assegnato TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE,
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "Conti": """
        CREATE TABLE Conti (
            id_conto INTEGER PRIMARY KEY AUTOINCREMENT,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            nome_conto TEXT NOT NULL,
            tipo TEXT NOT NULL,
            iban TEXT,
            valore_manuale REAL DEFAULT 0.0,
            rettifica_saldo REAL DEFAULT 0.0,
            borsa_default TEXT,
            nascosto BOOLEAN DEFAULT FALSE
        );
    """,
    "ContiCondivisi": """
        CREATE TABLE ContiCondivisi (
            id_conto_condiviso INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome_conto TEXT NOT NULL,
            tipo TEXT NOT NULL,
            tipo_condivisione TEXT NOT NULL CHECK(tipo_condivisione IN ('famiglia', 'utenti')),
            rettifica_saldo REAL DEFAULT 0.0
        );
    """,
    "PartecipazioneContoCondiviso": """
        CREATE TABLE PartecipazioneContoCondiviso (
            id_conto_condiviso INTEGER NOT NULL REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE CASCADE,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            PRIMARY KEY (id_conto_condiviso, id_utente)
        );
    """,
    "Categorie": """
        CREATE TABLE Categorie (
            id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome_categoria TEXT NOT NULL,
            UNIQUE(id_famiglia, nome_categoria)
        );
    """,
    "Sottocategorie": """
        CREATE TABLE Sottocategorie (
            id_sottocategoria INTEGER PRIMARY KEY AUTOINCREMENT,
            id_categoria INTEGER NOT NULL REFERENCES Categorie(id_categoria) ON DELETE CASCADE,
            nome_sottocategoria TEXT NOT NULL,
            UNIQUE(id_categoria, nome_sottocategoria)
        );
    """,
    "Transazioni": """
        CREATE TABLE Transazioni (
            id_transazione INTEGER PRIMARY KEY AUTOINCREMENT,
            id_conto INTEGER NOT NULL REFERENCES Conti(id_conto) ON DELETE CASCADE,
            id_sottocategoria INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL,
            id_carta INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL,
            data TEXT NOT NULL,
            descrizione TEXT NOT NULL,
            importo REAL NOT NULL
        );
    """,
    "TransazioniCondivise": """
        CREATE TABLE TransazioniCondivise (
            id_transazione_condivisa INTEGER PRIMARY KEY AUTOINCREMENT,
            id_utente_autore INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            id_conto_condiviso INTEGER NOT NULL REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE CASCADE,
            id_sottocategoria INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL,
            data TEXT NOT NULL,
            descrizione TEXT NOT NULL,
            importo REAL NOT NULL,
            id_carta INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL,
            importo_nascosto BOOLEAN DEFAULT FALSE
        );
    """,
    "Budget": """
        CREATE TABLE Budget (
            id_budget INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            id_sottocategoria INTEGER NOT NULL REFERENCES Sottocategorie(id_sottocategoria) ON DELETE CASCADE,
            importo_limite TEXT NOT NULL,
            periodo TEXT NOT NULL DEFAULT 'Mensile',
            UNIQUE(id_famiglia, id_sottocategoria, periodo)
        );
    """,
    "Budget_Storico": """
        CREATE TABLE Budget_Storico (
            id_storico INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER NOT NULL,
            id_sottocategoria INTEGER NOT NULL,
            nome_sottocategoria TEXT NOT NULL,
            anno INTEGER NOT NULL,
            mese INTEGER NOT NULL,
            importo_limite TEXT NOT NULL,
            importo_speso TEXT NOT NULL,
            UNIQUE(id_famiglia, id_sottocategoria, anno, mese)
        );
    """,
    "Prestiti": """
        CREATE TABLE Prestiti (
            id_prestito INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            descrizione TEXT,
            data_inizio TEXT NOT NULL,
            numero_mesi_totali INTEGER NOT NULL,
            importo_finanziato REAL NOT NULL,
            importo_interessi REAL,
            importo_residuo REAL NOT NULL,
            importo_rata REAL NOT NULL,
            giorno_scadenza_rata INTEGER NOT NULL,
            id_conto_pagamento_default INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
            id_conto_condiviso_pagamento_default INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL,
            id_categoria_pagamento_default INTEGER REFERENCES Categorie(id_categoria) ON DELETE SET NULL,
            id_sottocategoria_pagamento_default INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL,
            addebito_automatico BOOLEAN DEFAULT FALSE
        );
    """,
    "StoricoPagamentiRate": """
        CREATE TABLE StoricoPagamentiRate (
            id_pagamento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_prestito INTEGER NOT NULL REFERENCES Prestiti(id_prestito) ON DELETE CASCADE,
            anno INTEGER NOT NULL,
            mese INTEGER NOT NULL,
            data_pagamento TEXT NOT NULL,
            importo_pagato REAL NOT NULL,
            UNIQUE(id_prestito, anno, mese)
        );
    """,
    "Immobili": """
        CREATE TABLE Immobili (
            id_immobile INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome TEXT NOT NULL,
            via TEXT,
            citta TEXT,
            valore_acquisto REAL,
            valore_attuale REAL NOT NULL,
            nuda_proprieta BOOLEAN DEFAULT FALSE,
            id_prestito_collegato INTEGER REFERENCES Prestiti(id_prestito) ON DELETE SET NULL
        );
    """,
    "Asset": """
        CREATE TABLE Asset (
            id_asset INTEGER PRIMARY KEY AUTOINCREMENT,
            id_conto INTEGER NOT NULL REFERENCES Conti(id_conto) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            nome_asset TEXT NOT NULL,
            quantita REAL NOT NULL,
            costo_iniziale_unitario REAL NOT NULL,
            prezzo_attuale_manuale REAL NOT NULL,
            data_aggiornamento TEXT,
            UNIQUE(id_conto, ticker)
        );
    """,
    "Storico_Asset": """
        CREATE TABLE Storico_Asset (
            id_storico_asset INTEGER PRIMARY KEY AUTOINCREMENT,
            id_conto INTEGER NOT NULL REFERENCES Conti(id_conto) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            data TEXT NOT NULL,
            tipo_movimento TEXT NOT NULL,
            quantita REAL NOT NULL,
            prezzo_unitario_movimento REAL NOT NULL
        );
    """,
    "SpeseFisse": """
        CREATE TABLE SpeseFisse (
            id_spesa_fissa INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome TEXT NOT NULL,
            importo REAL NOT NULL,
            id_conto_personale_addebito INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
            id_conto_condiviso_addebito INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL,
            id_categoria INTEGER NOT NULL REFERENCES Categorie(id_categoria) ON DELETE CASCADE,
            id_sottocategoria INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL,
            giorno_addebito INTEGER NOT NULL,
            attiva BOOLEAN DEFAULT TRUE,
            addebito_automatico BOOLEAN DEFAULT FALSE
        );
    """,
    "Configurazioni": """
        CREATE TABLE Configurazioni (
            id_configurazione SERIAL PRIMARY KEY,
            id_famiglia INTEGER REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            chiave TEXT NOT NULL,
            valore TEXT,
            UNIQUE(id_famiglia, chiave)
        );
    """,
    "QuoteImmobili": """
        CREATE TABLE QuoteImmobili (
            id_quota SERIAL PRIMARY KEY,
            id_immobile INTEGER NOT NULL REFERENCES Immobili(id_immobile) ON DELETE CASCADE,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            percentuale REAL NOT NULL CHECK(percentuale > 0 AND percentuale <= 100),
            UNIQUE(id_immobile, id_utente)
        );
    """,
    "QuotePrestiti": """
        CREATE TABLE QuotePrestiti (
            id_quota SERIAL PRIMARY KEY,
            id_prestito INTEGER NOT NULL REFERENCES Prestiti(id_prestito) ON DELETE CASCADE,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            percentuale REAL NOT NULL CHECK(percentuale > 0 AND percentuale <= 100),
            UNIQUE(id_prestito, id_utente)
        );
    """,
    "PianoAmmortamento": """
        CREATE TABLE PianoAmmortamento (
            id_rata INTEGER PRIMARY KEY AUTOINCREMENT,
            id_prestito INTEGER NOT NULL REFERENCES Prestiti(id_prestito) ON DELETE CASCADE,
            numero_rata INTEGER NOT NULL,
            data_scadenza TEXT NOT NULL,
            importo_rata REAL NOT NULL,
            quota_capitale REAL NOT NULL,
            quota_interessi REAL NOT NULL,
            spese_fisse REAL DEFAULT 0,
            stato TEXT DEFAULT 'da_pagare',
            UNIQUE(id_prestito, numero_rata)
        );
    """,
    "Carte": """
        CREATE TABLE Carte (
            id_carta INTEGER PRIMARY KEY AUTOINCREMENT,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            nome_carta TEXT NOT NULL,
            tipo_carta TEXT NOT NULL CHECK(tipo_carta IN ('credito', 'debito')),
            circuito TEXT NOT NULL,
            id_conto_riferimento INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
            id_conto_contabile INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
            id_conto_riferimento_condiviso INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL,
            id_conto_contabile_condiviso INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL,
            massimale_encrypted TEXT,
            giorno_addebito_encrypted TEXT,
            spesa_tenuta_encrypted TEXT,
            soglia_azzeramento_encrypted TEXT,
            giorno_addebito_tenuta_encrypted TEXT,
            addebito_automatico BOOLEAN DEFAULT FALSE,
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            attiva BOOLEAN DEFAULT TRUE
        );
    """,
    "StoricoMassimaliCarte": """
        CREATE TABLE StoricoMassimaliCarte (
            id_storico INTEGER PRIMARY KEY AUTOINCREMENT,
            id_carta INTEGER NOT NULL REFERENCES Carte(id_carta) ON DELETE CASCADE,
            data_inizio_validita TEXT NOT NULL,
            massimale_encrypted TEXT NOT NULL,
            UNIQUE(id_carta, data_inizio_validita)
        );
    """,
    "Contatti": """
        CREATE TABLE Contatti (
            id_contatto SERIAL PRIMARY KEY,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            nome_encrypted TEXT NOT NULL,
            cognome_encrypted TEXT,
            societa_encrypted TEXT,
            iban_encrypted TEXT,
            email_encrypted TEXT,
            telefono_encrypted TEXT,
            tipo_condivisione TEXT NOT NULL DEFAULT 'privato' CHECK(tipo_condivisione IN ('privato', 'famiglia', 'selezione')),
            id_famiglia INTEGER REFERENCES Famiglie(id_famiglia) ON DELETE SET NULL,
            colore TEXT DEFAULT '#424242',
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "CondivisioneContatto": """
        CREATE TABLE CondivisioneContatto (
            id_contatto INTEGER NOT NULL REFERENCES Contatti(id_contatto) ON DELETE CASCADE,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            PRIMARY KEY (id_contatto, id_utente)
        );
    """,
    "Log_Sistema": """
        CREATE TABLE Log_Sistema (
            id_log SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            livello TEXT NOT NULL CHECK(livello IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL')),
            componente TEXT NOT NULL,
            messaggio TEXT NOT NULL,
            dettagli TEXT,
            id_utente INTEGER REFERENCES Utenti(id_utente) ON DELETE SET NULL,
            id_famiglia INTEGER REFERENCES Famiglie(id_famiglia) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_log_timestamp ON Log_Sistema(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_log_livello ON Log_Sistema(livello);
        CREATE INDEX IF NOT EXISTS idx_log_componente ON Log_Sistema(componente);
    """,
    "Config_Logger": """
        CREATE TABLE Config_Logger (
            componente TEXT PRIMARY KEY,
            abilitato BOOLEAN DEFAULT FALSE,
            livello_minimo TEXT DEFAULT 'INFO' CHECK(livello_minimo IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL'))
        );
    """,
    "Salvadanai": """
        CREATE TABLE Salvadanai (
            id_salvadanaio INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            id_conto INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
            id_conto_condiviso INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL,
            id_asset INTEGER REFERENCES Asset(id_asset) ON DELETE SET NULL,
            id_obiettivo INTEGER REFERENCES Obiettivi_Risparmio(id) ON DELETE SET NULL,
            nome TEXT NOT NULL,
            importo_assegnato TEXT NOT NULL,
            incide_su_liquidita BOOLEAN DEFAULT FALSE,
            note TEXT,
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usa_saldo_totale BOOLEAN DEFAULT FALSE
        );
    """,
    "Obiettivi_Risparmio": """
        CREATE TABLE Obiettivi_Risparmio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_famiglia INTEGER REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome TEXT NOT NULL,
            importo_obiettivo TEXT NOT NULL,
            data_obiettivo DATE NOT NULL,
            note TEXT,
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mostra_suggerimento_mensile BOOLEAN DEFAULT TRUE
        );
    """,
    "StoricoAssetGlobale": """
        CREATE TABLE StoricoAssetGlobale (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            data DATE NOT NULL,
            prezzo_chiusura REAL NOT NULL,
            data_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
}


def setup_database(db_path=DB_FILE):
    """Crea e imposta il database se non esiste."""
    if os.path.exists(db_path):
        print(f"Database '{db_path}' già esistente.")
        return

    try:
        with sqlite3.connect(db_path) as con:
            cur = con.cursor()
            print(f"Creazione tabelle nel database '{db_path}'...")
            for table_name, schema in TABLES.items():
                cur.execute(schema)
            # Imposta la versione dello schema
            cur.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            con.commit()
        print(f"Database '{db_path}' creato e tabelle impostate con successo.")
    except Exception as e:
        print(f"❌ Errore durante la creazione del database: {e}")
        # In caso di errore, rimuovi il file parzialmente creato
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == '__main__':
    # Per testare la creazione del database da riga di comando
    print("--- ESECUZIONE SCRIPT CREAZIONE DATABASE ---")
    setup_database()
    print("\n--- VERIFICA TABELLE CREATE ---")
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = cur.fetchall()
            for table in tables:
                print(f"- {table[0]}")
    except Exception as e:
        print(f"❌ Impossibile verificare le tabelle: {e}")