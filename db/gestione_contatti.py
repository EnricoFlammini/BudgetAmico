"""
Funzioni rubrica contatti: CRUD
Modulo estratto da gestione_db.py — Refactoring v0.51
"""
from db.supabase_manager import get_db_connection
from utils.logger import setup_logger
from utils.crypto_manager import CryptoManager
from typing import List, Dict, Any, Optional, Tuple, Union
import datetime
import os

logger = setup_logger(__name__)
import base64
from db.crypto_helpers import (
    _encrypt_if_key, _decrypt_if_key, 
    _get_crypto_and_key, _valida_id_int,
    compute_blind_index, encrypt_system_data, decrypt_system_data,
    generate_unique_code,
    SERVER_SECRET_KEY,
    crypto as _crypto_instance,
    _get_family_key_for_user
)

# Importazioni da altri moduli per evitare NameError
from db.gestione_famiglie import ottieni_prima_famiglia_utente


def crea_contatto(id_utente: str, nome: str, cognome: str, societa: str, iban: str, email: str, telefono: str, tipo_condivisione: str, contatti_condivisi_ids: list = None, id_famiglia: str = None, master_key_b64: str = None, colore: str = '#424242') -> bool:
    """
    Crea un nuovo contatto.
    tipo_condivisione: 'privato', 'famiglia', 'selezione'
    """
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        
        # Determina chiave di crittografia
        key_to_use = master_key
        
        # Se condiviso 'famiglia' o 'selezione', usa Family Key se disponibile
        if tipo_condivisione in ['famiglia', 'selezione'] and id_famiglia and master_key:
             family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
             if family_key:
                 key_to_use = family_key

        iban_enc = _encrypt_if_key(iban, key_to_use, crypto) if iban else None
        nome_enc = _encrypt_if_key(nome, key_to_use, crypto)
        cognome_enc = _encrypt_if_key(cognome, key_to_use, crypto) if cognome else None
        societa_enc = _encrypt_if_key(societa, key_to_use, crypto) if societa else None
        email_enc = _encrypt_if_key(email, key_to_use, crypto) if email else None
        telefono_enc = _encrypt_if_key(telefono, key_to_use, crypto) if telefono else None
        
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Tentativo di inserimento con RETURNING (Postgres/Supabase standard)
            # Usiamo SAVEPOINT per evitare "current transaction is aborted" in caso di fallimento prima del fallback
            try:
                cur.execute("SAVEPOINT insert_contact")
                cur.execute("""
                    INSERT INTO Contatti (id_utente, nome_encrypted, cognome_encrypted, societa_encrypted, iban_encrypted, email_encrypted, telefono_encrypted, tipo_condivisione, id_famiglia, colore)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_contatto
                """, (id_utente, nome_enc, cognome_enc, societa_enc, iban_enc, email_enc, telefono_enc, tipo_condivisione, id_famiglia if tipo_condivisione != 'privato' else None, colore))
                row = cur.fetchone()
                id_contatto = row['id_contatto']
                cur.execute("RELEASE SAVEPOINT insert_contact")
            except Exception as e:
                 # Se fallisce (es. SQLite vecchio o errore PG vero), proviamo fallback ma DOPO rollback al savepoint
                 try:
                     cur.execute("ROLLBACK TO SAVEPOINT insert_contact")
                 except: pass # Se il DB non supporta savepoints (es. sqlite molto vecchio), ignoriamo
                 
                 logger.warning(f"Insert con RETURNING fallito ({e}), tentativo fallback standard...")
                 
                 # Fallback standard (senza returning)
                 cur.execute("""
                    INSERT INTO Contatti (id_utente, nome_encrypted, cognome_encrypted, societa_encrypted, iban_encrypted, email_encrypted, telefono_encrypted, tipo_condivisione, id_famiglia, colore)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (id_utente, nome_enc, cognome_enc, societa_enc, iban_enc, email_enc, telefono_enc, tipo_condivisione, id_famiglia if tipo_condivisione != 'privato' else None, colore))
                 id_contatto = cur.lastrowid
            
            # Gestione Condivisione Selezione
            if tipo_condivisione == 'selezione' and contatti_condivisi_ids:
                for uid in contatti_condivisi_ids:
                    # Avoid self-share
                    if int(uid) != int(id_utente):
                        cur.execute("INSERT INTO CondivisioneContatto (id_contatto, id_utente) VALUES (%s, %s)", (id_contatto, uid))
            
            con.commit()
            return True
            
    except Exception as e:
        logger.error(f"Errore crea_contatto: {e}")
        return False

def ottieni_contatti_utente(id_utente: str, master_key_b64: str = None) -> List[Dict[str, Any]]:
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        id_famiglia = ottieni_prima_famiglia_utente(id_utente)
        family_key = None
        if id_famiglia and master_key:
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)

        with get_db_connection() as con:
            cur = con.cursor()
            
            # 1. Privati e miei condivisi
            cur.execute("SELECT * FROM Contatti WHERE id_utente = %s", (id_utente,))
            miei = [dict(r) for r in cur.fetchall()]
            
            # 2. Condivisi 'famiglia' da altri
            altri_fam = []
            if id_famiglia:
                cur.execute("""
                    SELECT * FROM Contatti 
                    WHERE tipo_condivisione = 'famiglia' 
                      AND id_famiglia = %s 
                      AND id_utente != %s
                """, (id_famiglia, id_utente))
                altri_fam = [dict(r) for r in cur.fetchall()]
            
            # 3. Condivisi 'selezione' con me
            cur.execute("""
                SELECT C.* 
                FROM Contatti C
                JOIN CondivisioneContatto CC ON C.id_contatto = CC.id_contatto
                WHERE CC.id_utente = %s
            """, (id_utente,))
            altri_sel = [dict(r) for r in cur.fetchall()]
            
            unici_map = {}
            for c in miei + altri_fam + altri_sel:
                unici_map[c['id_contatto']] = c
            
            unici = unici_map.values()
            

            final_list = []
            for c in unici:
                iban_enc = c.get('iban_encrypted')
                # Try new encrypted columns, fallback to old if missing (for resilience during migration)
                nome_enc = c.get('nome_encrypted')
                cognome_enc = c.get('cognome_encrypted')
                societa_enc = c.get('societa_encrypted')
                email_enc = c.get('email_encrypted')
                telefono_enc = c.get('telefono_encrypted')

                share_type = c['tipo_condivisione']
                owner = c['id_utente']
                
                # Decrypt Logic
                key = master_key 
                
                if share_type in ['famiglia', 'selezione']:
                     key = family_key
                elif owner == int(id_utente) and share_type == 'privato':
                     key = master_key
                
                def decrypt_safe(val_enc):
                    if not val_enc: return ""
                    if not key: return "**Encrypted**"
                    try:
                        return _decrypt_if_key(val_enc, key, crypto, silent=True)
                    except:
                        # Fallback: maybe it's not encrypted (during migration) or key is wrong
                        # Check if it looks like fernet token? No easy way.
                        # Assume if it fails, return as is (if it was plaintext rename).
                         return val_enc

                # Map back to clean keys
                c['iban'] = decrypt_safe(iban_enc) if iban_enc else ""
                c['nome'] = decrypt_safe(nome_enc) if nome_enc else c.get('nome', '')
                c['cognome'] = decrypt_safe(cognome_enc) if cognome_enc else c.get('cognome', '')
                c['societa'] = decrypt_safe(societa_enc) if societa_enc else c.get('societa', '')
                c['email'] = decrypt_safe(email_enc) if email_enc else c.get('email', '')
                c['telefono'] = decrypt_safe(telefono_enc) if telefono_enc else c.get('telefono', '')
                
                # Handle [ENCRYPTED] error return from helper
                for k in ['iban', 'nome', 'cognome', 'societa', 'email', 'telefono']:
                     if c[k] == "[ENCRYPTED]": c[k] = "**Encrypted**"

                c['condiviso_con'] = []
                if owner == int(id_utente) and c['tipo_condivisione'] == 'selezione':
                    cur.execute("SELECT id_utente FROM CondivisioneContatto WHERE id_contatto = %s", (c['id_contatto'],))
                    c['condiviso_con'] = [r['id_utente'] for r in cur.fetchall()]

                final_list.append(c)
                
            return final_list
            
    except Exception as e:
        logger.error(f"Errore ottieni_contatti: {e}")
        return []

def modifica_contatto(id_contatto: int, id_utente: str, dati: dict, master_key_b64: str = None) -> bool:
    try:
        crypto, master_key = _get_crypto_and_key(master_key_b64)
        id_famiglia = dati.get('id_famiglia') 
        if not id_famiglia:
             id_famiglia = ottieni_prima_famiglia_utente(id_utente)

        # Verify ownership
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente FROM Contatti WHERE id_contatto = %s", (id_contatto,))
            row = cur.fetchone()
            if not row or row['id_utente'] != int(id_utente):
                return False

            # Update logic
            nome = dati['nome']
            cognome = dati.get('cognome')
            societa = dati.get('societa')
            email = dati.get('email')
            telefono = dati.get('telefono')
            tipo_condivisione = dati['tipo_condivisione']
            condivisi_ids = dati.get('condivisi_ids', [])
            iban = dati.get('iban')
            colore = dati.get('colore', '#424242')
            
            # Re-encrypt IBAN based on new share type
            key_to_use = master_key
            if tipo_condivisione in ['famiglia', 'selezione'] and id_famiglia and master_key:
                 fk = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
                 if fk: key_to_use = fk
            
            iban_enc = _encrypt_if_key(iban, key_to_use, crypto) if iban else None
            nome_enc = _encrypt_if_key(nome, key_to_use, crypto)
            cognome_enc = _encrypt_if_key(cognome, key_to_use, crypto) if cognome else None
            societa_enc = _encrypt_if_key(societa, key_to_use, crypto) if societa else None
            email_enc = _encrypt_if_key(email, key_to_use, crypto) if email else None
            telefono_enc = _encrypt_if_key(telefono, key_to_use, crypto) if telefono else None
            
            cur.execute("""
                UPDATE Contatti 
                SET nome_encrypted=%s, cognome_encrypted=%s, societa_encrypted=%s, email_encrypted=%s, telefono_encrypted=%s, 
                    tipo_condivisione=%s, iban_encrypted=%s, id_famiglia=%s, colore=%s
                WHERE id_contatto=%s
            """, (nome_enc, cognome_enc, societa_enc, email_enc, telefono_enc, tipo_condivisione, iban_enc, id_famiglia if tipo_condivisione != 'privato' else None, colore, id_contatto))
            
            # Aggiorna Condivisione
            cur.execute("DELETE FROM CondivisioneContatto WHERE id_contatto = %s", (id_contatto,))
            if tipo_condivisione == 'selezione' and condivisi_ids:
                 for uid in condivisi_ids:
                     if int(uid) != int(id_utente):
                        cur.execute("INSERT INTO CondivisioneContatto (id_contatto, id_utente) VALUES (%s, %s)", (id_contatto, uid))
            
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore modifica_contatto: {e}")
        return False

def elimina_contatto(id_contatto: int, id_utente: str) -> bool:
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT id_utente FROM Contatti WHERE id_contatto = %s", (id_contatto,))
            row = cur.fetchone()
            if not row or row['id_utente'] != int(id_utente): return False
            
            cur.execute("DELETE FROM Contatti WHERE id_contatto = %s", (id_contatto,))
            con.commit()
            return True
    except Exception as e:
        logger.error(f"Errore elimina_contatto: {e}")
        return False

