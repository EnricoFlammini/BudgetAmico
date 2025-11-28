#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script per aggiornare automaticamente tutti i file rimanenti
per passare master_key_b64 alle funzioni del database
"""

import re
from pathlib import Path

# File da modificare e le loro funzioni
FILES_TO_UPDATE = {
    "tabs/tab_conti.py": {
        "functions": ["ottieni_dettagli_conti_utente"],
        "line_numbers": [49]
    },
    "tabs/tab_personale.py": {
        "functions": ["ottieni_transazioni_utente"],
        "line_numbers": [77]
    },
    "tabs/tab_investimenti.py": {
        "functions": ["ottieni_dettagli_conti_utente"],
        "line_numbers": [39, 293, 342]
    },
    "dialogs/fondo_pensione_dialog.py": {
        "functions": ["ottieni_conti_utente"],
        "line_numbers": [64]
    },
    "dialogs/investimento_dialog.py": {
        "functions": ["aggiungi_conto"],
        "line_numbers": [77]
    }
}

def add_master_key_to_function_call(line, function_name):
    """Aggiunge master_key_b64=master_key_b64 alla chiamata di funzione"""
    # Pattern per trovare la chiamata di funzione
    pattern = rf'{function_name}\s*\('
    
    if re.search(pattern, line):
        # Se la linea termina con ), aggiungi il parametro prima
        if line.rstrip().endswith(')'):
            line = line.rstrip()[:-1] + ', master_key_b64=master_key_b64)\n'
        # Se la linea termina con ,), aggiungi il parametro
        elif line.rstrip().endswith(',)'):
            line = line.rstrip()[:-2] + ', master_key_b64=master_key_b64)\n'
        else:
            # La chiamata continua sulla riga successiva, non modifichiamo
            pass
    
    return line

def update_file(file_path, functions, line_numbers):
    """Aggiorna un file aggiungendo master_key_b64 alle chiamate specificate"""
    print(f"\n📝 Aggiornamento: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Trova la prima funzione/metodo nel file per aggiungere master_key retrieval
    master_key_added = False
    modified_lines = []
    
    for i, line in enumerate(lines, 1):
        # Se siamo su una linea da modificare
        if i in line_numbers:
            # Assicurati che master_key sia recuperato prima
            if not master_key_added:
                # Trova l'inizio della funzione corrente
                for j in range(i-1, -1, -1):
                    if 'def ' in lines[j]:
                        # Trova la prima linea dopo la def
                        indent = len(lines[j]) - len(lines[j].lstrip())
                        insert_line = j + 1
                        
                        # Salta docstring se presente
                        if '"""' in lines[insert_line] or "'''" in lines[insert_line]:
                            # Trova la fine del docstring
                            while insert_line < len(lines):
                                insert_line += 1
                                if '"""' in lines[insert_line] or "'''" in lines[insert_line]:
                                    insert_line += 1
                                    break
                        
                        # Inserisci il recupero della master_key
                        master_key_line = ' ' * (indent + 4) + '# Get master_key from session for encryption\n'
                        master_key_line += ' ' * (indent + 4) + 'master_key_b64 = self.page.session.get("master_key")\n'
                        master_key_line += ' ' * (indent + 4) + '\n'
                        
                        lines.insert(insert_line, master_key_line)
                        master_key_added = True
                        print(f"  ✅ Aggiunto recupero master_key alla linea {insert_line}")
                        break
            
            # Modifica la chiamata di funzione
            for func in functions:
                if func in line:
                    original_line = line
                    line = add_master_key_to_function_call(line, func)
                    if line != original_line:
                        print(f"  ✅ Modificata chiamata a {func} alla linea {i}")
                    break
        
        modified_lines.append(line)
    
    # Scrivi il file modificato
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(modified_lines)
    
    print(f"  ✅ File aggiornato con successo!")

def main():
    print("="*70)
    print("  AGGIORNAMENTO AUTOMATICO FILE PER CRITTOGRAFIA E2EE")
    print("="*70)
    
    base_path = Path(__file__).parent
    
    for file_rel_path, config in FILES_TO_UPDATE.items():
        file_path = base_path / file_rel_path
        
        if not file_path.exists():
            print(f"\n⚠️  File non trovato: {file_path}")
            continue
        
        try:
            update_file(file_path, config["functions"], config["line_numbers"])
        except Exception as e:
            print(f"\n❌ Errore durante l'aggiornamento di {file_path}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print("  ✅ AGGIORNAMENTO COMPLETATO!")
    print("="*70)
    print("\nFile aggiornati:")
    for file_path in FILES_TO_UPDATE.keys():
        print(f"  - {file_path}")
    
    print("\n⚠️  IMPORTANTE: Verifica manualmente le modifiche prima di eseguire l'app!")

if __name__ == "__main__":
    main()
