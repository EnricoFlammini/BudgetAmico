-- Add password_algo column to Utenti table
-- Default to 'sha256' for existing users

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='password_algo') THEN
        ALTER TABLE Utenti ADD COLUMN password_algo VARCHAR(20) DEFAULT 'sha256';
    END IF;
END $$;
