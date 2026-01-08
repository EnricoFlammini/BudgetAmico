-- ============================================================================
-- ABILITAZIONE RLS SU public.storicoassetglobale
-- ============================================================================

-- IMPORTANTE:
-- La tabella `storicoassetglobale` è una cache globale dei dati di mercato (prezzi storici).
-- Non è legata a un singolo utente, ma condivisa tra tutti per efficienza.
-- Pertanto, la policy RLS deve permettere a tutti gli utenti AUTENTICATI di:
-- 1. Leggere i dati (SELECT)
-- 2. Aggiornare i dati se mancano o sono vecchi (INSERT/UPDATE)

-- 1. Abilita Row Level Security
ALTER TABLE public.storicoassetglobale ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Enable read access for all users" ON public.storicoassetglobale;
DROP POLICY IF EXISTS "Enable all access for all users" ON public.storicoassetglobale;
DROP POLICY IF EXISTS "RLS Policy Always True" ON public.storicoassetglobale;
DROP POLICY IF EXISTS "Users can view own asset history (global)" ON public.storicoassetglobale;
DROP POLICY IF EXISTS "Users can manage own asset history (global)" ON public.storicoassetglobale;
-- Policies reported by Linter
DROP POLICY IF EXISTS "storicoassetglobale_delete_all" ON public.storicoassetglobale;
DROP POLICY IF EXISTS "storicoassetglobale_insert_all" ON public.storicoassetglobale;
DROP POLICY IF EXISTS "storicoassetglobale_update_all" ON public.storicoassetglobale;
DROP POLICY IF EXISTS "Authenticated users can manage global asset history" ON public.storicoassetglobale;

-- 3. Crea nuova policy (Accesso Condiviso per Utenti Autenticati)
-- Questa policy permette l'accesso completo MA SOLO agli utenti loggati (authenticated).
-- Impedisce l'accesso anonimo.
CREATE POLICY "Authenticated users can manage global asset history" ON public.storicoassetglobale
    FOR ALL
    TO authenticated
    USING ((select auth.uid()) IS NOT NULL)
    WITH CHECK ((select auth.uid()) IS NOT NULL);
