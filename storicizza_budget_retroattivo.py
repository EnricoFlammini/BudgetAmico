"""
Script per storicizzare retroattivamente i budget per tutti i mesi passati.
Questo script popola la tabella Budget_Storico con i limiti correnti
per tutti i mesi storici che hanno transazioni.

Eseguire questo script UNA SOLA VOLTA dopo la migrazione a v8.
"""

import sys
import os

# Aggiungi il percorso della directory Sviluppo al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.gestione_db import storicizza_budget_retroattivo, DB_FILE
import sqlite3


def main():
    print("=" * 60)
    print("STORICIZZAZIONE RETROATTIVA BUDGET")
    print("=" * 60)
    print()
    print("Questo script popolerà Budget_Storico con i limiti correnti")
    print("per tutti i mesi passati che hanno transazioni.")
    print()
    
    # Verifica che il database esista
    if not os.path.exists(DB_FILE):
        print(f"Database non trovato: {DB_FILE}")
        return
    
    # Ottieni tutte le famiglie
    try:
        with sqlite3.connect(DB_FILE) as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia, nome_famiglia FROM Famiglie")
            famiglie = cur.fetchall()
            
            if not famiglie:
                print("Nessuna famiglia trovata nel database.")
                return
            
            print(f"Trovate {len(famiglie)} famiglia/e:")
            for id_fam, nome_fam in famiglie:
                print(f"  - {nome_fam} (ID: {id_fam})")
            print()
            
            # Chiedi conferma
            risposta = input("Procedere con la storicizzazione? (s/n): ")
            if risposta.lower() != 's':
                print("Operazione annullata.")
                return
            
            print()
            print("Inizio storicizzazione...")
            print("-" * 60)
            
            # Storicizza per ogni famiglia
            for id_fam, nome_fam in famiglie:
                print(f"\nFamiglia: {nome_fam} (ID: {id_fam})")
                print("-" * 60)
                storicizza_budget_retroattivo(id_fam)
            
            print()
            print("=" * 60)
            print("STORICIZZAZIONE COMPLETATA")
            print("=" * 60)
            
    except Exception as e:
        print(f"\nErrore durante l'esecuzione: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
