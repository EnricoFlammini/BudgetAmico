import tokenize

file_path = r'c:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo\db\gestione_db.py'

print(f"Checking file: {file_path}")
with open(file_path, 'rb') as f:
    try:
        for token in tokenize.tokenize(f.readline):
            pass
        print("No syntax errors found by tokenize.")
    except tokenize.TokenError as e:
        print(f"TokenError: {e}")
        # The error message usually contains the position
    except Exception as e:
        print(f"Error: {e}")
