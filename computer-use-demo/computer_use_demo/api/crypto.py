import os

from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    key = os.environ.get("API_SECRET_KEY", "")
    if not key:
        # Generate a temporary key for development (not persistent across restarts)
        key = Fernet.generate_key().decode()
        os.environ["API_SECRET_KEY"] = key
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    return _get_fernet().encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    if not encrypted:
        return ""
    return _get_fernet().decrypt(encrypted.encode()).decode()
