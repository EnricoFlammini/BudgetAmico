import os
import sys
import json
import datetime

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection

def dump_schema(output_file):
    print(f"Dumping schema to {output_file}...")
    schema = {}
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Get all tables
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [row['table_name'] for row in cur.fetchall()]
        
        for table in tables:
            table_schema = {'columns': {}}
            
            # Get columns
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = %s
            """, (table,))
            
            for row in cur.fetchall():
                table_schema['columns'][row['column_name']] = {
                    'type': row['data_type'],
                    'nullable': row['is_nullable'],
                    'default': row['column_default']
                }
            
            schema[table] = table_schema
            
    with open(output_file, 'w') as f:
        json.dump(schema, f, indent=4, default=str)
        
    print(f"Dump complete: {len(schema)} tables.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        outfile = sys.argv[1]
    else:
        outfile = 'schema_dump.json'
    dump_schema(outfile)
