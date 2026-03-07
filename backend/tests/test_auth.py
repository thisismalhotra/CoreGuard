"""Tests for JWT helpers and auth dependencies."""


# Patch env before importing auth module
import os
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, User

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests")

from auth import create_token, decode_token, get_current_user, require_role


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_and_decode_token():
    """Round-trip: create a token and decode it back."""
    token = create_token(user_id=1, email="test@example.com", role="admin")
    payload = decode_token(token)
    assert payload["sub"] == "1"
    assert payload["email"] == "test@example.com"
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_decode_expired_token():
    """Expired token raises HTTPException 401."""
    token = create_token(user_id=1, email="test@example.com", role="viewer", expires_minutes=-1)
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    assert exc_info.value.status_code == 401


def test_decode_invalid_token():
    """Garbage token raises HTTPException 401."""
    with pytest.raises(HTTPException) as exc_info:
        decode_token("not-a-real-token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_valid():
    """Valid token + active user returns the user."""
    db = _make_session()
    user = User(google_id="g-1", email="test@example.com", name="Test", role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user_id=user.id, email=user.email, role=user.role)
    result = await get_current_user(authorization=f"Bearer {token}", db=db)
    assert result.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_current_user_inactive():
    """Inactive user raises HTTPException 403."""
    db = _make_session()
    user = User(google_id="g-1", email="test@example.com", name="Test", is_active=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user_id=user.id, email=user.email, role=user.role)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization=f"Bearer {token}", db=db)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_no_header():
    """Missing Authorization header raises HTTPException 401."""
    db = _make_session()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization=None, db=db)
    assert exc_info.value.status_code == 401


def test_require_role_allowed():
    """User with sufficient role passes the check."""
    checker = require_role("operator", "admin")
    user = MagicMock()
    user.role = "admin"
    result = checker(user)
    assert result == user


def test_require_role_denied():
    """User without sufficient role raises HTTPException 403."""
    checker = require_role("admin")
    user = MagicMock()
    user.role = "viewer"
    with pytest.raises(HTTPException) as exc_info:
        checker(user)
    assert exc_info.value.status_code == 403
