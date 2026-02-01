import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection

def get_table_ddl(table_name):
    print(f"--- GENERATING DDL FOR {table_name} ---")
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # 1. Get Columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        columns = cur.fetchall()
        
        cols_sql = []
        for col in columns:
            cname = col['column_name']
            ctype = col['data_type']
            cnull = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            cdef = f"DEFAULT {col['column_default']}" if col['column_default'] else ""
            
            # Fix type mapping if needed (postgres info schema types vs create types)
            if ctype == 'character varying': ctype = 'TEXT' # Simplified
            if ctype == 'timestamp without time zone': ctype = 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP' # Approximation for default
            
            # Map auto-increment
            if col['column_default'] and 'nextval' in col['column_default']:
               cdef = "" # Handled by SERIAL or AUTOINCREMENT usually, but for Postgres keep logic simple
               if 'integer' in ctype:
                   ctype = 'SERIAL' # Valid for PG
                   cnull = "" # Serial implies Not Null
            
            cols_sql.append(f"    {cname} {ctype} {cnull} {cdef}".strip())
            
        # 2. Get Constraints (PK, FK)
        # Simplified: Just output columns for now. FKs are hard to reverse fully portable without regexing default strings
        # But we can try querying constraint tables
        
        ddl = f"CREATE TABLE {table_name} (\n" + ",\n".join(cols_sql) + "\n);"
        print(ddl)
        print("-" * 30)

if __name__ == "__main__":
    tables = ['salvadanai', 'obiettivi_risparmio', 'storicoassetglobale']
    for t in tables:
        get_table_ddl(t)
