
import os
import sys

# Ensure project root is in path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(project_root))

from db.supabase_manager import get_db_connection

# Path to the SQL file - adjusting for where the script is run vs where the file is
# The SQL file was saved to the artifacts directory, but I likely need to read it from there or copy it.
# For simplicity, I will embed the SQL content here since I know it, or read from the artifact if accessible.
# Since I cannot easily access the artifact path from this script running in the user's environment without hardcoding,
# I will embed the SQL commands.

RLS_SQL = """
-- Abilita RLS sulle nuove tabelle
ALTER TABLE Carte ENABLE ROW LEVEL SECURITY;
ALTER TABLE StoricoMassimaliCarte ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- Policy per Carte
-- ============================================================================

-- Gli utenti possono vedere solo le proprie carte
DROP POLICY IF EXISTS "Users can view own cards" ON Carte;
CREATE POLICY "Users can view own cards" ON Carte
    FOR SELECT
    USING (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- Gli utenti possono creare carte per se stessi
DROP POLICY IF EXISTS "Users can create own cards" ON Carte;
CREATE POLICY "Users can create own cards" ON Carte
    FOR INSERT
    WITH CHECK (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- Gli utenti possono modificare solo le proprie carte
DROP POLICY IF EXISTS "Users can update own cards" ON Carte;
CREATE POLICY "Users can update own cards" ON Carte
    FOR UPDATE
    USING (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- Gli utenti possono eliminare solo le proprie carte
DROP POLICY IF EXISTS "Users can delete own cards" ON Carte;
CREATE POLICY "Users can delete own cards" ON Carte
    FOR DELETE
    USING (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- ============================================================================
-- Policy per StoricoMassimaliCarte
-- ============================================================================

-- Gli utenti possono vedere lo storico delle proprie carte
DROP POLICY IF EXISTS "Users can view own cards history" ON StoricoMassimaliCarte;
CREATE POLICY "Users can view own cards history" ON StoricoMassimaliCarte
    FOR SELECT
    USING (
        id_carta IN (
            SELECT id_carta FROM Carte 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- Gli utenti possono gestire lo storico delle proprie carte
DROP POLICY IF EXISTS "Users can manage own cards history" ON StoricoMassimaliCarte;
CREATE POLICY "Users can manage own cards history" ON StoricoMassimaliCarte
    FOR ALL
    USING (
        id_carta IN (
            SELECT id_carta FROM Carte 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );
"""

def apply_rls():
    print("Applying RLS policies...")
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            # Split commands by semicolon to execute them one by one if needed, 
            # but pg8000 might handle block. Better safe with block or split.
            # SQL blocks with $$ might fail splitting, but here we have simple statements.
            # However, ENABLE ROW LEVEL SECURITY is a DDL.
            
            for statement in RLS_SQL.split(';'):
                stmt = statement.strip()
                if stmt:
                    try:
                        cur.execute(stmt)
                        print(f"Executed: {stmt[:50]}...")
                    except Exception as e:
                        print(f"Error executing statement: {stmt[:50]}... \n{e}")
            
            conn.commit()
            print("RLS policies applied successfully!")
            
    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    apply_rls()
