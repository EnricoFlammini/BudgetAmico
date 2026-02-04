-- Migration script to update account types from 'Corrente' to 'Conto Corrente'
-- This ensures consistency with the FOP matrix configuration

-- Backup first (optional, for safety)
-- CREATE TABLE Conti_backup AS SELECT * FROM Conti;

-- Update all accounts with tipo 'Corrente' to 'Conto Corrente'
UPDATE Conti SET tipo = 'Conto Corrente' WHERE tipo = 'Corrente';

-- Also update 'Investimento' to 'Investimenti' for FOP consistency (if needed)
UPDATE Conti SET tipo = 'Investimenti' WHERE tipo = 'Investimento';

-- Verify the changes
SELECT id_conto, tipo FROM Conti WHERE tipo IN ('Conto Corrente', 'Investimenti');
