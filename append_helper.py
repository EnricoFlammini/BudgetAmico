
import os

file_path = r'g:\Il mio Drive\PROGETTI\BudgetAmico\Sviluppo\db\gestione_db.py'
new_code = """

def calcola_totale_speso_carta(id_carta: int, mese: int, anno: int) -> float:
    conn = get_db_connection()
    if not conn: return 0.0
    try:
        start_date = f'{anno}-{mese:02d}-01'
        if mese == 12:
            end_date = f'{anno+1}-01-01'
        else:
            end_date = f'{anno}-{mese+1:02d}-01'
        
        # SQLite uses ? for placeholders usually in python sqlite3, 
        # but if get_db_connection returns pg8000/psycopg2 it uses %s.
        # However, the codebase mostly uses sqlite3 currently BUT we migrated to Postgres...
        # Wait, the codebase uses 'sqlite3' in migration scripts but 'pg8000' in supabase_manager.
        # 'get_db_connection' usually returns the supabase connection (pg8000).
        # pg8000 uses %s.
        
        query = "SELECT SUM(importo) FROM Transazioni WHERE id_carta = %s AND data >= %s AND data < %s"
        cur = conn.cursor()
        cur.execute(query, (id_carta, start_date, end_date))
        res = cur.fetchone()
        val = res[0] if res and res[0] else 0.0
        return abs(float(val)) # Return positive value for 'Spent'
    except Exception as e:
        print(f'Error calc speso carta: {e}')
        return 0.0
    finally:
        conn.close()
"""

with open(file_path, 'a', encoding='utf-8') as f:
    f.write(new_code)
print("Appended successfully.")
