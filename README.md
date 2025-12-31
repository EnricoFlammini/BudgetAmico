# Budget Amico v0.30.00

<!-- Sostituisci con un URL a un'icona/logo se ne hai uno -->

<img width="500" height="500" alt="Budget Amico" src="https://github.com/user-attachments/assets/ed2e29d2-c8a4-4e95-82b0-c6b40e125179" />


**Budget Amico** è un'applicazione avanzata per la gestione delle finanze personali e familiari, sviluppata in Python con framework Flet.

---

## 📅 Changelog

### v0.30.00 (31/12/2025)
- **Web Layout**:
    - **Navigazione Semplificata**: Rimossi "Conti" e "Famiglia" per una navigazione più pulita (solo Home e Budget).
    - **Header Collassabile**: L'intera sezione superiore (Patrimonio Netto + Selezione Mese) è ora collassabile sulla versione Web per massimizzare lo spazio.
    - **Info Patrimonio**: I dettagli del patrimonio (Liquidità, Investimenti, ecc.) sono collassabili e nascosti di default su Web.
    - **Divisore Pro**: Nuovo strumento per la gestione delle spese di gruppo (Travel Spending), accessibile sia dalla dashboard che dalla pagina di login (senza account). Include calcolo debiti minimi e condivisione WhatsApp.

### v0.29.01 (30/12/2025)
- **HOTFIX BUG**: Risolto problema critico che impediva il corretto salvataggio dello storico budget (errore "NotNullViolation"), causando la visualizzazione errata dei limiti (tutti a 0) nel mese corrente.

### v0.29.00 (30/12/2025)
- **Web App**:
    - **Ottimizzazione Mobile**: La dashboard e la pagina Conti ora utilizzano un layout completamente responsivo per una migliore esperienza su smartphone e tablet.
    - **Pagina Famiglia**: Anche la scheda Famiglia è stata ottimizzata per dispositivi mobili.
    - **Investimenti**: Rimossa la scheda Investimenti dalla versione Web per semplificare l'interfaccia mobile.
- **Info**: Aggiunti link diretti alla Versione Web e al repository GitHub nel pannello Informazioni.

### v0.28.00 (30/12/2025)
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

L'eseguibile sarà disponibile in `dist\Budget Amico_0.26.00.exe`.
**Importante**: Assicurati che il file `.env` sia presente nella stessa cartella dell'eseguibile o configurato nel sistema target.

### Build per Mobile (Android/iOS)

Per creare un pacchetto installabile per dispositivi mobili (APK per Android o IPA per iOS), utilizza il comando `flet build` con il file dei requisiti specifico:

**Android (APK):**
```bash
flet build apk --requirements requirements_mobile.txt
```
*L'APK generato si troverà nella cartella `build/apk`.*

**iOS (IPA):**
```bash
flet build ipa --requirements requirements_mobile.txt
```
*Nota: Per compilare per iOS è necessario un Mac.*

**Importante**:
- Assicurati di avere installato l'SDK appropriato (Android SDK o Xcode).
- Potresti dover configurare le chiavi di firma per la distribuzione sugli store.

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
    - `pg8000` - Driver PostgreSQL pure-Python (compatibile mobile)
    - `python-dotenv` - Gestione configurazione
    - `pandas` e `openpyxl` - Esportazione dati
    - `cryptography` - Crittografia dati sensibili (Fernet)

---

## 📊 Novità Versione 0.28

### Pagina Budget Ridisegnata
-   **Nuova Logica Colori**: Semplificazione visiva con indicatori di stato più chiari (Verde: OK, Giallo: >100%, Rosso: >110%).
-   **Riepilogo Totale**: Nuova card "Budget Totale" che aggrega limiti e spese di tutte le categorie.
-   **Drilldown Categorie**: Cliccando su una categoria è ora possibile espandere/collassare la vista per mostrare le sottocategorie, mantenendo l'interfaccia pulita.

### Sidebar Collassabile
-   **Modalità Compatta**: La barra laterale è ora compressa di default per massimizzare lo spazio utile su schermo.
-   **Menu Toggle**: Nuovo pulsante nell'AppBar per espandere temporaneamente il menu e visualizzare le etichette di testo.
-   **Tooltip**: In modalità compatta, passando il mouse sulle icone viene mostrato il nome della sezione.

---

## 📊 Novità Versione 0.27

### Analisi Storica Avanzata
-   **Storico Esteso a 25 Anni**: È ora possibile visualizzare l'andamento storico degli asset fino a 25 anni (con opzioni 10y, 20y, 25y).
-   **Ottimizzazione Dati**: I dati salvati utilizzano una risoluzione ibrida (giornaliera recenti, mensile storici) per garantire velocità e leggerezza.
-   **Download Intelligente**: Il sistema riconosce la data di inizio trading (inception date) di ogni asset, evitando tentativi inutili di scaricare dati storici inesistenti.

### Ricerca Asset Potenziata
-   **Supporto ISIN Migliorato**: La ricerca ticker ora gestisce correttamente gli ISIN con o senza suffissi di borsa (es. `IT...` o `IT....MI`), verificandoli direttamente su Yahoo Finance se la ricerca standard fallisce.

