
import os

filepath = r"g:\Il mio Drive\PROGETTI\BudgetAmico\Sviluppo\db\gestione_db.py"

# Read the file as binary to see what's wrong or just read as text expecting utf-8
with open(filepath, 'rb') as f:
    content = f.read()

# Find the point of corruption. 
# We know it ends with the new content which was likely written as UTF-16 or something.
# The previous content ended around line 7071.
# Let's search for the last known good string before valid end.
# "return False" inside "trigger_budget_history_update" block?
# Line 7070: "        return False"
# Then line 7071 was empty.

# Let's look for the byte sequence of the new header I added: "# --- GESTIONE CARTE ---"
# If it was added with wide chars, it might look like "\x23\x00\x20\x00..."
# Search for the start of the appended section.
marker = b"# --- GESTIONE CARTE ---"
split_index = content.find(marker)

if split_index == -1:
    # Maybe it is corrupted in a way that marker is not found exactly?
    # The `type` command output logic.
    # Let's try to find the end of the `trigger_budget_history_update` function.
    # It ends with "return False" inside the except block.
    # The file view showed line 7068: except Exception as e:
    # 7069: print ...
    # 7070: return False
    
    # We can try to truncate after the last valid "return False" of that function.
    pass

# Option 2: Just rewrite the whole file since I have the tools.
# I will read the file until I hit the corruption or just use the line count from previous view?
# Previous view showed validation up to 7071.
# I will fix it by rewriting the file with the clean content + the extension content validly.

# Let's read lines and stop when we detect null bytes.
clean_lines = []
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if '\x00' in line:
            break
        clean_lines.append(line)

