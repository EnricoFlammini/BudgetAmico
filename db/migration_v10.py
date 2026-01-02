
def _migra_da_v9_a_v10(con):
    """
    Logica specifica per migrare un DB dalla versione 9 alla 10.
    - Crea la tabella Carte.
    - Aggiunge id_carta alla tabella Transazioni.
    """
    print("Esecuzione migrazione da v9 a v10...")
    try:
        cur = con.cursor()

        # 1. Crea la tabella Carte
        print("  - Creazione tabella Carte...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Carte (
                id_carta INTEGER PRIMARY KEY AUTOINCREMENT,
                id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
                nome_carta TEXT NOT NULL,
                tipo_carta TEXT NOT NULL CHECK(tipo_carta IN ('credito', 'debito')),
                circuito TEXT NOT NULL,
                id_conto_riferimento INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
                id_conto_contabile INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
                massimale_encrypted TEXT,
                giorno_addebito_encrypted TEXT,
                spesa_tenuta_encrypted TEXT,
                soglia_azzeramento_encrypted TEXT,
                giorno_addebito_tenuta_encrypted TEXT,
                addebito_automatico BOOLEAN DEFAULT 0,
                data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                attiva BOOLEAN DEFAULT 1
            );
        """)

        # 2. Aggiungi colonna id_carta a Transazioni
        print("  - Aggiunta colonna id_carta a Transazioni...")
        try:
            cur.execute("ALTER TABLE Transazioni ADD COLUMN id_carta INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL")
        except Exception: # sqlite3.OperationalError se esiste già
             print("    Colonna id_carta già esistente (ignorato).")

        con.commit()
        print("Migrazione a v10 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v9 a v10: {e}")
        con.rollback()
        return False
