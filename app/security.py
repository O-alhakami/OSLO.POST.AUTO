from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY must be set before connecting social accounts.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is invalid; generate one with Fernet.generate_key().") from exc


def encrypt_token(token: str | None) -> str | None:
    if token is None:
        return None
    return _fernet().encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_token(token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError) as exc:
        raise RuntimeError("Could not decrypt a stored social-account token.") from exc
