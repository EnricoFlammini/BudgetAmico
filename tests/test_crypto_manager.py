
import unittest
import base64
import os
from utils.crypto_manager import CryptoManager

class TestCryptoManager(unittest.TestCase):
    def setUp(self):
        self.crypto = CryptoManager()

    def test_generate_salt(self):
        salt = self.crypto.generate_salt()
        self.assertIsInstance(salt, bytes)
        self.assertEqual(len(salt), 16)
        
        salt2 = self.crypto.generate_salt()
        self.assertNotEqual(salt, salt2)

    def test_derive_key(self):
        password = "test_password"
        salt = self.crypto.generate_salt()
        
        key1 = self.crypto.derive_key(password, salt)
        self.assertIsInstance(key1, bytes)
        # Fernet keys are base64 encoded 32 bytes, so len should be 44
        self.assertEqual(len(key1), 44) 
        
        key2 = self.crypto.derive_key(password, salt)
        self.assertEqual(key1, key2)
        
        salt3 = self.crypto.generate_salt()
        key3 = self.crypto.derive_key(password, salt3)
        self.assertNotEqual(key1, key3)

    def test_generate_master_key(self):
        key = self.crypto.generate_master_key()
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 44)

    def test_encrypt_decrypt_master_key(self):
        master_key = self.crypto.generate_master_key()
        kek = self.crypto.generate_master_key() # Using another fernet key as KEK for simplicity
        
        enc_master_key = self.crypto.encrypt_master_key(master_key, kek)
        self.assertNotEqual(master_key, enc_master_key)
        
        dec_master_key = self.crypto.decrypt_master_key(enc_master_key, kek)
        self.assertEqual(master_key, dec_master_key)

    def test_encrypt_decrypt_data(self):
        master_key = self.crypto.generate_master_key()
        data = "Secret Message"
        
        enc_data = self.crypto.encrypt_data(data, master_key)
        self.assertNotEqual(data, enc_data)
        self.assertTrue(enc_data.startswith("gAAAAA")) # Standard Fernet prefix
        
        dec_data = self.crypto.decrypt_data(enc_data, master_key)
        self.assertEqual(data, dec_data)

    def test_encrypt_data_empty(self):
        master_key = self.crypto.generate_master_key()
        self.assertEqual(self.crypto.encrypt_data("", master_key), "")
        self.assertEqual(self.crypto.encrypt_data(None, master_key), "")

    def test_decrypt_data_empty(self):
        master_key = self.crypto.generate_master_key()
        self.assertEqual(self.crypto.decrypt_data("", master_key), "")
        self.assertEqual(self.crypto.decrypt_data(None, master_key), "")

    def test_decrypt_invalid_data(self):
        master_key = self.crypto.generate_master_key()
        invalid_data = "NotEncrypted"
        
        # Should return [ENCRYPTED] by default or act silently?
        # Based on code: returns "[ENCRYPTED]" on exception
        result = self.crypto.decrypt_data(invalid_data, master_key, silent=True)
        self.assertEqual(result, "[ENCRYPTED]")

    def test_generate_recovery_key(self):
        rk = self.crypto.generate_recovery_key()
        self.assertIsInstance(rk, str)
        self.assertEqual(len(rk), 44) # 32 bytes -> b64 -> 44 chars

    def test_hash_recovery_key(self):
        rk = "some_recovery_key"
        hashed = self.crypto.hash_recovery_key(rk)
        self.assertNotEqual(rk, hashed)
        
        hashed2 = self.crypto.hash_recovery_key(rk)
        self.assertEqual(hashed, hashed2)

if __name__ == '__main__':
    unittest.main()
