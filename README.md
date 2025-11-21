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
    -   **Portafogli di Investimento**: Traccia i tuoi investimenti, aggiungendo asset (azioni, ETF) e monitorando guadagni e perdite.
    -   **Prestiti e Mutui**: Gestisci i tuoi finanziamenti, tracciando l'importo residuo e le rate pagate.
    -   **Immobili**: Aggiungi i tuoi immobili per avere una visione completa del tuo patrimonio.
    -   **Fondi Pensione**: Monitora il valore dei tuoi fondi pensione.

-   **Gestione Familiare Avanzata**:
    -   Invita i membri della tua famiglia via email.
    -   Assegna ruoli diversi (`Admin`, `Livello 1`, `Livello 2`, `Livello 3`) per controllare l'accesso ai dati familiari.
    -   Visualizza le transazioni di tutti i membri della famiglia in un unico posto (per i ruoli autorizzati).
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

```bash
pyinstaller "Budget Amico.spec"
```

L'eseguibile sarà disponibile nella cartella `dist/`.

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
-   **API**: Google Drive API, Gmail API
-   **Librerie**:
    - `pandas` e `openpyxl` - Esportazione dati
    - `google-auth` - Autenticazione OAuth2
    - `pyinstaller` - Build eseguibili

---

## 🐛 Risoluzione Problemi

### ModuleNotFoundError

Se ricevi errori di moduli mancanti, assicurati di:
1. Aver attivato l'ambiente virtuale (`.venv`)
2. Aver installato tutte le dipendenze con `pip install`

### Database non trovato

Al primo avvio, l'applicazione creerà automaticamente il database `budget_familiare.db`. Se riscontri problemi, elimina il file e riavvia l'applicazione.

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