### Analisi Monte Carlo
-   **Robustezza Migliorata**: Le simulazioni Monte Carlo ora utilizzano dati ricampionati su base mensile per garantire coerenza statistica anche su periodi lunghi e misti.

---

## 📊 Novità Versione 0.26

### Piani Ammortamento Personalizzati
-   **Importazione CSV / Inserimento Manuale**: È ora possibile caricare un piano di ammortamento personalizzato (o inserirlo manualmente) per ogni prestito.
-   **Calcoli Precisi**: Il debito residuo, la quota capitale e la quota interessi vengono calcolati direttamente dal piano caricato senza approssimazioni.
-   **Interfaccia Intelligente**:
    -   Pulsante rapido "Gestisci Piano Ammortamento" nel dialog del prestito.
    -   Protezione campi automatici: quando è attivo un piano, importi e date sono bloccati per garantire la coerenza dei dati.
    -   Visualizzazione dettagliata del residuo (Capitale + Interessi) in tutte le schede.

### Pagamenti Automatici Potenziati
-   **Rispetto del Piano**: L'addebito automatico mensile ora verifica se esiste una rata specifica in scadenza nel piano di ammortamento e utilizza l'importo esatto previsto.
-   **Aggiornamento Stato**: Il pagamento automatico segna automaticamente la rata come "Pagata" nel piano.

### Coerenza Patrimoniale
-   **Patrimonio Netto Reale**: I calcoli del patrimonio netto (Personale e Famiglia) ora integrano il debito residuo esatto derivante dai piani di ammortamento personalizzati.

### Export Livellato
-   **Permessi Export Differenziati**: 
    -   Gli utenti **Livello 2** possono esportare solo i propri dati personali e quelli condivisi.
    -   Gli utenti **Livello 3** non hanno accesso all'export.

### Gestione Utenti
-   **Pulizia Database**: Rimozione automatizzata di utenti di test e duplicati per mantenere l'integrità dei dati.

---

## 📊 Novità Versione 0.25

### Patrimonio Immobiliare Integrato
-   **Pagina Personale**: Nuova riga "Patrimonio Immobile" nel riepilogo totali, mostrando il valore netto (valore immobile - mutuo residuo) della quota personale dell'utente.
-   **Pagina Famiglia**: Nuova card riepilogo per Admin/Livello1 con: Patrimonio Totale Famiglia, Liquidità Totale, Investimenti Totali e Patrimonio Immobile Totale.
-   **Esclusione Nuda Proprietà**: Gli immobili contrassegnati come "Nuda Proprietà" sono automaticamente esclusi dai calcoli del patrimonio.
-   **Quote di Proprietà**: Il calcolo tiene conto delle percentuali di proprietà e delle quote mutuo per ogni membro della famiglia.

### Privacy Transazioni
-   **Nascondi Importo**: Nuova opzione "Nascondi importo in Famiglia" nel dialog di creazione/modifica transazione.
-   **Visualizzazione Riservata**: Le transazioni con importo nascosto mostrano "Riservato" invece dell'importo nella pagina Famiglia.
-   **Privacy Selettiva**: Ogni utente può decidere quali transazioni rendere visibili agli altri membri della famiglia.

### Calcolo Liquidità Migliorato
-   **Saldi Reali**: La liquidità ora viene calcolata come somma dei saldi reali dei conti (transazioni + rettifica), non più dalla sola somma delle transazioni.
-   **Pro-Quota Condivisi**: Per i conti condivisi, la liquidità personale è calcolata come saldo / numero partecipanti.
-   **Esclusione Corretta**: I conti di tipo Investimento, Fondo Pensione e Risparmio sono correttamente esclusi dalla liquidità.

---

## 📊 Novità Versione 0.24

### Gestione Conti Migliorata
-   **Nascondi Conti a Saldo Zero**: I conti con transazioni ma saldo zero possono ora essere nascosti invece che eliminati, mantenendo lo storico delle transazioni intatto.
-   **Nome Proprietario nei Giroconti**: Il dropdown destinazione nei giroconti mostra ora il nome del proprietario del conto tra parentesi (es. "BBVA (Roberta)").
-   **Esclusione Giroconti dalle Spese**: I trasferimenti tra conti (giroconti) sono ora esplicitamente esclusi dal calcolo delle spese totali mensili e annuali.

### Sicurezza e Crittografia
-   **Crittografia con Family Key**: I nomi dei conti personali vengono ora criptati con la chiave famiglia, permettendo la visibilità tra tutti i membri della famiglia.
-   **Decriptazione Migliorata**: Logica di fallback per decriptare dati legacy (criptati con master_key) mantenendo la retrocompatibilità.
-   **Migrazione Trasparente**: I conti rinominati vengono automaticamente ri-criptati con la nuova chiave famiglia.

---

## 📊 Novità Versione 0.23

