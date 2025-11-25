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
    -   **Immobili**: Aggiungi i tuoi immobili per avere una visione completa del tuo patrimonio.
    -   **Fondi Pensione**: Monitora il valore dei tuoi fondi pensione.

-   **Gestione Familiare Avanzata**:
    -   Invita i membri della tua famiglia via email.
    -   Assegna ruoli diversi (`Admin`, `Livello 1`, `Livello 2`, `Livello 3`) per controllare l'accesso ai dati familiari.
    -   Visualizza le transazioni di tutti i membri della famiglia in un unico posto (per i ruoli autorizzati).

-   **Sincronizzazione e Backup**:
    -   **Sincronizzazione con Google Drive**: Utilizza il tuo account Google per sincronizzare il database dell'applicazione e usare Budget Amico su più dispositivi.
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
pip install flet flet-desktop google-api-python-client google-auth-httplib2 google-auth-oauthlib openpyxl pandas
```

**Dipendenze principali:**
- `flet` - Framework GUI
- `google-api-python-client` - API Google Drive e Gmail
- `google-auth-httplib2` e `google-auth-oauthlib` - Autenticazione Google
- `openpyxl` e `pandas` - Esportazione Excel
- `requests` - Chiamate HTTP per recupero prezzi asset (v0.10+)
- `python-dotenv` - Gestione variabili d'ambiente (opzionale)

---

## ⚙️ Configurazione

### Configurazione Google API (Opzionale)

Se desideri utilizzare la sincronizzazione con Google Drive:

1. Vai alla [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuovo progetto o selezionane uno esistente
3. Abilita le API:
   - Google Drive API
   - Gmail API
4. Crea le credenziali OAuth 2.0
5. Scarica il file `credentials.json` e posizionalo nella directory `Sviluppo/`

**Nota:** Il file `credentials.json` è già incluso nel `.gitignore` per motivi di sicurezza.

---

## ▶️ Esecuzione

### Modalità Sviluppo

Con l'ambiente virtuale attivato:

```bash
python main.py
```

L'applicazione si avvierà in una finestra desktop.

### Build dell'Eseguibile

Per creare un eseguibile standalone usando PyInstaller:

**Windows:**
```powershell
.\build.ps1
```

**Manuale:**
```bash
pyinstaller --name "Budget Amico" --windowed --onedir --clean --noconfirm --add-data "assets;assets" --add-data "credentials.json;." --icon "assets/icon.ico" --hidden-import=yfinance --hidden-import=python_dotenv main.py
```

L'eseguibile sarà disponibile in `dist\Budget Amico\Budget Amico.exe`.

**Note sulla Build:**
- Il modulo `python-dotenv` è opzionale nell'eseguibile (gestito con try/except)
- I prezzi degli asset vengono recuperati tramite chiamate HTTP dirette alle API Yahoo Finance
- Non sono richieste dipendenze complesse come `curl_cffi`

---

## 📁 Struttura del Progetto

```
BudgetAmico/
├── Sviluppo/
│   ├── main.py                    # Entry point dell'applicazione
│   ├── app_controller.py          # Controller principale e routing
│   ├── db/                        # Moduli database
│   │   ├── crea_database.py       # Setup e schema database
│   │   ├── gestione_db.py         # Operazioni CRUD
│   │   └── migration_manager.py   # Gestione migrazioni
│   ├── tabs/                      # Tab dell'interfaccia
│   │   ├── tab_conti.py
│   │   ├── tab_transazioni.py
│   │   ├── tab_budget.py
│   │   ├── tab_patrimonio.py
│   │   └── ...
│   ├── dialogs/                   # Dialog e modali
│   │   ├── dialog_aggiungi_conto.py
│   │   ├── dialog_aggiungi_transazione.py
│   │   └── ...
│   ├── views/                     # Viste principali
│   │   ├── login_view.py
│   │   ├── registrazione_view.py
│   │   └── home_view.py
│   ├── utils/                     # Utilità
│   │   ├── date_utils.py
│   │   └── export_utils.py
│   ├── google_auth_manager.py     # Gestione autenticazione Google
│   ├── google_drive_manager.py    # Gestione Google Drive
│   ├── assets/                    # Risorse (icone, immagini)
│   ├── .venv/                     # Ambiente virtuale (non versionato)
│   ├── .gitignore
│   ├── LICENSE
│   └── README.md
```

---

## 🛠️ Tecnologie Utilizzate

-   **Framework GUI**: [Flet](https://flet.dev/) - Framework Python per creare app multi-piattaforma
-   **Linguaggio**: Python 3.10+
-   **Database**: SQLite con gestione migrazioni automatiche
-   **API**: Google Drive API, Gmail API, Yahoo Finance API
-   **Librerie**:
    - `pandas` e `openpyxl` - Esportazione dati
    - `google-auth` - Autenticazione OAuth2
    - `requests` - Chiamate HTTP per recupero prezzi asset
    - `pyinstaller` - Build eseguibili

---

## 📊 Novità Versione 0.11

### Gestione Saldi e Admin
-   **Rettifica Saldo (Admin)**: Nuova funzionalità riservata agli amministratori per allineare il saldo dei conti (personali e condivisi) al valore reale, utile per correggere discrepanze senza dover inserire transazioni fittizie.
-   **Protezione Saldo Iniziale**: Il saldo iniziale dei conti non è più modificabile liberamente dopo la creazione. Eventuali correzioni devono passare tramite la funzione di rettifica.

### Miglioramenti Investimenti
-   **Data Aggiornamento Prezzi**: Visualizzazione chiara della data e ora dell'ultimo aggiornamento prezzi per ogni asset nel portafoglio.

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

### Database non trovato

Al primo avvio, l'applicazione creerà automaticamente il database `budget_amico.db`. Se riscontri problemi, elimina il file e riavvia l'applicazione.

### Problemi con Google Drive

Assicurati di aver configurato correttamente il file `credentials.json` e di aver abilitato le API necessarie nella Google Cloud Console.

---

## 📝 Licenza

Questo progetto è distribuito sotto licenza GPL-3.0. Vedi il file [LICENSE](LICENSE) per maggiori dettagli.

---

## ✍️ Autore

Sviluppato con ❤️ da **Enrico Flammini (Iscavar79)**.

---

## 📧 Contatti

Per domande, suggerimenti o segnalazioni di bug, apri una issue su GitHub.
