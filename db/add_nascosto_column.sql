DO $$
BEGIN
    -- nascosto in Conti
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conti' AND column_name='nascosto') THEN
        ALTER TABLE Conti ADD COLUMN nascosto BOOLEAN DEFAULT FALSE;
    END IF;

END $$;
