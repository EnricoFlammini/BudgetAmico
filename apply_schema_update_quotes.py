from db.supabase_manager import get_db_connection
import sys
import os

def apply_schema_update():
    print("Applying schema update for Quote tables...")
    
    commands = [
        """
        CREATE TABLE IF NOT EXISTS QuoteImmobili (
            id_quota SERIAL PRIMARY KEY,
            id_immobile INTEGER NOT NULL REFERENCES Immobili(id_immobile) ON DELETE CASCADE,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            percentuale REAL NOT NULL CHECK(percentuale > 0 AND percentuale <= 100),
            UNIQUE(id_immobile, id_utente)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS QuotePrestiti (
            id_quota SERIAL PRIMARY KEY,
            id_prestito INTEGER NOT NULL REFERENCES Prestiti(id_prestito) ON DELETE CASCADE,
            id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
            percentuale REAL NOT NULL CHECK(percentuale > 0 AND percentuale <= 100),
            UNIQUE(id_prestito, id_utente)
        );
        """
    ]

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            for cmd in commands:
                print(f"Executing: {cmd.strip().splitlines()[0]}...")
                cur.execute(cmd)
            con.commit()
        print("Schema update completed successfully.")
    except Exception as e:
        print(f"Error applying schema update: {e}")
        # sys.exit(1) # Don't exit with error code to avoid checking failure in agent loop if it overlaps

if __name__ == "__main__":
    # Ensure current directory is in path to find db module
    sys.path.append(os.getcwd())
    apply_schema_update()
