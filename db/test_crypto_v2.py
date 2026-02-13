import sys
import os
import base64

# Add path to Sviluppo
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.crypto_manager import CryptoManager
from cryptography.fernet import Fernet

def test_v2():
    print("[*] Starting Crypto V2 (AES-GCM) Tests")
    cm = CryptoManager()
    master_key = cm.generate_master_key() # 44-char Fernet key
    
    print(f"[*] Master Key (Fernet style b64): {master_key.decode()}")
    
    # 1. Test Legacy Fernet Decryption
    f = Fernet(master_key)
    legacy_text = "Hello BudgetAmico Legacy"
    legacy_data = f.encrypt(legacy_text.encode()).decode()
    print(f"[*] Legacy Data (Fernet): {legacy_data[:20]}...")
    dec_legacy = cm.decrypt_data(legacy_data, master_key)
    print(f"[*] Decrypted Legacy: {dec_legacy}")
    assert dec_legacy == legacy_text
    
    # 2. Test New GCM Encryption
    new_text = "Hello BudgetAmico GCM"
    gcm_data = cm.encrypt_data(new_text, master_key)
    print(f"[*] GCM Data: {gcm_data[:20]}...")
    assert gcm_data.startswith("v2:")
    
    # 3. Test GCM Decryption
    dec_gcm = cm.decrypt_data(gcm_data, master_key)
    print(f"[*] Decrypted GCM: {dec_gcm}")
    assert dec_gcm == new_text
    
    # 4. Test with raw 32-byte key
    raw_key = os.urandom(32)
    print(f"[*] Raw Key (32 bytes): {raw_key.hex()}")
    raw_text = "Checking raw 32-byte key support"
    gcm_raw = cm.encrypt_data(raw_text, raw_key)
    print(f"[*] GCM Raw: {gcm_raw[:20]}...")
    dec_raw = cm.decrypt_data(gcm_raw, raw_key)
    print(f"[*] Decrypted Raw: {dec_raw}")
    assert dec_raw == raw_text
    
    # 5. Test Fallback/Error (Wrong key)
    wrong_key = cm.generate_master_key()
    dec_wrong = cm.decrypt_data(gcm_data, wrong_key, silent=True)
    print(f"[*] Decrypted with wrong key: {dec_wrong}")
    assert dec_wrong == "[ENCRYPTED]"
    
    # 6. Test crypto_helpers logic
    from db.crypto_helpers import _decrypt_if_key
    print("[*] Testing _decrypt_if_key helper...")
    # Fernet
    h_legacy = _decrypt_if_key(legacy_data, master_key)
    assert h_legacy == legacy_text
    # GCM
    h_gcm = _decrypt_if_key(gcm_data, master_key)
    assert h_gcm == new_text
    # Plain text (should return as is)
    plain = "plain_text"
    h_plain = _decrypt_if_key(plain, master_key)
    assert h_plain == plain

    print("\n[SUCCESS] All crypto migration tests passed!")

if __name__ == "__main__":
    try:
        test_v2()
    except Exception as e:
        print(f"\n[FAILURE] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
