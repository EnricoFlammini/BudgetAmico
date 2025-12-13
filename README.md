# Budget Amico

<!-- Sostituisci con un URL a un'icona/logo se ne hai uno -->

<img width="500" height="500" alt="Budget Amico" src="https://github.com/user-attachments/assets/ed2e29d2-c8a4-4e95-82b0-c6b40e125179" />


**La tua app desktop per la gestione del budget personale e familiare, semplice e potente.**

Budget Amico è un'applicazione cross-platform costruita con Python e Flet che ti aiuta a tenere traccia delle tue finanze, a monitorare le spese, a gestire i budget e a pianificare il tuo futuro finanziario, da solo o con la tua famiglia.

---

## ✨ Funzionalità Principali

-   **Gestione Conti Completa**:
    -   Crea e gestisci conti personali (Correnti, Risparmio, Contanti, ecc.).
    -   Crea e gestisci conti condivisi con i membri della famiglia, con logica di partecipazione personalizzabile.

-   **Tracciamento Transazioni**:
    -   Registra entrate e uscite in modo rapido e intuitivo.
    -   Categorizza ogni transazione con categorie e sottocategorie personalizzabili per un'analisi dettagliata.
    -   Visualizza lo storico delle transazioni filtrato per mese.

-   **Budget Mensile**:
    -   Imposta limiti di spesa mensili per ogni sottocategoria.
    -   Monitora l'andamento delle spese con barre di progresso chiare e intuitive.

-   **Patrimonio a 360°**:
    -   **Dashboard Riepilogativa**: Tieni sotto controllo il tuo patrimonio netto personale e quello aggregato di tutta la famiglia.
    -   **Tab Investimenti Dedicato** (v0.10): Gestione completa e autonoma dei conti di investimento con:
        -   Creazione, modifica ed eliminazione conti investimento
        -   Visualizzazione unificata di tutti i portafogli
        -   Sincronizzazione automatica prezzi asset tramite yfinance
        -   Statistiche aggregate (valore totale e gain/loss)
    -   **Portafogli di Investimento**: Traccia i tuoi investimenti, aggiungendo asset (azioni, ETF) e monitorando guadagni e perdite.
    -   **Prestiti e Mutui**: Gestisci i tuoi finanziamenti, tracciando l'importo residuo e le rate pagate.
    -   **Immobili**: Aggiungi i tuoi immobili per avere una visione completa del tuo patrimonio. Gestione della **Nuda Proprietà** con evidenziazione visiva ed esclusione dai totali patrimoniali disponibili.
    -   **Fondi Pensione**: Monitora il valore dei tuoi fondi pensione.

-   **Gestione Familiare Avanzata**:
    -   Invita i membri della tua famiglia via email.
    -   Assegna ruoli diversi (`Admin`, `Livello 1`, `Livello 2`, `Livello 3`) per controllare l'accesso ai dati familiari.
    -   Visualizza le transazioni di tutti i membri della famiglia in un unico posto (per i ruoli autorizzati).

-   **Sincronizzazione e Backup**:
    -   **Backup e Ripristino Locale**: Crea backup manuali del tuo database e ripristinali in qualsiasi momento.

-   **Automazioni**:
    -   Gestione automatica delle **spese fisse** mensili.
    -   Pagamento automatico delle **rate dei prestiti** alla data di scadenza.

-   **Esportazione Dati**:
    -   Esporta i riepiloghi dei conti, i dettagli dei portafogli e lo storico delle transazioni in formato Excel per analisi più approfondite.

---

## 📋 Prerequisiti

Prima di iniziare, assicurati di avere installato:

