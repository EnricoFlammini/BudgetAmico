#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Patch auth_view.py for encryption support"""

import sys

# Read file
with open('views/auth_view.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace line 199: id_nuovo_utente = registra_utente(...) -> result = registra_utente(...)
for i, line in enumerate(lines):
    if i == 198 and 'id_nuovo_utente = registra_utente' in line:  # Line 199 (0-indexed = 198)
        lines[i] = '        result = registra_utente(nome, cognome, username, password, email, data_nascita, codice_fiscale, indirizzo)\n'
        print(f"✓ Patched line 199")
        break

# Find line 201 "if id_nuovo_utente:" and replace the entire block until line 212
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'if id_nuovo_utente:' in line and i > 195:
        start_idx = i
    if start_idx and 'self.txt_reg_username.error_text = "Username o Email' in line:
        end_idx = i + 1  # Include the line with page.update()
        break

if start_idx and end_idx:
    # New block
    new_block = '''        if result:
            id_nuovo_utente = result.get("id_utente")
            recovery_key = result.get("recovery_key")
            
            invito_attivo = self.page.session.get("invito_attivo")
            if invito_attivo:
                aggiungi_utente_a_famiglia(invito_attivo['id_famiglia'], id_nuovo_utente,
                                           invito_attivo['ruolo_assegnato'])
                self.page.session.remove("invito_attivo")

            # Show recovery key dialog
            def close_dialog(e):
                dialog.open = False
                self.page.update()
                self.page.go("/")
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("SALVA LA TUA CHIAVE DI RECUPERO", weight=ft.FontWeight.BOLD),
                content=ft.Column([
                    ft.Text("Questa e' la tua chiave di recupero. SALVALA IN UN POSTO SICURO!", size=14),
                    ft.Text("Se perdi la password, questa chiave e' l'UNICO modo per recuperare i tuoi dati.", 
                           size=12, color=ft.Colors.RED_400),
                    ft.Container(height=10),
                    ft.TextField(
                        value=recovery_key,
                        read_only=True,
                        multiline=True,
                        text_size=12,
                        border_color=ft.Colors.BLUE_400
                    ),
                    ft.Container(height=10),
                    ft.Text("Senza questa chiave, i dati criptati saranno PERSI per sempre!", 
                           size=11, italic=True, color=ft.Colors.ORANGE_400)
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                actions=[
                    ft.TextButton("Ho salvato la chiave", on_click=close_dialog)
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()
        else:
            self.txt_reg_username.error_text = "Username o Email gia' in uso."
            self.page.update()
'''
    lines[start_idx:end_idx+1] = [new_block]
    print(f"✓ Replaced registration block (lines {start_idx+1}-{end_idx+2})")

# Write back
with open('views/auth_view.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("\n✓ Successfully patched auth_view.py")
