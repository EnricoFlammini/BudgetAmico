
import os
import sys
from dotenv import load_dotenv

# Load env BEFORE importing db/gestione_db to ensure SERVER_SECRET_KEY is available
load_dotenv()

import flet as ft
from db.gestione_db import (
    get_db_connection, 
    _get_family_key_for_user, 
    ottieni_tutti_i_conti_utente,
    _encrypt_if_key, 
    _decrypt_if_key,
    compute_blind_index
)
from utils.crypto_manager import CryptoManager
import getpass
import base64

def migra_asset_utente():
    print("=== STRUMENTO MIGRAZIONE ASSET FAMIGLIA ===")
    print("Questo script converte gli asset criptati con la chiave personale")
    print("in asset criptati con la Chiave Famiglia, per renderli visibili a tutti.")
    print("\n")
    
    username = input("Inserisci Username (es. roberta): ").strip()
    password = getpass.getpass("Inserisci Password: ").strip()
    
    # 1. Autenticazione e Derivazione Chiave
    print(f"\n--> Autenticazione per '{username}'...")
    try:
        # Calcola Blind Index
        username_bindex = compute_blind_index(username)
        if not username_bindex:
             # Fallback manuale se .env fallisce ancora (giusto per sicurezza)
             import hashlib
             # Assumiamo una stringa vuota se salt manca, o cerchiamo di non crashare
             # Ma qui dovrebbe andare se load_dotenv ha funzionato.
             pass

        with get_db_connection() as con:
            cur = con.cursor()
            
            # Cerca per Blind Index
            # Se username_bindex è None (es. chiave mancante), la query non troverà nulla.
            cur.execute("SELECT id_utente, password_hash, salt, encrypted_master_key FROM Utenti WHERE username_bindex = %s", (username_bindex,))
            user = cur.fetchone()
            
            if not user:
                print(f"[ERRORE] Utente '{username}' non trovato nel database.")
                # Debug help
                cur.execute("SELECT username_bindex FROM Utenti")
                # Non possiamo stampare i nomi in chiaro qui perché non li abbiamo...
                print("Suggerimento: Verifica di aver digitato esattamente lo username usato in registrazione.")
                return

            id_utente = user['id_utente']
            salt_stored = user['salt']
            encrypted_mk_stored = user['encrypted_master_key']

            # --- DECODING SALT & MK ---
            # Salt e Encrypted MK sono salvati come Base64 string nel DB (vedi registra_utente)
            try:
                salt = base64.urlsafe_b64decode(salt_stored)
                encrypted_mk = base64.urlsafe_b64decode(encrypted_mk_stored)
            except Exception as e:
                print(f"[ERRORE] Corruzione dati utente (Salt/MK non valido): {e}")
                return

            # --- DERIVAZIONE KEK (Key Encryption Key) ---
            crypto = CryptoManager()
            kek = crypto.derive_key(password, salt)
            
            # --- SBLOCCO MASTER KEY ---
            try:
                # Tenta di decriptare la Master Key usando la KEK derivata dalla password
                master_key = crypto.decrypt_master_key(encrypted_mk, kek)
                print("--> Password corretta! Master Key sbloccata.")
            except Exception:
                print("\n[ERRORE] PASSWORD ERRATA.")
                print("La password inserita non è in grado di sbloccare la chiave crittografica.")
                return
            
            # Convert MK to bytes for functions (decrypt_master_key returns bytes)
            # But functions often check if it's string/bytes. Keep as bytes is safest for internal calls.
            # However _get_family_key might expect the base64 string rep if passed as arg?
            # Looking at gestione_db: _get_family_key_for_user(..., master_key, crypto) 
            # where master_key is usually bytes if internal, or passed as b64 from session.
            # _get_family_key_for_user logic: decrypts 'chiave_famiglia_criptata' using 'master_key' arg.
            # decrypt_data handles both.
            
            # Get Family Key
            cur.execute("SELECT id_famiglia FROM Appartenenza_Famiglia WHERE id_utente = %s", (id_utente,))
            fam_rows = cur.fetchall()
            if not fam_rows:
                 print("[ERRORE] L'utente non appartiene a nessuna famiglia.")
                 return
            
            id_famiglia = fam_rows[0]['id_famiglia']
            family_key = _get_family_key_for_user(id_famiglia, id_utente, master_key, crypto)
            
            if not family_key:
                print("[ERRORE] Impossibile recuperare la Chiave Famiglia (forse non creata corretta?).")
                return
            
            print(f"--> Chiave Famiglia recuperata (ID Famiglia: {id_famiglia}).")
            
            # 2. Recupero Conti Famiglia
            print("\n--> Ricerca conti di investimento familiari...")
            # Nota: La tabella Conti non ha id_famiglia. I conti sono personali.
            # Se l'utente è in famiglia, i suoi conti investimento sono automaticamente "di famiglia" (aggregati).
            cur.execute("""
                SELECT id_conto, nome_conto 
                FROM Conti 
                WHERE id_utente = %s AND tipo = 'Investimento'
            """, (id_utente,))
            conti = cur.fetchall()
            
            if not conti:
                print("Nessun conto di investimento familiare trovato.")
                return

            totale_aggiornati = 0
            
            for conto in conti:
                id_conto = conto['id_conto']
                nome_conto = conto['nome_conto']
                
                # --- UPDATE NOME CONTO (NEW) ---
                # Check decryption of nome_conto with Master Key
                nome_conto_dec = _decrypt_if_key(nome_conto, master_key, crypto, silent=True)
                
                if nome_conto_dec == "[ENCRYPTED]":
                    # Check if already Family Key encrypted
                    nome_conto_check = _decrypt_if_key(nome_conto, family_key, crypto, silent=True)
                    if nome_conto_check != "[ENCRYPTED]":
                        print(f"    [INFO] Conto '{nome_conto_check}' è GIÀ aggiornato.")
                        nome_conto_dec = nome_conto_check # Use decrypted name for logs
                    else:
                        print(f"    [WARN] Impossibile decriptare nome conto ID {id_conto}.")
                else: 
                     # It was Master Key encrypted (or plaintext?), so re-encrypt with Family Key
                    print(f"    Aggiornamento nome conto: {nome_conto_dec}...")
                    nome_conto_enc_new = _encrypt_if_key(nome_conto_dec, family_key, crypto)
                    cur.execute("UPDATE Conti SET nome_conto = %s WHERE id_conto = %s", (nome_conto_enc_new, id_conto))
                    totale_aggiornati += 1

                # Fetch Assets
                cur.execute("SELECT id_asset, ticker, nome_asset FROM Asset WHERE id_conto = %s", (id_conto,))
                assets = cur.fetchall()
                
                for asset in assets:
                    # Tenta decrittazione con Master Key (Vecchio metodo)
                    # NOTE: Usiamo silent=True per non crashare se è già criptato giusto
                    ticker_dec = _decrypt_if_key(asset['ticker'], master_key, crypto, silent=True)
                    nome_dec = _decrypt_if_key(asset['nome_asset'], master_key, crypto, silent=True)
                    
                    if ticker_dec == "[ENCRYPTED]" or nome_dec == "[ENCRYPTED]":
                        # Forse è già criptato con Family Key? Proviamo
                        ticker_check = _decrypt_if_key(asset['ticker'], family_key, crypto, silent=True)
                        if ticker_check != "[ENCRYPTED]":
                            print(f"        Asset '{ticker_check}' è GIÀ aggiornato. Salto.")
                            continue
                        else:
                            print(f"        [WARN] Impossibile decriptare asset ID {asset['id_asset']}. Chiave errata o asset corrotto.")
                            continue
                    
                    # Se arriviamo qui, abbiamo decriptato con Master Key. Ora ricriptiamo con Family Key.
                    print(f"        Aggiornamento asset: {ticker_dec}...")
                    
                    ticker_enc_new = _encrypt_if_key(ticker_dec, family_key, crypto)
                    nome_enc_new = _encrypt_if_key(nome_dec, family_key, crypto)
                    
                    cur.execute("""
                        UPDATE Asset 
                        SET ticker = %s, nome_asset = %s 
                        WHERE id_asset = %s
                    """, (ticker_enc_new, nome_enc_new, asset['id_asset']))
                    totale_aggiornati += 1

            con.commit()
            print(f"\n[SUCCESSO] Migrazione completata! {totale_aggiornati} asset aggiornati.")
            print("Per terminare, premi ENTER.")
            input()

    except Exception as e:
        print(f"\n[ERRORE CRITICO] {e}")
        import traceback
        traceback.print_exc()
        input() # Keep window open on error

if __name__ == "__main__":
    migra_asset_utente()
