"""
Script per verificare lo stato della crittografia nel database Supabase.
Controlla che i dati sensibili siano correttamente crittografati.
"""
import os
import sys

# Forza encoding UTF-8 per output console Windows
sys.stdout.reconfigure(encoding='utf-8')

# Aggiungi il path per gli import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Carica variabili d'ambiente
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from db.supabase_manager import SupabaseManager

def check_encrypted_field(value, field_name):
    """Verifica se un valore sembra essere crittografato (base64 Fernet)."""
    if value is None:
        return "NULL", "⚪"
    if isinstance(value, (int, float)):
        return "NUMERICO", "🔴"  # I numeri dovrebbero essere crittografati come stringhe
    if not isinstance(value, str):
        return f"TIPO: {type(value)}", "🟡"
    
    # I dati Fernet sono base64 e iniziano con 'gAAAAA'
    if value.startswith('gAAAAA') and len(value) > 50:
        return "CRITTOGRAFATO", "🟢"
    elif len(value) == 0:
        return "VUOTO", "⚪"
    else:
        preview = value[:25] + "..." if len(value) > 25 else value
        return f"CHIARO: '{preview}'", "🔴"

def safe_query(cur, query, fallback_query=None):
    """Esegue una query con fallback se fallisce."""
    try:
        cur.execute(query)
        return cur.fetchall()
    except Exception as e:
        if fallback_query:
            try:
                cur.execute(fallback_query)
                return cur.fetchall()
            except:
                pass
        return None

def main():
    print("=" * 70)
    print("VERIFICA CRITTOGRAFIA DATABASE SUPABASE")
    print("=" * 70)
    
    if not SupabaseManager.test_connection():
        print("[ERRORE] Impossibile connettersi al database!")
        return
    
    print("[OK] Connessione al database\n")
    
    conn = SupabaseManager.get_connection()
    if not conn:
        print("[ERRORE] Errore apertura connessione!")
        return
    
    try:
        cur = conn.cursor()
        
        # Prima otteniamo lo schema delle tabelle
        print("Recupero schema tabelle...")
        
        tables_to_check = [
            ("Conti", ["nome_conto"]),
            ("Transazioni", ["descrizione", "importo"]),
            ("ContiCondivisi", ["nome_conto", "saldo"]),
            ("Categorie", ["nome_categoria"]),
            ("SottoCategorie", ["nome_sottocategoria"]),
            ("Budget", ["limite"]),
            ("Portafogli", ["nome_portafoglio"]),
            ("Prestiti", ["nome_prestito", "importo_totale"]),
            ("Immobili", ["nome_immobile", "valore"]),
            ("FondiPensione", ["nome_fondo", "valore_attuale"]),
            ("Asset", ["ticker", "quantita", "prezzo_medio_acquisto"]),
            ("ChiaviFamiglia", ["chiave_crittografata"]),
        ]
        
        for table_name, fields_to_check in tables_to_check:
            print(f"\n{'=' * 50}")
            print(f"📁 TABELLA: {table_name}")
            print("=" * 50)
            
            try:
                # Prima verifichiamo quali colonne esistono
                cur.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name.lower()}'
                """)
                existing_cols = [row['column_name'] for row in cur.fetchall()]
                
                if not existing_cols:
                    print(f"  [WARN] Tabella non trovata o vuota")
                    continue
                
                # Costruisci query con colonne esistenti
                cols_to_select = []
                # Trova colonna ID
                id_col = next((c for c in existing_cols if c.startswith('id_')), None)
                if id_col:
                    cols_to_select.append(id_col)
                
                # Aggiungi colonne da verificare che esistono
                valid_fields = [f for f in fields_to_check if f.lower() in [c.lower() for c in existing_cols]]
                cols_to_select.extend(valid_fields)
                
                if len(cols_to_select) < 2:
                    print(f"  [INFO] Colonne trovate: {existing_cols}")
                    continue
                
                query = f"SELECT {', '.join(cols_to_select)} FROM {table_name} LIMIT 5"
                cur.execute(query)
                rows = cur.fetchall()
                
                if not rows:
                    print("  (nessun record)")
                    continue
                
                for row in rows:
                    id_val = row[cols_to_select[0]] if cols_to_select else "?"
                    parts = [f"ID {id_val}:"]
                    
                    for field in valid_fields:
                        if field in row.keys():
                            status, icon = check_encrypted_field(row[field], field)
                            parts.append(f"{field}={icon} {status}")
                    
                    print(f"  {', '.join(parts)}")
                    
            except Exception as e:
                print(f"  [ERRORE] {e}")
        
        print("\n" + "=" * 70)
        print("LEGENDA:")
        print("  🟢 = Dati correttamente crittografati (Fernet)")
        print("  🔴 = Dati in chiaro (potenziale problema)")
        print("  🟡 = Tipo dati inatteso")
        print("  ⚪ = Valore NULL o vuoto")
        print("=" * 70)
        
    except Exception as e:
        print(f"[ERRORE] {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
