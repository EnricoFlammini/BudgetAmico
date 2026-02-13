import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from utils.logger import setup_logger

logger = setup_logger("CryptoManager")

class CryptoManager:
    def __init__(self):
        self.backend = default_backend()

    @staticmethod
    def is_encrypted(data: Any) -> bool:
        """Verifica se il dato è una stringa criptata (v2 GCM o legacy Fernet)."""
        if not isinstance(data, str):
            return False
        return data.startswith("v2:") or data.startswith("gAAAAA")

    def generate_salt(self) -> bytes:
        """Generates a random 16-byte salt."""
        return os.urandom(16)

    def derive_key(self, password: str, salt: bytes) -> bytes:
        """Derives a 32-byte key from the password and salt using PBKDF2HMAC."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=self.backend
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def generate_master_key(self) -> bytes:
        """Generates a new random Master Key (Fernet key)."""
        return Fernet.generate_key()

    def encrypt_master_key(self, master_key: bytes, kek: bytes) -> bytes:
        """Encrypts the Master Key using the Key Encryption Key (KEK)."""
        f = Fernet(kek)
        return f.encrypt(master_key)

    def decrypt_master_key(self, encrypted_master_key: bytes, kek: bytes) -> bytes:
        """Decrypts the Master Key using the Key Encryption Key (KEK)."""
        f = Fernet(kek)
        return f.decrypt(encrypted_master_key)

    def encrypt_data(self, data: str, master_key: bytes) -> str:
        """
        Encrypts a string using AES-256-GCM (v2).
        Returns a string with 'v2:' prefix.
        """
        if not data:
            return ""
        
        try:
            # 1. Prepare raw 32-byte key
            raw_key = self._ensure_raw_key(master_key)
            
            # 2. AES-GCM Encryption
            nonce = os.urandom(12)
            aesgcm = AESGCM(raw_key)
            # data.encode() -> bytes
            ciphertext = aesgcm.encrypt(nonce, data.encode(), None)
            
            # 3. Combine nonce + ciphertext and base64 encode
            combined = nonce + ciphertext
            return "v2:" + base64.b64encode(combined).decode()
            
        except Exception as e:
            logger.error(f"Encryption failed (AES-GCM): {e}")
            # Fallback to Fernet for safety if GCM fails for some reason (shouldn't happen with valid key)
            return self._encrypt_fernet_legacy(data, master_key)

    def decrypt_data(self, encrypted_data: str, master_key: bytes, silent: bool = False) -> str:
        """
        Decrypts data. Supports both v2 (AES-GCM) and legacy (Fernet).
        """
        if not encrypted_data:
            return ""
            
        try:
            # Check for version prefix
            if encrypted_data.startswith("v2:"):
                return self._decrypt_gcm_v2(encrypted_data, master_key, silent)
            else:
                # Fallback to legacy Fernet
                return self._decrypt_fernet_legacy(encrypted_data, master_key, silent)
        except Exception as e:
            if not silent:
                logger.error(f"Decryption failed globally: {e}")
            return "[ENCRYPTED]"

    def _ensure_raw_key(self, key: bytes) -> bytes:
        """Ensures the key is 32 raw bytes for AESGCM."""
        if isinstance(key, str):
            key = key.encode()
        
        # If it's a 44-char base64 string (Fernet style), decode it
        if len(key) == 44:
            try:
                decoded = base64.urlsafe_b64decode(key)
                if len(decoded) == 32:
                    return decoded
            except: pass
            
        # If it's already 32 bytes, perfect
        if len(key) == 32:
            return key
            
        raise ValueError(f"Invalid key length for AES-256: {len(key)} bytes. Expected 32.")

    def _encrypt_fernet_legacy(self, data: str, master_key: bytes) -> str:
        """Legacy Fernet encryption."""
        if isinstance(master_key, str): master_key = master_key.encode()
        if len(master_key) == 32: master_key = base64.urlsafe_b64encode(master_key)
        f = Fernet(master_key)
        return f.encrypt(data.encode()).decode()

    def _decrypt_fernet_legacy(self, encrypted_data: str, master_key: bytes, silent: bool = False) -> str:
        """Legacy Fernet decryption."""
        try:
            if isinstance(master_key, str): master_key = master_key.encode()
            if len(master_key) == 32: master_key = base64.urlsafe_b64encode(master_key)
            f = Fernet(master_key)
            return f.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            if not silent: logger.debug(f"Legacy Fernet decryption failed: {e}")
            raise e

    def _decrypt_gcm_v2(self, encrypted_data: str, master_key: bytes, silent: bool = False) -> str:
        """AES-256-GCM (v2) decryption."""
        try:
            raw_key = self._ensure_raw_key(master_key)
            
            # Remove prefix and decode
            payload_b64 = encrypted_data[3:]
            combined = base64.b64decode(payload_b64)
            
            # Nonce is 12 bytes
            nonce = combined[:12]
            ciphertext = combined[12:]
            
            aesgcm = AESGCM(raw_key)
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_bytes.decode()
        except Exception as e:
            if not silent: logger.error(f"AES-GCM decryption failed: {e}")
            raise e

    def generate_recovery_key(self) -> str:
        """Generates a human-readable recovery key."""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()

    def hash_recovery_key(self, recovery_key: str) -> str:
        """Hashes the recovery key for storage."""
        digest = hashes.Hash(hashes.SHA256(), backend=self.backend)
        digest.update(recovery_key.encode())
        return base64.urlsafe_b64encode(digest.finalize()).decode()
