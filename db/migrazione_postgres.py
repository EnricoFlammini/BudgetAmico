import sqlite3
import psycopg2
import os
import sys
from dotenv import load_dotenv

# Aggiungi la cartella padre al path per importare i moduli se necessario
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carica .env dalla directory padre (Sviluppo)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
print(f"Caricamento .env da: {env_path}")
print(f"File .env esiste: {os.path.exists(env_path)}")
load_dotenv(dotenv_path=env_path)

DB_FILE = os.path.join(os.getenv('APPDATA'), 'BudgetAmico', 'budget_amico.db')
SUPABASE_DB_URL = os.getenv('SUPABASE_DB_URL')

print(f"SUPABASE_DB_URL caricato: {SUPABASE_DB_URL}")

if not SUPABASE_DB_URL:
    print("ERRORE: SUPABASE_DB_URL non trovato nel file .env!")
    sys.exit(1)

def get_sqlite_conn():
    return sqlite3.connect(DB_FILE)

def get_postgres_conn():
    return psycopg2.connect(SUPABASE_DB_URL)

def create_tables(cur):
    print("Creazione tabelle su Postgres...")
    
    # Ordine di creazione per minimizzare errori di dipendenza, 
    # ma useremo ALTER TABLE per le dipendenze circolari.
    
    # 1. Famiglie
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Famiglie (
            id_famiglia SERIAL PRIMARY KEY,
            nome_famiglia TEXT UNIQUE NOT NULL
        );
    """)

    # 2. Utenti (Senza FK verso Conti per ora)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Utenti (
            id_utente SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nome TEXT,
            cognome TEXT,
            data_nascita TEXT,
            codice_fiscale TEXT,
            indirizzo TEXT,
            id_conto_default INTEGER, -- FK aggiunta dopo
            id_conto_condiviso_default INTEGER, -- FK aggiunta dopo
            forza_cambio_password BOOLEAN DEFAULT FALSE
        );
    """)

    # 3. Appartenenza_Famiglia
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Appartenenza_Famiglia (
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            ruolo TEXT NOT NULL CHECK(ruolo IN ('admin', 'livello1', 'livello2', 'livello3')),
            PRIMARY KEY (id_utente, id_famiglia)
        );
    """)

    # 4. Inviti
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Inviti (
            id_invito SERIAL PRIMARY KEY,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            email_invitato TEXT NOT NULL UNIQUE,
            ruolo_assegnato TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE,
            data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 5. Conti
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Conti (
            id_conto SERIAL PRIMARY KEY,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            nome_conto TEXT NOT NULL,
            tipo TEXT NOT NULL,
            iban TEXT,
            valore_manuale DOUBLE PRECISION DEFAULT 0.0,
            rettifica_saldo DOUBLE PRECISION DEFAULT 0.0,
            borsa_default TEXT
        );
    """)

    # 6. ContiCondivisi
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ContiCondivisi (
            id_conto_condiviso SERIAL PRIMARY KEY,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome_conto TEXT NOT NULL,
            tipo TEXT NOT NULL,
            tipo_condivisione TEXT NOT NULL CHECK(tipo_condivisione IN ('famiglia', 'utenti')),
            rettifica_saldo DOUBLE PRECISION DEFAULT 0.0
        );
    """)

    # 7. PartecipazioneContoCondiviso
    cur.execute("""
        CREATE TABLE IF NOT EXISTS PartecipazioneContoCondiviso (
            id_conto_condiviso INTEGER NOT NULL REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE CASCADE,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            PRIMARY KEY (id_conto_condiviso, id_utente)
        );
    """)

    # 8. Categorie
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Categorie (
            id_categoria SERIAL PRIMARY KEY,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome_categoria TEXT NOT NULL,
            UNIQUE(id_famiglia, nome_categoria)
        );
    """)

    # 9. Sottocategorie
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Sottocategorie (
            id_sottocategoria SERIAL PRIMARY KEY,
            id_categoria INTEGER NOT NULL REFERENCES Categorie(id_categoria) ON DELETE CASCADE,
            nome_sottocategoria TEXT NOT NULL,
            UNIQUE(id_categoria, nome_sottocategoria)
        );
    """)

    # 10. Transazioni
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Transazioni (
            id_transazione SERIAL PRIMARY KEY,
            id_conto INTEGER NOT NULL REFERENCES Conti(id_conto) ON DELETE CASCADE,
            id_sottocategoria INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL,
            data TEXT NOT NULL,
            descrizione TEXT NOT NULL,
            importo DOUBLE PRECISION NOT NULL
        );
    """)

    # 11. TransazioniCondivise
    cur.execute("""
        CREATE TABLE IF NOT EXISTS TransazioniCondivise (
            id_transazione_condivisa SERIAL PRIMARY KEY,
            id_utente_autore INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            id_conto_condiviso INTEGER NOT NULL REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE CASCADE,
            id_sottocategoria INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL,
            data TEXT NOT NULL,
            descrizione TEXT NOT NULL,
            importo DOUBLE PRECISION NOT NULL
        );
    """)

    # 12. Budget
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Budget (
            id_budget SERIAL PRIMARY KEY,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            id_sottocategoria INTEGER NOT NULL REFERENCES Sottocategorie(id_sottocategoria) ON DELETE CASCADE,
            importo_limite DOUBLE PRECISION NOT NULL,
            periodo TEXT NOT NULL DEFAULT 'Mensile',
            UNIQUE(id_famiglia, id_sottocategoria, periodo)
        );
    """)

    # 13. Budget_Storico
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Budget_Storico (
            id_storico SERIAL PRIMARY KEY,
            id_famiglia INTEGER NOT NULL,
            id_sottocategoria INTEGER NOT NULL,
            nome_sottocategoria TEXT NOT NULL,
            anno INTEGER NOT NULL,
            mese INTEGER NOT NULL,
            importo_limite DOUBLE PRECISION NOT NULL,
            importo_speso DOUBLE PRECISION NOT NULL,
            UNIQUE(id_famiglia, id_sottocategoria, anno, mese)
        );
    """)

    # 14. Prestiti
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Prestiti (
            id_prestito SERIAL PRIMARY KEY,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            descrizione TEXT,
            data_inizio TEXT NOT NULL,
            numero_mesi_totali INTEGER NOT NULL,
            importo_finanziato DOUBLE PRECISION NOT NULL,
            importo_interessi DOUBLE PRECISION,
            importo_residuo DOUBLE PRECISION NOT NULL,
            importo_rata DOUBLE PRECISION NOT NULL,
            giorno_scadenza_rata INTEGER NOT NULL,
            id_conto_pagamento_default INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
            id_conto_condiviso_pagamento_default INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL,
            id_categoria_pagamento_default INTEGER REFERENCES Categorie(id_categoria) ON DELETE SET NULL,
            id_sottocategoria_pagamento_default INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL,
            addebito_automatico BOOLEAN DEFAULT FALSE
        );
    """)

    # 15. StoricoPagamentiRate
    cur.execute("""
        CREATE TABLE IF NOT EXISTS StoricoPagamentiRate (
            id_pagamento SERIAL PRIMARY KEY,
            id_prestito INTEGER NOT NULL REFERENCES Prestiti(id_prestito) ON DELETE CASCADE,
            anno INTEGER NOT NULL,
            mese INTEGER NOT NULL,
            data_pagamento TEXT NOT NULL,
            importo_pagato DOUBLE PRECISION NOT NULL,
            UNIQUE(id_prestito, anno, mese)
        );
    """)

    # 16. Immobili
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Immobili (
            id_immobile SERIAL PRIMARY KEY,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome TEXT NOT NULL,
            via TEXT,
            citta TEXT,
            valore_acquisto DOUBLE PRECISION,
            valore_attuale DOUBLE PRECISION NOT NULL,
            nuda_proprieta BOOLEAN DEFAULT FALSE,
            id_prestito_collegato INTEGER REFERENCES Prestiti(id_prestito) ON DELETE SET NULL
        );
    """)

    # 17. Asset
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Asset (
            id_asset SERIAL PRIMARY KEY,
            id_conto INTEGER NOT NULL REFERENCES Conti(id_conto) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            nome_asset TEXT NOT NULL,
            quantita DOUBLE PRECISION NOT NULL,
            costo_iniziale_unitario DOUBLE PRECISION NOT NULL,
            prezzo_attuale_manuale DOUBLE PRECISION NOT NULL,
            data_aggiornamento TEXT,
            UNIQUE(id_conto, ticker)
        );
    """)

    # 18. Storico_Asset
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Storico_Asset (
            id_storico_asset SERIAL PRIMARY KEY,
            id_conto INTEGER NOT NULL REFERENCES Conti(id_conto) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            data TEXT NOT NULL,
            tipo_movimento TEXT NOT NULL,
            quantita DOUBLE PRECISION NOT NULL,
            prezzo_unitario_movimento DOUBLE PRECISION NOT NULL
        );
    """)

    # 19. SpeseFisse
    cur.execute("""
        CREATE TABLE IF NOT EXISTS SpeseFisse (
            id_spesa_fissa SERIAL PRIMARY KEY,
            id_famiglia INTEGER NOT NULL REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
            nome TEXT NOT NULL,
            importo DOUBLE PRECISION NOT NULL,
            id_conto_personale_addebito INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
            id_conto_condiviso_addebito INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL,
            id_categoria INTEGER NOT NULL REFERENCES Categorie(id_categoria) ON DELETE CASCADE,
            id_sottocategoria INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL,
            giorno_addebito INTEGER NOT NULL,
            attiva BOOLEAN DEFAULT TRUE,
            addebito_automatico BOOLEAN DEFAULT FALSE
        );
    """)

    # 20. InfoDB
    cur.execute("""
        CREATE TABLE IF NOT EXISTS InfoDB (
            chiave TEXT PRIMARY KEY,
            valore TEXT NOT NULL
        );
    """)
    
    # Inserisci versione se non esiste
    cur.execute("INSERT INTO InfoDB (chiave, valore) VALUES ('versione', '9') ON CONFLICT (chiave) DO NOTHING;")

    # Aggiunta FK circolari per Utenti
    print("Aggiunta vincoli FK circolari...")
    cur.execute("""
        ALTER TABLE Utenti 
        ADD CONSTRAINT fk_conto_default 
        FOREIGN KEY (id_conto_default) REFERENCES Conti(id_conto) ON DELETE SET NULL;
    """)
    cur.execute("""
        ALTER TABLE Utenti 
        ADD CONSTRAINT fk_conto_condiviso_default 
        FOREIGN KEY (id_conto_condiviso_default) REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL;
    """)


