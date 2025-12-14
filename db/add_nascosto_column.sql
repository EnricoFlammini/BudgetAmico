-- Migrazione: Aggiungere colonna nascosto alla tabella Conti
-- Eseguire su Supabase SQL Editor

ALTER TABLE Conti ADD COLUMN IF NOT EXISTS nascosto BOOLEAN DEFAULT FALSE;
