"""
Script completo per convertire gestione_db.py da SQLite a PostgreSQL
Questo script applica tutte le trasformazioni necessarie in modo sistematico.
"""

import re
import os

def convert_file():
    input_file = r'c:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo\db\gestione_db.py'
    
    print("=" * 70)
    print("CONVERSIONE GESTIONE_DB.PY DA SQLITE A POSTGRESQL")
    print("=" * 70)
    
    print(f"\nLeggendo {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_lines = content.count('\n')
    print(f"[OK] File letto: {original_lines} righe")
    
    # Conta occorrenze prima della conversione
    sqlite_connects = content.count('sqlite3.connect')
    print(f"\nTrovate {sqlite_connects} occorrenze di sqlite3.connect da convertire")
    
    print("\nApplicando conversioni...")
    
    # 1. Sostituisci with sqlite3.connect(DB_FILE) as con:
    print("  1. Convertendo sqlite3.connect -> get_db_connection...")
    content = re.sub(
        r'with sqlite3\.connect\(DB_FILE\) as con:',
        'with get_db_connection() as conn:',
        content
    )
    
    # 2. Sostituisci with sqlite3.connect(db_path) as con:
    content = re.sub(
        r'with sqlite3\.connect\(db_path\) as con:',
        'with get_db_connection() as conn:',
        content
    )
    
    # 3. Sostituisci con.row_factory = sqlite3.Row seguito da cur = con.cursor()
    print("  2. Rimuovendo row_factory e aggiustando cursori...")
    content = re.sub(
        r'con\.row_factory = sqlite3\.Row\s*\n\s*cur = con\.cursor\(\)',
        'with conn.cursor() as cur:',
        content
    )
    
    # 4. Sostituisci cur = con.cursor() standalone
    content = re.sub(
        r'(\s+)cur = con\.cursor\(\)(\s*\n)',
        r'\1with conn.cursor() as cur:\2',
        content
    )
    
    # 5. Sostituisci placeholder ? con %s nelle query SQL
    print("  3. Convertendo placeholder ? -> %s...")
    # Trova tutte le cur.execute e sostituisci ? con %s
    def replace_placeholders(match):
        return match.group(0).replace('?', '%s')
    
    content = re.sub(
        r'cur\.execute\([^)]+\)',
        replace_placeholders,
        content
    )
    
    # 6. Sostituisci sqlite3.IntegrityError con pg_errors.UniqueViolation
    print("  4. Convertendo gestione errori...")
    content = content.replace('sqlite3.IntegrityError', 'pg_errors.UniqueViolation')
    content = content.replace('except sqlite3.IntegrityError:', 'except pg_errors.UniqueViolation:')
    
    # 7. Rimuovi PRAGMA foreign_keys = ON
    print("  5. Rimuovendo PRAGMA statements...")
    content = re.sub(
        r'\s*cur\.execute\("PRAGMA foreign_keys = ON;"\)\s*\n',
        '',
        content
    )
    
    # 8. Sostituisci con con conn
    print("  6. Rinominando variabile connessione...")
    content = content.replace(' con.', ' conn.')
    content = content.replace('(con)', '(conn)')
    content = content.replace('(con,', '(conn,')
    content = content.replace(' con,', ' conn,')
    
    # 9. Gestisci cur.lastrowid -> RETURNING
    print("  7. Convertendo lastrowid -> RETURNING...")
    # Questo è complesso, facciamo pattern comuni
    
    # Pattern: cur.execute("INSERT...) seguito da cur.lastrowid
    def add_returning(match):
        insert_stmt = match.group(1)
        table_match = re.search(r'INSERT INTO (\w+)', insert_stmt, re.IGNORECASE)
        if table_match:
            table = table_match.group(1)
            # Determina il nome della colonna ID
            id_col_map = {
                'Famiglie': 'id_famiglia',
                'Utenti': 'id_utente',
                'Conti': 'id_conto',
                'ContiCondivisi': 'id_conto_condiviso',
                'Categorie': 'id_categoria',
                'Sottocategorie': 'id_sottocategoria',
                'Transazioni': 'id_transazione',
                'TransazioniCondivise': 'id_transazione_condivisa',
                'Budget': 'id_budget',
                'Prestiti': 'id_prestito',
                'Immobili': 'id_immobile',
                'Asset': 'id_asset',
                'SpeseFisse': 'id_spesa_fissa',
                'Inviti': 'id_invito',
            }
            id_col = id_col_map.get(table, 'id')
            # Aggiungi RETURNING se non c'è già
            if 'RETURNING' not in insert_stmt.upper():
                insert_stmt = insert_stmt.rstrip(')') + f" RETURNING {id_col})"
        return f'cur.execute({insert_stmt})'
    
    # Trova pattern INSERT seguito da lastrowid
    content = re.sub(
        r'cur\.execute\(("INSERT INTO [^"]+"\s*,\s*[^)]+)\)\s*\n\s*\w+\s*=\s*cur\.lastrowid',
        lambda m: add_returning(m) + '\n                result = cur.fetchone()\n                ' + m.group(0).split('=')[0].strip() + ' = result[0] if isinstance(result, tuple) else result[\'' + 'id' + '\']',
        content
    )
    
    # 10. Gestisci BEGIN TRANSACTION
    print("  8. Convertendo BEGIN TRANSACTION...")
    content = content.replace('cur.execute("BEGIN TRANSACTION;")', '# Transaction gestita automaticamente da context manager')
    
    # 11. Gestisci con.commit() e con.rollback()
    print("  9. Rimuovendo commit/rollback espliciti...")
    content = re.sub(r'\s*con\.commit\(\)\s*\n', '\n', content)
    content = re.sub(r'\s*con\.rollback\(\)\s*\n', '\n', content)
    content = content.replace('conn.commit()', '# Commit automatico')
    content = content.replace('conn.rollback()', '# Rollback automatico')
    
    # 12. Gestisci dict(row) per compatibilità
    print("  10. Aggiustando accesso risultati...")
    # Già gestito con isinstance checks nel codice
    
    print("\n[OK] Conversioni completate!")
    
    # Salva il file convertito
    print(f"\nSalvando file convertito...")
    with open(input_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    converted_lines = content.count('\n')
    print(f"[OK] File salvato: {converted_lines} righe")
    
    # Verifica conversioni
    remaining_sqlite = content.count('sqlite3.connect')
    print(f"\nVerifica conversione:")
    print(f"  - sqlite3.connect rimasti: {remaining_sqlite}")
    print(f"  - get_db_connection aggiunti: {content.count('get_db_connection')}")
    print(f"  - Placeholder %s: {content.count('%s')}")
    
    if remaining_sqlite == 0:
        print("\n[OK] CONVERSIONE COMPLETATA CON SUCCESSO!")
    else:
        print(f"\n[WARN] Attenzione: rimangono {remaining_sqlite} occorrenze di sqlite3.connect")
        print("   Potrebbero richiedere conversione manuale")
    
    print("\n" + "=" * 70)
    print("PROSSIMI PASSI:")
    print("1. Rivedi il file per verificare la correttezza")
    print("2. Testa le funzioni critiche")
    print("3. Esegui i test di connessione")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        convert_file()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
