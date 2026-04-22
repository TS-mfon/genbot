"""Fernet encryption utilities for wallet private keys."""

import base64
import hashlib

from cryptography.fernet import Fernet

from bot.config import settings


def _get_fernet() -> Fernet:
    """Get a Fernet instance from the configured key.

    The key from settings may not be a valid Fernet key (which requires
    exactly 32 url-safe base64-encoded bytes). We normalize it by
    hashing and re-encoding if necessary.
    """
    raw_key = settings.wallet_encryption_key.encode()
    # Ensure we have a valid 32-byte key by hashing
    key_bytes = hashlib.sha256(raw_key).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_data(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_data(ciphertext: str) -> str:
    """Decrypt base64-encoded ciphertext back to string."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
