"""Tests that verify RBAC enforcement across all routers."""

import os
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, User
from database.connection import get_db
from auth import create_token
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


def _make_user(db, role="viewer"):
    user = User(google_id=f"g-{role}", email=f"{role}@test.com", name=role.title(), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_token(user_id=user.id, email=user.email, role=user.role)}"}


# --- Unauthenticated access blocked ---

def test_inventory_requires_auth(client):
    assert client.get("/api/inventory").status_code == 401


def test_orders_requires_auth(client):
    assert client.get("/api/orders").status_code == 401


def test_kpis_requires_auth(client):
    assert client.get("/api/kpis").status_code == 401


# --- Read endpoints: any authenticated user ---

def test_viewer_can_read_inventory(client, db_session):
    viewer = _make_user(db_session, "viewer")
    assert client.get("/api/inventory", headers=_auth(viewer)).status_code == 200


def test_viewer_can_read_orders(client, db_session):
    viewer = _make_user(db_session, "viewer")
    assert client.get("/api/orders", headers=_auth(viewer)).status_code == 200


# --- Simulation endpoints: operator+ only ---

def test_viewer_cannot_trigger_simulation(client, db_session):
    viewer = _make_user(db_session, "viewer")
    resp = client.post("/api/simulate/spike", headers=_auth(viewer))
    assert resp.status_code == 403


def test_operator_can_trigger_simulation(client, db_session):
    operator = _make_user(db_session, "operator")
    resp = client.post("/api/simulate/spike", headers=_auth(operator))
    # May be 200 or 404/422 due to missing seed data — but NOT 401/403
    assert resp.status_code not in (401, 403)


# --- PO approval: approver+ only ---

def test_viewer_cannot_approve_po(client, db_session):
    viewer = _make_user(db_session, "viewer")
    resp = client.patch("/api/orders/PO-FAKE", json={"status": "APPROVED"}, headers=_auth(viewer))
    assert resp.status_code == 403


def test_operator_cannot_approve_po(client, db_session):
    operator = _make_user(db_session, "operator")
    resp = client.patch("/api/orders/PO-FAKE", json={"status": "APPROVED"}, headers=_auth(operator))
    assert resp.status_code == 403


# --- Reset: admin only ---

def test_operator_cannot_reset(client, db_session):
    operator = _make_user(db_session, "operator")
    resp = client.post("/api/simulate/reset", headers=_auth(operator))
    assert resp.status_code == 403