def copy_data(sqlite_cur, pg_cur):
    print("Copia dei dati...")
    
    # Disabilita temporaneamente i vincoli FK per gestire dipendenze circolari
    print("Disabilitazione vincoli foreign key...")
    pg_cur.execute("SET session_replication_role = 'replica';")
    
    tables = [
        "Famiglie", "Utenti", "Conti", "ContiCondivisi", "Appartenenza_Famiglia", "Inviti", 
        "PartecipazioneContoCondiviso",
        "Categorie", "Sottocategorie", "Transazioni", "TransazioniCondivise",
        "Budget", "Budget_Storico", "Prestiti", "StoricoPagamentiRate",
        "Immobili", "Asset", "Storico_Asset", "SpeseFisse"
    ]

    for table in tables:
        print(f"Copia tabella {table}...")
        try:
            sqlite_cur.execute(f"SELECT * FROM {table}")
            rows = sqlite_cur.fetchall()
            
            if not rows:
                continue

            # Ottieni i nomi delle colonne
            col_names = [description[0] for description in sqlite_cur.description]
            cols_str = ", ".join(col_names)
            placeholders = ", ".join(["%s"] * len(col_names))
            
            # Converti i valori booleani da SQLite (0/1) a PostgreSQL (True/False)
            # Colonne booleane note nel database
            boolean_columns = {
                'Utenti': ['forza_cambio_password'],
                'Conti': [],
                'ContiCondivisi': [],
                'Transazioni': [],
                'TransazioniCondivise': [],
                'Prestiti': ['completato', 'addebito_automatico'],
                'Immobili': ['nuda_proprieta'],
                'Asset': [],
                'SpeseFisse': ['attiva', 'addebito_automatico']
            }
            
            # Converti i dati
            converted_rows = []
            bool_cols_for_table = boolean_columns.get(table, [])
            bool_col_indices = [i for i, col in enumerate(col_names) if col in bool_cols_for_table]
            
            for row in rows:
                row_list = list(row)
                for idx in bool_col_indices:
                    if row_list[idx] is not None:
                        row_list[idx] = bool(row_list[idx])
                converted_rows.append(tuple(row_list))
            
            query = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})"
            
            pg_cur.executemany(query, converted_rows)
            print(f"Copiati {len(rows)} record in {table}.")
            
            # Aggiorna la sequenza per l'ID (se esiste una colonna id_...)
            pk_col = None
            for col in col_names:
                if col.startswith("id_") and col != "id_utente_autore" and col != "id_conto_default": # Euristiche semplici
                     # Assumiamo che la prima colonna id_ sia la PK se segue il pattern id_NomeTabellaSingolare o simile
                     # Ma per sicurezza usiamo il nome della tabella
                     expected_pk = f"id_{table.lower().rstrip('s')}" # es. Conti -> id_conti (no), id_conto (si)
                     if col == expected_pk or (table == "Conti" and col == "id_conto") or (table == "Famiglie" and col == "id_famiglia"):
                         pk_col = col
                         break
            
            # Fix manuale per nomi PK non standard o plurali
            if table == "Conti": pk_col = "id_conto"
            if table == "ContiCondivisi": pk_col = "id_conto_condiviso"
            if table == "Inviti": pk_col = "id_invito"
            if table == "Budget_Storico": pk_col = "id_storico"
            if table == "StoricoPagamentiRate": pk_col = "id_pagamento"
            if table == "Storico_Asset": pk_col = "id_storico_asset"
            if table == "SpeseFisse": pk_col = "id_spesa_fissa"
            if table == "Appartenenza_Famiglia": pk_col = None # PK composta
            if table == "PartecipazioneContoCondiviso": pk_col = None # PK composta
            
            if pk_col:
                print(f"Aggiornamento sequenza per {table} su colonna {pk_col}...")
                pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', '{pk_col}'), COALESCE(MAX({pk_col}), 1)) FROM {table};")

        except Exception as e:
            print(f"Errore durante la copia di {table}: {e}")
            raise e
    
    # Riabilita i vincoli FK
    print("Riabilitazione vincoli foreign key...")
    pg_cur.execute("SET session_replication_role = 'origin';")

