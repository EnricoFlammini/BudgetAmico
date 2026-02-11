
# Script to fix gestione_db.py v2
filepath = r"g:\Il mio Drive\PROGETTI\BudgetAmico\Sviluppo\db\gestione_db.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines, 1):
    # Fix the redundant else: in crea_conto_condiviso and modifica_conto_condiviso
    # Look for "else:" preceded by "encrypted_config = config_speciale"
    
    # Specifically line 3976 (now it might have shifted slightly, so search by content)
    # The erroneous lines are:
    #             else:
    #                 encrypted_config = config_speciale # Fallback if no key
    # (where the first else is at indentation 12 spaces, matching 'with')
    
    # Let's be safer: if a line is exactly "            else:\n" and follows "            encrypted_config = config_speciale # Fallback if no key\n" (which is at indentation 20? No, check indentation)
    
    # Actually, I'll just look for that specific pattern in the file.
    if line.strip() == "else:" and i > 1 and "encrypted_config = config_speciale" in lines[i-2]:
        # Check indentation of current line
        indent = len(line) - len(line.lstrip())
        prev_indent = len(lines[i-2]) - len(lines[i-2].lstrip())
        
        # If indentation is same as 'with' (12 spaces) and prev line was 'encrypted_config = config_speciale'
        if indent == 12:
            print(f"Removing redundant else at line {i}")
            continue # Skip this line
            
    new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("File fixed successfully")
