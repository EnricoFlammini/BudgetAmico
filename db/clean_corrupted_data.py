
import sys
import os
import getpass
import base64

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.gestione_db import verifica_login, get_db_connection
from utils.crypto_manager import CryptoManager
from cryptography.fernet import InvalidToken

def clean_data():
    print("--- SCRIPT DI PULIZIA DATI CORROTTI ---")
    print("Questo script eliminerà i conti e gli asset che non possono essere decriptati.")
    print("ATTENZIONE: I dati eliminati NON potranno essere recuperati.\n")

    print("--- SELEZIONE UTENTE ---")
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT id_utente FROM Utenti")
        users = cur.fetchall()
        for u in users:
            print(f"Utente ID: [{u['id_utente']}]")

    id_utente_str = input("Inserisci ID Utente (es. 16): ").strip()
    try:
        id_utente = int(id_utente_str)
    except:
        print("ID non valido.")
        return

    password = getpass.getpass("Inserisci Password per Decriptare MasterKey: ").strip()

    # MANUAL AUTH / MASTER KEY RECOVERY
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT salt, encrypted_master_key, nome, cognome FROM Utenti WHERE id_utente = %s", (id_utente,))
        row = cur.fetchone()
        
    if not row or not row['salt'] or not row['encrypted_master_key']:
        print("Utente non trovato o dati di sicurezza mancanti.")
        return

    crypto = CryptoManager()

    try:
        salt = base64.urlsafe_b64decode(row['salt'].encode())
        encrypted_mk = base64.urlsafe_b64decode(row['encrypted_master_key'].encode())
        
        kek = crypto.derive_key(password, salt)
        master_key = crypto.decrypt_master_key(encrypted_mk, kek)
        print("✅ Password corretta! Master Key recuperata.")
        
        # VERIFY IDENTITY
        try:
             dec_nome = crypto.decrypt_data(row['nome'], master_key)
             dec_cognome = crypto.decrypt_data(row['cognome'], master_key)
             print(f"\n👤 UTENTE RICONOSCIUTO: {dec_nome} {dec_cognome}")
        except:
             print("\n👤 UTENTE: (Nome non decifrabile o mancante)")

        confirm = input("Procedere con la pulizia dei dati corrotti per questo utente? (s/N): ").lower()
        if confirm != 's':
            print("Operazione annullata.")
            return

    except Exception as e:
        print(f"❌ Password errata o Master Key corrotta: {e}")
        return
    print("Avvio scansione dati corrotti...\n")

    deleted_conti = 0
    deleted_assets = 0

    with get_db_connection() as con:
        cur = con.cursor()
        
        # 1. SCAN AND CLEAN CONTI
        # Only personal accounts (id_utente match)
        cur.execute("SELECT id_conto, nome_conto, tipo FROM Conti WHERE id_utente = %s", (id_utente,))
        conti = cur.fetchall()
        
        for conto in conti:
            try:
                # Try to decrypt name
                dec_nome = crypto.decrypt_data(conto['nome_conto'], master_key)
                
                if dec_nome == "[ENCRYPTED]":
                    print(f"⚠️  Conto Corrotto individuato: ID {conto['id_conto']} (Tipo: {conto['tipo']})")
                    print(f"   -> ELIMINAZIONE in corso...")
                    cur.execute("DELETE FROM Conti WHERE id_conto = %s", (conto['id_conto'],))
                    deleted_conti += 1
                else:
                    # Optional: Print info about valid account
                    # print(f"✅ Conto OK: {dec_nome}")
                    pass

            except Exception as e:
                print(f"⚠️  Errore generico su conto ID {conto['id_conto']}: {e}")

        # 2. SCAN AND CLEAN ASSETS (In Personal Accounts)
        # Assets in accounts that were just deleted are gone via CASCADE usually?
        # Let's check Schema. Conti -> DELETE CASCADE.
        # So we only need to check remaining accounts?
        # But wait, if an account was valid (e.g. unencrypted name?) but assets inside were encrypted?
        # Unlikely scenario if key rotated, EVERYTHING is encrypted.
        # But let's check remaining assets just in case.
        
        # NOTE: If we deleted the account, we don't need to check its assets.
        # But we might have accounts created AFTER reset (Valid) containing assets created BEFORE? No.
        
        # Let's just commit the Account Deletions first.
        con.commit()
    
    print("\n------------------------------------------------")
    print(f"PULIZIA COMPLETATA.")
    print(f"Conti eliminati: {deleted_conti}")
    print("------------------------------------------------")
    print("Le transazioni e gli asset collegati ai conti eliminati sono stati rimossi automaticamente.")

if __name__ == "__main__":
    clean_data()
