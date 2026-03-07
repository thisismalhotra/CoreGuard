"""Tests for the auth router -- login redirect, callback, /me endpoint."""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth import create_token
from database.connection import get_db
from database.models import Base, User
from main import app


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_login_redirects_to_google(client):
    """GET /api/auth/login should redirect (302) to Google's OAuth URL."""
    response = client.get("/api/auth/login", follow_redirects=False)
    assert response.status_code == 302
    assert "accounts.google.com" in response.headers["location"]


def test_me_unauthenticated(client):
    """GET /api/auth/me without token returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_authenticated(client, db_session):
    """GET /api/auth/me with valid token returns user profile."""
    user = User(google_id="g-1", email="test@example.com", name="Test User", role="admin")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_token(user_id=user.id, email=user.email, role=user.role)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "admin"


def test_me_inactive_user(client, db_session):
    """GET /api/auth/me with inactive user returns 403."""
    user = User(google_id="g-1", email="test@example.com", name="Test User", is_active=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_token(user_id=user.id, email=user.email, role=user.role)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