### Manuali Utente Integrati
-   **Guida Rapida**: Nuovo manuale per i nuovi utenti con i primi passi essenziali (registrazione, creazione conti, prima transazione).
-   **Manuale Completo**: Documentazione dettagliata di tutte le funzionalità dell'applicazione.
-   **Accesso dall'App**: I manuali sono accessibili cliccando sul pulsante ℹ️ (Info) nella barra superiore.
-   **Formato HTML**: I manuali si aprono nel browser predefinito per una facile consultazione.

### Bug Fix
-   **Nomi Utenti Prestiti**: Corretto bug che non mostrava i nomi degli utenti nella sezione "Ripartizione Quote di Competenza" del dialog prestiti/mutui.

---

## 📊 Novità Versione 0.22

### Notifica Aggiornamenti Automatica
-   **Controllo Versione GitHub**: All'avvio, l'app controlla se è disponibile una nuova versione su GitHub Releases.
-   **Banner Aggiornamento**: Se disponibile un aggiornamento, appare un banner blu con pulsante "Scarica".
-   **Download Diretto**: Il pulsante apre il browser sulla pagina di download della nuova versione.

---

## 📊 Novità Versione 0.21

### Migrazione Driver Database
-   **Da psycopg2 a pg8000**: Migrazione al driver PostgreSQL pure-Python per compatibilità mobile.
-   **Connection Pool Custom**: Implementato pool di connessioni thread-safe per pg8000.
-   **DictCursor Wrapper**: Cursore personalizzato che restituisce dizionari invece di tuple.

### Preferiti Asset per Utente
-   **Preferiti Privati**: I ticker preferiti nel grafico storico sono ora salvati per singolo utente.
-   **Eliminazione Preferiti**: Aggiunto pulsante X rossa per rimuovere i preferiti dalla lista.

### Bug Fix
-   **Fix Commit Database**: Corretto bug che annullava le modifiche al database dopo il commit.
-   **Fix NoneType Error**: Aggiunto controllo null in `InvestimentiTab` per evitare errori.

---

## 📊 Novità Versione 0.20

### Ristrutturazione Livelli Utente
-   **Nuova Gerarchia Progressiva**: I livelli utente ora seguono una progressione lineare e intuitiva:
    | Livello | Accesso |
    |---------|---------|
    | **Livello 3** | Solo Dati Personali (ideale per bambini) |
    | **Livello 2** | + Investimenti, Prestiti, Immobili, Famiglia (riepilogo spese mensili) |
    | **Livello 1** | + Dettagli completi transazioni Famiglia |
    | **Admin** | + Gestione pannello Admin |
-   **Visibilità Tab Dinamica**: I tab Budget, Investimenti, Prestiti e Immobili sono nascosti per Livello 3.
-   **Tabella Riferimento Livelli**: Nuova tabella nel pannello Admin > Membri con i permessi per ogni livello.
-   **Descrizioni Aggiornate**: Dialog "Invita Membro" e "Modifica Ruolo" mostrano descrizioni chiare per ogni livello.

### Permessi Spese Fisse
-   **Controllo Accesso Conti**: Le azioni (modifica, elimina, paga) sulle spese fisse sono disabilitate se l'utente non ha accesso al conto associato.
-   **Dropdown Conti Filtrato**: Nel dialog spesa fissa, il dropdown mostra solo i conti dell'utente e quelli condivisi a cui ha accesso.

### Tab Famiglia per Livello 2
-   **Riepilogo Spese Mensili**: Gli utenti Livello 2 vedono entrate, spese totali e risparmio del mese invece del patrimonio dei membri.
-   **Filtro Mese**: Possibilità di selezionare il mese da visualizzare.

### Logging Opzionale
-   **Toggle Admin**: Nuovo switch in Admin > Backup/Export per abilitare/disabilitare il logging.
-   **Default Disabilitato**: Nessun file di log generato di default per risparmiare spazio.
-   **Handler Sicuro Windows**: Risolti errori di rotazione log su Windows.

---

## 📊 Novità Versione 0.19

### Ricerca Ticker con Autocomplete
-   **Nuovo Componente `TickerSearchField`**: Campo di ricerca intelligente che interroga Yahoo Finance in tempo reale.
-   **Filtro per Borsa**: Supporto per ricerca combinata nome + borsa (es. "Apple Milano", "Amazon XETRA").
-   **Integrazione Completa nei Dialog**:
    -   Dialog "Aggiungi Operazione" (compra/vendi asset)
    -   Dialog "Aggiungi Asset Esistente"
    -   Dialog "Modifica Asset"
    -   Tab "Andamento Storico" per ticker preferiti
-   **Compilazione Automatica Nome**: Selezionando un ticker dal dropdown, il nome dell'asset viene compilato automaticamente.
-   **Debounce Intelligente**: Ritardo di 500ms per evitare chiamate API eccessive durante la digitazione.

### Miglioramenti Grafici Storici
-   **Visualizzazione Descrizione Asset**: Ticker e descrizione ora mostrati su righe separate con tooltip per nomi lunghi.
-   **Preferiti Persistenti**: I ticker preferiti vengono salvati nel client storage e ripristinati all'avvio.

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
