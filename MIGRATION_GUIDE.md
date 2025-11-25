# Guida alla Migrazione a Supabase

## Panoramica

Questa guida ti aiuterà a migrare la tua installazione di Budget Amico da SQLite locale + Google Drive a Supabase PostgreSQL cloud.

**Tempo stimato**: 15-20 minuti  
**Difficoltà**: Media  
**Requisiti**: Account Supabase (gratuito)

---

## ⚠️ Importante: Backup dei Dati

Prima di iniziare, **crea un backup** del tuo database:

1. Apri Budget Amico
2. Vai su **Impostazioni** → **Backup e Ripristino**
3. Clicca su **Backup Dati**
4. Salva il file in un luogo sicuro

---

## Fase 1: Creazione Progetto Supabase

### 1.1 Registrazione

1. Vai su [https://supabase.com](https://supabase.com)
2. Clicca su **Start your project**
3. Registrati con email o GitHub (gratuito)

### 1.2 Creazione Progetto

1. Dalla dashboard, clicca su **New project**
2. Compila i campi:
   - **Name**: `budget-amico` (o nome a tua scelta)
   - **Database Password**: Scegli una password sicura e **salvala**
   - **Region**: Scegli la regione più vicina (es. `Europe West (Frankfurt)`)
   - **Pricing Plan**: Seleziona **Free** (sufficiente per uso personale)
3. Clicca su **Create new project**
4. Attendi 1-2 minuti per la creazione del progetto

### 1.3 Ottenere l'URL di Connessione

1. Nel tuo progetto, vai su **Settings** (icona ingranaggio) → **Database**
2. Scorri fino a **Connection string**
3. Seleziona la tab **URI**
4. Copia l'URL che inizia con `postgresql://postgres:[YOUR-PASSWORD]@...`
5. **Sostituisci** `[YOUR-PASSWORD]` con la password che hai scelto al punto 1.2

Esempio:
```
postgresql://postgres:MiaPasswordSicura123@db.abcdefghijk.supabase.co:5432/postgres
```

---

## Fase 2: Configurazione Locale

### 2.1 Aggiornamento Applicazione

1. Scarica l'ultima versione di Budget Amico con supporto Supabase
2. Estrai i file nella cartella di installazione

### 2.2 Configurazione File .env

1. Nella cartella `Sviluppo`, crea un file chiamato `.env` (se non esiste)
2. Apri il file con un editor di testo
3. Aggiungi la seguente riga, sostituendo con il tuo URL:

```env
SUPABASE_DB_URL=postgresql://postgres:TuaPassword@db.xyz.supabase.co:5432/postgres
```

4. Salva il file

### 2.3 Installazione Dipendenze

Apri PowerShell nella cartella `Sviluppo` ed esegui:

```powershell
# Attiva l'ambiente virtuale
.\.venv\Scripts\activate

# Installa le nuove dipendenze
pip install -r requirements.txt
```

---

## Fase 3: Migrazione Dati

### 3.1 Test Connessione

Prima di migrare, verifica che la connessione funzioni:

```powershell
python tests\test_supabase_connection.py
```

Se vedi `✅ CONNESSIONE RIUSCITA!`, puoi procedere.

### 3.2 Esecuzione Migrazione

```powershell
python db\migrazione_postgres.py
```

Lo script:
1. Legge il database SQLite locale
2. Crea tutte le tabelle su Supabase
3. Copia tutti i dati
4. Verifica l'integrità

**Tempo stimato**: 1-5 minuti (dipende dalla quantità di dati)

### 3.3 Verifica Migrazione

Alla fine, lo script mostrerà un riepilogo:
```
Migrazione completata con successo!
Copiati X record in Famiglie
Copiati Y record in Utenti
...
```

Puoi anche verificare su Supabase:
1. Vai su **Table Editor** nella dashboard
2. Dovresti vedere tutte le tabelle (Famiglie, Utenti, Conti, ecc.)
3. Clicca su una tabella per vedere i dati migrati

---

## Fase 4: Configurazione Row Level Security

### 4.1 Esecuzione Script RLS

1. Nella dashboard Supabase, vai su **SQL Editor**
2. Clicca su **New query**
3. Apri il file `db\setup_rls_policies.sql` dal tuo computer
4. Copia tutto il contenuto
5. Incollalo nell'editor SQL di Supabase
6. Clicca su **Run** (o premi `Ctrl+Enter`)

Dovresti vedere: `Success. No rows returned`

### 4.2 Verifica RLS

1. Vai su **Authentication** → **Policies**
2. Dovresti vedere le policy create per ogni tabella
3. Verifica che RLS sia abilitato (icona scudo verde)

---

## Fase 5: Primo Avvio

### 5.1 Avvio Applicazione

```powershell
python main.py
```

### 5.2 Login

1. Usa le stesse credenziali di prima (username/email e password)
2. L'applicazione ora si connette a Supabase invece che al database locale
3. Dovresti vedere tutti i tuoi dati come prima

### 5.3 Verifica Funzionalità

Testa le funzionalità principali:
- ✅ Visualizzazione conti e saldi
- ✅ Creazione nuova transazione
- ✅ Visualizzazione budget
- ✅ Gestione categorie (se admin)

---

## Fase 6: Pulizia (Opzionale)

Dopo aver verificato che tutto funzioni:

### 6.1 Rimozione File Google Drive

Puoi eliminare:
- `credentials.json` (se presente)
- `token.pickle` (se presente)
- `google_auth_manager.py`
- `google_drive_manager.py`

### 6.2 Conservazione Backup

**NON eliminare** il backup SQLite creato all'inizio! Conservalo per sicurezza.

---

## Risoluzione Problemi

### Errore: "SUPABASE_DB_URL non trovato"

**Soluzione**: Verifica che il file `.env` sia nella cartella `Sviluppo` e contenga la riga corretta.

### Errore: "Connection refused" o "Timeout"

**Possibili cause**:
1. Password errata nell'URL
2. Firewall che blocca la connessione
3. Progetto Supabase in pausa (riattivalo dalla dashboard)

**Soluzione**: 
- Verifica l'URL di connessione
- Controlla il firewall
- Riavvia il progetto Supabase

### Errore durante la migrazione

**Soluzione**:
1. Verifica che il database SQLite esista in `%APPDATA%\BudgetAmico\budget_amico.db`
2. Controlla che Supabase sia vuoto (nessuna tabella esistente)
3. Se necessario, elimina le tabelle su Supabase e riprova

### I dati non sono visibili dopo il login

**Possibili cause**:
1. RLS policies non configurate correttamente
2. Contesto utente non impostato

**Soluzione**:
1. Riesegui lo script `setup_rls_policies.sql`
2. Verifica i log dell'applicazione per errori

---

## Vantaggi della Nuova Architettura

✅ **Sincronizzazione automatica**: I dati sono sempre aggiornati  
✅ **Multi-dispositivo**: Usa Budget Amico su più computer  
✅ **Backup automatici**: Supabase fa backup giornalieri  
✅ **Nessuna configurazione Google**: Non serve più Google Drive  
✅ **Più veloce**: Database cloud ottimizzato  

---

## Supporto

Se incontri problemi:

1. Controlla i log dell'applicazione
2. Esegui `python tests\test_supabase_connection.py` per diagnostica
3. Verifica la documentazione Supabase: [https://supabase.com/docs](https://supabase.com/docs)
4. Apri una issue su GitHub con i dettagli dell'errore

---

## Rollback (Tornare a SQLite)

Se vuoi tornare alla versione precedente:

1. Ripristina il backup SQLite creato all'inizio
2. Usa la versione precedente di Budget Amico (senza Supabase)
3. I tuoi dati locali saranno ripristinati

**Nota**: Le modifiche fatte dopo la migrazione non saranno presenti nel backup locale.
