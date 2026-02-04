# Budget Amico v0.47.05

<!-- Sostituisci con un URL a un'icona/logo se ne hai uno -->

<img width="500" height="500" alt="Budget Amico" src="https://github.com/user-attachments/assets/ed2e29d2-c8a4-4e95-82b0-c6b40e125179" />


> Il tuo assistente personale per la gestione delle finanze familiari. Semplice, sicuro, multipiattaforma. Web App in Python con framework Flet.

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
    -   **Tab Investimenti Dedicato**: Gestione completa e autonoma dei conti di investimento con:
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
pip install flet openpyxl pandas
```

**Dipendenze principali:**
- `flet` - Framework GUI (Web)
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

### Server Web Locale

Con l'ambiente virtuale attivato:

```bash
python main.py
```

L'applicazione avvierà un server web locale e aprirà automaticamente il browser all'indirizzo `http://localhost:8556`.

### Build per Mobile (Android/iOS)

Per creare un pacchetto installabile per dispositivi mobili (APK per Android o IPA per iOS), utilizza il comando `flet build` con un file dei requisiti (usa `requirements.txt` per l'app completa o crea un file ottimizzato):

**Android (APK):**
```bash
flet build apk --requirements requirements.txt
```
*L'APK generato si troverà nella cartella `build/apk`.*

**iOS (IPA):**
```bash
flet build ipa --requirements requirements.txt
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
│   ├── utils/                     # Utility e helper
│   ├── views/                     # Viste dell'applicazione
│   └── ...
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

## 📅 Changelog

Il changelog completo con la storia delle versioni è disponibile nel file [CHANGELOG.md](CHANGELOG.md).

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
