-- ============================================================================
-- OPTIMIZE RLS POLICIES (Linter Fixes & Performance) - MASTER SCRIPT (FINAL)
-- ============================================================================
-- Questo script ottimizza le policy esistenti per risolvere TUTTI i warning di Supabase:
-- 1. "Auth RLS Init Plan": Avvolge `current_setting` e `auth.uid()` in `(SELECT ...)`
-- 2. "Multiple Permissive Policies": Consolida policy sovrapposte (es. Configurazioni).

-- ============================================================================
-- 1. Helper Function Optimization (STABLE)
-- ============================================================================

CREATE OR REPLACE FUNCTION get_current_user_family_id()
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT id_famiglia 
        FROM public.Appartenenza_Famiglia 
        WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE SET search_path = '';

-- ============================================================================
-- 2. Consolidation: Own Resources (Owner Management)
-- ============================================================================

-- *** CONTI ***
DROP POLICY IF EXISTS "Users can view own accounts" ON Conti;
DROP POLICY IF EXISTS "Users can create own accounts" ON Conti;
DROP POLICY IF EXISTS "Users can update own accounts" ON Conti;
DROP POLICY IF EXISTS "Users can delete own accounts" ON Conti;
DROP POLICY IF EXISTS "Users can manage own accounts" ON Conti;

CREATE POLICY "Users can manage own accounts" ON Conti
    FOR ALL
    USING (id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER))
    WITH CHECK (id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER));

-- *** CARTE ***
DROP POLICY IF EXISTS "Users can view own cards" ON Carte;
DROP POLICY IF EXISTS "Users can create own cards" ON Carte;
DROP POLICY IF EXISTS "Users can update own cards" ON Carte;
DROP POLICY IF EXISTS "Users can delete own cards" ON Carte;
DROP POLICY IF EXISTS "Users can manage own cards" ON Carte;

CREATE POLICY "Users can manage own cards" ON Carte
    FOR ALL
    USING (id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER))
    WITH CHECK (id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER));

-- *** ASSET ***
DROP POLICY IF EXISTS "Users can view own assets" ON Asset;
DROP POLICY IF EXISTS "Users can manage own assets" ON Asset;

CREATE POLICY "Users can manage own assets" ON Asset
    FOR ALL
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    )
    WITH CHECK (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    );

-- *** STORICO_ASSET ***
DROP POLICY IF EXISTS "Users can view own asset history" ON Storico_Asset;
DROP POLICY IF EXISTS "Users can manage own asset history" ON Storico_Asset;

CREATE POLICY "Users can manage own asset history" ON Storico_Asset
    FOR ALL
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    )
    WITH CHECK (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    );

-- *** STORICO_MASSIMALI_CARTE ***
DROP POLICY IF EXISTS "Users can view own cards history" ON StoricoMassimaliCarte;
DROP POLICY IF EXISTS "Users can manage own cards history" ON StoricoMassimaliCarte;

