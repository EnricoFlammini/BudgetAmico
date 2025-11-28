import os
import sys
from db.gestione_db import (
    crea_famiglia_e_admin, registra_utente, crea_utente_invitato, 
    cambia_password_e_username, verifica_login, ottieni_utente_da_email
)
from db.supabase_manager import SupabaseManager

# Initialize DB
SupabaseManager.initialize_pool()

def test_invitation_flow():
    print("--- Starting Invitation Flow Test ---")
    
    # 1. Setup Admin and Family
    admin_email = "admin_test@example.com"
    admin_user = "admin_test"
    
    # Clean up if exists (optional, or just use random)
    import secrets
    suffix = secrets.token_hex(4)
    admin_email = f"admin_{suffix}@test.com"
    admin_user = f"admin_{suffix}"
    
    print(f"Creating Admin: {admin_user}")
    id_admin = registra_utente("Admin", "Test", admin_user, "password123", admin_email, "1990-01-01", "CF_TEST_123", "Via Test 1")
    if not id_admin:
        print("Failed to create admin")
        return

    print(f"Creating Family for Admin {id_admin}")
    id_famiglia = crea_famiglia_e_admin(f"Famiglia {suffix}", id_admin)
    if not id_famiglia:
        print("Failed to create family")
        return
        
    # 2. Invite User
    invite_email = f"invited_{suffix}@test.com"
    print(f"Inviting user: {invite_email}")
    
    creds = crea_utente_invitato(invite_email, "livello1", id_famiglia)
    if not creds:
        print("Failed to invite user")
        return
        
    print(f"User invited. Temp Creds: {creds}")
    
    # 3. Verify User Exists
    user = ottieni_utente_da_email(invite_email)
    if not user:
        print("Invited user not found in DB")
        return
        
    if not user['forza_cambio_password']:
        print("Error: forza_cambio_password should be True")
        return
        
    print("User found and flag correct.")
    
    # 4. Simulate First Login Update
    new_username = f"real_user_{suffix}"
    new_password = "NewPassword123!"
    
    # Need hash for update
    from db.gestione_db import hash_password
    new_hash = hash_password(new_password)
    
    print(f"Updating profile to: {new_username}")
    success = cambia_password_e_username(user['id_utente'], new_hash, new_username)
    
    if not success:
        print("Failed to update profile")
        return
        
    # 5. Verify Update
    updated_user = ottieni_utente_da_email(invite_email)
    if updated_user['username'] != new_username:
        print(f"Error: Username not updated. Got {updated_user['username']}")
        return
        
    if updated_user['forza_cambio_password']:
        print("Error: forza_cambio_password should be False")
        return
        
    # Verify Login
    login_user = verifica_login(new_username, new_password)
    if not login_user:
        print("Error: Login failed with new credentials")
        return
        
    print("--- Test Passed Successfully ---")

if __name__ == "__main__":
    test_invitation_flow()
