#!/bin/bash

# Budget Amico - Script di Backup Automatico
# Questo script deve essere posizionato nella cartella del progetto sul server Linux.

# 1. Ottieni la directory in cui si trova questo script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

echo "=== Inizio Backup: $(date) ==="
echo "Directory di lavoro: $(pwd)"

# 2. Configurazione Ambiente Virtuale
VENV_DIR="venv_linux"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Ambiente virtuale non trovato o incompleto. Creazione in corso..."
    # Rimuovi directory se esiste ma è rotta
    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
    fi
    
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "ERRORE: Impossibile creare l'ambiente virtuale."
        echo "SUGGERIMENTO: Esegui 'sudo apt install python3-venv' (o python3.X-venv) sul server."
        exit 1
    fi
    echo "Ambiente virtuale creato."
fi

# 3. Attivazione Ambiente Virtuale
source "$VENV_DIR/bin/activate"

# 4. Installazione Dipendenze
# Installiamo solo lo stretto necessario per il backup per mantenere leggero l'ambiente
echo "Verifica dipendenze..."
pip install --upgrade pip > /dev/null
pip install pg8000 python-dotenv scramp > /dev/null

# 5. Esecuzione Backup
echo "Avvio script Python..."
python3 db/backup_supabase.py

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "=== Backup completato con successo: $(date) ==="
else
    echo "=== ERRORE durante il backup (Codice: $EXIT_CODE): $(date) ==="
fi

# Disattivazione ambiente (opzionale alla fine dello script, ma buona pratica)
deactivate
