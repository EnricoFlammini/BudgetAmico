-- SCRIPT DI CONSOLIDAMENTO E SICUREZZA PRODUZIONE
-- BudgetAmico v0.53

-- 1. INDICI DI INTEGRITÀ PER CONFIGURAZIONI UTENTE
-- Necessario per supportare l'isolamento dei dati utente tramite prefixing "user:{id}:*"
CREATE UNIQUE INDEX IF NOT EXISTS idx_configurazioni_user_null_famiglia 
ON Configurazioni (chiave) 
WHERE id_famiglia IS NULL;

-- 2. ABILITAZIONE RLS (ROW LEVEL SECURITY)
-- Nota: Richiede configurazione manuale su Supabase Dashbord per le policy specifiche,
-- ma l'abilitazione della tabella è il primo passo.
ALTER TABLE Utenti ENABLE ROW LEVEL SECURITY;
ALTER TABLE Famiglie ENABLE ROW LEVEL SECURITY;
ALTER TABLE Conti ENABLE ROW LEVEL SECURITY;
ALTER TABLE Transazioni ENABLE ROW LEVEL SECURITY;
ALTER TABLE Configurazioni ENABLE ROW LEVEL SECURITY;

-- 3. VINCOLI DI INTEGRITÀ ADDIZIONALI (Esempio: non permettere importi nulli o descrizioni vuote)
ALTER TABLE Transazioni ADD CONSTRAINT chk_importo_not_null CHECK (importo IS NOT NULL);
ALTER TABLE Transazioni ADD CONSTRAINT chk_descriz_not_empty CHECK (LENGTH(descrizione) > 0);

-- 4. OTTIMIZZAZIONE PERFORMANCE (INDICI)
CREATE INDEX IF NOT EXISTS idx_transazioni_data ON Transazioni(data);
CREATE INDEX IF NOT EXISTS idx_transazioni_conto ON Transazioni(id_conto);
CREATE INDEX IF NOT EXISTS idx_trans_condivise_data ON TransazioniCondivise(data);

-- 5. PULIZIA DATI ORFANI (Opzionale, cautelativo)
-- Se ON DELETE CASCADE non è stato impostato ovunque
-- DELETE FROM Asset WHERE id_conto NOT IN (SELECT id_conto FROM Conti);