-   **Python 3.10 o superiore** ([Download Python](https://www.python.org/downloads/))
-   **Git** (opzionale, per clonare il repository)

---

## 🚀 Installazione

### 1. Clona il Repository

```bash
git clone https://github.com/tuousername/budget-amico.git
cd budget-amico/Sviluppo
```

### 2. Crea un Ambiente Virtuale

È fortemente consigliato utilizzare un ambiente virtuale per isolare le dipendenze del progetto:

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Installa le Dipendenze

Con l'ambiente virtuale attivato, installa tutte le dipendenze necessarie:

**Opzione 1 - Usando requirements.txt (consigliato):**
```bash
pip install -r requirements.txt
```

**Opzione 2 - Installazione manuale:**
```bash
pip install flet flet-desktop openpyxl pandas
```

**Dipendenze principali:**
- `flet` - Framework GUI
- `openpyxl` e `pandas` - Esportazione Excel
- `requests` - Chiamate HTTP per recupero prezzi asset (v0.10+)
- `python-dotenv` - Gestione variabili d'ambiente (opzionale)

---

## ⚙️ Configurazione

### 1. Database (Obbligatorio)

Questa versione utilizza **PostgreSQL** (testato su Supabase, ma compatibile con qualsiasi provider Postgres).

1. Crea un file `.env` nella cartella `Sviluppo/` (puoi copiare un eventuale `.env.example`).
2. Aggiungi la stringa di connessione al tuo database:

```env
SUPABASE_DB_URL=postgresql://postgres:password@db.supabase.co:5432/postgres
SERVER_SECRET_KEY=la_tua_chiave_segreta_molto_lunga_e_casuale
```

**Nota**: `SERVER_SECRET_KEY` è fondamentale per il recupero password e la visibilità dei nomi in famiglia. Generane una sicura (es. 32-64 caratteri casuali).

L'applicazione gestirà automaticamente la creazione delle tabelle al primo avvio se non esistono.

---

## ▶️ Esecuzione

### Modalità Sviluppo

Con l'ambiente virtuale attivato:

```bash
python main.py
```

L'applicazione si avvierà in una finestra desktop e tenterà la connessione al database configurato nel `.env`.

### Build dell'Eseguibile

Per creare un eseguibile standalone usando PyInstaller:

**Windows:**
```powershell
.\build.ps1
```

**Manuale:**
```bash
pyinstaller --name "Budget Amico" --windowed --onedir --clean --noconfirm --add-data "assets;assets" --icon "assets/icon.ico" --hidden-import=yfinance --hidden-import=python_dotenv main.py
```

L'eseguibile sarà disponibile in `dist\Budget Amico\Budget Amico.exe`.
**Importante**: Assicurati che il file `.env` sia presente nella stessa cartella dell'eseguibile o configurato nel sistema target.

---

## 📁 Struttura del Progetto

```
BudgetAmico/
├── Sviluppo/
│   ├── main.py                    # Entry point dell'applicazione
│   ├── .env                       # Variabili d'ambiente (DB URL)
│   ├── app_controller.py          # Controller principale e routing
│   ├── db/                        # Moduli database
│   │   ├── supabase_manager.py    # Gestione connessione PostgreSQL
│   │   ├── gestione_db.py         # Operazioni CRUD
│   │   └── ...
│   ├── tabs/                      # Tab dell'interfaccia
... (resto della struttura)
```

---

## 🛠️ Tecnologie Utilizzate

-   **Framework GUI**: [Flet](https://flet.dev/) - Framework Python per creare app multi-piattaforma
-   **Linguaggio**: Python 3.10+
-   **Database**: PostgreSQL su Supabase (sostituisce SQLite)
-   **API**: Yahoo Finance API per prezzi asset
-   **Librerie**:
    - `psycopg2` - Connessione PostgreSQL
    - `python-dotenv` - Gestione configurazione
    - `pandas` e `openpyxl` - Esportazione dati
    - `cryptography` - Crittografia dati sensibili (Fernet)

---

## 📊 Novità Versione 0.18.01

### Miglioramenti Gestione Utenti
-   **Soft Delete Utenti**: La rimozione di un membro ora disabilita l'account invece di eliminarlo, preservando tutti i dati storici (transazioni, nomi per riferimento).
-   **Pulsante "Rimanda Credenziali"**: Nuovo pulsante nella gestione membri per inviare nuove credenziali di accesso via email.

### Correzioni Bug
-   **Spese Fisse Automatiche**: Corretto bug che registrava le transazioni con la categoria sbagliata invece della sottocategoria.
-   **Conti Condivisi Criptati**: Risolto problema di visualizzazione nomi criptati per conti creati da altri utenti autorizzati.
-   **Dialog Conto Condiviso**: Risolto errore "Column Control must be added to page first".
-   **Quote Immobili**: I nomi dei membri sono ora visibili correttamente nel dialog di ripartizione quote.
-   **SnackBar Messaggi**: Migrazione a `page.open()` per garantire la visualizzazione corretta dei messaggi di conferma.

### Logging e Diagnostica
-   **Logging Login**: Tracciamento dettagliato dell'inizio sessione con stato master key e forza cambio password.
-   **Pulsante Chiusura App**: Nuovo pulsante nell'AppBar per chiudere l'applicazione con log di chiusura.

## 📊 Novità Versione 0.18

### Performance e Caching
-   **Sistema Cache Stale-While-Revalidate**: I dati (categorie, sottocategorie) vengono ora memorizzati localmente in `%APPDATA%\BudgetAmico\cache.json` per un avvio quasi istantaneo.
-   **Lazy Loading Tab**: All'avvio l'app carica solo la tab visibile, le altre vengono caricate on-demand quando l'utente ci clicca.
-   **Invalidazione Automatica Cache**: La cache viene invalidata automaticamente dopo ogni operazione di scrittura (aggiunta, modifica, eliminazione di categorie/sottocategorie).
-   **Pulsante Refresh**: Nuovo pulsante 🔄 nell'AppBar per forzare l'aggiornamento manuale di tutti i dati.

### Stabilità UI
-   **Risolto "Rettangolo Grigio"**: Eliminato definitivamente il problema del rettangolo grigio che appariva durante la chiusura dei dialog.
-   **Dialoghi Moderni**: Migrazione dei dialog a `page.open()`/`page.close()` per una gestione più affidabile.
-   **Fix NoneType Errors**: Corretti errori in `subtab_budget_manager.py` relativi a riferimenti pagina nulli.

## 📊 Novità Versione 0.17

### Stabilità, Sicurezza e Logging
-   **Logging Completo**: Implementazione di un sistema di logging rotativo (conservazione 48h) in `%APPDATA%\BudgetAmico\logs`. Tracciamento dettagliato di errori, operazioni critiche e flusso UI per facilitare il debug.
-   **Database Cleanup**: Risolto un bug critico negli script di pulizia database che causava errori di decrittazione (`InvalidToken`) dopo la ri-registrazione utente.
-   **Row Level Security (RLS)**: Abilitata e configurata la sicurezza a livello di riga su tutte le tabelle critiche, incluse `QuoteImmobili` e `QuotePrestiti`, garantendo che gli utenti accedano solo ai dati della propria famiglia.
-   **UI Debugging**: Aggiunti strumenti diagnostici per monitorare il ciclo di vita degli overlay di caricamento e risolvere problemi di interfaccia (es. "rettangolo grigio").

### Sicurezza SMTP e Inviti
-   **SMTP per Famiglia**: Ogni famiglia ha ora la propria configurazione SMTP, criptata con la chiave server per permettere il recupero password senza contesto utente.
-   **Invito Membri Asincrono**: L'invio email per l'invito membri ora avviene in background, il dialog si chiude immediatamente.
-   **Chiavi Complete per Utenti Invitati**: Gli utenti invitati ora ricevono correttamente `encrypted_master_key_recovery` e `encrypted_master_key_backup` per il recupero password.
-   **Privacy Dati Utente**: I campi legacy `email` e `username` ora sono `NULL` nel database - usiamo solo i campi criptati `*_bindex` e `*_enc`.

### UI/UX
-   **Spinner Uniformati**: Stile inline leggero (cerchio blu) per tutti gli spinner di caricamento.
-   **Feedback Pulsanti**: Disabilitazione pulsanti durante operazioni critiche (login, registrazione, recupero password, salvataggio SMTP) per prevenire click multipli.
-   **Chiusura Dialog Corretta**: I dialog (invito membri, modifica ruolo) ora si chiudono correttamente in tutti i percorsi usando `page.close()`.

## 📊 Novità Versione 0.16

### Miglioramenti Tecnici e Qualità del Codice
-   **Type Hinting Completo**: Estesa la copertura dei type hints a tutte le funzioni critiche del database per una maggiore robustezza e prevenzione bug.
-   **Refactoring Codebase**: Rimozione di funzioni duplicate e codice legacy (es. vecchie implementazioni di `registra_utente`).
-   **Documentazione**: Potenziata la documentazione inline per le funzioni di gestione database, sicurezza e budget.
-   **Verifica Automatica**: Introduzione di script di verifica per garantire la coerenza delle firme delle funzioni.

## 📊 Novità Versione 0.15

### Sicurezza e Privacy (Major Update)
-   **Blind Indexing**: Username ed Email sono ora salvati in modo cifrato (non leggibili in chiaro sul DB) ma ricercabili tramite hash sicuri, garantendo massima privacy anche in caso di accesso non autorizzato al DB.
-   **Architettura Server Key**: Introdotta una chiave di sistema (`SERVER_SECRET_KEY`) per gestire funzioni privilegiate come il **Recupero Password** e la **Visibilità Nomi Famiglia** senza compromettere la crittografia End-to-End dei dati personali.
-   **Recupero Password Sicuro**: Il reset della password via email ora ri-cripta correttamente le chiavi di sicurezza, prevenendo la perdita dei dati storici.
-   **Inviti Sicuri**: Corretto il flusso di invito per garantire che i nuovi membri vengano creati immediatamente con gli standard di sicurezza (Blind Index) attivi.

## 📊 Novità Versione 0.14

### Analisi Budget Avanzata
-   **Nuova Dashboard Analisi**: Pagina completamente ridisegnata con doppia vista (Mensile e Annuale).
-   **Metriche di Dettaglio**:
    -   Visualizzazione chiara di Entrate, Spese, Budget allocato e Risparmio effettivo.
    -   Calcolo del "Delta" (Budget - Spese) per monitorare lo scostamento.
-   **Logica Annuale Intelligente**:
    -   Medie calcolate sui soli "mesi attivi" (periodi con spese registrate) per una stima più realistica.
    -   Confronto automatico con l'anno precedente solo se presenti dati storici.
-   **Grafici Interattivi**: Nuovi grafici a torta con logica dinamica per visualizzare la ripartizione del budget o delle entrate.
-   **Prestazioni Ottimizzate**: Caricamento asincrono dei dati per i tab "Admin" e "Impostazioni" per un'esperienza utente fluida e reattiva senza blocchi dell'interfaccia.
-   **Gestione Nuda Proprietà**: Possibilità di contrassegnare gli immobili come "Nuda proprietà", escludendoli dai calcoli del patrimonio netto disponibile ma mantenendoli nell'inventario.
-   **Privacy e Sicurezza**:
    -   Risolti problemi di visibilità dei dati familiari crittografati.
    -   Migliorata la gestione del pool di connessioni database per prevenire errori sotto carico.

## 📊 Novità Versione 0.12

### Migrazione a PostgreSQL/Supabase
-   **Database Cloud**: Migrazione completa da SQLite a PostgreSQL su Supabase
-   **Crittografia End-to-End**: Tutti i dati sensibili (nomi conti, importi, transazioni) sono crittografati con chiave per famiglia
-   **Multi-dispositivo**: Accesso sicuro ai dati da qualsiasi dispositivo

### Miglioramenti UI/UX
-   **Stili Centralizzati**: Layout uniformato su tutte le pagine con `AppStyles.section_header()` e `PageConstants`
-   **Spinner di Caricamento**: Feedback visivo durante il cambio pagina e operazioni lunghe

### Gestione Famiglia
-   **Sistema Inviti via Email**: Invita nuovi membri con credenziali temporanee
-   **Configurazione SMTP**: Impostazioni email configurabili dal pannello admin
-   **Export Dati Famiglia**: Backup della chiave famiglia e configurazioni

---

## 📊 Novità Versione 0.11

### Gestione Saldi e Admin
-   **Rettifica Saldo (Admin)**: Nuova funzionalità riservata agli amministratori per allineare il saldo dei conti (personali e condivisi) al valore reale.
-   **Protezione Saldo Iniziale**: Il saldo iniziale dei conti non è più modificabile liberamente dopo la creazione.

### Miglioramenti Investimenti
-   **Data Aggiornamento Prezzi**: Visualizzazione chiara della data e ora dell'ultimo aggiornamento prezzi.

---

## 📊 Novità Versione 0.10

### Tab Investimenti Autonomo

La versione 0.10 introduce un tab dedicato alla gestione degli investimenti:

-   **Separazione Completa**: I conti di tipo "Investimento" sono ora gestiti esclusivamente nel tab "Investimenti", separati dai conti personali
-   **Gestione Autonoma**: Creazione, modifica ed eliminazione conti investimento direttamente dal tab
-   **Sincronizzazione Prezzi**: Recupero automatico prezzi asset tramite API Yahoo Finance
    -   Implementazione con chiamate HTTP dirette (senza dipendenze esterne complesse)
    -   Sincronizzazione singola per ogni asset
    -   Sincronizzazione globale per tutti gli asset
    -   Compatibile con PyInstaller per eseguibili standalone
-   **Vista Unificata**: Tutti i portafogli visibili in un'unica schermata con statistiche aggregate
-   **Gestione Errori**: Supporto per ticker internazionali con suffissi di mercato (es. `.MI`, `.L`, `.DE`)

---

## 🐛 Risoluzione Problemi

### ModuleNotFoundError

Se ricevi errori di moduli mancanti, assicurati di:
1. Aver attivato l'ambiente virtuale (`.venv`)
2. Aver installato tutte le dipendenze con `pip install`

### Errori di Connessione Database

Assicurati che:
1. Il file `.env` esista e contenga `SUPABASE_DB_URL`.
2. La stringa di connessione sia corretta.
3. Il firewall non blocchi la porta 5432.

---

## 📝 Licenza

Questo progetto è distribuito sotto licenza GPL-3.0. Vedi il file [LICENSE](LICENSE) per maggiori dettagli.

---

## ✍️ Autore

Sviluppato con ❤️ da **Enrico Flammini (Iscavar79)**.

---

## 📧 Contatti

Per domande, suggerimenti o segnalazioni di bug, apri una issue su GitHub.
