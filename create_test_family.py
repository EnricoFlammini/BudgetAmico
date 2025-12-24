
import os
import sys
import datetime
import secrets
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment logic
load_dotenv()

from db.gestione_db import (
    registra_utente, 
    crea_famiglia_e_admin, 
    aggiungi_utente_a_famiglia
)
from db.supabase_manager import get_db_connection

def create_test_family():
    print("--- CREAZIONE FAMIGLIA DI TEST ---")
    
    timestamp = datetime.datetime.now().strftime("%H%M")
    suffix = secrets.token_hex(2)
    
    famiglia_nome = f"Famiglia Test {timestamp}-{suffix}"
    
    # Define users to create
    # (Role Label, System Role)
    users_config = [
        ("Admin", "admin"),
        ("Level 1", "livello1"),
        ("Level 2", "livello2"),
        ("Level 3", "livello3")
    ]
    
    created_users = []
    
    try:
        # 1. Create Users
        for label, role in users_config:
            username = f"Test_{label.replace(' ', '')}_{timestamp}_{suffix}"
            password = "Password123!"
            email = f"test.{label.replace(' ', '').lower()}.{timestamp}.{suffix}@example.com"
            
            print(f"Creating user {username}...")
            
            res = registra_utente(
                nome=f"Nome {label}",
                cognome="Test",
                username=username,
                password=password,
                email=email,
                data_nascita="1990-01-01",
                codice_fiscale=None,
                indirizzo="Via Test 123"
            )
            
            if not res or not res.get('id_utente'):
                print(f"Error creating user {username}. Skipping.")
                continue
                
            created_users.append({
                'id': res['id_utente'],
                'username': username,
                'password': password,
                'email': email,
                'role': role,
                'label': label,
                'master_key': res.get('master_key')
            })

        if not created_users:
            print("No users created. Aborting.")
            return

        # 2. Create Family with Admin
        admin_user = created_users[0]
        print(f"Creating family '{famiglia_nome}' with Admin {admin_user['username']}...")
        
        # Note: crea_famiglia_e_admin returns id_famiglia or None/False
        # Check signature: crea_famiglia_e_admin(nome, id_admin, mk_b64)
        id_famiglia = crea_famiglia_e_admin(
            famiglia_nome, 
            admin_user['id'], 
            admin_user['master_key'] # Pass master key to encrypt family key
        )
        
        if not id_famiglia:
            print("Error creating family.")
            return

        print(f"Family created with ID: {id_famiglia}")

        # 3. Add other users to family
        for u in created_users[1:]:
            print(f"Adding {u['username']} as {u['role']}...")
            ok = aggiungi_utente_a_famiglia(id_famiglia, u['id'], u['role'])
            if ok:
                print("OK")
            else:
                print("FAILED")

        # 4. Output Credentials
        print("\n\n" + "="*60)
        print(f"FAMIGLIA TEST CREATA: {famiglia_nome}")
        print("="*60)
        print(f"{'RUOLO':<15} {'USERNAME':<30} {'PASSWORD':<15} {'EMAIL':<40}")
        print("-" * 100)
        for u in created_users:
            print(f"{u['label']:<15} {u['username']:<30} {u['password']:<15} {u['email']:<40}")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_test_family()
