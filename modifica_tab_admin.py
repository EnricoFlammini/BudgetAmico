"""
Script per aggiungere i valori del budget alle sottocategorie in tab_admin.py
"""

# Leggi il file
with open(r"c:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo\tabs\tab_admin.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Trova e modifica la riga dell'import
for i, line in enumerate(lines):
    if "from db.gestione_db import ottieni_categorie_e_sottocategorie, ottieni_membri_famiglia, rimuovi_utente_da_famiglia" in line:
        lines[i] = "from db.gestione_db import ottieni_categorie_e_sottocategorie, ottieni_membri_famiglia, rimuovi_utente_da_famiglia, ottieni_budget_famiglia\r\n"
        print(f"Modificata riga {i+1}: import aggiornato")
        break

# Trova la funzione update_tab_categorie e modifica
in_function = False
for i, line in enumerate(lines):
    if "def update_tab_categorie(self):" in line:
        in_function = True
        function_start = i
        print(f"Trovata funzione update_tab_categorie alla riga {i+1}")
        
    # Aggiungi il recupero dei budget dopo categorie_data
    if in_function and "categorie_data = ottieni_categorie_e_sottocategorie(id_famiglia)" in line:
        # Inserisci le nuove righe dopo questa
        insert_pos = i + 1
        new_lines = [
            "        \r\n",
            "        # Recupera i budget impostati\r\n",
            "        budget_impostati = ottieni_budget_famiglia(id_famiglia)\r\n",
            "        mappa_budget = {b['id_sottocategoria']: b['importo_limite'] for b in budget_impostati}\r\n"
        ]
        lines[insert_pos:insert_pos] = new_lines
        print(f"Aggiunte righe per recupero budget alla riga {insert_pos+1}")
        break

# Trova e modifica la riga che mostra il nome della sottocategoria
for i, line in enumerate(lines):
    if 'ft.Text(sub[\'nome_sottocategoria\'], expand=True)' in line:
        # Trova l'indentazione
        indent = len(line) - len(line.lstrip())
        # Sostituisci con la nuova riga che include il budget
        lines[i] = " " * indent + "ft.Text(f\"{sub['nome_sottocategoria']}: €{mappa_budget.get(sub['id_sottocategoria'], 0.0):.2f}\", expand=True),\r\n"
        print(f"Modificata riga {i+1}: aggiunto valore budget")
        break

# Aggiungi spazio in basso prima della chiusura del metodo update_tab_categorie
for i in range(len(lines) - 1, -1, -1):
    line = lines[i]
    if "self.lv_categorie.controls.append(" in line and "ft.ExpansionPanelList(" in lines[i+1]:
        # Trova la chiusura di questo blocco
        paren_count = 0
        for j in range(i, len(lines)):
            paren_count += lines[j].count('(') - lines[j].count(')')
            if paren_count == 0 and ')' in lines[j]:
                # Inserisci il container di spazio dopo questo blocco
                insert_pos = j + 1
                new_lines = [
                    "            \r\n",
                    "            # Aggiungi spazio in basso per evitare interferenze con il pulsante +\r\n",
                    "            self.lv_categorie.controls.append(ft.Container(height=80))\r\n"
                ]
                # Trova la fine del ciclo for delle categorie
                for k in range(insert_pos, len(lines)):
                    if lines[k].strip() and not lines[k].strip().startswith('#') and lines[k][0] not in [' ', '\t', '\r', '\n']:
                        insert_pos = k
                        break
                    if 'def ' in lines[k]:
                        insert_pos = k
                        break
                        
                print(f"Tentativo di aggiungere spazio in basso alla riga {insert_pos+1}")
                break
        break

# Scrivi il file modificato
with open(r"c:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo\tabs\tab_admin.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Modifiche completate!")
