import getpass
import sys
import os
import base64
import hashlib

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.gestione_db import get_db_connection, hash_password
from utils.crypto_manager import CryptoManager

def fix_login():
    print("--- FIX LOGIN ENCRYPTION ---")
    print("Questo script risolve l'errore 'Errore decryption' dopo un reset della password.")
    
    username = input("Username: ")
    
    # Check user existence
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT id_utente, salt, encrypted_master_key, password_hash FROM Utenti WHERE username = %s", (username,))
        user = cur.fetchone()
    
    if not user:
        print("Utente non trovato.")
        return

    print(f"\nUtente trovato: {username}")
    print("Scegli un'opzione:")
    print("1. Ho cambiato la password ma CONOSCO la vecchia password (Tenta recupero dati)")
    print("2. NON conosco la vecchia password (RESET TOTALE - I dati criptati andranno persi)")
    
    choice = input("Scelta (1/2): ")
    
    if choice == "1":
        attempt_recovery(user, username)
    elif choice == "2":
        force_reset(user, username)
    else:
        print("Scelta non valida.")

def attempt_recovery(user, username):
    print("\n--- RECUPERO DATI ---")
    old_password = getpass.getpass("Inserisci la VECCHIA password (quella usata prima del reset): ")
    current_password = getpass.getpass("Inserisci la NUOVA password (quella impostata con reset_password): ")
    
    try:
        crypto = CryptoManager()
        salt = base64.urlsafe_b64decode(user['salt'].encode())
        
        # 1. Derive OLD KEK
        print("Derivazione vecchia chiave...")
        old_kek = crypto.derive_key(old_password, salt)
        
        # 2. Decrypt Master Key
        print("Decriptazione Master Key...")
        encrypted_mk = base64.urlsafe_b64decode(user['encrypted_master_key'].encode())
        master_key = crypto.decrypt_master_key(encrypted_mk, old_kek)
        
        print("Master Key recuperata con successo!")
        
        # 3. Derive NEW KEK
        print("Derivazione nuova chiave...")
        new_kek = crypto.derive_key(current_password, salt)
        
        # 4. Re-encrypt Master Key
        print("Ricriptazione Master Key...")
        new_encrypted_mk_bytes = crypto.encrypt_master_key(master_key, new_kek)
        new_encrypted_mk = base64.urlsafe_b64encode(new_encrypted_mk_bytes).decode()
        
        # 5. Update DB
        with get_db_connection() as con:
            cur = con.cursor()
            # Update encrypted_master_key AND ensure password_hash matches current_password
            new_hash = hash_password(current_password)
            cur.execute("""
                UPDATE Utenti 
                SET encrypted_master_key = %s, password_hash = %s 
                WHERE id_utente = %s
            """, (new_encrypted_mk, new_hash, user['id_utente']))
            con.commit()
            
        print("\n[SUCCESS] Login ripristinato! Ora puoi accedere con la nuova password.")
        
    except Exception as e:
        print(f"\n[ERRORE] Recupero fallito: {e}")
        print("Probabilmente la vecchia password non è corretta o il salt è stato modificato.")

def force_reset(user, username):
    print("\n--- RESET TOTALE ---")
    print("ATTENZIONE: Questa operazione genererà una nuova Master Key.")
    print("Tutti i dati precedentemente criptati (Nomi Spese Fisse, Password SMTP, ecc.) NON saranno più leggibili.")
    confirm = input("Sei sicuro di voler procedere? (scrivi 'SI' per confermare): ")
    
    if confirm != "SI":
        print("Operazione annullata.")
        return
        
    new_password = getpass.getpass("Inserisci la NUOVA password da usare: ")
    
    # Ask for plain text data to overwrite encrypted fields if necessary
    print("\nPoiché i dati criptati saranno persi, inserisci i dati anagrafici per ripristinarli:")
    new_nome = input("Nome: ")
    new_cognome = input("Cognome: ")
    
    try:
        crypto = CryptoManager()
        
        # 1. Generate New Master Key
        master_key = crypto.generate_master_key()
        
        # 2. Generate New Salt
        salt_bytes = os.urandom(16)
        salt = base64.urlsafe_b64encode(salt_bytes).decode()
        
        # 3. Derive New KEK
        kek = crypto.derive_key(new_password, salt_bytes)
        
        # 4. Encrypt New Master Key
        encrypted_mk_bytes = crypto.encrypt_master_key(master_key, kek)
        encrypted_mk = base64.urlsafe_b64encode(encrypted_mk_bytes).decode()
        
        # 5. Encrypt User Data
        enc_nome = crypto.encrypt_data(new_nome, master_key)
        enc_cognome = crypto.encrypt_data(new_cognome, master_key)
        
        # 6. Update DB
        new_hash = hash_password(new_password)
        
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                UPDATE Utenti 
                SET password_hash = %s, 
                    salt = %s, 
                    encrypted_master_key = %s,
                    nome = %s,
                    cognome = %s
                WHERE id_utente = %s
            """, (new_hash, salt, encrypted_mk, enc_nome, enc_cognome, user['id_utente']))
            
            # Note: We are NOT clearing SpeseFisse or Configurazioni here. 
            # They will remain "corrupted" (unreadable) until overwritten.
            
            con.commit()
            
        print("\n[SUCCESS] Utente resettato. La nuova password è attiva.")
        print("NOTA: I dati criptati precedenti (es. nomi spese fisse) non saranno leggibili e appariranno come stringhe senza senso o daranno errore.")
        
    except Exception as e:
        print(f"\n[ERRORE] Reset fallito: {e}")

if __name__ == "__main__":
    fix_login()
