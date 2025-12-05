import inspect
from db.gestione_db import aggiungi_prestito

print(f"Function: {aggiungi_prestito}")
print(f"Signature: {inspect.signature(aggiungi_prestito)}")
print(f"File: {inspect.getfile(aggiungi_prestito)}")
print(f"Line: {inspect.getsourcelines(aggiungi_prestito)[1]}")
