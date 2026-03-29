import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import settings


class TokenVault:
    """Encrypts and decrypts sensitive tokens using Fernet."""

    def __init__(self):
        # Derive a proper Fernet key from the settings key
        key_material = settings.encryption_key
        if isinstance(key_material, str):
            key_material = key_material.encode()
        
        # Use SHA-256 to derive a 32-byte key, then base64 encode it
        derived_key = hashlib.sha256(key_material).digest()
        encryption_key = base64.urlsafe_b64encode(derived_key)
        
        self.cipher = Fernet(encryption_key)

    def encrypt(self, token: str) -> str:
        """Encrypt token to string."""
        encrypted = self.cipher.encrypt(token.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_token: str) -> str:
        """Decrypt token from string."""
        if isinstance(encrypted_token, str):
            encrypted_token = encrypted_token.encode()
        decrypted = self.cipher.decrypt(encrypted_token)
        return decrypted.decode()


vault = TokenVault()