CREATE POLICY "Users can manage own cards history" ON StoricoMassimaliCarte
    FOR ALL
    USING (
        id_carta IN (
            SELECT id_carta FROM Carte 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    )
    WITH CHECK (
        id_carta IN (
            SELECT id_carta FROM Carte 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    );

-- *** TRANSAZIONI ***
DROP POLICY IF EXISTS "Users can view own transactions" ON Transazioni;
DROP POLICY IF EXISTS "Users can create own transactions" ON Transazioni;
DROP POLICY IF EXISTS "Users can update own transactions" ON Transazioni;
DROP POLICY IF EXISTS "Users can delete own transactions" ON Transazioni;
DROP POLICY IF EXISTS "Users can manage own transactions" ON Transazioni;

CREATE POLICY "Users can manage own transactions" ON Transazioni
    FOR ALL
    USING (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    )
    WITH CHECK (
        id_conto IN (
            SELECT id_conto FROM Conti 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    );

-- *** UTENTI ***
DROP POLICY IF EXISTS "Users can view own profile" ON Utenti;
DROP POLICY IF EXISTS "Users can update own profile" ON Utenti;

CREATE POLICY "Users can view own profile" ON Utenti
    FOR SELECT
    USING (id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER));
    
CREATE POLICY "Users can update own profile" ON Utenti
    FOR UPDATE
    USING (id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER));

-- *** FAMIGLIE ***
DROP POLICY IF EXISTS "Users can view own family" ON Famiglie;

CREATE POLICY "Users can view own family" ON Famiglie
    FOR SELECT
    USING (
        id_famiglia IN (
            SELECT id_famiglia FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    );

-- ============================================================================
-- 3. Consolidated & Split Logic (Family vs Admin vs Global)
-- ============================================================================

-- *** CONFIGURAZIONI (Fixed Overlap) ***
DROP POLICY IF EXISTS "Admins can manage family configurations" ON Configurazioni;
DROP POLICY IF EXISTS "Family members can view family configurations" ON Configurazioni;
DROP POLICY IF EXISTS "Global configurations are readable by everyone" ON Configurazioni;
DROP POLICY IF EXISTS "Admins can create family configurations" ON Configurazioni;
DROP POLICY IF EXISTS "Admins can update family configurations" ON Configurazioni;
DROP POLICY IF EXISTS "Admins can delete family configurations" ON Configurazioni;

-- Consolidated View Policy: View global configs (null family) OR own family configs
DROP POLICY IF EXISTS "Users can view relevant configurations" ON Configurazioni;
CREATE POLICY "Users can view relevant configurations" ON Configurazioni
    FOR SELECT
    USING (
        id_famiglia IS NULL 
        OR 
        id_famiglia = (SELECT get_current_user_family_id())
    );

-- Admin Management (Insert/Update/Delete only)
CREATE POLICY "Admins can create family configurations" ON Configurazioni
    FOR INSERT WITH CHECK (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can update family configurations" ON Configurazioni
    FOR UPDATE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can delete family configurations" ON Configurazioni
    FOR DELETE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );


-- *** APPARTENENZA_FAMIGLIA ***
DROP POLICY IF EXISTS "Users can view family members" ON Appartenenza_Famiglia;
DROP POLICY IF EXISTS "Users can view own membership" ON Appartenenza_Famiglia;
DROP POLICY IF EXISTS "Users can view family membership" ON Appartenenza_Famiglia;

CREATE POLICY "Users can view family membership" ON Appartenenza_Famiglia
    FOR SELECT
    USING (
        id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER) 
        OR 
        id_famiglia IN (
            SELECT id_famiglia FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    );

-- *** CONTI CONDIVISI ***
DROP POLICY IF EXISTS "Admins can create shared accounts" ON ContiCondivisi;
CREATE POLICY "Admins can create shared accounts" ON ContiCondivisi
    FOR INSERT
    WITH CHECK (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
DROP POLICY IF EXISTS "Admins can update shared accounts" ON ContiCondivisi;
CREATE POLICY "Admins can update shared accounts" ON ContiCondivisi
    FOR UPDATE
    USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );

-- *** TRANSAZIONI CONDIVISE ***
DROP POLICY IF EXISTS "Users can update own shared transactions" ON TransazioniCondivise;
CREATE POLICY "Users can update own shared transactions" ON TransazioniCondivise
    FOR UPDATE
    USING (id_utente_autore = (SELECT current_setting('app.current_user_id', true)::INTEGER));

DROP POLICY IF EXISTS "Users can delete own shared transactions" ON TransazioniCondivise;
CREATE POLICY "Users can delete own shared transactions" ON TransazioniCondivise
    FOR DELETE
    USING (id_utente_autore = (SELECT current_setting('app.current_user_id', true)::INTEGER));

DROP POLICY IF EXISTS "Users can create family shared transactions" ON Transazionicondivise;
CREATE POLICY "Users can create family shared transactions" ON Transazionicondivise
   FOR INSERT
   WITH CHECK (
       id_utente_autore = (SELECT current_setting('app.current_user_id', true)::INTEGER) AND
       id_conto_condiviso IN (
           SELECT id_conto_condiviso FROM ContiCondivisi 
           WHERE id_famiglia = (SELECT get_current_user_family_id())
       )
   );

-- *** INVITI ***
DROP POLICY IF EXISTS "Admins can manage invitations" ON Inviti;
DROP POLICY IF EXISTS "Users can view family invitations" ON Inviti;
DROP POLICY IF EXISTS "Admins can delete invitations" ON Inviti;

CREATE POLICY "Users can view family invitations" ON Inviti
    FOR SELECT
    USING (id_famiglia = (SELECT get_current_user_family_id()));

CREATE POLICY "Admins can manage invitations" ON Inviti
    FOR INSERT WITH CHECK (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can delete invitations" ON Inviti
    FOR DELETE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );

-- ============================================================================
-- 4. Shared Resources with Admin Management
-- ============================================================================

-- *** CATEGORIE ***
DROP POLICY IF EXISTS "Users can view family categories" ON Categorie;
DROP POLICY IF EXISTS "Admins can manage categories" ON Categorie;
DROP POLICY IF EXISTS "Admins can update categories" ON Categorie;
DROP POLICY IF EXISTS "Admins can delete categories" ON Categorie;

CREATE POLICY "Users can view family categories" ON Categorie
    FOR SELECT
    USING (id_famiglia = (SELECT get_current_user_family_id()));

CREATE POLICY "Admins can manage categories" ON Categorie
    FOR INSERT WITH CHECK (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can update categories" ON Categorie
    FOR UPDATE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can delete categories" ON Categorie
    FOR DELETE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );

-- *** SOTTOCATEGORIE ***
DROP POLICY IF EXISTS "Users can view family subcategories" ON Sottocategorie;
DROP POLICY IF EXISTS "Admins can manage subcategories" ON Sottocategorie;
DROP POLICY IF EXISTS "Admins can modify subcategories" ON Sottocategorie;
DROP POLICY IF EXISTS "Admins can delete subcategories" ON Sottocategorie;

CREATE POLICY "Users can view family subcategories" ON Sottocategorie
    FOR SELECT
    USING (
        id_categoria IN (
            SELECT id_categoria FROM Categorie 
            WHERE id_famiglia = (SELECT get_current_user_family_id())
        )
    );

CREATE POLICY "Admins can manage subcategories" ON Sottocategorie
    FOR INSERT WITH CHECK (
        id_categoria IN (
            SELECT id_categoria FROM Categorie 
            WHERE id_famiglia = (SELECT get_current_user_family_id()) AND
            EXISTS (
                SELECT 1 FROM Appartenenza_Famiglia 
                WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
                AND ruolo = 'admin'
            )
        )
    );
CREATE POLICY "Admins can modify subcategories" ON Sottocategorie
    FOR UPDATE USING (
        id_categoria IN (
            SELECT id_categoria FROM Categorie 
            WHERE id_famiglia = (SELECT get_current_user_family_id()) AND
            EXISTS (
                SELECT 1 FROM Appartenenza_Famiglia 
                WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
                AND ruolo = 'admin'
            )
        )
    );
CREATE POLICY "Admins can delete subcategories" ON Sottocategorie
    FOR DELETE USING (
        id_categoria IN (
            SELECT id_categoria FROM Categorie 
            WHERE id_famiglia = (SELECT get_current_user_family_id()) AND
            EXISTS (
                SELECT 1 FROM Appartenenza_Famiglia 
                WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
                AND ruolo = 'admin'
            )
        )
    );

-- *** BUDGET ***
DROP POLICY IF EXISTS "Users can view family budgets" ON Budget;
DROP POLICY IF EXISTS "Admins can manage budgets" ON Budget;
DROP POLICY IF EXISTS "Admins can update budgets" ON Budget;
DROP POLICY IF EXISTS "Admins can delete budgets" ON Budget;

CREATE POLICY "Users can view family budgets" ON Budget
    FOR SELECT
    USING (id_famiglia = (SELECT get_current_user_family_id()));

CREATE POLICY "Admins can manage budgets" ON Budget
    FOR INSERT WITH CHECK (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can update budgets" ON Budget
    FOR UPDATE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can delete budgets" ON Budget
    FOR DELETE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );

-- *** PRESTITI ***
DROP POLICY IF EXISTS "Users can view family loans" ON Prestiti;
DROP POLICY IF EXISTS "Admins can manage loans" ON Prestiti;
DROP POLICY IF EXISTS "Admins can modify loans" ON Prestiti;
DROP POLICY IF EXISTS "Admins can delete loans" ON Prestiti;

CREATE POLICY "Users can view family loans" ON Prestiti
    FOR SELECT
    USING (id_famiglia = (SELECT get_current_user_family_id()));

CREATE POLICY "Admins can manage loans" ON Prestiti
    FOR INSERT WITH CHECK (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can modify loans" ON Prestiti
    FOR UPDATE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can delete loans" ON Prestiti
    FOR DELETE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );

-- *** IMMOBILI ***
DROP POLICY IF EXISTS "Users can view family properties" ON Immobili;
DROP POLICY IF EXISTS "Admins can manage properties" ON Immobili;
DROP POLICY IF EXISTS "Admins can modify properties" ON Immobili;
DROP POLICY IF EXISTS "Admins can delete properties" ON Immobili;

CREATE POLICY "Users can view family properties" ON Immobili
    FOR SELECT
    USING (id_famiglia = (SELECT get_current_user_family_id()));

CREATE POLICY "Admins can manage properties" ON Immobili
    FOR INSERT WITH CHECK (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can modify properties" ON Immobili
    FOR UPDATE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can delete properties" ON Immobili
    FOR DELETE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );

-- *** SPESE FISSE ***
DROP POLICY IF EXISTS "Users can view family fixed expenses" ON SpeseFisse;
DROP POLICY IF EXISTS "Admins can manage fixed expenses" ON SpeseFisse;
DROP POLICY IF EXISTS "Admins can modify fixed expenses" ON SpeseFisse;
DROP POLICY IF EXISTS "Admins can delete fixed expenses" ON SpeseFisse;

CREATE POLICY "Users can view family fixed expenses" ON SpeseFisse
    FOR SELECT
    USING (id_famiglia = (SELECT get_current_user_family_id()));

CREATE POLICY "Admins can manage fixed expenses" ON SpeseFisse
    FOR INSERT WITH CHECK (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can modify fixed expenses" ON SpeseFisse
    FOR UPDATE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can delete fixed expenses" ON SpeseFisse
    FOR DELETE USING (
        id_famiglia = (SELECT get_current_user_family_id()) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );

-- *** SALVADANAI ***
DROP POLICY IF EXISTS "Users can manage family piggy banks" ON Salvadanai;
CREATE POLICY "Users can manage family piggy banks" ON Salvadanai
    FOR ALL
    USING (
        id_famiglia IN (
            SELECT id_famiglia FROM public.Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    )
    WITH CHECK (
        id_famiglia IN (
            SELECT id_famiglia FROM public.Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    );

-- *** OBIETTIVI_RISPARMIO ***
DROP POLICY IF EXISTS "Users can manage family savings goals" ON Obiettivi_Risparmio;
CREATE POLICY "Users can manage family savings goals" ON Obiettivi_Risparmio
    FOR ALL
    USING (
        id_famiglia IN (
            SELECT id_famiglia FROM public.Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    )
    WITH CHECK (
        id_famiglia IN (
            SELECT id_famiglia FROM public.Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
        )
    );

-- *** PIANO AMMORTAMENTO ***
DROP POLICY IF EXISTS "Users can view family amortization plan" ON PianoAmmortamento;
DROP POLICY IF EXISTS "Admins can manage amortization plan" ON PianoAmmortamento;
DROP POLICY IF EXISTS "Admins can modify amortization plan" ON PianoAmmortamento;
DROP POLICY IF EXISTS "Admins can delete amortization plan" ON PianoAmmortamento;

CREATE POLICY "Users can view family amortization plan" ON PianoAmmortamento
    FOR SELECT
    USING (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti 
            WHERE id_famiglia = (SELECT get_current_user_family_id())
        )
    );

CREATE POLICY "Admins can manage amortization plan" ON PianoAmmortamento
    FOR INSERT WITH CHECK (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti 
            WHERE id_famiglia = (SELECT get_current_user_family_id())
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin' AND id_famiglia = (SELECT get_current_user_family_id())
        )
    );
CREATE POLICY "Admins can modify amortization plan" ON PianoAmmortamento
    FOR UPDATE USING (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti 
            WHERE id_famiglia = (SELECT get_current_user_family_id())
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin' AND id_famiglia = (SELECT get_current_user_family_id())
        )
    );
CREATE POLICY "Admins can delete amortization plan" ON PianoAmmortamento
    FOR DELETE USING (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti 
            WHERE id_famiglia = (SELECT get_current_user_family_id())
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin' AND id_famiglia = (SELECT get_current_user_family_id())
        )
    );

-- *** QUOTE PRESTITI ***
DROP POLICY IF EXISTS "Admins can manage loan shares" ON QuotePrestiti;
DROP POLICY IF EXISTS "Admins can update loan shares" ON QuotePrestiti;
DROP POLICY IF EXISTS "Admins can delete loan shares" ON QuotePrestiti;
DROP POLICY IF EXISTS "Users can view family loan shares" ON QuotePrestiti;

CREATE POLICY "Users can view family loan shares" ON QuotePrestiti
    FOR SELECT
    USING (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti WHERE id_famiglia = (SELECT get_current_user_family_id())
        )
    );

CREATE POLICY "Admins can manage loan shares" ON QuotePrestiti
    FOR INSERT WITH CHECK (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti WHERE id_famiglia = (SELECT get_current_user_family_id())
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can update loan shares" ON QuotePrestiti
    FOR UPDATE USING (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti WHERE id_famiglia = (SELECT get_current_user_family_id())
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can delete loan shares" ON QuotePrestiti
    FOR DELETE USING (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti WHERE id_famiglia = (SELECT get_current_user_family_id())
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );

-- *** QUOTE IMMOBILI ***
DROP POLICY IF EXISTS "Admins can manage property shares" ON QuoteImmobili;
DROP POLICY IF EXISTS "Admins can update property shares" ON QuoteImmobili;
DROP POLICY IF EXISTS "Admins can delete property shares" ON QuoteImmobili;
DROP POLICY IF EXISTS "Users can view family property shares" ON QuoteImmobili;

CREATE POLICY "Users can view family property shares" ON QuoteImmobili
    FOR SELECT
    USING (
        id_immobile IN (
            SELECT id_immobile FROM Immobili WHERE id_famiglia = (SELECT get_current_user_family_id())
        )
    );

CREATE POLICY "Admins can manage property shares" ON QuoteImmobili
    FOR INSERT WITH CHECK (
        id_immobile IN (
            SELECT id_immobile FROM Immobili WHERE id_famiglia = (SELECT get_current_user_family_id())
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can update property shares" ON QuoteImmobili
    FOR UPDATE USING (
        id_immobile IN (
            SELECT id_immobile FROM Immobili WHERE id_famiglia = (SELECT get_current_user_family_id())
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
CREATE POLICY "Admins can delete property shares" ON QuoteImmobili
    FOR DELETE USING (
        id_immobile IN (
            SELECT id_immobile FROM Immobili WHERE id_famiglia = (SELECT get_current_user_family_id())
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );

-- *** STORICO ASSET GLOBALE (Shared Cache) ***
-- Drop potential duplicates
DROP POLICY IF EXISTS "Authenticated users can manage global asset history" ON storicoassetglobale;
DROP POLICY IF EXISTS "storicoassetglobale_select_all" ON storicoassetglobale;
DROP POLICY IF EXISTS "Everyone can read global asset history" ON storicoassetglobale;

CREATE POLICY "Authenticated users can manage global asset history" ON storicoassetglobale
    FOR ALL
    TO authenticated
    USING ((SELECT auth.uid()) IS NOT NULL)
    WITH CHECK ((SELECT auth.uid()) IS NOT NULL);
