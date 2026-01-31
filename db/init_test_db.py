import os
import sys
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

# Aggiungi la cartella root al path per importare i moduli backend
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.crea_database import TABLES, SCHEMA_VERSION

def get_connection_params(db_url):
    result = urlparse(db_url)
    return {
        'user': result.username,
        'password': result.password,
        'host': result.hostname,
        'port': result.port or 5432,
        'database': result.path[1:] if result.path else 'postgres'
    }

def adapt_sql_for_postgres(sql):
    """
    Adatta lo schema SQLite per PostgreSQL.
    Principale differenza: INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY
    """
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    # Fix Boolean Defaults (SQLite uses 0/1, Postgres prefers FALSE/TRUE)
    sql = sql.replace("BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE")
    sql = sql.replace("BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT TRUE")
    
    # Fix missing columns in Utenti (schema bug where indexes exist but columns don't)
    if "CREATE TABLE Utenti" in sql and "username_bindex" not in sql.split("CREATE UNIQUE INDEX")[0]:
        # Inject columns before the closing parenthesis of CREATE TABLE
        # We look for the last field definition or the closing parenthesis
        sql = sql.replace("forza_cambio_password BOOLEAN DEFAULT FALSE", "forza_cambio_password BOOLEAN DEFAULT FALSE,\n            username_bindex TEXT,\n            email_bindex TEXT")
    
    # Altri adattamenti se necessari (es. DATETIME vs TIMESTAMP)
    # Postgres accetta TEXT per date ISO8601, quindi compatibile con SQLite TEXT dates
    return sql

