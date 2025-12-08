file_path =r"c:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo\db\gestione_db.py"

# Check if file has BOM or encoding issues
with open(file_path, 'rb') as f:
    first_bytes = f.read(100)
    print("First 100 bytes:", first_bytes)
    
# Try to compile the file to see exact syntax error
import py_compile
try:
    py_compile.compile(file_path, doraise=True)
    print("File compiles successfully!")
except py_compile.PyCompileError as e:
    print(f"Compile error: {e}")
