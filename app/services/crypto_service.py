from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode())


def encrypt(plain: str) -> str:
    """Encrypt plain-text string; returns URL-safe base64 token as str."""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt Fernet token; returns original plain-text string."""
    return _fernet().decrypt(token.encode()).decode()
