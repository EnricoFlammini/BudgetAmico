-- ============================================================================
-- Row Level Security (RLS) Policies per Budget Amico
-- ============================================================================
-- Questo script configura le policy RLS su Supabase per garantire che ogni
-- utente veda solo i propri dati e quelli della propria famiglia.
--
-- IMPORTANTE: Eseguire questo script DOPO aver migrato i dati con migrazione_postgres.py
-- ============================================================================

-- Abilita RLS su tutte le tabelle
-- ============================================================================

ALTER TABLE Famiglie ENABLE ROW LEVEL SECURITY;
ALTER TABLE Utenti ENABLE ROW LEVEL SECURITY;
ALTER TABLE Appartenenza_Famiglia ENABLE ROW LEVEL SECURITY;
ALTER TABLE Inviti ENABLE ROW LEVEL SECURITY;
ALTER TABLE Conti ENABLE ROW LEVEL SECURITY;
ALTER TABLE ContiCondivisi ENABLE ROW LEVEL SECURITY;
ALTER TABLE PartecipazioneContoCondiviso ENABLE ROW LEVEL SECURITY;
ALTER TABLE Categorie ENABLE ROW LEVEL SECURITY;
ALTER TABLE Sottocategorie ENABLE ROW LEVEL SECURITY;
ALTER TABLE Transazioni ENABLE ROW LEVEL SECURITY;
ALTER TABLE TransazioniCondivise ENABLE ROW LEVEL SECURITY;
ALTER TABLE Budget ENABLE ROW LEVEL SECURITY;
ALTER TABLE Budget_Storico ENABLE ROW LEVEL SECURITY;
ALTER TABLE Prestiti ENABLE ROW LEVEL SECURITY;
ALTER TABLE StoricoPagamentiRate ENABLE ROW LEVEL SECURITY;
ALTER TABLE Immobili ENABLE ROW LEVEL SECURITY;
ALTER TABLE Asset ENABLE ROW LEVEL SECURITY;
ALTER TABLE Storico_Asset ENABLE ROW LEVEL SECURITY;
ALTER TABLE SpeseFisse ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- Helper Function: Ottieni ID Famiglia dell'utente corrente
-- ============================================================================

CREATE OR REPLACE FUNCTION get_current_user_family_id()
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT id_famiglia 
        FROM Appartenenza_Famiglia 
        WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- Policy per Utenti
-- ============================================================================

