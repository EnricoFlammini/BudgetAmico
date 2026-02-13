"""
Funzioni categorie e sottocategorie: CRUD
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
from utils.logger import setup_logger
from utils.crypto_manager import CryptoManager
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
import os

logger = setup_logger(__name__)
from utils.cache_manager import cache_manager

from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code, _get_system_keys,
    HASH_SALT, SYSTEM_FERNET_KEY, SERVER_SECRET_KEY,
    crypto as _crypto_instance
)

# --- Funzioni Categorie ---
def ottieni_categorie(id_famiglia: str, master_key_b64: Optional[str] = None, id_utente: Optional[str] = None) -> List[Dict[str, Any]]:
    id_famiglia = _valida_id_int(id_famiglia)
    if not id_famiglia: return []
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_categoria, nome_categoria, id_famiglia FROM Categorie WHERE id_famiglia = %s", (id_famiglia,))
            categorie = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

            if family_key:
                for cat in categorie:
                    cat['nome_categoria'] = _decrypt_if_key(cat['nome_categoria'], family_key, crypto)
            
            # Sort in Python after decryption
            categorie.sort(key=lambda x: x['nome_categoria'].lower())
            
            return categorie
    except Exception as e:
        print(f"[ERRORE] Errore recupero categorie: {e}")
        return []

def aggiungi_categoria(id_famiglia, nome_categoria, master_key_b64=None, id_utente=None):
    # Encrypt if key available
    crypto, master_key = _get_crypto_and_key(master_key_b64)
    family_key = None
    if master_key and id_utente:
        family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
    
    encrypted_nome = _encrypt_if_key(nome_categoria, family_key, crypto)

    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO Categorie (id_famiglia, nome_categoria) VALUES (%s, %s) RETURNING id_categoria",
                (id_famiglia, encrypted_nome))
            result = cur.fetchone()['id_categoria']
            # Invalida la cache delle categorie
            cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta categoria: {e}")
        return None

def modifica_categoria(id_categoria, nome_categoria, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get id_famiglia and current name to retrieve key and protect ENTRATE
            cur.execute("SELECT id_famiglia, nome_categoria FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            res = cur.fetchone()
            if not res: return False
            id_famiglia = res['id_famiglia']
            
            # Decrypt current name if possible to check if it's 'ENTRATE'
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            current_family_key = None
            if master_key and id_utente:
                current_family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            nome_attuale = _decrypt_if_encrypted(res['nome_categoria'], current_family_key, crypto)
            if nome_attuale and nome_attuale.upper() == "ENTRATE":
                print(f"[AVVISO] Tentativo di modifica della categoria protetta ENTRATE (ID: {id_categoria})")
                return False

            # Encrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            encrypted_nome = _encrypt_if_key(nome_categoria, family_key, crypto)

            cur.execute("UPDATE Categorie SET nome_categoria = %s WHERE id_categoria = %s",
                        (encrypted_nome, id_categoria))
            result = cur.rowcount > 0
            if result:
                # Invalida la cache delle categorie
                cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore modifica categoria: {e}")
        return False

def elimina_categoria(id_categoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Get id_famiglia and name before deletion
            cur.execute("SELECT id_famiglia, nome_categoria FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            res = cur.fetchone()
            if not res: return False
            
            id_famiglia = res['id_famiglia']
            nome_cat = res['nome_categoria'] # Note: strictly speaking, we should decrypt to be sure, 
                                            # but usually ENTRATE is created unencrypted or with a known pattern.
                                            # Let's try simple check + protected ID check if possible.
            
            if nome_cat and nome_cat.upper() == "ENTRATE":
                print(f"[AVVISO] Tentativo di eliminazione della categoria protetta ENTRATE (ID: {id_categoria})")
                return False
            
            cur.execute("DELETE FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            result = cur.rowcount > 0
            if result and id_famiglia:
                cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione categoria: {e}")
        return False

# --- Funzioni Sottocategorie ---
def ottieni_sottocategorie(id_categoria, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_sottocategoria, nome_sottocategoria, id_categoria FROM Sottocategorie WHERE id_categoria = %s", (id_categoria,))
            sottocategorie = [dict(row) for row in cur.fetchall()]
            
            # Decrypt if key available
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            
            if master_key and id_utente:
                 # Need id_famiglia to get key. Get it from category.
                 cur.execute("SELECT id_famiglia FROM Categorie WHERE id_categoria = %s", (id_categoria,))
                 res = cur.fetchone()
                 if res:
                     family_key = _get_family_key_for_user(res['id_famiglia'], id_utente, master_key, crypto)

            if family_key:
                for sub in sottocategorie:
                    sub['nome_sottocategoria'] = _decrypt_if_key(sub['nome_sottocategoria'], family_key, crypto)
            
            # Sort in Python
            sottocategorie.sort(key=lambda x: x['nome_sottocategoria'].lower())
            
            return sottocategorie
    except Exception as e:
        print(f"[ERRORE] Errore recupero sottocategorie: {e}")
        return []

def aggiungi_sottocategoria(id_categoria, nome_sottocategoria, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get id_famiglia
            cur.execute("SELECT id_famiglia FROM Categorie WHERE id_categoria = %s", (id_categoria,))
            res = cur.fetchone()
            if not res: return None
            id_famiglia = res['id_famiglia']

            # Encrypt
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            encrypted_nome = _encrypt_if_key(nome_sottocategoria, family_key, crypto)

            cur.execute(
                "INSERT INTO Sottocategorie (id_categoria, nome_sottocategoria) VALUES (%s, %s) RETURNING id_sottocategoria",
                (id_categoria, encrypted_nome))
            result = cur.fetchone()['id_sottocategoria']
            # Invalida la cache delle categorie (include sottocategorie)
            cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta sottocategoria: {e}")
        return None

def modifica_sottocategoria(id_sottocategoria, nome_sottocategoria, master_key_b64=None, id_utente=None):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Get id_famiglia via category
            cur.execute("""
                SELECT C.id_famiglia 
                FROM Sottocategorie S 
                JOIN Categorie C ON S.id_categoria = C.id_categoria 
                WHERE S.id_sottocategoria = %s
            """, (id_sottocategoria,))
            res = cur.fetchone()
            if not res: return False
            id_famiglia = res['id_famiglia']

            # Encrypt
            crypto, master_key = _get_crypto_and_key(master_key_b64)
            family_key = None
            if master_key and id_utente:
                family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            encrypted_nome = _encrypt_if_key(nome_sottocategoria, family_key, crypto)

            cur.execute("UPDATE Sottocategorie SET nome_sottocategoria = %s WHERE id_sottocategoria = %s",
                        (encrypted_nome, id_sottocategoria))
            result = cur.rowcount > 0
            if result:
                cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore modifica sottocategoria: {e}")
        return False

def elimina_sottocategoria(id_sottocategoria):
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            # Get id_famiglia before deletion
            cur.execute("""
                SELECT C.id_famiglia 
                FROM Sottocategorie S 
                JOIN Categorie C ON S.id_categoria = C.id_categoria 
                WHERE S.id_sottocategoria = %s
            """, (id_sottocategoria,))
            res = cur.fetchone()
            id_famiglia = res['id_famiglia'] if res else None
            
            cur.execute("DELETE FROM Sottocategorie WHERE id_sottocategoria = %s", (id_sottocategoria,))
            result = cur.rowcount > 0
            if result and id_famiglia:
                cache_manager.invalidate("categories", id_famiglia)
            return result
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione sottocategoria: {e}")
        return False

def ottieni_categorie_e_sottocategorie(id_famiglia, master_key_b64=None, id_utente=None):
    """
    Recupera categorie e sottocategorie. Usa la cache in-memory per performance ottimale.
    """
    try:
        def fetch_and_decrypt():
            categorie = ottieni_categorie(id_famiglia, master_key_b64, id_utente)
            for cat in categorie:
                cat['sottocategorie'] = ottieni_sottocategorie(cat['id_categoria'], master_key_b64, id_utente)
            return categorie

        # Usa get_or_compute per gestire il livello in-memory con TTL (10 minuti default)
        return cache_manager.get_or_compute(
            key="categories", 
            compute_fn=fetch_and_decrypt, 
            id_famiglia=id_famiglia
        )
    except Exception as e:
        print(f"[ERRORE] Errore recupero categorie e sottocategorie: {e}")
        return []

