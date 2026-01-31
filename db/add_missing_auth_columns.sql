DO $$
BEGIN
    -- salt
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='salt') THEN
        ALTER TABLE Utenti ADD COLUMN salt TEXT;
    END IF;

    -- encrypted_master_key
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='encrypted_master_key') THEN
        ALTER TABLE Utenti ADD COLUMN encrypted_master_key TEXT;
    END IF;

    -- recovery_key_hash
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='recovery_key_hash') THEN
        ALTER TABLE Utenti ADD COLUMN recovery_key_hash TEXT;
    END IF;

    -- encrypted_master_key_recovery
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='encrypted_master_key_recovery') THEN
        ALTER TABLE Utenti ADD COLUMN encrypted_master_key_recovery TEXT;
    END IF;

    -- encrypted_master_key_backup
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='encrypted_master_key_backup') THEN
        ALTER TABLE Utenti ADD COLUMN encrypted_master_key_backup TEXT;
    END IF;

    -- username_bindex
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='username_bindex') THEN
        ALTER TABLE Utenti ADD COLUMN username_bindex TEXT;
    END IF;

    -- email_bindex
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='email_bindex') THEN
        ALTER TABLE Utenti ADD COLUMN email_bindex TEXT;
    END IF;

    -- username_enc
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='username_enc') THEN
        ALTER TABLE Utenti ADD COLUMN username_enc TEXT;
    END IF;

    -- email_enc
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='email_enc') THEN
        ALTER TABLE Utenti ADD COLUMN email_enc TEXT;
    END IF;

    -- nome_enc_server
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='nome_enc_server') THEN
        ALTER TABLE Utenti ADD COLUMN nome_enc_server TEXT;
    END IF;

    -- cognome_enc_server
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='cognome_enc_server') THEN
        ALTER TABLE Utenti ADD COLUMN cognome_enc_server TEXT;
    END IF;

    -- password_algo (Già aggiunto ma per sicurezza)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='utenti' AND column_name='password_algo') THEN
        ALTER TABLE Utenti ADD COLUMN password_algo VARCHAR(20) DEFAULT 'sha256';
    END IF;

END $$;
