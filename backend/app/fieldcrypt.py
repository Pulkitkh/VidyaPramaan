"""Field-level encryption at rest for contact details and travel-document numbers (AES-256-GCM).

The database file, a backup or a replica shows only ciphertext for these columns; the application
decrypts them on read. They are never searched in SQL (shared-contact detection runs in Python),
so a random nonce per value is safe and equal values do not reveal each other.

Key, in order of preference: VP_DATA_KEY (32 bytes, base64; from a secrets manager or KMS in
production, kept apart from the database), else a key file next to the development database.
Values written before encryption was enabled are read as they are and encrypted on the next write.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.types import String, TypeDecorator

from .config import DATA_DIR

PREFIX = "enc1:"
KEY_PATH = DATA_DIR / "data_key.bin"


def _load_key() -> bytes:
    env = os.getenv("VP_DATA_KEY", "").strip()
    if env:
        key = base64.b64decode(env)
        if len(key) != 32:
            raise ValueError("VP_DATA_KEY must be 32 bytes, base64-encoded")
        return key
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()
    key = AESGCM.generate_key(bit_length=256)
    KEY_PATH.write_bytes(key)
    try:
        KEY_PATH.chmod(0o600)
    except OSError:
        pass
    return key


_AEAD = AESGCM(_load_key())


def encrypt(value: str) -> str:
    nonce = os.urandom(12)
    return PREFIX + base64.b64encode(nonce + _AEAD.encrypt(nonce, value.encode(), b"vp-field")).decode()


def decrypt(value: str) -> str:
    if not value.startswith(PREFIX):
        return value  # written before encryption was enabled
    raw = base64.b64decode(value[len(PREFIX):])
    return _AEAD.decrypt(raw[:12], raw[12:], b"vp-field").decode()


class Encrypted(TypeDecorator):
    """A string column stored encrypted. Not usable in WHERE clauses: compare after reading."""
    impl = String(255)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value in (None, "") else encrypt(str(value))

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt(value)
