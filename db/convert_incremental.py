#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script di conversione incrementale: converte solo le funzioni critiche per l'avvio
"""

import re
from pathlib import Path

# Funzioni da convertire
CRITICAL_FUNCTIONS = [
    'ottieni_versione_db',
    'get_user_count',
    'ottieni_prima_famiglia_utente', 
    'ottieni_ruolo_utente',
    'check_e_paga_rate_scadute',
    'check_e_processa_spese_fisse',
    'crea_famiglia_e_admin',
    'aggiungi_categorie_iniziali',
    'cerca_utente_per_username',
    'aggiungi_utente_a_famiglia',
    'crea_invito',
    'ottieni_invito_per_token',
    'ottieni_utenti_senza_famiglia'
]

def convert_critical_functions():
    file_path = Path(__file__).parent / "gestione_db.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Aggiungi import get_db_connection se non presente
    if 'from db.supabase_manager import get_db_connection' not in content:
        # Trova la riga "from db.crea_database import setup_database"
        content = content.replace(
            'from db.crea_database import setup_database',
            'from db.crea_database import setup_database\nfrom db.supabase_manager import get_db_connection'
        )
        print("[OK] Aggiunto import get_db_connection")
    
    # 2. Aggiungi import psycopg2.errors se non presente  
    if 'import psycopg2.errors as pg_errors' not in content:
        content = content.replace(
            'import string',
            'import string\nimport psycopg2.errors as pg_errors'
        )
        print("[OK] Aggiunto import psycopg2.errors")
    
    # 3. Converti placeholder ? in %s
    num_placeholders = content.count('?')
    content = re.sub(r'\(\?\)', '(%s)', content)
    content = re.sub(r' = \?', ' = %s', content)
    content = re.sub(r', \?', ', %s', content) 
    content = re.sub(r'\? ', '%s ', content)
    converted = num_placeholders - content.count('?')
    if converted > 0:
        print(f"[OK] Convertiti {converted} placeholder (? -> %s)")
    
    # 4. Sostituisci sqlite3.connect con get_db_connection SOLO nelle funzioni critiche
    for func_name in CRITICAL_FUNCTIONS:
        # Pattern per trovare la funzione
        pattern = rf'(def {func_name}\([^)]*\):.*?)(\n(?=def |# ---|if __name__))'
        
        def replace_in_function(match):
            func_content = match.group(1)
            end = match.group(2)
            
            # Sostituisci sqlite3.connect con get_db_connection
            func_content = func_content.replace(
                'with sqlite3.connect(DB_FILE) as con:',
                'with get_db_connection() as conn:'
            )
            func_content = func_content.replace('con.', 'conn.')
            func_content = func_content.replace('cur = con.cursor()', 'cur = conn.cursor()')
            
            # Rimuovi PRAGMA foreign_keys (non serve in PostgreSQL)
            func_content = re.sub(r'\s*cur\.execute\("PRAGMA foreign_keys = ON;"\)\s*', '', func_content)
            
            # Sostituisci sqlite3.IntegrityError con pg_errors.UniqueViolation
            func_content = func_content.replace(
                'except sqlite3.IntegrityError:',
                'except pg_errors.UniqueViolation:'
            )
            
            # Gestisci row_factory per PostgreSQL (RealDictCursor)
            if 'con.row_factory = sqlite3.Row' in func_content:
                func_content = func_content.replace('con.row_factory = sqlite3.Row', '# RealDictCursor già configurato in supabase_manager')
            
            return func_content + end
        
        content = re.sub(pattern, replace_in_function, content, flags=re.DOTALL)
    
    print(f"[OK] Convertite {len(CRITICAL_FUNCTIONS)} funzioni critiche")
    
    # Salva il file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("[OK] Conversione incrementale completata!")

if __name__ == "__main__":
    convert_critical_functions()
