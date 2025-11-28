#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script for encryption functionality"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from utils.crypto_manager import CryptoManager
import base64

def test_crypto():
    print("=== Testing CryptoManager ===\n")
    
    crypto = CryptoManager()
    
    # Test 1: Key derivation
    print("1. Testing key derivation...")
    password = "TestPassword123"
    salt = crypto.generate_salt()
    kek1 = crypto.derive_key(password, salt)
    kek2 = crypto.derive_key(password, salt)
    assert kek1 == kek2, "Key derivation should be deterministic"
    print("   [OK] Key derivation is deterministic\n")
    
    # Test 2: Master key generation and encryption
    print("2. Testing master key encryption...")
    master_key = crypto.generate_master_key()
    encrypted_mk = crypto.encrypt_master_key(master_key, kek1)
    decrypted_mk = crypto.decrypt_master_key(encrypted_mk, kek1)
    assert master_key == decrypted_mk, "Master key should decrypt correctly"
    print("   [OK] Master key encryption/decryption works\n")
    
    # Test 3: Data encryption
    print("3. Testing data encryption...")
    test_data = "Mario Rossi"
    encrypted_data = crypto.encrypt_data(test_data, master_key)
    decrypted_data = crypto.decrypt_data(encrypted_data, master_key)
    assert test_data == decrypted_data, "Data should decrypt correctly"
    print(f"   Original: {test_data}")
    print(f"   Encrypted: {encrypted_data[:50]}...")
    print(f"   Decrypted: {decrypted_data}")
    print("   [OK] Data encryption/decryption works\n")
    
    # Test 4: Recovery key
    print("4. Testing recovery key...")
    recovery_key = crypto.generate_recovery_key()
    recovery_hash = crypto.hash_recovery_key(recovery_key)
    print(f"   Recovery Key: {recovery_key}")
    print(f"   Hash: {recovery_hash[:50]}...")
    print("   [OK] Recovery key generation works\n")
    
    print("=== All tests passed! ===")

if __name__ == "__main__":
    test_crypto()
