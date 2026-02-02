-- Migrazione per la persistenza delle configurazioni globali
-- 1. Aggiunta indice univoco parziale per permettere ON CONFLICT su id_famiglia IS NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_configurazioni_globali 
ON Configurazioni (chiave) 
WHERE id_famiglia IS NULL;

-- 2. Aggiornamento Policy RLS per permettere agli Admin di gestire le configurazioni globali
-- Nota: L'utente admin di sistema opera in un contesto dove get_current_user_family_id() potrebbe essere NULL 
-- o legato alla sua famiglia personale, ma deve poter gestire le config globali.

DROP POLICY IF EXISTS "Admins can manage global configurations" ON Configurazioni;
CREATE POLICY "Admins can manage global configurations" ON Configurazioni
    FOR ALL
    USING (
        id_famiglia IS NULL AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    )
    WITH CHECK (
        id_famiglia IS NULL AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = (SELECT current_setting('app.current_user_id', true)::INTEGER)
            AND ruolo = 'admin'
        )
    );