def main():
    if not os.path.exists(DB_FILE):
        print(f"Database SQLite non trovato in {DB_FILE}")
        return

    print(f"Connessione a SQLite: {DB_FILE}")
    sqlite_conn = get_sqlite_conn()
    sqlite_cur = sqlite_conn.cursor()

    print(f"Connessione a Postgres...")
    try:
        pg_conn = get_postgres_conn()
        pg_cur = pg_conn.cursor()
        
        # Pulisci tutto prima (opzionale, ma utile per test)
        # pg_cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        # No, troppo aggressivo. Droppiamo le tabelle in ordine inverso.
        print("Pulizia tabelle esistenti...")
        tables_rev = [
            "SpeseFisse", "Storico_Asset", "Asset", "Immobili", "StoricoPagamentiRate", "Prestiti",
            "Budget_Storico", "Budget", "TransazioniCondivise", "Transazioni", 
            "Sottocategorie", "Categorie", "PartecipazioneContoCondiviso", "ContiCondivisi", 
            "Conti", "Inviti", "Appartenenza_Famiglia", "Utenti", "Famiglie"
        ]
        for t in tables_rev:
            pg_cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")

        create_tables(pg_cur)
        copy_data(sqlite_cur, pg_cur)
        
        pg_conn.commit()
        print("Migrazione completata con successo!")
        
    except Exception as e:
        print(f"Errore critico: {e}")
        if 'pg_conn' in locals():
            pg_conn.rollback()
    finally:
        sqlite_conn.close()
        if 'pg_conn' in locals():
            pg_conn.close()

if __name__ == "__main__":
    main()
