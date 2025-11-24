import sqlite3
import os
import sys

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.gestione_db import DB_FILE

def show_current_budgets():
    if not os.path.exists(DB_FILE):
        print(f"Database not found: {DB_FILE}")
        return

    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            
            # Get families first
            cur.execute("SELECT id_famiglia, nome_famiglia FROM Famiglie")
            famiglie = cur.fetchall()
            
            for id_fam, nome_fam in famiglie:
                print(f"\n=== Budget Attuali per Famiglia: {nome_fam} (ID: {id_fam}) ===")
                print(f"{'Categoria':<20} | {'Sottocategoria':<25} | {'Budget Mensile':>15}")
                print("-" * 65)
                
                query = """
                    SELECT 
                        C.nome_categoria, 
                        S.nome_sottocategoria, 
                        B.importo_limite
                    FROM Sottocategorie S
                    JOIN Categorie C ON S.id_categoria = C.id_categoria
                    LEFT JOIN Budget B ON S.id_sottocategoria = B.id_sottocategoria 
                        AND B.id_famiglia = ? 
                        AND B.periodo = 'Mensile'
                    WHERE C.id_famiglia = ?
                    ORDER BY C.nome_categoria, S.nome_sottocategoria
                """
                
                cur.execute(query, (id_fam, id_fam))
                rows = cur.fetchall()
                
                current_cat = ""
                for row in rows:
                    cat, subcat, limit = row
                    limit_str = f"€ {limit:,.2f}" if limit is not None else "Non impostato"
                    
                    if cat != current_cat:
                        print("-" * 65)
                        current_cat = cat
                        
                    print(f"{cat:<20} | {subcat:<25} | {limit_str:>15}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    show_current_budgets()
