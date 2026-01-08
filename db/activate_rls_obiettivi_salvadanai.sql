-- ============================================================================
-- ABILITAZIONE RLS SU public.obiettivi_risparmio E public.salvadanai
-- ============================================================================

-- ============================================================================
-- 1. TABELLA: SALVADANAI
-- ============================================================================

-- Abilita RLS
ALTER TABLE public.salvadanai ENABLE ROW LEVEL SECURITY;

-- Rimuovi policy vecchie
DROP POLICY IF EXISTS "Enable read access for all users" ON public.salvadanai;
DROP POLICY IF EXISTS "Enable all access for all users" ON public.salvadanai;
DROP POLICY IF EXISTS "RLS Enabled No Policy" ON public.salvadanai;

-- Policy di VISUALIZZAZIONE E GESTIONE
-- Ipotesi: Salvadanai collegati alla Famiglia (id_famiglia)
CREATE POLICY "Users can manage family piggy banks" ON public.salvadanai
    FOR ALL
    USING (
        id_famiglia IN (
            SELECT id_famiglia FROM public.Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );

-- Opzionale: Se i salvadanai possono essere personali (senza famiglia), aggiungi check su id_utente se presente
-- OR id_utente = auth.uid()


-- ============================================================================
-- 2. TABELLA: OBIETTIVI_RISPARMIO
-- ============================================================================

-- Abilita RLS
ALTER TABLE public.obiettivi_risparmio ENABLE ROW LEVEL SECURITY;

-- Rimuovi policy vecchie
DROP POLICY IF EXISTS "Enable read access for all users" ON public.obiettivi_risparmio;
DROP POLICY IF EXISTS "Enable all access for all users" ON public.obiettivi_risparmio;
DROP POLICY IF EXISTS "RLS Enabled No Policy" ON public.obiettivi_risparmio;

-- Policy di VISUALIZZAZIONE E GESTIONE
-- Ipotesi: Obiettivi collegati alla Famiglia (id_famiglia)
CREATE POLICY "Users can manage family savings goals" ON public.obiettivi_risparmio
    FOR ALL
    USING (
        id_famiglia IN (
            SELECT id_famiglia FROM public.Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER
        )
    );
