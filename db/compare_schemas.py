import json
import os

def compare_schemas(prod_file, test_file, output_sql):
    with open(prod_file, 'r') as f:
        prod = json.load(f)
    
    with open(test_file, 'r') as f:
        test = json.load(f)
        
    sql = ["DO $$", "BEGIN"]
    
    # 1. Check Tables
    for table, p_schema in prod.items():
        if table not in test:
            print(f"[MISSING TABLE] {table} missing in Test (Handling complex create manually if needed, or flagging)")
            # Generating full CREATE TABLE is complex due to keys/indexes. 
            # Ideally we skip full tables or alert user. 
            # For this context, we assume tables exist and check columns.
            continue
            
        t_schema = test[table]
        
        # 2. Check Columns
        for col, col_def in p_schema['columns'].items():
            if col not in t_schema['columns']:
                print(f"[MISSING COLUMN] {table}.{col}")
                # Determine type and default
                col_type = col_def['type']
                col_default = col_def['default']
                is_null = col_def['nullable'] == 'YES'
                
                # Construct ALTER TABLE
                stmt = f"IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{table.lower()}' AND column_name='{col}') THEN\n"
                
                alter = f"    ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                
                # Default?
                if col_default:
                   # Clean up default string if needed, mostly it comes like "nextval(...)" or "'text'::text"
                   # For safety on syncing, usually adding nullable columns is safer.
                   pass
                
                # Simplification: If nullable=NO, we might have issues adding it without default.
                # For sync, we assume we can add it as NULLABLE first, or with simplistic defaults.
                if not is_null:
                     # Attempt reasonable default based on type
                     if 'int' in col_type or 'numeric' in col_type or 'real' in col_type:
                         alter += " DEFAULT 0"
                     elif 'bool' in col_type:
                         alter += " DEFAULT FALSE"
                     else:
                         alter += " DEFAULT ''"
                         
                stmt += f"        {alter};\n    END IF;"
                sql.append(stmt)
            else:
                # 3. Check Mismatches (Type/Nullable) - Advanced
                # Ignore for now to stick to "column does not exist" fixing.
                pass
                
    sql.append("END $$;")
    
    with open(output_sql, 'w') as f:
        f.write('\n'.join(sql))
    
    print(f"Migration script generated: {output_sql}")

if __name__ == "__main__":
    compare_schemas('schema_prod.json', 'schema_test.json', 'db/sync_test_schema.sql')
