-- ============================================================================
-- PERFORMANCE OPTIMIZATION: UNINDEXED FOREIGN KEYS
-- ============================================================================
-- Questo script crea indici per le chiavi esterne che non ne hanno uno,
-- risolvendo i warning "unindexed_foreign_keys" del linter di Supabase.

-- Appartenenza_Famiglia
CREATE INDEX IF NOT EXISTS idx_appartenenza_famiglia_id_famiglia ON public.Appartenenza_Famiglia(id_famiglia);

-- Budget
CREATE INDEX IF NOT EXISTS idx_budget_id_sottocategoria ON public.Budget(id_sottocategoria);

-- Carte
CREATE INDEX IF NOT EXISTS idx_carte_id_conto_contabile_condiviso ON public.Carte(id_conto_contabile_condiviso);
CREATE INDEX IF NOT EXISTS idx_carte_id_conto_contabile ON public.Carte(id_conto_contabile);
CREATE INDEX IF NOT EXISTS idx_carte_id_conto_riferimento_condiviso ON public.Carte(id_conto_riferimento_condiviso);
CREATE INDEX IF NOT EXISTS idx_carte_id_conto_riferimento ON public.Carte(id_conto_riferimento);
CREATE INDEX IF NOT EXISTS idx_carte_id_utente ON public.Carte(id_utente);

-- Conti
CREATE INDEX IF NOT EXISTS idx_conti_id_utente ON public.Conti(id_utente);

-- ContiCondivisi
CREATE INDEX IF NOT EXISTS idx_conticondivisi_id_famiglia ON public.ContiCondivisi(id_famiglia);

-- Immobili
CREATE INDEX IF NOT EXISTS idx_immobili_id_famiglia ON public.Immobili(id_famiglia);
CREATE INDEX IF NOT EXISTS idx_immobili_id_prestito_collegato ON public.Immobili(id_prestito_collegato);

-- Inviti
CREATE INDEX IF NOT EXISTS idx_inviti_id_famiglia ON public.Inviti(id_famiglia);

-- Obiettivi_Risparmio
CREATE INDEX IF NOT EXISTS idx_obiettivi_risparmio_id_famiglia ON public.Obiettivi_Risparmio(id_famiglia);

-- PartecipazioneContoCondiviso
CREATE INDEX IF NOT EXISTS idx_partecipazione_id_utente ON public.PartecipazioneContoCondiviso(id_utente);

-- Prestiti
CREATE INDEX IF NOT EXISTS idx_prestiti_id_categoria_pagamento ON public.Prestiti(id_categoria_pagamento_default);
CREATE INDEX IF NOT EXISTS idx_prestiti_id_conto_condiviso_pagamento ON public.Prestiti(id_conto_condiviso_pagamento_default);
CREATE INDEX IF NOT EXISTS idx_prestiti_id_conto_pagamento ON public.Prestiti(id_conto_pagamento_default);
CREATE INDEX IF NOT EXISTS idx_prestiti_id_famiglia ON public.Prestiti(id_famiglia);
CREATE INDEX IF NOT EXISTS idx_prestiti_id_sottocategoria_pagamento ON public.Prestiti(id_sottocategoria_pagamento_default);

-- QuoteImmobili
CREATE INDEX IF NOT EXISTS idx_quoteimmobili_id_utente ON public.QuoteImmobili(id_utente);

-- QuotePrestiti
CREATE INDEX IF NOT EXISTS idx_quoteprestiti_id_utente ON public.QuotePrestiti(id_utente);

-- Salvadanai
CREATE INDEX IF NOT EXISTS idx_salvadanai_id_asset ON public.Salvadanai(id_asset);
CREATE INDEX IF NOT EXISTS idx_salvadanai_id_conto_condiviso ON public.Salvadanai(id_conto_condiviso);
CREATE INDEX IF NOT EXISTS idx_salvadanai_id_conto ON public.Salvadanai(id_conto);
CREATE INDEX IF NOT EXISTS idx_salvadanai_id_famiglia ON public.Salvadanai(id_famiglia);
CREATE INDEX IF NOT EXISTS idx_salvadanai_id_obiettivo ON public.Salvadanai(id_obiettivo);

-- SpeseFisse
CREATE INDEX IF NOT EXISTS idx_spesefisse_id_carta ON public.SpeseFisse(id_carta);
CREATE INDEX IF NOT EXISTS idx_spesefisse_id_categoria ON public.SpeseFisse(id_categoria);
CREATE INDEX IF NOT EXISTS idx_spesefisse_id_conto_condiviso_addebito ON public.SpeseFisse(id_conto_condiviso_addebito);
CREATE INDEX IF NOT EXISTS idx_spesefisse_id_conto_personale_addebito ON public.SpeseFisse(id_conto_personale_addebito);
CREATE INDEX IF NOT EXISTS idx_spesefisse_id_famiglia ON public.SpeseFisse(id_famiglia);
CREATE INDEX IF NOT EXISTS idx_spesefisse_id_sottocategoria ON public.SpeseFisse(id_sottocategoria);

-- Storico_Asset
CREATE INDEX IF NOT EXISTS idx_storico_asset_id_conto ON public.Storico_Asset(id_conto);

-- Transazioni
CREATE INDEX IF NOT EXISTS idx_transazioni_id_carta ON public.Transazioni(id_carta);
CREATE INDEX IF NOT EXISTS idx_transazioni_id_conto ON public.Transazioni(id_conto);
CREATE INDEX IF NOT EXISTS idx_transazioni_id_sottocategoria ON public.Transazioni(id_sottocategoria);

-- TransazioniCondivise
CREATE INDEX IF NOT EXISTS idx_transazionicondivise_id_carta ON public.TransazioniCondivise(id_carta);
CREATE INDEX IF NOT EXISTS idx_transazionicondivise_id_conto_condiviso ON public.TransazioniCondivise(id_conto_condiviso);
CREATE INDEX IF NOT EXISTS idx_transazionicondivise_id_sottocategoria ON public.TransazioniCondivise(id_sottocategoria);
CREATE INDEX IF NOT EXISTS idx_transazionicondivise_id_utente_autore ON public.TransazioniCondivise(id_utente_autore);

-- Utenti
CREATE INDEX IF NOT EXISTS idx_utenti_id_conto_condiviso_default ON public.Utenti(id_conto_condiviso_default);
CREATE INDEX IF NOT EXISTS idx_utenti_id_conto_default ON public.Utenti(id_conto_default);
CREATE INDEX IF NOT EXISTS idx_utenti_id_carta_default ON public.Utenti(id_carta_default);
