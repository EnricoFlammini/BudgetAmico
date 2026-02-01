DO $$
BEGIN
    -- chiave_famiglia_criptata
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appartenenza_famiglia' AND column_name='chiave_famiglia_criptata') THEN
        ALTER TABLE Appartenenza_Famiglia ADD COLUMN chiave_famiglia_criptata TEXT;
    END IF;

END $$;
