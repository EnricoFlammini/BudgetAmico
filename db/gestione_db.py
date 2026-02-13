"""
gestione_db.py — Re-export Facade (v0.51 Refactoring)

Questo file mantiene la compatibilità con tutto il codice che importa da db.gestione_db.
Il codice sorgente effettivo è in _gestione_db_monolith.py, ed è stato organizzato
logicamente nei seguenti moduli tematici nella directory db/:

  crypto_helpers.py       — Crittografia, system keys, funzioni condivise
  gestione_admin.py       — Admin, sicurezza, statistiche
  gestione_config.py      — Configurazioni, feature flags
  gestione_budget.py      — Budget, storico, analisi
  gestione_utenti.py      — Login, registrazione, profilo
  gestione_famiglie.py    — Famiglie, membri, ruoli
  gestione_categorie.py   — Categorie, sottocategorie
  gestione_conti.py       — Conti personali, condivisi
  gestione_inviti.py      — Inviti, token
  gestione_transazioni.py — Transazioni personali/condivise
  gestione_patrimonio.py  — Prestiti, immobili, fondi pensione
  gestione_investimenti.py — Asset, portafoglio, storico
  gestione_giroconti.py   — Trasferimenti tra conti
  gestione_export.py      — Backup, export dati
  gestione_spese_fisse.py — Spese fisse
  gestione_carte.py       — Carte credito/debito
  gestione_obiettivi.py   — Obiettivi, salvadanai
  gestione_contatti.py    — Rubrica contatti

MIGRAZIONE PROGRESSIVA:
  Per il nuovo codice, importa direttamente dal modulo specifico:
    from db.gestione_budget import ottieni_budget_famiglia
  invece di:
    from db.gestione_db import ottieni_budget_famiglia
"""

# Re-export completo dal monolite per compatibilità al 100%.
# I moduli tematici sono la versione organizzata dello stesso codice,
# pronti per la migrazione progressiva.
from db._gestione_db_monolith import *  # noqa: F401, F403
