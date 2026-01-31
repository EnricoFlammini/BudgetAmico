DO $$
BEGIN
    -- failed_login_attempts
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='failed_login_attempts') THEN
        ALTER TABLE Utenti ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;
    END IF;

    -- lockout_until
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='lockout_until') THEN
        ALTER TABLE Utenti ADD COLUMN lockout_until TIMESTAMP WITH TIME ZONE;
    END IF;

    -- last_failed_login
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='last_failed_login') THEN
        ALTER TABLE Utenti ADD COLUMN last_failed_login TIMESTAMP WITH TIME ZONE;
    END IF;

    -- sospeso
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='sospeso') THEN
        ALTER TABLE Utenti ADD COLUMN sospeso BOOLEAN DEFAULT FALSE;
    END IF;

END $$;
