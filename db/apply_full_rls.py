import os
import sys
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

# Configura path come prima
script_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def get_connection_params(db_url):
    result = urlparse(db_url)
    return {
        'user': result.username,
        'password': result.password,
        'host': result.hostname,
        'port': result.port or 5432,
        'database': result.path[1:] if result.path else 'postgres'
    }

def apply_rls():
    load_dotenv()
    db_url = os.getenv("SUPABASE_DB_URL")
    
    if not db_url:
        print("Errore: SUPABASE_DB_URL non trovata")
        return

    print(f"Connessione a: {db_url.split('@')[1]}")

    try:
        params = get_connection_params(db_url)
        conn = psycopg2.connect(**params)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Applying Optimized RLS policies (v2)...")
        
        # 1. Helper Function: auth_uid()
        # This function wraps current_setting and is marked STABLE to allow optimization (InitPlan)
        print("- Function: auth_uid")
        cur.execute("""
        CREATE OR REPLACE FUNCTION auth_uid()
        RETURNS INTEGER AS $$
        BEGIN
            RETURN current_setting('app.current_user_id', true)::INTEGER;
        END;
        $$ LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '';
        """)

        # 2. Helper Function: get_current_user_family_id()
        # Updated to use auth_uid() and marked STABLE
        print("- Function: get_current_user_family_id")
        cur.execute("""
        CREATE OR REPLACE FUNCTION get_current_user_family_id()
        RETURNS INTEGER AS $$
        BEGIN
            RETURN (
                SELECT id_famiglia 
                FROM public.Appartenenza_Famiglia 
                WHERE id_utente = auth_uid()
                LIMIT 1
            );
        END;
        $$ LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '';
        """)

        # 3. Enable RLS on ALL tables
        tables = [
            "Famiglie", "Utenti", "Appartenenza_Famiglia", "Inviti",
            "Conti", "ContiCondivisi", "PartecipazioneContoCondiviso",
            "Categorie", "Sottocategorie", "Transazioni", "TransazioniCondivise",
            "Budget", "Budget_Storico", "Prestiti", "StoricoPagamentiRate",
            "Immobili", "QuoteImmobili", "Asset", "Storico_Asset", "SpeseFisse",
            "PianoAmmortamento", "QuotePrestiti",
            "Carte", "StoricoMassimaliCarte",
            "Contatti", "CondivisioneContatto",
            "Configurazioni", "Log_Sistema", "Config_Logger",
            "InfoDB"
        ]
        
        print("- Enabling RLS on tables...")
        for table in tables:
            try:
                cur.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
            except Exception as e:
                print(f"  Warning enabling RLS on {table}: {e}")

        # 4. Apply Policies (using auth_uid() and helper functions)
        
        # InfoDB
        cur.execute("""
            DROP POLICY IF EXISTS "Everyone can read InfoDB" ON InfoDB;
            CREATE POLICY "Everyone can read InfoDB" ON InfoDB FOR SELECT USING (true);
        """)
        
        # Utenti
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view own profile" ON Utenti;
            CREATE POLICY "Users can view own profile" ON Utenti FOR SELECT USING (id_utente = auth_uid());
            DROP POLICY IF EXISTS "Users can update own profile" ON Utenti;
            CREATE POLICY "Users can update own profile" ON Utenti FOR UPDATE USING (id_utente = auth_uid());
        """)

        # Famiglie
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view own family" ON Famiglie;
            CREATE POLICY "Users can view own family" ON Famiglie FOR SELECT USING (id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = auth_uid()));
        """)

        # Appartenenza_Famiglia
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view own memberships" ON Appartenenza_Famiglia;
            CREATE POLICY "Users can view own memberships" ON Appartenenza_Famiglia FOR SELECT USING (
                id_utente = auth_uid() OR
                id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = auth_uid())
            );
        """)
        
        # Inviti
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view own invitations" ON Inviti;
            CREATE POLICY "Users can view own invitations" ON Inviti FOR SELECT USING (
                email_invitato = (SELECT email FROM Utenti WHERE id_utente = auth_uid()) OR
                id_famiglia IN (SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = auth_uid())
            );
        """)

        # Conti
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view own accounts" ON Conti;
            CREATE POLICY "Users can view own accounts" ON Conti FOR SELECT USING (id_utente = auth_uid());
            
            DROP POLICY IF EXISTS "Users can create own accounts" ON Conti;
            CREATE POLICY "Users can create own accounts" ON Conti FOR INSERT WITH CHECK (id_utente = auth_uid());
            
            DROP POLICY IF EXISTS "Users can update own accounts" ON Conti;
            CREATE POLICY "Users can update own accounts" ON Conti FOR UPDATE USING (id_utente = auth_uid());
            
            DROP POLICY IF EXISTS "Users can delete own accounts" ON Conti;
            CREATE POLICY "Users can delete own accounts" ON Conti FOR DELETE USING (id_utente = auth_uid());
        """)

        # ContiCondivisi
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view family shared accounts" ON ContiCondivisi;
            CREATE POLICY "Users can view family shared accounts" ON ContiCondivisi FOR SELECT USING (id_famiglia = get_current_user_family_id());
            
            DROP POLICY IF EXISTS "Admins can create shared accounts" ON ContiCondivisi;
            CREATE POLICY "Admins can create shared accounts" ON ContiCondivisi FOR INSERT WITH CHECK (
                id_famiglia = get_current_user_family_id() AND
                EXISTS (SELECT 1 FROM Appartenenza_Famiglia WHERE id_utente = auth_uid() AND id_famiglia = get_current_user_family_id() AND ruolo = 'admin')
            );
            
            DROP POLICY IF EXISTS "Admins can update shared accounts" ON ContiCondivisi;
            CREATE POLICY "Admins can update shared accounts" ON ContiCondivisi FOR UPDATE USING (
                id_famiglia = get_current_user_family_id() AND
                EXISTS (SELECT 1 FROM Appartenenza_Famiglia WHERE id_utente = auth_uid() AND id_famiglia = get_current_user_family_id() AND ruolo = 'admin')
            );
        """)
        
        # PartecipazioneContoCondiviso
        cur.execute("""
            DROP POLICY IF EXISTS "Users see participation" ON PartecipazioneContoCondiviso;
            CREATE POLICY "Users see participation" ON PartecipazioneContoCondiviso FOR SELECT USING (
                id_conto_condiviso IN (SELECT id_conto_condiviso FROM ContiCondivisi WHERE id_famiglia = get_current_user_family_id())
            );
        """)

        # Carte
        cur.execute("""
            DROP POLICY IF EXISTS "Users can view own cards" ON Carte;
            CREATE POLICY "Users can view own cards" ON Carte FOR SELECT USING (id_utente = auth_uid());
            
            DROP POLICY IF EXISTS "Users can create own cards" ON Carte;
            CREATE POLICY "Users can create own cards" ON Carte FOR INSERT WITH CHECK (id_utente = auth_uid());
            
            DROP POLICY IF EXISTS "Users can update own cards" ON Carte;
            CREATE POLICY "Users can update own cards" ON Carte FOR UPDATE USING (id_utente = auth_uid());
            
            DROP POLICY IF EXISTS "Users can delete own cards" ON Carte;
            CREATE POLICY "Users can delete own cards" ON Carte FOR DELETE USING (id_utente = auth_uid());
        """)
        
        # StoricoMassimaliCarte
        cur.execute("""
            DROP POLICY IF EXISTS "Users view card history" ON StoricoMassimaliCarte;
            DROP POLICY IF EXISTS "Users manage card history" ON StoricoMassimaliCarte;
            
            CREATE POLICY "Users manage card history" ON StoricoMassimaliCarte FOR ALL USING (
                 id_carta IN (SELECT id_carta FROM Carte WHERE id_utente = auth_uid())
            );
        """)

        # Categorie / Sottocategorie
        cur.execute("""
            DROP POLICY IF EXISTS "Users view family categories" ON Categorie;
            CREATE POLICY "Users view family categories" ON Categorie FOR SELECT USING (id_famiglia = get_current_user_family_id());
            
            DROP POLICY IF EXISTS "Users view family subcategories" ON Sottocategorie;
            CREATE POLICY "Users view family subcategories" ON Sottocategorie FOR SELECT USING ((SELECT id_famiglia FROM Categorie WHERE id_categoria = Sottocategorie.id_categoria) = get_current_user_family_id());
        """)

        # Transazioni
        cur.execute("""
            DROP POLICY IF EXISTS "Users view own transactions" ON Transazioni;
            DROP POLICY IF EXISTS "Users manage own transactions" ON Transazioni;
            
            CREATE POLICY "Users manage own transactions" ON Transazioni FOR ALL USING (
                id_conto IN (SELECT id_conto FROM Conti WHERE id_utente = auth_uid())
            );
        """)
        
        # Transazioni Condivise
        cur.execute("""
            DROP POLICY IF EXISTS "Users view shared transactions" ON TransazioniCondivise;
            CREATE POLICY "Users view shared transactions" ON TransazioniCondivise FOR SELECT USING (
                 id_conto_condiviso IN (SELECT id_conto_condiviso FROM ContiCondivisi WHERE id_famiglia = get_current_user_family_id())
            );
            
            DROP POLICY IF EXISTS "Users create shared transactions" ON TransazioniCondivise;
            CREATE POLICY "Users create shared transactions" ON TransazioniCondivise FOR INSERT WITH CHECK (
                id_utente_autore = auth_uid() AND
                id_conto_condiviso IN (SELECT id_conto_condiviso FROM ContiCondivisi WHERE id_famiglia = get_current_user_family_id())
            );
            
            DROP POLICY IF EXISTS "Users manage own shared transactions" ON TransazioniCondivise;
            CREATE POLICY "Users manage own shared transactions" ON TransazioniCondivise FOR UPDATE USING (id_utente_autore = auth_uid());
            
            DROP POLICY IF EXISTS "Users delete own shared transactions" ON TransazioniCondivise;
            CREATE POLICY "Users delete own shared transactions" ON TransazioniCondivise FOR DELETE USING (id_utente_autore = auth_uid());
        """)

        # Budget
        cur.execute("""
            DROP POLICY IF EXISTS "Users view budgets" ON Budget;
            CREATE POLICY "Users view budgets" ON Budget FOR SELECT USING (id_famiglia = get_current_user_family_id());
            DROP POLICY IF EXISTS "Users view budget history" ON Budget_Storico;
            CREATE POLICY "Users view budget history" ON Budget_Storico FOR SELECT USING (id_famiglia = get_current_user_family_id());
        """)

        # Prestiti / Immobili / SpeseFisse
        cur.execute("""
            DROP POLICY IF EXISTS "Users view loans" ON Prestiti;
            CREATE POLICY "Users view loans" ON Prestiti FOR SELECT USING (id_famiglia = get_current_user_family_id());
            
            DROP POLICY IF EXISTS "Users view properties" ON Immobili;
            CREATE POLICY "Users view properties" ON Immobili FOR SELECT USING (id_famiglia = get_current_user_family_id());
            
            DROP POLICY IF EXISTS "Users view fixed expenses" ON SpeseFisse;
            CREATE POLICY "Users view fixed expenses" ON SpeseFisse FOR SELECT USING (id_famiglia = get_current_user_family_id());
        """)
        
        # Piano Ammortamento
        cur.execute("""
            DROP POLICY IF EXISTS "Users view amortization plan" ON PianoAmmortamento;
            CREATE POLICY "Users view amortization plan" ON PianoAmmortamento FOR SELECT USING (
                id_prestito IN (SELECT id_prestito FROM Prestiti WHERE id_famiglia = get_current_user_family_id())
            );
        """)
        
        # Quote Prestiti / Immobili
        cur.execute("""
            DROP POLICY IF EXISTS "Users view loan quotes" ON QuotePrestiti;
            CREATE POLICY "Users view loan quotes" ON QuotePrestiti FOR SELECT USING (
                id_prestito IN (SELECT id_prestito FROM Prestiti WHERE id_famiglia = get_current_user_family_id())
            );
            
            DROP POLICY IF EXISTS "Users view property quotes" ON QuoteImmobili;
            CREATE POLICY "Users view property quotes" ON QuoteImmobili FOR SELECT USING (
                id_immobile IN (SELECT id_immobile FROM Immobili WHERE id_famiglia = get_current_user_family_id())
            );
        """)

        # Asset / Storico Asset
        cur.execute("""
            DROP POLICY IF EXISTS "Users view own assets" ON Asset;
            CREATE POLICY "Users view own assets" ON Asset FOR SELECT USING (
                id_conto IN (SELECT id_conto FROM Conti WHERE id_utente = auth_uid())
            );
            DROP POLICY IF EXISTS "Users manage own assets" ON Asset;
            CREATE POLICY "Users manage own assets" ON Asset FOR ALL USING (
                id_conto IN (SELECT id_conto FROM Conti WHERE id_utente = auth_uid())
            );
            
            DROP POLICY IF EXISTS "Users view asset history" ON Storico_Asset;
            CREATE POLICY "Users view asset history" ON Storico_Asset FOR SELECT USING (
                id_conto IN (SELECT id_conto FROM Conti WHERE id_utente = auth_uid())
            );
            DROP POLICY IF EXISTS "Users manage asset history" ON Storico_Asset;
            CREATE POLICY "Users manage asset history" ON Storico_Asset FOR ALL USING (
                id_conto IN (SELECT id_conto FROM Conti WHERE id_utente = auth_uid())
            );
        """)

        # Storico Pagamenti Rate (Linked to Prestiti -> Family)
        cur.execute("""
            DROP POLICY IF EXISTS "Users view loan payments" ON StoricoPagamentiRate;
            CREATE POLICY "Users view loan payments" ON StoricoPagamentiRate FOR SELECT USING (
                id_prestito IN (SELECT id_prestito FROM Prestiti WHERE id_famiglia = get_current_user_family_id())
            );
        """)

        # Configurazioni (Linked to Family)
        cur.execute("""
            DROP POLICY IF EXISTS "Users view family configs" ON Configurazioni;
            CREATE POLICY "Users view family configs" ON Configurazioni FOR SELECT USING (id_famiglia = get_current_user_family_id());
            DROP POLICY IF EXISTS "Admins manage family configs" ON Configurazioni;
            CREATE POLICY "Admins manage family configs" ON Configurazioni FOR ALL USING (
                 id_famiglia = get_current_user_family_id() AND
                 EXISTS (SELECT 1 FROM Appartenenza_Famiglia WHERE id_utente = auth_uid() AND id_famiglia = get_current_user_family_id() AND ruolo = 'admin')
            );
        """)

        # Log Sistema
        cur.execute("""
            DROP POLICY IF EXISTS "Users view own logs" ON Log_Sistema;
            CREATE POLICY "Users view own logs" ON Log_Sistema FOR SELECT USING (
                id_utente = auth_uid() OR
                id_famiglia = get_current_user_family_id()
            );
            DROP POLICY IF EXISTS "Users insert logs" ON Log_Sistema;
            CREATE POLICY "Users insert logs" ON Log_Sistema FOR INSERT WITH CHECK (
                auth_uid() IS NOT NULL 
            );
        """)

        # Config Logger (Read-only for authenticated)
        cur.execute("""
             DROP POLICY IF EXISTS "Users view logger config" ON Config_Logger;
             CREATE POLICY "Users view logger config" ON Config_Logger FOR SELECT USING (auth_uid() IS NOT NULL);
        """)

        # Contatti
        cur.execute("""
            DROP POLICY IF EXISTS "Users view contacts" ON Contatti;
            CREATE POLICY "Users view contacts" ON Contatti FOR SELECT USING (
                id_utente = auth_uid() OR
                id_contatto IN (SELECT id_contatto FROM CondivisioneContatto WHERE id_utente = auth_uid())
            );
            
            DROP POLICY IF EXISTS "Users manage own contacts" ON Contatti;
            -- Splitted policies
            DROP POLICY IF EXISTS "Users insert own contacts" ON Contatti;
            CREATE POLICY "Users insert own contacts" ON Contatti FOR INSERT WITH CHECK (id_utente = auth_uid());
            DROP POLICY IF EXISTS "Users update own contacts" ON Contatti;
            CREATE POLICY "Users update own contacts" ON Contatti FOR UPDATE USING (id_utente = auth_uid());
            DROP POLICY IF EXISTS "Users delete own contacts" ON Contatti;
            CREATE POLICY "Users delete own contacts" ON Contatti FOR DELETE USING (id_utente = auth_uid());
        """)
        
        # Condivisione Contatto
        cur.execute("""
            DROP POLICY IF EXISTS "Users view shared contacts" ON CondivisioneContatto;
            CREATE POLICY "Users view shared contacts" ON CondivisioneContatto FOR SELECT USING (
                id_contatto IN (SELECT id_contatto FROM Contatti WHERE id_utente = auth_uid()) OR
                id_utente = auth_uid()
            );
             DROP POLICY IF EXISTS "Users manage shared contacts" ON CondivisioneContatto;
             -- Splitted policies (Only the owner of the contact can manage sharing)
            DROP POLICY IF EXISTS "Users insert sharing" ON CondivisioneContatto;
            CREATE POLICY "Users insert sharing" ON CondivisioneContatto FOR INSERT WITH CHECK (
                 id_contatto IN (SELECT id_contatto FROM Contatti WHERE id_utente = auth_uid())
            );
            DROP POLICY IF EXISTS "Users update sharing" ON CondivisioneContatto;
            CREATE POLICY "Users update sharing" ON CondivisioneContatto FOR UPDATE USING (
                 id_contatto IN (SELECT id_contatto FROM Contatti WHERE id_utente = auth_uid())
            );
            DROP POLICY IF EXISTS "Users delete sharing" ON CondivisioneContatto;
            CREATE POLICY "Users delete sharing" ON CondivisioneContatto FOR DELETE USING (
                 id_contatto IN (SELECT id_contatto FROM Contatti WHERE id_utente = auth_uid())
            );
        """)

        print("Correctly applied Optimized RLS policies to all tables.")
        conn.close()

    except Exception as e:
        print(f"Error applying RLS: {e}")
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    apply_rls()