# Now append the new content cleanly.
new_content = """

# --- GESTIONE CARTE ---

def aggiungi_carta(id_utente, nome_carta, tipo_carta, circuito, id_conto_riferimento=None, id_conto_contabile=None, 
                   massimale=None, giorno_addebito=None, spesa_tenuta=None, soglia_azzeramento=None, giorno_addebito_tenuta=None,
                   addebito_automatico=False, master_key=None, crypto=None):
    \"\"\"
    Aggiunge una nuova carta nel database. Cripta i dati sensibili.
    \"\"\"
    try:
        crypto, master_key = _get_crypto_and_key(master_key)
        
        massimale_enc = _encrypt_if_key(str(massimale) if massimale is not None else None, master_key, crypto)
        giorno_addebito_enc = _encrypt_if_key(str(giorno_addebito) if giorno_addebito is not None else None, master_key, crypto)
        spesa_tenuta_enc = _encrypt_if_key(str(spesa_tenuta) if spesa_tenuta is not None else None, master_key, crypto)
        soglia_azzeramento_enc = _encrypt_if_key(str(soglia_azzeramento) if soglia_azzeramento is not None else None, master_key, crypto)
        giorno_addebito_tenuta_enc = _encrypt_if_key(str(giorno_addebito_tenuta) if giorno_addebito_tenuta is not None else None, master_key, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(\"\"\"
                INSERT INTO Carte (
                    id_utente, nome_carta, tipo_carta, circuito, id_conto_riferimento, id_conto_contabile,
                    massimale_encrypted, giorno_addebito_encrypted, spesa_tenuta_encrypted, 
                    soglia_azzeramento_encrypted, giorno_addebito_tenuta_encrypted, addebito_automatico
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            \"\"\", (id_utente, nome_carta, tipo_carta, circuito, id_conto_riferimento, id_conto_contabile,
                  massimale_enc, giorno_addebito_enc, spesa_tenuta_enc, soglia_azzeramento_enc, giorno_addebito_tenuta_enc, addebito_automatico))
            con.commit()
            return True
    except Exception as e:
        print(f\"[ERRORE] Errore aggiunta carta: {e}\")
        return False

def ottieni_carte_utente(id_utente, master_key_b64=None):
    \"\"\"
    Restituisce la lista delle carte attive dell'utente, decriptando i dati sensibili.
    \"\"\"
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Carte WHERE id_utente = %s AND attiva = TRUE", (id_utente,))
            carte_raw = cur.fetchall()
            
            carte = []
            for row in carte_raw:
                try:
                    c = dict(row)
                    c['massimale'] = _decrypt_and_convert(c['massimale_encrypted'], float, master_key, crypto)
                    c['giorno_addebito'] = _decrypt_and_convert(c['giorno_addebito_encrypted'], int, master_key, crypto)
                    c['spesa_tenuta'] = _decrypt_and_convert(c['spesa_tenuta_encrypted'], float, master_key, crypto)
                    c['soglia_azzeramento'] = _decrypt_and_convert(c['soglia_azzeramento_encrypted'], float, master_key, crypto)
                    c['giorno_addebito_tenuta'] = _decrypt_and_convert(c['giorno_addebito_tenuta_encrypted'], int, master_key, crypto)
                    carte.append(c)
                except Exception as e:
                     print(f\"[WARN] Errore decriptazione carta {row.get('id_carta')}: {e}\")
            return carte
    except Exception as e:
        print(f\"[ERRORE] Errore recupero carte utente: {e}\")
        return []

def _decrypt_and_convert(encrypted_val, type_func, master_key, crypto):
    \"\"\"Helper per decriptare e convertire. Ritorna None se vuoto o errore.\"\"\"
    if not encrypted_val: return None
    val_str = _decrypt_if_key(encrypted_val, master_key, crypto, silent=True)
    if not val_str or val_str == \"[ENCRYPTED]\": return None
    try:
        return type_func(val_str)
    except:
        return None

def modifica_carta(id_carta, nome_carta=None, tipo_carta=None, circuito=None, id_conto_riferimento=None, id_conto_contabile=None,
                   massimale=None, giorno_addebito=None, spesa_tenuta=None, soglia_azzeramento=None, giorno_addebito_tenuta=None,
                   addebito_automatico=None, master_key_b64=None):
    \"\"\"
    Modifica una carta esistente. Aggiorna solo i campi forniti.
    \"\"\"
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        updates = []
        params = []

        if nome_carta is not None:
            updates.append("nome_carta = %s")
            params.append(nome_carta)
        if tipo_carta is not None:
            updates.append("tipo_carta = %s")
            params.append(tipo_carta)
        if circuito is not None:
            updates.append("circuito = %s")
            params.append(circuito)
        if id_conto_riferimento is not None: 
            updates.append("id_conto_riferimento = %s")
            params.append(id_conto_riferimento)
        if id_conto_contabile is not None:
            updates.append("id_conto_contabile = %s")
            params.append(id_conto_contabile)
        if addebito_automatico is not None:
            updates.append("addebito_automatico = %s")
            params.append(addebito_automatico)

        if massimale is not None:
            updates.append("massimale_encrypted = %s")
            params.append(_encrypt_if_key(str(massimale), master_key, crypto))
        if giorno_addebito is not None:
            updates.append("giorno_addebito_encrypted = %s")
            params.append(_encrypt_if_key(str(giorno_addebito), master_key, crypto))
        if spesa_tenuta is not None:
            updates.append("spesa_tenuta_encrypted = %s")
            params.append(_encrypt_if_key(str(spesa_tenuta), master_key, crypto))
        if soglia_azzeramento is not None:
            updates.append("soglia_azzeramento_encrypted = %s")
            params.append(_encrypt_if_key(str(soglia_azzeramento), master_key, crypto))
        if giorno_addebito_tenuta is not None:
            updates.append("giorno_addebito_tenuta_encrypted = %s")
            params.append(_encrypt_if_key(str(giorno_addebito_tenuta), master_key, crypto))

        if not updates:
            return False

        params.append(id_carta)
        query = f\"UPDATE Carte SET {', '.join(updates)} WHERE id_carta = %s\"

        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(query, tuple(params))
            con.commit()
            return True
            
    except Exception as e:
        print(f\"[ERRORE] Errore modifica carta: {e}\")
        return False

def elimina_carta(id_carta, soft_delete=True):
    \"\"\"
    Elimina una carta (soft delete di default per preservare storico).
    \"\"\"
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            if soft_delete:
                cur.execute("UPDATE Carte SET attiva = FALSE WHERE id_carta = %s", (id_carta,))
            else:
                cur.execute("DELETE FROM Carte WHERE id_carta = %s", (id_carta,))
            con.commit()
            return True
    except Exception as e:
        print(f\"[ERRORE] Errore eliminazione carta: {e}\")
        return False
"""

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(clean_lines)
    f.write(new_content)

print("File healed.")
