-- ============================================================================
-- RLS Policies per PianoAmmortamento
-- ============================================================================

-- Abilita RLS sulla tabella
ALTER TABLE PianoAmmortamento ENABLE ROW LEVEL SECURITY;

-- 1. Policy di LETTURA per tutti i membri della famiglia
-- I membri della famiglia possono vedere il piano di ammortamento dei prestiti della propria famiglia
DROP POLICY IF EXISTS "Users can view family amortization plan" ON PianoAmmortamento;
CREATE POLICY "Users can view family amortization plan" ON PianoAmmortamento
    FOR SELECT
    USING (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti 
            WHERE id_famiglia = get_current_user_family_id()
        )
    );

-- 2. Policy di GESTIONE (Insert, Update, Delete) per gli ADMIN
-- Solo gli admin possono generare/modificare il piano di ammortamento
DROP POLICY IF EXISTS "Admins can manage amortization plan" ON PianoAmmortamento;
CREATE POLICY "Admins can manage amortization plan" ON PianoAmmortamento
    FOR ALL
    USING (
        id_prestito IN (
            SELECT id_prestito FROM Prestiti 
            WHERE id_famiglia = get_current_user_family_id()
        ) AND
        EXISTS (
            SELECT 1 FROM Appartenenza_Famiglia 
            WHERE id_utente = current_setting('app.current_user_id', true)::INTEGER 
            AND ruolo = 'admin'
            AND id_famiglia = get_current_user_family_id()
        )
    );
