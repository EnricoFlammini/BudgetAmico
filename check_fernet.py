from cryptography.fernet import Fernet
import base64

print("--- Fernet Check ---")
key = Fernet.generate_key()
print(f"Generated Key: {key}")
print(f"Type: {type(key)}")
print(f"Length: {len(key)}")

try:
    f = Fernet(key)
    print("Fernet(key) initialized successfully.")
except Exception as e:
    print(f"Fernet(key) failed: {e}")

print("\n--- Raw Bytes Check ---")
raw_bytes = b'\x05' * 32
print(f"Raw Bytes: {raw_bytes}")
try:
    f = Fernet(raw_bytes)
    print("Fernet(raw_bytes) initialized successfully.")
except Exception as e:
    print(f"Fernet(raw_bytes) failed: {e}")

print("\n--- Base64 Encoded Raw Bytes Check ---")
encoded_raw = base64.urlsafe_b64encode(raw_bytes)
print(f"Encoded Raw: {encoded_raw}")
try:
    f = Fernet(encoded_raw)
    print("Fernet(encoded_raw) initialized successfully.")
except Exception as e:
    print(f"Fernet(encoded_raw) failed: {e}")
