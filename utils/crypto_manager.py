import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from utils.logger import setup_logger

logger = setup_logger("CryptoManager")

class CryptoManager:
    def __init__(self):
        self.backend = default_backend()

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
        """Encrypts a string using the Master Key. Returns a base64 string (Fernet token)."""
        if not data:
            return ""
        
        # Ensure master_key is bytes
        if isinstance(master_key, str):
            master_key = master_key.encode()
            
        # Fix for raw bytes key (32 bytes) -> encode to base64 (44 bytes)
        if len(master_key) == 32:
            # print(f"[CRYPTO FIX] Encoding raw 32-byte key to base64.") # Reduced log noise
            master_key = base64.urlsafe_b64encode(master_key)
            
        try:
            f = Fernet(master_key)
        except Exception as e:
            logger.error(f"Invalid Master Key in encrypt_data: {e}")
            raise e
            
        # Fernet.encrypt returns bytes that are already base64 encoded
        return f.encrypt(data.encode()).decode()

    def decrypt_data(self, encrypted_data: str, master_key: bytes, silent: bool = False) -> str:
        """Decrypts a base64 string (Fernet token) using the Master Key."""
        if not encrypted_data:
            return ""
        try:
            # Ensure master_key is bytes
            if isinstance(master_key, str):
                master_key = master_key.encode()
                
            # Fix for raw bytes key (32 bytes) -> encode to base64 (44 bytes)
            if len(master_key) == 32:
                # print(f"[CRYPTO FIX] Encoding raw 32-byte key to base64.") # Reduced log noise
                master_key = base64.urlsafe_b64encode(master_key)
                
            try:
                f = Fernet(master_key)
            except Exception as e:
                if not silent:
                    logger.error(f"Invalid Master Key in decrypt_data: {e}")
                raise e
                
            # Fernet.decrypt expects bytes (the token)
            return f.decrypt(encrypted_data.encode()).decode()
            # Fernet.decrypt expects bytes (the token)
            return f.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            if not silent:
                # SECURITY: Do NOT log the master_key or the full encrypted data if it might leak info.
                logger.error(f"Decryption failed. Error: {e}")
            return "[ENCRYPTED]"

    def generate_recovery_key(self) -> str:
        """Generates a human-readable recovery key."""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()

    def hash_recovery_key(self, recovery_key: str) -> str:
        """Hashes the recovery key for storage."""
        digest = hashes.Hash(hashes.SHA256(), backend=self.backend)
        digest.update(recovery_key.encode())
        return base64.urlsafe_b64encode(digest.finalize()).decode()
