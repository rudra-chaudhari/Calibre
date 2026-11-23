from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings


def encrypt_token(plain: str) -> str:
    """
    Encrypts a Moodle token using Fernet.
    Raises ImproperlyConfigured if MOODLE_TOKEN_KEY is missing or invalid.
    """
    key = getattr(settings, "MOODLE_TOKEN_KEY", None)
    if not key:
        raise ImproperlyConfigured(
            "MOODLE_TOKEN_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return fernet.encrypt(plain.encode()).decode()
    except Exception as e:
        raise ImproperlyConfigured(f"Invalid MOODLE_TOKEN_KEY: {e}")


def decrypt_token(cipher: str) -> str:
    """
    Decrypts an encrypted Moodle token using Fernet.
    Raises ImproperlyConfigured if MOODLE_TOKEN_KEY is missing or invalid.
    """
    key = getattr(settings, "MOODLE_TOKEN_KEY", None)
    if not key:
        raise ImproperlyConfigured(
            "MOODLE_TOKEN_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return fernet.decrypt(cipher.encode()).decode()
    except InvalidToken:
        raise ImproperlyConfigured("Invalid MOODLE_TOKEN_KEY or corrupted token.")
