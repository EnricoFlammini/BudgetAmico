#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script di conversione automatica da SQLite a PostgreSQL
Converte i placeholder e corregge i context manager in gestione_db.py
"""

import re
import shutil
from pathlib import Path

def convert_sqlite_to_postgres(file_path):
    """Converte sintassi SQLite in PostgreSQL"""
    
    # Backup del file originale
    backup_path = file_path.with_suffix('.py.backup')
    shutil.copy2(file_path, backup_path)
    print(f"[OK] Backup creato: {backup_path}")
    
    # Leggi il contenuto
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # 1. Sostituisci placeholder ? con %s
    # Cerca pattern come (?), = ?, , ?
    content = re.sub(r'\(\?\)', '(%s)', content)
    content = re.sub(r' = \?', ' = %s', content)
    content = re.sub(r', \?', ', %s', content)
    content = re.sub(r'\? ', '%s ', content)
    
    # 2. Correggi context manager in ottieni_versione_db
    content = re.sub(
        r'conn = get_db_connection\(db_path\) if db_path else get_db_connection\(\)\s+with conn:',
        'with get_db_connection() as conn:',
        content,
        flags=re.MULTILINE
    )
    
    # Conta le sostituzioni
    num_placeholders = original_content.count('?') - content.count('?')
    
    # Scrivi il risultato
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] Conversione completata:")
    print(f"  - {num_placeholders} placeholder convertiti (? -> %s)")
    print(f"  - Context manager corretti")
    
    return True

if __name__ == "__main__":
    file_path = Path(__file__).parent / "gestione_db.py"
    
    if not file_path.exists():
        print(f"[ERRORE] File non trovato: {file_path}")
        exit(1)
    
    print(f"Conversione di {file_path}...")
    convert_sqlite_to_postgres(file_path)
    print("\n[OK] Conversione completata con successo!")