def init_test_db():
    load_dotenv()
    db_url = os.getenv("SUPABASE_DB_URL")
    
    if not db_url:
        print("Errore: SUPABASE_DB_URL non trovata nel file .env")
        return

    print(f"Connessione al database: {db_url.split('@')[1] if '@' in db_url else '...'}")
    
    # Check for --yes or -y flag
    auto_confirm = len(sys.argv) > 1 and (sys.argv[1] == '--yes' or sys.argv[1] == '-y')
    
    if not auto_confirm:
        confirm = input("ATTENZIONE: Questo script creerà le tabelle nel database configurato. \nSei sicuro di voler procedere? (s/N): ")
        if confirm.lower() != 's':
            print("Operazione annullata.")
            return
    else:
        print("Moadlità non interattiva: Procedo automaticamente.")

    try:
        params = get_connection_params(db_url)
        conn = psycopg2.connect(**params)
        cur = conn.cursor()
        
        print("Creazione tabelle...")
        
        # Ordine di creazione importante per le Foreign Keys?
        # Le definizioni hanno REFERENCES, quindi l'ordine conta se non si creano tutte insieme.
        # Postgres verifica le FK alla creazione.
        # TABLES è un dizionario (non ordinato pre-3.7, ma qui ok).
        # Meglio definire un ordine esplicito per sicurezza, o provare e riprovare (brutto).
        # Ordine logico basato sulle dipendenze:
        ordered_tables = [
            "Famiglie",         # No dep
            "Utenti",           # References Famiglie (via Appartenenza ma anche id_conto, circolare.. wait)
                                # Utenti references Conti... ma Conti references Utenti. 
                                # Circular dependency! SQLite è permissivo, Postgres no.
            "Appartenenza_Famiglia", 
            "Inviti",
            "Conti",            # Ref Utenti
            "ContiCondivisi",   # Ref Famiglie
            "PartecipazioneContoCondiviso",
            "Categorie",        # Ref Famiglie
            "Sottocategorie",   # Ref Categorie
            "Carte",            # Ref Utenti, Conti
            "StoricoMassimaliCarte",
            "Contatti",         # Ref Utenti, Famiglie
            "CondivisioneContatto",
            "Transazioni",      # Ref Conti, Sottocategorie, Carte
            "TransazioniCondivise",
            "Budget",           # Ref Famiglie, Sottocategorie
            "Budget_Storico",
            "Prestiti",         # Ref Famiglie, Conti
            "StoricoPagamentiRate",
            "QuotePrestiti",
            "PianoAmmortamento",
            "Immobili",         # Ref Famiglie, Prestiti
            "QuoteImmobili",
            "Asset",            # Ref Conti
            "Storico_Asset",
            "SpeseFisse",       # Ref Famiglie, Conti, Categorie
            "Configurazioni",   # Ref Famiglie
            "Log_Sistema",      # Ref Utenti
            "Config_Logger"
        ]

        # Strategia per dipendenze circolari (Utenti <-> Conti):
        # 1. Creare tabelle senza FK o ALTER TABLE dopo.
        # 2. Oppure creare tabelle e poi aggiungere constraint.
        # Dato che lo schema è stringa fissa, è difficile splittare.
        # Tentativo: Creare tutto, se fallisce per FK, ritardare constraint? No.
        # Postgres permette REFERENCES a tabelle non ancora create? No.
        
        # Facciamo un approccio "Create Tables Basic" poi "Add Constraints"?
        # Troppo complesso per modificare i testi SQL al volo.
        
        # Soluzione semplice: Creare 'Utenti' SENZA le FK verso 'Conti'/'Carte' inizialmente.
        # Poi ALTER TABLE.
        
        # Modifica dinamica per Utenti
        schema_utenti = TABLES["Utenti"]
        # Rimuovi REFERENCES temporaneamente o rendili grezzi integer e aggiungi FK dopo
        # Regex replacement per rimuovere le FK inline pericolose in Utenti
        import re
        schema_utenti_clean = re.sub(r'REFERENCES Conti\(\w+\) ON DELETE SET NULL', '', schema_utenti)
        schema_utenti_clean = re.sub(r'REFERENCES ContiCondivisi\(\w+\) ON DELETE SET NULL', '', schema_utenti_clean)
        schema_utenti_clean = re.sub(r'REFERENCES Carte\(\w+\) ON DELETE SET NULL', '', schema_utenti_clean)
        
        # Esegui creazione tabelle in ordine
        processed_tables = set()
        
        # 1. Utenti (Clean)
        print("  - Utenti (Base)")
        cur.execute(adapt_sql_for_postgres(schema_utenti_clean))
        processed_tables.add("Utenti")
        
        # 2. Famiglie
        print("  - Famiglie")
        cur.execute(adapt_sql_for_postgres(TABLES["Famiglie"]))
        processed_tables.add("Famiglie")

        # 3. Resto in ordine
        for table_name in ordered_tables:
            if table_name in ["Utenti", "Famiglie"]: continue
            if table_name not in TABLES: continue
            
            print(f"  - {table_name}")
            sql = TABLES[table_name]
            cur.execute(adapt_sql_for_postgres(sql))
            processed_tables.add(table_name)
            
        # 4. Aggiungi FK mancanti a Utenti
        print("  - Ripristino FK circolari su Utenti...")
        cur.execute("ALTER TABLE Utenti ADD CONSTRAINT fk_utenti_conti FOREIGN KEY (id_conto_default) REFERENCES Conti(id_conto) ON DELETE SET NULL")
        cur.execute("ALTER TABLE Utenti ADD CONSTRAINT fk_utenti_conticondivisi FOREIGN KEY (id_conto_condiviso_default) REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL")
        cur.execute("ALTER TABLE Utenti ADD CONSTRAINT fk_utenti_carte FOREIGN KEY (id_carta_default) REFERENCES Carte(id_carta) ON DELETE SET NULL")

        # 5. InfoDB per versione
        print("  - InfoDB")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS InfoDB (
                chiave TEXT PRIMARY KEY,
                valore TEXT
            )
        """)
        cur.execute("INSERT INTO InfoDB (chiave, valore) VALUES ('versione', %s)", (str(SCHEMA_VERSION),))
        
        conn.commit()
        print("Database inizializzato con successo!")
        conn.close()
        
    except Exception as e:
        print(f"Errore durante l'inizializzazione: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    init_test_db()
