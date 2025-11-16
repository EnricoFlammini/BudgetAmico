import sqlite3
import os
import sys

# --- BLOCCO DI CODICE PER CORREGGERE IL PERCORSO ---
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
# --- FINE BLOCCO DI CODICE ---


def setup_database(db_path=None):
    """
    Crea il file del database e tutte le tabelle necessarie
    se non esistono già.
    """
    if db_path is None:
        # Usa il percorso centralizzato definito in gestione_db
        try:
            from db.gestione_db import DB_FILE
            db_path = DB_FILE
        except ImportError:
            # Fallback per l'esecuzione diretta dello script
            db_path = os.path.join(parent_dir, 'budget_familiare.db')

    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        cur.execute("PRAGMA foreign_keys = ON;")

        # Versione 6: Aggiunta campi profilo utente
        cur.execute("PRAGMA user_version = 6;")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Utenti
                    (
                        id_utente INTEGER PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        forza_cambio_password INTEGER NOT NULL DEFAULT 0,
                        password_hash TEXT NOT NULL,
                        nome TEXT,
                        cognome TEXT,
                        data_nascita TEXT,
                        codice_fiscale TEXT,
                        indirizzo TEXT,
                        id_conto_default INTEGER, -- Riferimento a Conti personali
                        id_conto_condiviso_default INTEGER, -- Riferimento a Conti condivisi
                        FOREIGN KEY (id_conto_default) REFERENCES Conti (id_conto) ON DELETE SET NULL,
                        FOREIGN KEY (id_conto_condiviso_default) REFERENCES ContiCondivisi (id_conto_condiviso) ON DELETE SET NULL
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Famiglie
                    (
                        id_famiglia INTEGER PRIMARY KEY,
                        nome_famiglia TEXT UNIQUE NOT NULL
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Appartenenza_Famiglia
                    (
                        id_utente INTEGER,
                        id_famiglia INTEGER,
                        ruolo TEXT NOT NULL CHECK (ruolo IN ('admin', 'livello1', 'livello2', 'livello3')),
                        FOREIGN KEY (id_utente) REFERENCES Utenti (id_utente) ON DELETE CASCADE,
                        FOREIGN KEY (id_famiglia) REFERENCES Famiglie (id_famiglia) ON DELETE CASCADE,
                        PRIMARY KEY (id_utente, id_famiglia)
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Conti
                    (
                        id_conto INTEGER PRIMARY KEY,
                        id_utente INTEGER NOT NULL,
                        nome_conto TEXT NOT NULL,
                        tipo TEXT CHECK (tipo IN ('Corrente', 'Investimento', 'Risparmio', 'Altro', 'Fondo Pensione', 'Contanti')),
                        iban TEXT UNIQUE,
                        valore_manuale REAL DEFAULT 0,
                        FOREIGN KEY (id_utente) REFERENCES Utenti (id_utente) ON DELETE CASCADE
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Categorie
                    (
                        id_categoria INTEGER PRIMARY KEY,
                        id_famiglia INTEGER NOT NULL,
                        nome_categoria TEXT NOT NULL,
                        FOREIGN KEY (id_famiglia) REFERENCES Famiglie (id_famiglia) ON DELETE CASCADE,
                        UNIQUE (id_famiglia, nome_categoria)
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Transazioni
                    (
                        id_transazione INTEGER PRIMARY KEY,
                        id_conto INTEGER NOT NULL,
                        id_categoria INTEGER,
                        data TEXT NOT NULL,
                        descrizione TEXT,
                        importo REAL NOT NULL,
                        FOREIGN KEY (id_conto) REFERENCES Conti (id_conto) ON DELETE CASCADE,
                        FOREIGN KEY (id_categoria) REFERENCES Categorie (id_categoria) ON DELETE SET NULL
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Asset
                    (
                        id_asset INTEGER PRIMARY KEY,
                        id_conto INTEGER NOT NULL,
                        ticker TEXT NOT NULL,
                        nome_asset TEXT,
                        quantita REAL NOT NULL DEFAULT 0,
                        prezzo_attuale_manuale REAL NOT NULL DEFAULT 0,
                        costo_iniziale_unitario REAL NOT NULL DEFAULT 0,
                        FOREIGN KEY (id_conto) REFERENCES Conti (id_conto) ON DELETE CASCADE,
                        UNIQUE (id_conto, ticker)
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Storico_Asset
                    (
                        id_movimento INTEGER PRIMARY KEY,
                        id_conto INTEGER NOT NULL,
                        ticker TEXT NOT NULL,
                        data TEXT NOT NULL,
                        tipo_movimento TEXT NOT NULL CHECK (tipo_movimento IN ('COMPRA', 'VENDI', 'INIZIALE')),
                        quantita REAL NOT NULL,
                        prezzo_unitario_movimento REAL NOT NULL,
                        FOREIGN KEY (id_conto) REFERENCES Conti (id_conto) ON DELETE CASCADE
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Budget
                    (
                        id_budget INTEGER PRIMARY KEY,
                        id_famiglia INTEGER NOT NULL,
                        id_categoria INTEGER NOT NULL,
                        importo_limite REAL NOT NULL,
                        periodo TEXT NOT NULL DEFAULT 'Mensile',
                        FOREIGN KEY (id_famiglia) REFERENCES Famiglie (id_famiglia) ON DELETE CASCADE,
                        FOREIGN KEY (id_categoria) REFERENCES Categorie (id_categoria) ON DELETE CASCADE,
                        UNIQUE (id_famiglia, id_categoria, periodo)
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Budget_Storico
                    (
                        id_storico INTEGER PRIMARY KEY,
                        id_famiglia INTEGER NOT NULL,
                        id_categoria INTEGER NOT NULL,
                        nome_categoria TEXT NOT NULL,
                        anno INTEGER NOT NULL,
                        mese INTEGER NOT NULL,
                        importo_limite REAL NOT NULL,
                        importo_speso REAL NOT NULL,
                        FOREIGN KEY (id_famiglia) REFERENCES Famiglie (id_famiglia) ON DELETE CASCADE,
                        FOREIGN KEY (id_categoria) REFERENCES Categorie (id_categoria) ON DELETE SET NULL,
                        UNIQUE (id_famiglia, id_categoria, anno, mese)
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Prestiti
                    (
                        id_prestito INTEGER PRIMARY KEY,
                        id_famiglia INTEGER NOT NULL,
                        nome TEXT NOT NULL,
                        descrizione TEXT,
                        tipo TEXT NOT NULL CHECK (tipo IN ('Prestito', 'Finanziamento', 'Mutuo')),
                        data_inizio TEXT NOT NULL,
                        numero_mesi_totali INTEGER NOT NULL,
                        importo_finanziato REAL NOT NULL,
                        importo_interessi REAL NOT NULL,
                        importo_residuo REAL NOT NULL,
                        importo_rata REAL NOT NULL,
                        giorno_scadenza_rata INTEGER NOT NULL,
                        id_conto_pagamento_default INTEGER,
                        id_categoria_pagamento_default INTEGER,
                        FOREIGN KEY (id_famiglia) REFERENCES Famiglie (id_famiglia) ON DELETE CASCADE,
                        FOREIGN KEY (id_conto_pagamento_default) REFERENCES Conti (id_conto) ON DELETE SET NULL,
                        FOREIGN KEY (id_categoria_pagamento_default) REFERENCES Categorie (id_categoria) ON DELETE SET NULL
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS StoricoPagamentiRate
                    (
                        id_pagamento INTEGER PRIMARY KEY,
                        id_prestito INTEGER NOT NULL,
                        anno INTEGER NOT NULL,
                        mese INTEGER NOT NULL,
                        data_pagamento TEXT NOT NULL,
                        importo_pagato REAL NOT NULL,
                        FOREIGN KEY (id_prestito) REFERENCES Prestiti (id_prestito) ON DELETE CASCADE,
                        UNIQUE (id_prestito, anno, mese)
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Immobili
                    (
                        id_immobile INTEGER PRIMARY KEY,
                        id_famiglia INTEGER NOT NULL,
                        nome TEXT NOT NULL,
                        via TEXT,
                        citta TEXT,
                        valore_acquisto REAL NOT NULL DEFAULT 0,
                        valore_attuale REAL NOT NULL DEFAULT 0,
                        nuda_proprieta INTEGER NOT NULL DEFAULT 0,
                        id_prestito_collegato INTEGER UNIQUE,
                        FOREIGN KEY (id_famiglia) REFERENCES Famiglie (id_famiglia) ON DELETE CASCADE,
                        FOREIGN KEY (id_prestito_collegato) REFERENCES Prestiti (id_prestito) ON DELETE SET NULL
                    )""")

        cur.execute("""
                    CREATE TABLE IF NOT EXISTS Inviti
                    (
                        id_invito INTEGER PRIMARY KEY AUTOINCREMENT,
                        id_famiglia INTEGER NOT NULL,
                        email_invitato TEXT NOT NULL,
                        ruolo_assegnato TEXT NOT NULL CHECK (ruolo_assegnato IN ('admin', 'livello1', 'livello2', 'livello3')),
                        token TEXT NOT NULL UNIQUE,
                        data_creazione DATE NOT NULL DEFAULT CURRENT_DATE,
                        FOREIGN KEY (id_famiglia) REFERENCES Famiglie (id_famiglia) ON DELETE CASCADE
                    );
                    """)

        # --- NUOVE TABELLE PER CONTI CONDIVISI ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ContiCondivisi
            (
                id_conto_condiviso INTEGER PRIMARY KEY,
                id_famiglia INTEGER, 
                nome_conto TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN ('Corrente', 'Risparmio', 'Altro', 'Contanti')),
                tipo_condivisione TEXT NOT NULL CHECK (tipo_condivisione IN ('famiglia', 'utenti')),
                FOREIGN KEY (id_famiglia) REFERENCES Famiglie (id_famiglia) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS PartecipazioneContoCondiviso
            (
                id_partecipazione INTEGER PRIMARY KEY,
                id_conto_condiviso INTEGER NOT NULL,
                id_utente INTEGER NOT NULL,
                FOREIGN KEY (id_conto_condiviso) REFERENCES ContiCondivisi (id_conto_condiviso) ON DELETE CASCADE,
                FOREIGN KEY (id_utente) REFERENCES Utenti (id_utente) ON DELETE CASCADE,
                UNIQUE (id_conto_condiviso, id_utente)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS TransazioniCondivise
            (
                id_transazione_condivisa INTEGER PRIMARY KEY,
                id_utente_autore INTEGER,
                id_conto_condiviso INTEGER NOT NULL,
                id_categoria INTEGER,
                data TEXT NOT NULL,
                descrizione TEXT,
                importo REAL NOT NULL,
                FOREIGN KEY (id_utente_autore) REFERENCES Utenti (id_utente) ON DELETE SET NULL,
                FOREIGN KEY (id_conto_condiviso) REFERENCES ContiCondivisi (id_conto_condiviso) ON DELETE CASCADE,
                FOREIGN KEY (id_categoria) REFERENCES Categorie (id_categoria) ON DELETE SET NULL
            )
        """)

        # --- NUOVA TABELLA PER SPESE FISSE ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS SpeseFisse
            (
                id_spesa_fissa INTEGER PRIMARY KEY,
                id_famiglia INTEGER NOT NULL,
                nome TEXT NOT NULL,
                importo REAL NOT NULL,
                note TEXT, -- Aggiunto in v2
                id_conto_personale_addebito INTEGER,
                id_conto_condiviso_addebito INTEGER,
                id_categoria INTEGER NOT NULL,
                giorno_addebito INTEGER NOT NULL,
                attiva INTEGER NOT NULL DEFAULT 1,
                data_prossima_esecuzione TEXT,
                FOREIGN KEY (id_famiglia) REFERENCES Famiglie (id_famiglia) ON DELETE CASCADE,
                FOREIGN KEY (id_conto_personale_addebito) REFERENCES Conti (id_conto) ON DELETE SET NULL,
                FOREIGN KEY (id_conto_condiviso_addebito) REFERENCES ContiCondivisi (id_conto_condiviso) ON DELETE SET NULL,
                FOREIGN KEY (id_categoria) REFERENCES Categorie (id_categoria) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS PasswordResets
            (
                id INTEGER PRIMARY KEY,
                id_utente INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expiry_date TEXT NOT NULL,
                FOREIGN KEY (id_utente) REFERENCES Utenti (id_utente) ON DELETE CASCADE
            )
        """)

        con.commit()

    print(f"Database '{db_path}' creato e tabelle impostate con successo.")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, '..', 'budget_familiare.db')

    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"File '{db_path}' rimosso per un test pulito.")
    setup_database()