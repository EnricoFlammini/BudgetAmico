import os
import sys

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.gestione_db import get_db_connection

def audit_schema():
    print("Auditing schema compatibility...")
    
    expected_columns = [
        'password_algo', 'salt', 'encrypted_master_key', 
        'recovery_key_hash', 'encrypted_master_key_recovery', 
        'encrypted_master_key_backup', 'username_bindex', 
        'email_bindex', 'username_enc', 'email_enc', 
        'nome_enc_server', 'cognome_enc_server',
        'failed_login_attempts', 'lockout_until', 'last_failed_login', 'sospeso'
    ]
    
    # Check Appartenenza_Famiglia columns as well
    family_cols = ['chiave_famiglia_criptata']
    
    missing_cols = []
    nullable_issues = []

    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # 1. Check Utenti Columns
        cur.execute("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name='utenti'")
        existing_info = {row['column_name']: row['is_nullable'] for row in cur.fetchall()}
        
        for col in expected_columns:
            if col not in existing_info:
                missing_cols.append(f"Utenti.{col}")
                
        # 2. Check Appartenenza_Famiglia Columns
        cur.execute("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name='appartenenza_famiglia'")
        fam_info = {row['column_name']: row['is_nullable'] for row in cur.fetchall()}
        
        for col in family_cols:
             if col not in fam_info:
                 missing_cols.append(f"Appartenenza_Famiglia.{col}")
                
        # 2. Check Nullable Username/Email
        if existing_info.get('username') == 'NO':
            nullable_issues.append('username is NOT NULL (should be nullable)')
        if existing_info.get('email') == 'NO':
            nullable_issues.append('email is NOT NULL (should be nullable)')

    if not missing_cols and not nullable_issues:
        print("[OK] Schema is ALIGNED with code expectations.")
        return True
    else:
        print("[FAIL] Schema MISMATCH found:")
        if missing_cols:
            print(f"   Missing Columns: {missing_cols}")
        if nullable_issues:
            print(f"   Nullable Issues: {nullable_issues}")
        return False

if __name__ == "__main__":
    audit_schema()
