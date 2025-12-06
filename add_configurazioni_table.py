from db.supabase_manager import get_db_connection

def add_configurazioni_table():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Configurazioni (
                    id_configurazione SERIAL PRIMARY KEY,
                    id_famiglia INTEGER REFERENCES Famiglie(id_famiglia) ON DELETE CASCADE,
                    chiave TEXT NOT NULL,
                    valore TEXT,
                    UNIQUE(id_famiglia, chiave)
                );
            """)
            con.commit()
            print("Tabella Configurazioni creata con successo.")
    except Exception as e:
        print(f"Errore durante la creazione della tabella: {e}")

if __name__ == "__main__":
    add_configurazioni_table()
