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

from db.gestione_db import storicizza_budget_retroattivo, get_db_connection
from db.supabase_manager import SupabaseManager


def main():
    print("=" * 60)
    print("STORICIZZAZIONE RETROATTIVA BUDGET (PostgreSQL)")
    print("=" * 60)
    print()
    print("Questo script popolerà Budget_Storico con i limiti correnti")
    print("per tutti i mesi passati che hanno transazioni.")
    print()
    
    # Verifica connessione
    if not SupabaseManager.test_connection():
        print("Errore: Impossibile connettersi al database.")
        return
    
    # Ottieni tutte le famiglie
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_famiglia, nome_famiglia FROM Famiglie")
            famiglie = cur.fetchall()
            
            if not famiglie:
                print("Nessuna famiglia trovata nel database.")
                return
            
            print(f"Trovate {len(famiglie)} famiglia/e:")
            for row in famiglie:
                # Supabase restituisce dizionari (RealDictCursor)
                id_fam = row['id_famiglia']
                nome_fam = row['nome_famiglia']
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
            for row in famiglie:
                id_fam = row['id_famiglia']
                nome_fam = row['nome_famiglia']
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
