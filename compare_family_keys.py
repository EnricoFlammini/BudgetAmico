"""
Script di debug per verificare che le family key decriptate siano uguali.
"""
import getpass
import base64
from db.gestione_db import get_db_connection
from utils.crypto_manager import CryptoManager

def compare_family_keys():
    id_utente_1 = int(input("ID Primo Utente (admin): "))
    password_1 = getpass.getpass(f"Password utente {id_utente_1}: ")
    
    id_utente_2 = int(input("ID Secondo Utente: "))
    password_2 = getpass.getpass(f"Password utente {id_utente_2}: ")
    
    id_famiglia = int(input("ID Famiglia: "))
    
    crypto = CryptoManager()
    
    with get_db_connection() as con:
        cur = con.cursor()
        
        # Decripta family key dell'utente 1
        cur.execute("SELECT salt, encrypted_master_key FROM Utenti WHERE id_utente = %s", (id_utente_1,))
        user1 = cur.fetchone()
        
        cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente_1, id_famiglia))
        fk1_enc = cur.fetchone()
        
        try:
            salt1 = base64.urlsafe_b64decode(user1['salt'].encode())
            kek1 = crypto.derive_key(password_1, salt1)
            enc_mk1 = base64.urlsafe_b64decode(user1['encrypted_master_key'].encode())
            master_key1 = crypto.decrypt_master_key(enc_mk1, kek1)
            
            fk1_b64 = crypto.decrypt_data(fk1_enc['chiave_famiglia_criptata'], master_key1)
            family_key1 = base64.b64decode(fk1_b64)
            print(f"\n[OK] Family key utente {id_utente_1}: {family_key1[:20]}...")
        except Exception as e:
            print(f"[ERRORE] Impossibile decriptare family key utente {id_utente_1}: {e}")
            return
        
        # Decripta family key dell'utente 2
        cur.execute("SELECT salt, encrypted_master_key FROM Utenti WHERE id_utente = %s", (id_utente_2,))
        user2 = cur.fetchone()
        
        cur.execute("SELECT chiave_famiglia_criptata FROM Appartenenza_Famiglia WHERE id_utente = %s AND id_famiglia = %s", (id_utente_2, id_famiglia))
        fk2_enc = cur.fetchone()
        
        try:
            salt2 = base64.urlsafe_b64decode(user2['salt'].encode())
            kek2 = crypto.derive_key(password_2, salt2)
            enc_mk2 = base64.urlsafe_b64decode(user2['encrypted_master_key'].encode())
            master_key2 = crypto.decrypt_master_key(enc_mk2, kek2)
            
            fk2_b64 = crypto.decrypt_data(fk2_enc['chiave_famiglia_criptata'], master_key2)
            family_key2 = base64.b64decode(fk2_b64)
            print(f"[OK] Family key utente {id_utente_2}: {family_key2[:20]}...")
        except Exception as e:
            print(f"[ERRORE] Impossibile decriptare family key utente {id_utente_2}: {e}")
            return
        
        # Confronta
        if family_key1 == family_key2:
            print("\n✅ LE FAMILY KEY SONO IDENTICHE!")
        else:
            print("\n❌ LE FAMILY KEY SONO DIVERSE!")
            print(f"   Key 1: {family_key1.hex()}")
            print(f"   Key 2: {family_key2.hex()}")

if __name__ == "__main__":
    compare_family_keys()
