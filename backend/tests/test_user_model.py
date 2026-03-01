"""Tests for the User model."""

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, User


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_user_creation_defaults():
    """New user gets viewer role, is_active=True, and timestamps."""
    db = _make_session()
    user = User(
        google_id="google-123",
        email="test@example.com",
        name="Test User",
        picture="https://example.com/pic.jpg",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.id is not None
    assert user.role == "viewer"
    assert user.is_active is True
    assert user.created_at is not None
    assert user.last_login is not None


def test_user_google_id_unique():
    """Duplicate google_id raises IntegrityError."""
    db = _make_session()
    db.add(User(google_id="dup-1", email="a@test.com", name="A"))
    db.commit()
    db.add(User(google_id="dup-1", email="b@test.com", name="B"))
    try:
        db.commit()
        assert False, "Should have raised IntegrityError"
    except Exception:
        db.rollback()


def test_user_email_unique():
    """Duplicate email raises IntegrityError."""
    db = _make_session()
    db.add(User(google_id="g-1", email="same@test.com", name="A"))
    db.commit()
    db.add(User(google_id="g-2", email="same@test.com", name="B"))
    try:
        db.commit()
        assert False, "Should have raised IntegrityError"
    except Exception:
        db.rollback()


def test_user_role_assignment():
    """Role can be set to any of the four valid values."""
    db = _make_session()
    for role in ("admin", "operator", "approver", "viewer"):
        user = User(
            google_id=f"g-{role}",
            email=f"{role}@test.com",
            name=role.title(),
            role=role,
        )
        db.add(user)
    db.commit()
    users = db.query(User).all()
    assert len(users) == 4
    assert {u.role for u in users} == {"admin", "operator", "approver", "viewer"}
