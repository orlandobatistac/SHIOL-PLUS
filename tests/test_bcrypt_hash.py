import pytest
from passlib.context import CryptContext


def test_bcrypt_hashing_supports_long_passwords():
    """Sanity check: hashing a long, multi-byte password should succeed."""
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password = ("pässwörd-🔒-very-long" * 10)  # multi-byte + long

    # Should not raise, and should return a bcrypt hash
    hashed = pwd_context.hash(password)
    assert isinstance(hashed, str) and hashed.startswith("$2"), "Expected a bcrypt hash"


def test_sha256_prehash_then_bcrypt_verification():
    """Ensure our SHA-256 prehash + bcrypt path works for any-length passwords."""
    from src.api_auth_endpoints import hash_password_secure, verify_password_secure

    password = ("pässwörd-🔒-very-long" * 20)  # even longer to exceed 72 bytes by far
    hashed = hash_password_secure(password)

    assert hashed.startswith("$2"), "Expected bcrypt hash from secure hasher"
    assert verify_password_secure(password, hashed) is True, "Verification should succeed"
