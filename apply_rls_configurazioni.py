import psycopg2
from db.supabase_manager import get_db_connection

def apply_rls():
    print("Applicazione RLS su tabella Configurazioni...")
    
    sql_commands = [
        # 1. Abilita RLS
        "ALTER TABLE Configurazioni ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE Configurazioni FORCE ROW LEVEL SECURITY;",
        
        # Redefine helper function to handle empty strings
        """
        CREATE OR REPLACE FUNCTION get_current_user_family_id()
        RETURNS INTEGER AS $$
        BEGIN
            RETURN (
                SELECT id_famiglia 
                FROM Appartenenza_Famiglia 
                WHERE id_utente = NULLIF(current_setting('app.current_user_id', true), '')::INTEGER
                LIMIT 1
            );
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        """,
        
        # Grant permissions to Supabase roles
        
        # Grant permissions to Supabase roles
        "GRANT ALL ON Configurazioni TO authenticated;",
        "GRANT ALL ON Configurazioni TO service_role;",
        "GRANT ALL ON Configurazioni TO postgres;",
        "GRANT ALL ON Configurazioni TO anon;",
        
        # 2. Policy Lettura Globale (Tutti possono leggere configurazioni senza famiglia)
        "DROP POLICY IF EXISTS \"Global configurations are readable by everyone\" ON Configurazioni;",
        """
        CREATE POLICY "Global configurations are readable by everyone" ON Configurazioni
            FOR SELECT
            USING (id_famiglia IS NULL);
        """,
        
        # 3. Policy Lettura Famiglia (Membri della famiglia possono leggere)
        "DROP POLICY IF EXISTS \"Family members can view family configurations\" ON Configurazioni;",
        """
        CREATE POLICY "Family members can view family configurations" ON Configurazioni
            FOR SELECT
            USING (id_famiglia = get_current_user_family_id());
        """,
        
        # 4. Policy Scrittura Famiglia (Solo Admin possono gestire)
        "DROP POLICY IF EXISTS \"Admins can manage family configurations\" ON Configurazioni;",
        """
        CREATE POLICY "Admins can manage family configurations" ON Configurazioni
            FOR ALL
            USING (
                id_famiglia = get_current_user_family_id() AND
                EXISTS (
                    SELECT 1 FROM Appartenenza_Famiglia 
                    WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
                    AND ruolo = 'admin'
                )
            );
        """
    ]
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            for cmd in sql_commands:
                print(f"Esecuzione: {cmd.strip().splitlines()[0]}...")
                cur.execute(cmd)
            con.commit()
            print("[OK] RLS abilitato e policy applicate con successo.")
            return True
    except Exception as e:
        print(f"[ERRORE] Errore durante l'applicazione RLS: {e}")
        return False

if __name__ == "__main__":
    apply_rls()