-- Gli utenti possono vedere solo il proprio profilo
CREATE POLICY "Users can view own profile" ON Utenti
    FOR SELECT
    USING (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- Gli utenti possono aggiornare solo il proprio profilo
CREATE POLICY "Users can update own profile" ON Utenti
    FOR UPDATE
    USING (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- ============================================================================
-- Policy per Famiglie
-- ============================================================================

-- Gli utenti possono vedere solo la propria famiglia
CREATE POLICY "Users can view own family" ON Famiglie
    FOR SELECT
    USING (
        id_famiglia IN (
            SELECT id_famiglia FROM Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- ============================================================================
-- Policy per Conti Personali
-- ============================================================================

-- Gli utenti possono vedere solo i propri conti
CREATE POLICY "Users can view own accounts" ON Conti
    FOR SELECT
    USING (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- Gli utenti possono creare conti per se stessi
CREATE POLICY "Users can create own accounts" ON Conti
    FOR INSERT
    WITH CHECK (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- Gli utenti possono modificare solo i propri conti
CREATE POLICY "Users can update own accounts" ON Conti
    FOR UPDATE
    USING (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- Gli utenti possono eliminare solo i propri conti
CREATE POLICY "Users can delete own accounts" ON Conti
    FOR DELETE
    USING (id_utente = current_setting('app.current_user_id', true)::INTEGER);

-- ============================================================================
-- Policy per Conti Condivisi
-- ============================================================================

-- Gli utenti possono vedere i conti condivisi della propria famiglia
CREATE POLICY "Users can view family shared accounts" ON ContiCondivisi
    FOR SELECT
    USING (id_famiglia = get_current_user_family_id());

-- Solo admin possono creare conti condivisi
CREATE POLICY "Admins can create shared accounts" ON ContiCondivisi
    FOR INSERT
    WITH CHECK (
        id_famiglia = get_current_user_family_id() AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
            AND id_famiglia = get_current_user_family_id()
            AND ruolo = 'admin'
        )
    );

-- Solo admin possono modificare conti condivisi
CREATE POLICY "Admins can update shared accounts" ON ContiCondivisi
    FOR UPDATE
    USING (
        id_famiglia = get_current_user_family_id() AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
            AND ruolo = 'admin'
        )
    );

-- ============================================================================
-- Policy per Transazioni Personali
-- ============================================================================

-- Gli utenti possono vedere solo le transazioni dei propri conti
CREATE POLICY "Users can view own transactions" ON Transazioni
    FOR SELECT
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- Gli utenti possono creare transazioni solo sui propri conti
CREATE POLICY "Users can create own transactions" ON Transazioni
    FOR INSERT
    WITH CHECK (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- Gli utenti possono modificare solo le proprie transazioni
CREATE POLICY "Users can update own transactions" ON Transazioni
    FOR UPDATE
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- Gli utenti possono eliminare solo le proprie transazioni
CREATE POLICY "Users can delete own transactions" ON Transazioni
    FOR DELETE
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- ============================================================================
-- Policy per Transazioni Condivise
-- ============================================================================

-- Gli utenti possono vedere le transazioni condivise della propria famiglia
CREATE POLICY "Users can view family shared transactions" ON TransazioniCondivise
    FOR SELECT
    USING (
        id_conto_condiviso IN (
            SELECT id_conto_condiviso FROM ContiCondivisi 
            WHERE id_famiglia = get_current_user_family_id()
        )
    );

-- Gli utenti possono creare transazioni sui conti condivisi della famiglia
CREATE POLICY "Users can create family shared transactions" ON TransazioniCondivise
    FOR INSERT
    WITH CHECK (
        id_utente_autore = current_setting('app.current_user_id', true)::INTEGER AND
        id_conto_condiviso IN (
            SELECT id_conto_condiviso FROM ContiCondivisi 
            WHERE id_famiglia = get_current_user_family_id()
        )
    );

-- Gli utenti possono modificare solo le transazioni che hanno creato
CREATE POLICY "Users can update own shared transactions" ON TransazioniCondivise
    FOR UPDATE
    USING (id_utente_autore = current_setting('app.current_user_id', true)::INTEGER);

-- Gli utenti possono eliminare solo le transazioni che hanno creato
CREATE POLICY "Users can delete own shared transactions" ON TransazioniCondivise
    FOR DELETE
    USING (id_utente_autore = current_setting('app.current_user_id', true)::INTEGER);

-- ============================================================================
-- Policy per Categorie e Sottocategorie
-- ============================================================================

-- Gli utenti possono vedere le categorie della propria famiglia
CREATE POLICY "Users can view family categories" ON Categorie
    FOR SELECT
    USING (id_famiglia = get_current_user_family_id());

-- Solo admin possono gestire categorie
CREATE POLICY "Admins can manage categories" ON Categorie
    FOR ALL
    USING (
        id_famiglia = get_current_user_family_id() AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
            AND ruolo = 'admin'
        )
    );

-- Gli utenti possono vedere le sottocategorie della propria famiglia
CREATE POLICY "Users can view family subcategories" ON Sottocategorie
    FOR SELECT
    USING (
        id_categoria IN (
            SELECT id_categoria FROM Categorie 
            WHERE id_famiglia = get_current_user_family_id()
        )
    );

-- Solo admin possono gestire sottocategorie
CREATE POLICY "Admins can manage subcategories" ON Sottocategorie
    FOR ALL
    USING (
        id_categoria IN (
            SELECT id_categoria FROM Categorie 
            WHERE id_famiglia = get_current_user_family_id() AND
            EXISTS (
                SELECT 1 FROM Appartenenza_Famiglia 
                WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
                AND ruolo = 'admin'
            )
        )
    );

-- ============================================================================
-- Policy per Budget
-- ============================================================================

-- Gli utenti possono vedere i budget della propria famiglia
CREATE POLICY "Users can view family budgets" ON Budget
    FOR SELECT
    USING (id_famiglia = get_current_user_family_id());

-- Solo admin possono gestire budget
CREATE POLICY "Admins can manage budgets" ON Budget
    FOR ALL
    USING (
        id_famiglia = get_current_user_family_id() AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
            AND ruolo = 'admin'
        )
    );

-- Policy simili per Budget_Storico
CREATE POLICY "Users can view family budget history" ON Budget_Storico
    FOR SELECT
    USING (id_famiglia = get_current_user_family_id());

-- ============================================================================
-- Policy per Asset e Portafogli
-- ============================================================================

-- Gli utenti possono vedere gli asset dei propri conti
CREATE POLICY "Users can view own assets" ON Asset
    FOR SELECT
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- Gli utenti possono gestire gli asset dei propri conti
CREATE POLICY "Users can manage own assets" ON Asset
    FOR ALL
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- Policy simili per Storico_Asset
CREATE POLICY "Users can view own asset history" ON Storico_Asset
    FOR SELECT
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

CREATE POLICY "Users can manage own asset history" ON Storico_Asset
    FOR ALL
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- ============================================================================
-- Policy per Prestiti, Immobili, Spese Fisse
-- ============================================================================

-- Gli utenti possono vedere prestiti/immobili/spese della propria famiglia
CREATE POLICY "Users can view family loans" ON Prestiti
    FOR SELECT
    USING (id_famiglia = get_current_user_family_id());

CREATE POLICY "Users can view family properties" ON Immobili
    FOR SELECT
    USING (id_famiglia = get_current_user_family_id());

CREATE POLICY "Users can view family fixed expenses" ON SpeseFisse
    FOR SELECT
    USING (id_famiglia = get_current_user_family_id());

-- Solo admin possono gestire prestiti/immobili/spese
CREATE POLICY "Admins can manage loans" ON Prestiti
    FOR ALL
    USING (
        id_famiglia = get_current_user_family_id() AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
            AND ruolo = 'admin'
        )
    );

CREATE POLICY "Admins can manage properties" ON Immobili
    FOR ALL
    USING (
        id_famiglia = get_current_user_family_id() AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
            AND ruolo = 'admin'
        )
    );

CREATE POLICY "Admins can manage fixed expenses" ON SpeseFisse
    FOR ALL
    USING (
        id_famiglia = get_current_user_family_id() AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
            AND ruolo = 'admin'
        )
    );

-- Policy per StoricoPagamentiRate
CREATE POLICY "Users can view family loan payments" ON StoricoPagamentiRate
    FOR SELECT
    USING (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti 
            WHERE id_famiglia = get_current_user_family_id()
        )
    );

-- ============================================================================
-- NOTA FINALE
-- ============================================================================
-- Dopo aver eseguito questo script, testare le policy con:
-- SET app.current_user_id = 1;  -- Imposta ID utente di test
-- SELECT * FROM Conti;           -- Dovrebbe mostrare solo i conti dell'utente 1
-- ============================================================================
