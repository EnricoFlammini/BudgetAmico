# Istruzioni per il Backup Automatico su Server Linux

Questa guida spiega come configurare il backup automatico del database Supabase sul tuo server Linux casalingo.

## 0. Prerequisiti

Sul server Linux, assicurati di avere Python 3 e il modulo `venv` installati. Su sistemi Debian/Ubuntu, potresti dover installare `python3-venv` manualmente:

```bash
sudo apt update
sudo apt install python3-venv
# Se ottieni errori specifici sulla versione (es. python3.13-venv), usa il comando suggerito dal sistema, es:
# sudo apt install python3.13-venv
```

## 1. Preparazione File

Crea una cartella sul tuo server (es. `~/budget_amico_backup`) e carica al suo interno i seguenti file/cartelle mantenendo questa struttura:

```text
~/budget_amico_backup/
├── db/
│   ├── backup_supabase.py
│   └── supabase_manager.py
└── linux_deployment/
    └── backup_runner.sh
```

> **Nota:** Puoi anche caricare tutto il progetto, ma questi sono i file essenziali. Assicurati che `db/` e `linux_deployment/` siano allo stesso livello (o che `linux_deployment` sia dentro la root come nel progetto originale). Lo script `backup_runner.sh` si aspetta di trovare la cartella `db` nella directory genitore (`..`).
>
> **Struttura consigliata sul server:**
> ```text
> /home/tuo_utente/scripts/budget_backup/
> ├── .env                      <-- IL TUO FILE CREDENZIALI
> ├── db/                       <-- Cartella copiata dal progetto
> │   ├── backup_supabase.py
> │   └── supabase_manager.py
> └── linux_deployment/         <-- Cartella copiata dal progetto
>     └── backup_runner.sh
> ```

## 2. Configurazione Credenziali (.env)

Questo è il passaggio fondamentale per permettere allo script di accedere a Supabase.
Crea un file chiamato `.env` nella cartella radice del progetto sul server (`/home/tuo_utente/scripts/budget_backup/.env`).

Il file deve contenere la stringa di connessione al database:

```env
SUPABASE_DB_URL=postgresql://postgres:[LA_TUA_PASSWORD]@[IL_TUO_HOST]:5432/postgres
```

**Dove trovare questi dati:**
1. Vai sulla dashboard di Supabase.
2. Vai su **Project Settings** -> **Database**.
3. Sotto **Connection parameters**, trova la **Connection String** (seleziona "URI").
4. Copia la stringa e sostituisci `[YOUR-PASSWORD]` con la tua password reale del database.

⚠️ **IMPORTANTE:** Assicurati che questo file non sia accessibile ad altri utenti sul server (`chmod 600 .env`).

## 3. Configurazione Script

Rendi eseguibile lo script di backup:

```bash
chmod +x linux_deployment/backup_runner.sh
```

## 4. Test Manuale

Prova a lanciare lo script manualmente per verificare che tutto funzioni:

```bash
./linux_deployment/backup_runner.sh
```

Se è la prima volta, lo script creerà un ambiente virtuale (`venv_linux`), installerà le librerie necessarie (`pg8000`, ecc.) ed eseguirà il backup.
Dovresti vedere un output che conferma il successo e la creazione del file di backup nella cartella `backups/`.

## 5. Automatizzazione con Cron (Pianificazione)

Per eseguire il backup ogni giorno automaticamente (es. alle 03:00 di notte):

1. Apri l'editor di cron:
   ```bash
   crontab -e
   ```

2. Aggiungi la seguente riga alla fine del file:

   ```cron
   # Esegue il backup di Budget Amico ogni giorno alle 03:00
   0 3 * * * /home/tuo_utente/scripts/budget_backup/linux_deployment/backup_runner.sh >> /home/tuo_utente/scripts/budget_backup/backup.log 2>&1
   ```

   **Spiegazione:**
   - `0 3 * * *`: Alle 03:00 di ogni giorno.
   - `/percorso/.../backup_runner.sh`: Il percorso assoluto del tuo script.
   - `>> .../backup.log`: Salva l'output in un file di log (utile per controllare errori).
   - `2>&1`: Reindirizza anche gli errori nel file di log.

3. Salva e chiudi (se usi nano, `CTRL+O`, `Invio`, `CTRL+X`).

## Verifica

Controlla ogni tanto il file `backup.log` per assicurarti che i backup stiano avvenendo correttamente. I file `.json` di backup verranno salvati nella cartella `backups/` creata automaticamente.
