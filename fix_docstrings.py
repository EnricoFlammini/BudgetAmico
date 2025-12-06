import re

file_path = r"c:\Users\Enrico.Flammini\OneDrive - GATTINONI\Documents\Progetti\Progetto Budget\BudgetAmico\Sviluppo\db\gestione_db.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace multi-line docstrings ("""\n...\n""") with comments
# Match triple quotes that span multiple lines
pattern = r'(\s+)"""\s*\n\s*(.*?)\s*\n\s*"""'
replacement = r'\1# \2'
content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Replace single-line docstrings ("""...""") with comments  
pattern2 = r'(\s+)"""([^"]+)"""'
replacement2 = r'\1# \2'
content = re.sub(pattern2, replacement2, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Docstrings replaced successfully!")
