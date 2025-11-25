#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script per convertire tutte le funzioni SQLite rimanenti in PostgreSQL
"""

import re
from pathlib import Path

def convert_remaining_sqlite():
    file_path = Path(__file__).parent / "gestione_db.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Sostituisci sqlite3.connect(DB_FILE) con get_db_connection()
    content = re.sub(
        r'with sqlite3\.connect\(DB_FILE\) as con:',
        'with get_db_connection() as conn:',
        content
    )
    
    # 2. Sostituisci con.row_factory = sqlite3.Row
    content = re.sub(
        r'con\.row_factory = sqlite3\.Row\s+',
        '# RealDictCursor già configurato in supabase_manager\n            ',
        content
    )
    
    # 3. Sostituisci tutte le occorrenze di con. con conn.
    # Ma solo nelle righe dove non c'è "con" come parte di parola (es. "condiviso", "contiene")
    content = re.sub(r'\bcon\.', 'conn.', content)
    
    # 4. Sostituisci sqlite3.IntegrityError con pg_errors.UniqueViolation
    content = re.sub(
        r'except sqlite3\.IntegrityError',
        'except pg_errors.UniqueViolation',
        content
    )
    
    # 5. Rimuovi tutte le occorrenze di PRAGMA foreign_keys
    content = re.sub(
        r'\s*cur\.execute\("PRAGMA foreign_keys = ON;"\)\s*\n',
        '',
        content
    )
    
    # Salva il file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("[OK] Conversione completata!")
    print("  - Sostituite connessioni SQLite con get_db_connection()")
    print("  - Rimosse row_factory SQLite")
    print("  - Aggiornati IntegrityError")
    print("  - Rimossi PRAGMA foreign_keys")

if __name__ == "__main__":
    convert_remaining_sqlite()
