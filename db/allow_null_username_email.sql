DO $$
BEGIN
    -- Allow NULL for username
    ALTER TABLE Utenti ALTER COLUMN username DROP NOT NULL;
    
    -- Allow NULL for email
    ALTER TABLE Utenti ALTER COLUMN email DROP NOT NULL;
    
END $$;
