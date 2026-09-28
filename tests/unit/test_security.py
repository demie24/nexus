"""
Unit Tests for NEXUS Security Module
Verifies bcrypt password hashing, JWT encoding, decoding, validation, and tampering.
"""

from datetime import timedelta
import pytest
from apps.api.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_password_hashing_and_verification():
    plain = "SuperSecretIndustrialPass123!"
    hashed = hash_password(plain)

    # Hash should not equal plain
    assert hashed != plain

    # Verification should succeed
    assert verify_password(plain, hashed) is True

    # Verification should fail with wrong password
    assert verify_password("WrongPassword123!", hashed) is False


def test_jwt_token_creation_and_decoding():
    payload = {"sub": "operator_42", "role": "lead_engineer", "line": "LINE_01"}
    token = create_access_token(payload, expires_delta=timedelta(minutes=30))

    assert isinstance(token, str)
    assert len(token) > 20

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "operator_42"
    assert decoded["role"] == "lead_engineer"
    assert decoded["line"] == "LINE_01"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_expired_token():
    payload = {"sub": "test_user"}
    # Token that expired 5 minutes ago
    expired_token = create_access_token(payload, expires_delta=timedelta(minutes=-5))

    decoded = decode_access_token(expired_token)
    assert decoded is None  # Should fail decoding due to expiration


def test_jwt_tampered_token():
    payload = {"sub": "legit_user"}
    token = create_access_token(payload)

    # Tamper with token characters
    tampered_token = token[:-5] + "AAAAA"
    decoded = decode_access_token(tampered_token)
    assert decoded is None
