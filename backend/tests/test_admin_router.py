"""Tests for the admin router — user management."""

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
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
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


def _make_user(db, role="viewer", **kwargs):
    defaults = dict(
        google_id=f"g-{kwargs.get('email', 'test')}",
        email="test@example.com",
        name="Test",
    )
    defaults.update(kwargs)
    user = User(role=role, **defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user):
    token = create_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def test_list_users_as_admin(client, db_session):
    """Admin can list all users."""
    admin = _make_user(db_session, role="admin", email="admin@test.com", google_id="g-admin")
    _make_user(db_session, role="viewer", email="viewer@test.com", google_id="g-viewer")
    response = client.get("/api/admin/users", headers=_auth_header(admin))
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_users_as_viewer_denied(client, db_session):
    """Viewer cannot list users."""
    viewer = _make_user(db_session, role="viewer")
    response = client.get("/api/admin/users", headers=_auth_header(viewer))
    assert response.status_code == 403


def test_change_role(client, db_session):
    """Admin can change another user's role."""
    admin = _make_user(db_session, role="admin", email="admin@test.com", google_id="g-admin")
    viewer = _make_user(db_session, role="viewer", email="viewer@test.com", google_id="g-viewer")
    response = client.patch(
        f"/api/admin/users/{viewer.id}/role",
        json={"role": "operator"},
        headers=_auth_header(admin),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "operator"


def test_change_role_invalid(client, db_session):
    """Invalid role value returns 400."""
    admin = _make_user(db_session, role="admin", email="admin@test.com", google_id="g-admin")
    viewer = _make_user(db_session, role="viewer", email="viewer@test.com", google_id="g-viewer")
    response = client.patch(
        f"/api/admin/users/{viewer.id}/role",
        json={"role": "superuser"},
        headers=_auth_header(admin),
    )
    assert response.status_code == 400


def test_deactivate_user(client, db_session):
    """Admin can deactivate a user."""
    admin = _make_user(db_session, role="admin", email="admin@test.com", google_id="g-admin")
    viewer = _make_user(db_session, role="viewer", email="viewer@test.com", google_id="g-viewer")
    response = client.patch(
        f"/api/admin/users/{viewer.id}/active",
        json={"is_active": False},
        headers=_auth_header(admin),
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_admin_cannot_deactivate_self(client, db_session):
    """Admin cannot deactivate themselves."""
    admin = _make_user(db_session, role="admin", email="admin@test.com", google_id="g-admin")
    response = client.patch(
        f"/api/admin/users/{admin.id}/active",
        json={"is_active": False},
        headers=_auth_header(admin),
    )
    assert response.status_code == 400
