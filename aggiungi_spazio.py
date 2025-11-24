"""
Script per aggiungere lo spazio in basso alla lista delle categorie
"""

# Leggi il file
with open(r"c:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo\tabs\tab_admin.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Trova la fine del ciclo for delle categorie (dopo l'ultimo self.lv_categorie.controls.append)
# e aggiungi lo spazio in basso
in_update_tab_categorie = False
last_append_line = -1

for i, line in enumerate(lines):
    if "def update_tab_categorie(self):" in line:
        in_update_tab_categorie = True
        print(f"Trovata funzione update_tab_categorie alla riga {i+1}")
    
    if in_update_tab_categorie and "self.lv_categorie.controls.append(" in line:
        last_append_line = i
        
    if in_update_tab_categorie and "def update_tab_membri(self):" in line:
        # Trovata la funzione successiva, inserisci lo spazio prima di questa
        if last_append_line > 0:
            # Trova la chiusura della chiamata append
            paren_count = 0
            for j in range(last_append_line, i):
                paren_count += lines[j].count('(') - lines[j].count(')')
                if paren_count == 0:
                    # Inserisci dopo questa riga
                    insert_pos = j + 1
                    new_lines = [
                        "\r\n",
                        "            # Aggiungi spazio in basso per evitare interferenze con il pulsante +\r\n",
                        "            self.lv_categorie.controls.append(ft.Container(height=80))\r\n"
                    ]
                    lines[insert_pos:insert_pos] = new_lines
                    print(f"Aggiunto spazio in basso alla riga {insert_pos+1}")
                    break
        break

# Scrivi il file modificato
with open(r"c:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo\tabs\tab_admin.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Spazio in basso aggiunto!")
