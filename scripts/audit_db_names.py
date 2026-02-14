
import os
import ast
import glob

def get_db_modules():
    return glob.glob("db/gestione_*.py") + ["db/crypto_helpers.py", "db/supabase_manager.py"]

def get_exports(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    
    exports = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            exports.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    exports.add(target.id)
    return exports

def audit_module(filepath, all_exports):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        tree = ast.parse(content)
    
    defined_names = set()
    imported_names = set()
    used_names = set()
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defined_names.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
    
    # Simple heuristic for builtins and common modules
    builtins = {"print", "range", "len", "dict", "list", "set", "int", "float", "str", "bool", "Exception", "ValueError", "TypeError", "StopIteration", "enumerate", "zip", "sum", "min", "max", "abs", "round", "any", "all", "isinstance", "getattr", "setattr", "hasattr", "open", "None", "True", "False", "tuple"}
    
    missing = []
    for name in used_names:
        if name not in defined_names and name not in imported_names and name not in builtins:
            if name in all_exports:
                missing.append(name)
    
    return missing

def main():
    modules = get_db_modules()
    all_exports = {}
    for mod in modules:
        try:
            exports = get_exports(mod)
            for e in exports:
                all_exports[e] = mod
        except:
            pass
            
    print(f"Audit of {len(modules)} modules...")
    for mod in modules:
        try:
            missing = audit_module(mod, all_exports)
            if missing:
                print(f"\n[!] Module {mod} is missing imports for:")
                for m in missing:
                    print(f"  - {m} (Found in {all_exports[m]})")
        except Exception as e:
            print(f"Error auditing {mod}: {e}")

if __name__ == "__main__":
    main()
