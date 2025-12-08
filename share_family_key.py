"""
Script per condividere la chiave famiglia con l'utente esistente che non ce l'ha.
Da eseguire UNA SOLA VOLTA per ogni utente da riparare.

Richiede che un admin con la chiave famiglia esegua questo script.
"""
import getpass
from db.gestione_db import get_db_connection, _get_crypto_and_key, _get_family_key_for_user
from utils.crypto_manager import CryptoManager
import base64

def condividi_chiave_con_utente(id_admin: int, id_utente_target: int, id_famiglia: int, admin_password: str):
    """
    Condivide la chiave famiglia dall'admin all'utente target.
    """
    crypto = CryptoManager()
    
    # 1. Recupera la master key dell'admin
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT salt, encrypted_master_key FROM Utenti WHERE id_utente = %s", (id_admin,))
        admin_data = cur.fetchone()
        
        if not admin_data:
            print(f"[ERRORE] Admin {id_admin} non trovato")
            return False
        
        try:
            admin_salt = base64.urlsafe_b64decode(admin_data['salt'].encode())
            admin_kek = crypto.derive_key(admin_password, admin_salt)
            admin_encrypted_mk = base64.urlsafe_b64decode(admin_data['encrypted_master_key'].encode())
            admin_master_key = crypto.decrypt_master_key(admin_encrypted_mk, admin_kek)
            print(f"[OK] Master key admin decriptata")
        except Exception as e:
            print(f"[ERRORE] Password admin non valida: {e}")
            return False
    
    # 2. Recupera la family key dell'admin
    family_key = _get_family_key_for_user(id_famiglia, id_admin, admin_master_key, crypto)
    if not family_key:
        print(f"[ERRORE] L'admin non ha la chiave famiglia per la famiglia {id_famiglia}")
        return False
    print(f"[OK] Family key dell'admin recuperata")
    
    # 3. Recupera la master key dell'utente target
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT salt, encrypted_master_key FROM Utenti WHERE id_utente = %s", (id_utente_target,))
        target_data = cur.fetchone()
        
        if not target_data or not target_data['salt'] or not target_data['encrypted_master_key']:
            print(f"[ERRORE] Utente target {id_utente_target} non ha salt/encrypted_master_key")
            return False
    
    # Nota: non possiamo decriptare la master key dell'utente target senza la sua password.
    # Dobbiamo chiedere la password dell'utente target.
    target_password = getpass.getpass(f"Inserisci la password dell'utente {id_utente_target}: ")
    
    try:
        target_salt = base64.urlsafe_b64decode(target_data['salt'].encode())
        target_kek = crypto.derive_key(target_password, target_salt)
        target_encrypted_mk = base64.urlsafe_b64decode(target_data['encrypted_master_key'].encode())
        target_master_key = crypto.decrypt_master_key(target_encrypted_mk, target_kek)
        print(f"[OK] Master key utente target decriptata")
    except Exception as e:
        print(f"[ERRORE] Password utente target non valida: {e}")
        return False
    
    # 4. Cripta la family key con la master key dell'utente target
    family_key_b64 = base64.b64encode(family_key).decode('utf-8')
    encrypted_family_key = crypto.encrypt_data(family_key_b64, target_master_key)
    
    # 5. Aggiorna il record dell'utente target
    with get_db_connection() as con:
        cur = con.cursor()
        cur.execute("""
            UPDATE Appartenenza_Famiglia 
            SET chiave_famiglia_criptata = %s 
            WHERE id_utente = %s AND id_famiglia = %s
        """, (encrypted_family_key, id_utente_target, id_famiglia))
        con.commit()
        print(f"[OK] Chiave famiglia condivisa con utente {id_utente_target}")
        return True


if __name__ == "__main__":
    print("=== Condivisione Chiave Famiglia ===")
    print()
    
    id_admin = int(input("ID Admin (che ha la chiave): "))
    id_utente_target = int(input("ID Utente Target (senza chiave): "))
    id_famiglia = int(input("ID Famiglia: "))
    
    admin_password = getpass.getpass(f"Password Admin (id={id_admin}): ")
    
    condividi_chiave_con_utente(id_admin, id_utente_target, id_famiglia, admin_password)
