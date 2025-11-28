#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug script to check encryption in database"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db.supabase_manager import get_db_connection

def check_last_user():
    print("=== Checking last registered user ===\n")
    
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT id_utente, username, nome, cognome, codice_fiscale, indirizzo, 
                       salt, encrypted_master_key, recovery_key_hash
                FROM Utenti 
                ORDER BY id_utente DESC 
                LIMIT 1
            """)
            
            user = cur.fetchone()
            if not user:
                print("No users found in database")
                return
            
            print(f"User ID: {user['id_utente']}")
            print(f"Username: {user['username']}")
            print(f"\n--- PII Fields (should be encrypted) ---")
            print(f"Nome: {user['nome'][:80] if user['nome'] else 'NULL'}...")
            print(f"Cognome: {user['cognome'][:80] if user['cognome'] else 'NULL'}...")
            print(f"Codice Fiscale: {user['codice_fiscale'][:80] if user['codice_fiscale'] else 'NULL'}...")
            print(f"Indirizzo: {user['indirizzo'][:80] if user['indirizzo'] else 'NULL'}...")
            
            print(f"\n--- Encryption Metadata ---")
            print(f"Salt: {user['salt'][:50] if user['salt'] else 'NULL'}...")
            print(f"Encrypted Master Key: {user['encrypted_master_key'][:50] if user['encrypted_master_key'] else 'NULL'}...")
            print(f"Recovery Key Hash: {user['recovery_key_hash'][:50] if user['recovery_key_hash'] else 'NULL'}...")
            
            # Check if data looks encrypted (should start with base64 encoded Fernet token)
            is_encrypted = (
                user['nome'] and user['nome'].startswith('Z0FBQUFB') and
                user['salt'] is not None and
                user['encrypted_master_key'] is not None
            )
            
            print(f"\n--- Status ---")
            if is_encrypted:
                print("✓ Data appears to be ENCRYPTED")
            else:
                print("✗ Data appears to be PLAIN TEXT")
                print("\nPossible issues:")
                print("- Salt is NULL" if not user['salt'] else "")
                print("- Encrypted Master Key is NULL" if not user['encrypted_master_key'] else "")
                print("- Nome doesn't look encrypted" if user['nome'] and not user['nome'].startswith('Z0FBQUFB') else "")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_last_user()
