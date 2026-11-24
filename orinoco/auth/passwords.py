"""Password hashing and verification using Argon2."""

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password with the configured Argon2id policy; reject weak or oversized input."""
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters long")
    if len(password) > 1024:
        raise ValueError("password is too long")
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a candidate password safely, returning false for malformed hashes or invalid input."""
    if not isinstance(password, str) or len(password) > 1024:
        return False
    try:
        return _password_hash.verify(password, password_hash)
    except (ValueError, TypeError):
        return False
