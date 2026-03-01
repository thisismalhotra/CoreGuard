# Google OAuth + RBAC Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Google OAuth login with 4-role RBAC (Admin, Operator, Approver, Viewer) to Core-Guard, protecting all API endpoints and conditionally rendering UI based on user role.

**Architecture:** Backend handles the full Google OAuth2 flow via `authlib`, issues signed JWTs via `python-jose`, and validates them on every request via a `get_current_user` FastAPI dependency. Frontend stores the JWT in localStorage, sends it as `Authorization: Bearer` header, and gates UI elements by role. First user auto-assigned Admin; subsequent users default to Viewer.

**Tech Stack:** authlib (Google OAuth), python-jose[cryptography] (JWT), FastAPI Depends (RBAC), localStorage (frontend token storage), Next.js middleware (route protection)

---

## Task 1: Add Backend Dependencies

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`

**Step 1: Add new packages to requirements.txt**

Add these lines to `backend/requirements.txt` after the existing entries:

```
authlib==1.4.1
python-jose[cryptography]==3.4.0
```

Note: `httpx` is already present. `python-multipart` is not needed since we're not doing form-based auth.

**Step 2: Add new env vars to .env.example**

Add to `backend/.env.example`:

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# JWT
JWT_SECRET=change-me-to-a-random-32-char-string

# Frontend URL (for OAuth redirect and CORS)
FRONTEND_URL=http://localhost:3000
```

**Step 3: Install dependencies**

Run: `cd backend && pip install -r requirements.txt`
Expected: All packages install successfully.

**Step 4: Commit**

```bash
git add backend/requirements.txt backend/.env.example
git commit -m "chore: add authlib and python-jose dependencies for Google OAuth"
```

---

## Task 2: User Model

**Files:**
- Modify: `backend/database/models.py` (after line 383)
- Create: `backend/tests/test_user_model.py`

**Step 1: Write the failing test**

Create `backend/tests/test_user_model.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_user_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'User' from 'database.models'`

**Step 3: Write the User model**

Add to the end of `backend/database/models.py` (after the `AgentLog` class):

```python
class User(Base):
    """Authenticated user with role-based access control."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    picture = Column(Text, nullable=True)
    role = Column(String(20), nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_login = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_user_model.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add backend/database/models.py backend/tests/test_user_model.py
git commit -m "feat: add User model with role-based access control"
```

---

## Task 3: JWT Helpers and Auth Dependencies

**Files:**
- Create: `backend/auth.py`
- Create: `backend/tests/test_auth.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_auth.py`:

```python
"""Tests for JWT helpers and auth dependencies."""

import time

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, User


# Patch env before importing auth module
import os
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'auth'`

**Step 3: Write the auth module**

Create `backend/auth.py`:

```python
"""
JWT helpers and FastAPI auth dependencies for Core-Guard RBAC.

- create_token / decode_token: sign and verify JWTs
- get_current_user: FastAPI Depends() — extracts user from Bearer token
- require_role: FastAPI Depends() — checks user role against allowed roles
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Header
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 24 hours


def create_token(
    user_id: int,
    email: str,
    role: str,
    expires_minutes: int = JWT_EXPIRE_MINUTES,
) -> str:
    """Create a signed JWT with user claims."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": now + timedelta(minutes=expires_minutes),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException 401 on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: extract and validate Bearer token, return active User.
    Usage: current_user: User = Depends(get_current_user)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ")
    payload = decode_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    return user


def require_role(*allowed_roles: str):
    """
    Returns a FastAPI dependency that checks the user's role.
    Usage: current_user: User = Depends(require_role("operator", "admin"))
    """

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{current_user.role}' not authorized. Requires: {', '.join(allowed_roles)}",
            )
        return current_user

    return checker
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pip install pytest-asyncio && pytest tests/test_auth.py -v`
Expected: All 8 tests PASS.

**Step 5: Commit**

```bash
git add backend/auth.py backend/tests/test_auth.py
git commit -m "feat: add JWT helpers and auth dependencies (get_current_user, require_role)"
```

---

## Task 4: Auth Schemas

**Files:**
- Modify: `backend/schemas.py` (add near line 358, after `ErrorResponse`)

**Step 1: Add auth-related Pydantic schemas**

Add to `backend/schemas.py` after the `ErrorResponse` class:

```python
class UserResponse(BaseModel):
    """Public user profile."""

    id: int
    email: str
    name: str
    picture: str | None = None
    role: str
    is_active: bool


class UpdateUserRoleRequest(BaseModel):
    """Admin request to change a user's role."""

    role: str  # admin, operator, approver, viewer


class UpdateUserActiveRequest(BaseModel):
    """Admin request to activate/deactivate a user."""

    is_active: bool
```

**Step 2: Commit**

```bash
git add backend/schemas.py
git commit -m "feat: add auth-related Pydantic schemas (UserResponse, role/active requests)"
```

---

## Task 5: Auth Router (Google OAuth Flow)

**Files:**
- Create: `backend/routers/auth.py`
- Create: `backend/tests/test_auth_router.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_auth_router.py`:

```python
"""Tests for the auth router — login redirect, callback, /me endpoint."""

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
    engine = create_engine("sqlite:///:memory:")
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auth_router.py -v`
Expected: FAIL — no `/api/auth/login` route registered.

**Step 3: Write the auth router**

Create `backend/routers/auth.py`:

```python
"""
Auth router: Google OAuth2 login flow + /me endpoint.

Flow:
1. GET /api/auth/login      → redirect to Google consent screen
2. GET /api/auth/callback   → exchange code for user info, upsert user, issue JWT
3. GET /api/auth/me         → return current user profile (requires JWT)
"""

import os
from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from auth import create_token, get_current_user
from database.connection import get_db
from database.models import User
from schemas import UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

# --- Google OAuth setup ---
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@router.get("/login")
async def login(request: Request):
    """Redirect user to Google OAuth consent screen."""
    callback_url = str(request.url_for("auth_callback"))
    return await oauth.google.authorize_redirect(request, callback_url)


@router.get("/callback", name="auth_callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    """
    Handle Google's OAuth callback.
    Exchanges auth code for user info, upserts user in DB, issues JWT,
    redirects to frontend with token in query param.
    """
    token_data = await oauth.google.authorize_access_token(request)
    user_info = token_data.get("userinfo")

    if not user_info:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_failed")

    google_id = user_info["sub"]
    email = user_info["email"]
    name = user_info.get("name", email)
    picture = user_info.get("picture")

    # Upsert user
    user = db.query(User).filter(User.google_id == google_id).first()
    if user:
        user.name = name
        user.picture = picture
        user.last_login = datetime.now(timezone.utc)
    else:
        # First user ever → admin, otherwise viewer
        is_first_user = db.query(User).count() == 0
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            picture=picture,
            role="admin" if is_first_user else "viewer",
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    jwt_token = create_token(user_id=user.id, email=user.email, role=user.role)
    return RedirectResponse(f"{FRONTEND_URL}?token={jwt_token}")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> dict:
    """Return the current authenticated user's profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture": current_user.picture,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }
```

**Step 4: Register the auth router in main.py**

In `backend/main.py`:

- Add to imports (line 21 area): `from routers import auth as auth_router`
- Add after existing router registrations (line 60 area): `app.include_router(auth_router.router)`
- Add `SessionMiddleware` (required by authlib for OAuth state):

```python
from starlette.middleware.sessions import SessionMiddleware
# ... after app creation, before CORS middleware:
app.add_middleware(SessionMiddleware, secret_key=os.getenv("JWT_SECRET", "dev-secret"))
```

Also add `import os` to the imports.

**Step 5: Run test to verify it passes**

Run: `cd backend && pip install starlette && pytest tests/test_auth_router.py -v`
Expected: All 4 tests PASS.

**Step 6: Commit**

```bash
git add backend/routers/auth.py backend/main.py backend/tests/test_auth_router.py
git commit -m "feat: add auth router with Google OAuth login flow and /me endpoint"
```

---

## Task 6: Admin Router (User Management)

**Files:**
- Create: `backend/routers/admin.py`
- Create: `backend/tests/test_admin_router.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_admin_router.py`:

```python
"""Tests for the admin router — user management."""

import os
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests")

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
    engine = create_engine("sqlite:///:memory:")
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_admin_router.py -v`
Expected: FAIL — no `/api/admin/users` route.

**Step 3: Write the admin router**

Create `backend/routers/admin.py`:

```python
"""
Admin router: user management endpoints (Admin role only).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database.connection import get_db
from database.models import User
from schemas import UpdateUserActiveRequest, UpdateUserRoleRequest, UserResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])

VALID_ROLES = {"admin", "operator", "approver", "viewer"}


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
) -> list[dict]:
    """List all users. Admin only."""
    users = db.query(User).order_by(User.created_at).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "picture": u.picture,
            "role": u.role,
            "is_active": u.is_active,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def change_user_role(
    user_id: int,
    body: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
) -> dict:
    """Change a user's role. Admin only."""
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = body.role
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "role": user.role,
        "is_active": user.is_active,
    }


@router.patch("/users/{user_id}/active", response_model=UserResponse)
def toggle_user_active(
    user_id: int,
    body: UpdateUserActiveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> dict:
    """Activate or deactivate a user. Admin only. Cannot deactivate self."""
    if user_id == current_user.id and not body.is_active:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "role": user.role,
        "is_active": user.is_active,
    }
```

**Step 4: Register the admin router in main.py**

In `backend/main.py`:

- Add to imports: `from routers import admin as admin_router`
- Add router: `app.include_router(admin_router.router)`

**Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_admin_router.py -v`
Expected: All 6 tests PASS.

**Step 6: Commit**

```bash
git add backend/routers/admin.py backend/main.py backend/tests/test_admin_router.py
git commit -m "feat: add admin router for user management (list, change role, deactivate)"
```

---

## Task 7: Protect Existing Backend Routes

**Files:**
- Modify: `backend/routers/inventory.py`
- Modify: `backend/routers/kpis.py`
- Modify: `backend/routers/agents_meta.py`
- Modify: `backend/routers/data_integrity.py`
- Modify: `backend/routers/orders.py`
- Modify: `backend/routers/simulations.py`
- Modify: `backend/main.py` (CORS update)
- Create: `backend/tests/test_rbac_endpoints.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_rbac_endpoints.py`:

```python
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
    engine = create_engine("sqlite:///:memory:")
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_rbac_endpoints.py -v`
Expected: FAIL — unauthenticated requests return 200 (no auth enforced yet).

**Step 3: Add auth dependencies to all routers**

For each router, add the appropriate dependency. The pattern is:

**Read-only routers** (inventory, kpis, agents_meta, data_integrity) — add `current_user: User = Depends(get_current_user)` to every endpoint:

In each file, add to imports:
```python
from auth import get_current_user
from database.models import User
```

Then add `current_user: User = Depends(get_current_user)` as a parameter to each endpoint function.

**orders.py** — add `get_current_user` for GET, `require_role("operator", "approver", "admin")` for POST, `require_role("approver", "admin")` for PATCH:

```python
from auth import get_current_user, require_role
from database.models import User
```

- `get_inventory` (GET): `current_user: User = Depends(get_current_user)`
- `create_order` (POST): `current_user: User = Depends(require_role("operator", "approver", "admin"))`
- `update_order_status` (PATCH): `current_user: User = Depends(require_role("approver", "admin"))`

**simulations.py** — add `require_role("operator", "approver", "admin")` to all simulation endpoints, `require_role("admin")` to reset:

```python
from auth import require_role
from database.models import User
```

- All `/simulate/*` endpoints (except reset): add `current_user: User = Depends(require_role("operator", "approver", "admin"))`
- `/simulate/reset`: replace the `X-Reset-Token` header check with `current_user: User = Depends(require_role("admin"))`

**Step 4: Update CORS in main.py**

Replace the CORS middleware block in `backend/main.py`:

```python
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Step 5: Update Socket.io CORS**

In `backend/main.py`, update the `sio` initialization:

```python
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
)
```

**Step 6: Add Socket.io JWT validation on connect**

Update the `connect` handler in `backend/main.py`:

```python
from auth import decode_token

@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> bool:
    """Validate JWT on Socket.io connection."""
    if not auth or not auth.get("token"):
        logger.warning("Socket connection rejected: no auth token (sid=%s)", sid)
        return False
    try:
        decode_token(auth["token"])
        logger.info("Client connected: %s", sid)
        return True
    except Exception:
        logger.warning("Socket connection rejected: invalid token (sid=%s)", sid)
        return False
```

**Step 7: Run test to verify it passes**

Run: `cd backend && pytest tests/test_rbac_endpoints.py -v`
Expected: All tests PASS.

**Step 8: Run full test suite to check for regressions**

Run: `cd backend && pytest tests/ -v --tb=short`
Expected: All tests PASS. Some existing tests may need auth headers added — fix any failures by adding a test user + auth header in the test fixtures.

**Step 9: Commit**

```bash
git add backend/routers/ backend/main.py backend/tests/test_rbac_endpoints.py
git commit -m "feat: protect all API endpoints with RBAC, add Socket.io JWT validation"
```

---

## Task 8: Frontend Auth Context and Token Management

**Files:**
- Create: `frontend/src/lib/auth.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/socket.ts`

**Step 1: Create the auth context**

Create `frontend/src/lib/auth.tsx`:

```tsx
"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";

type User = {
  id: number;
  email: string;
  name: string;
  picture: string | null;
  role: "admin" | "operator" | "approver" | "viewer";
  is_active: boolean;
};

type AuthContextType = {
  user: User | null;
  token: string | null;
  loading: boolean;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  logout: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function hasRole(user: User | null, ...roles: string[]): boolean {
  return user !== null && roles.includes(user.role);
}

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem("cg_token");
    setToken(null);
    setUser(null);
    window.location.href = "/login";
  }, []);

  // On mount: check for token in URL (OAuth redirect) or localStorage
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");

    if (urlToken) {
      localStorage.setItem("cg_token", urlToken);
      setToken(urlToken);
      // Clean the URL
      window.history.replaceState({}, "", window.location.pathname);
    } else {
      const stored = localStorage.getItem("cg_token");
      if (stored) {
        setToken(stored);
      } else {
        setLoading(false);
      }
    }
  }, []);

  // When token changes, fetch user profile
  useEffect(() => {
    if (!token) return;

    fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Unauthorized");
        return res.json();
      })
      .then((data) => {
        setUser(data);
        setLoading(false);
      })
      .catch(() => {
        localStorage.removeItem("cg_token");
        setToken(null);
        setUser(null);
        setLoading(false);
      });
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token, loading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
```

**Step 2: Wrap the app in AuthProvider**

In `frontend/src/app/layout.tsx`, add the `AuthProvider` wrapping `ThemeProvider`:

```tsx
import { AuthProvider } from "@/lib/auth";
// ...
<body ...>
  <AuthProvider>
    <ThemeProvider>
      <main id="main-content">{children}</main>
    </ThemeProvider>
    <Toaster />
  </AuthProvider>
</body>
```

**Step 3: Update api.ts to attach JWT**

In `frontend/src/lib/api.ts`, modify the `fetchJSON` function to read the token from localStorage and attach it:

```typescript
async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("cg_token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // ... rest of existing retry logic, but use the new headers object
}
```

Also: on 401 response, redirect to `/login`:

```typescript
if (res.status === 401 && typeof window !== "undefined") {
  localStorage.removeItem("cg_token");
  window.location.href = "/login";
  throw new Error("Unauthorized");
}
```

**Step 4: Update socket.ts to pass JWT on connect**

In `frontend/src/lib/socket.ts`, update the `getSocket` function:

```typescript
export function getSocket(): Socket {
  if (!globalForSocket.__coreGuardSocket) {
    const token = typeof window !== "undefined" ? localStorage.getItem("cg_token") : null;
    globalForSocket.__coreGuardSocket = io(BACKEND_URL, {
      transports: ["websocket", "polling"],
      autoConnect: false,
      auth: token ? { token } : undefined,
    });
  }
  return globalForSocket.__coreGuardSocket;
}
```

**Step 5: Commit**

```bash
git add frontend/src/lib/auth.tsx frontend/src/app/layout.tsx frontend/src/lib/api.ts frontend/src/lib/socket.ts
git commit -m "feat: add AuthProvider, attach JWT to API requests and Socket.io"
```

---

## Task 9: Login Page

**Files:**
- Create: `frontend/src/app/login/page.tsx`

**Step 1: Create the login page**

Create `frontend/src/app/login/page.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function LoginPage() {
  const { user, loading } = useAuth();

  // If already logged in, redirect to home
  useEffect(() => {
    if (!loading && user) {
      window.location.href = "/";
    }
  }, [user, loading]);

  const handleLogin = () => {
    window.location.href = `${API_BASE}/api/auth/login`;
  };

  const errorParam = typeof window !== "undefined"
    ? new URLSearchParams(window.location.search).get("error")
    : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">Core-Guard</CardTitle>
          <p className="text-sm text-muted-foreground">
            Autonomous Supply Chain Operating System
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {errorParam && (
            <p className="text-center text-sm text-destructive">
              Login failed. Please try again.
            </p>
          )}
          <Button onClick={handleLogin} className="w-full" size="lg">
            Sign in with Google
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/login/page.tsx
git commit -m "feat: add login page with Google sign-in button"
```

---

## Task 10: Next.js Middleware (Route Protection)

**Files:**
- Create: `frontend/src/middleware.ts`

**Step 1: Create the middleware**

Create `frontend/src/middleware.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Allow static assets and API routes
  if (pathname.startsWith("/_next") || pathname.startsWith("/api") || pathname.includes(".")) {
    return NextResponse.next();
  }

  // Check for token in cookie or URL param (OAuth redirect lands on / with ?token=)
  const token = request.cookies.get("cg_token")?.value
    || request.nextUrl.searchParams.get("token");

  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

**Important note:** Since we're using localStorage (not cookies) for the JWT, the middleware can't validate the token server-side on initial page loads. The middleware checks for the `token` URL param (present during OAuth redirect) as a fallback. For subsequent navigations, the `AuthProvider` handles redirects client-side. If you want stricter SSR protection, we can add a cookie mirror later.

**Alternative simpler approach:** If the middleware cookie check is too fragile, remove the middleware entirely and rely on the `AuthProvider` to redirect unauthenticated users to `/login` client-side. This is simpler and works fine for an MVP.

**Step 2: Commit**

```bash
git add frontend/src/middleware.ts
git commit -m "feat: add Next.js middleware for route protection"
```

---

## Task 11: Role-Based UI Gating

**Files:**
- Modify: `frontend/src/components/CommandCenter.tsx`
- Modify: `frontend/src/components/GodMode.tsx`
- Modify: `frontend/src/components/DigitalDock.tsx`

**Step 1: Add user menu and role gating to CommandCenter**

In `frontend/src/components/CommandCenter.tsx`:

- Import `useAuth` and `hasRole` from `@/lib/auth`
- Add at the top of the component: `const { user, logout } = useAuth();`
- Add a user menu in the header area showing avatar, name, role, and logout button
- Conditionally render the God Mode tab:

```tsx
{hasRole(user, "operator", "approver", "admin") && (
  <TabsTrigger value="godmode">God Mode</TabsTrigger>
)}
```

- Pass the user role to child components that need it:

```tsx
{hasRole(user, "operator", "approver", "admin") && (
  <TabsContent value="godmode">
    <GodMode userRole={user?.role} />
  </TabsContent>
)}
```

**Step 2: Gate the reset button in GodMode**

In `frontend/src/components/GodMode.tsx`:

- Accept a `userRole` prop
- Only show the Reset button if `userRole === "admin"`:

```tsx
{userRole === "admin" && (
  // Reset button JSX
)}
```

**Step 3: Gate approve/reject in DigitalDock**

In `frontend/src/components/DigitalDock.tsx`:

- Import `useAuth` and `hasRole`
- Only show approve/reject buttons if the user is an approver or admin:

```tsx
{hasRole(user, "approver", "admin") && (
  // Approve/Reject buttons
)}
```

**Step 4: Commit**

```bash
git add frontend/src/components/CommandCenter.tsx frontend/src/components/GodMode.tsx frontend/src/components/DigitalDock.tsx
git commit -m "feat: gate UI elements by user role (God Mode, reset, PO approval)"
```

---

## Task 12: Update Existing Tests

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: existing test files as needed

**Step 1: Add auth helper to conftest**

In `backend/tests/conftest.py`, add a shared fixture for creating authenticated test users:

```python
import os
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests")

from database.models import User
from auth import create_token

@pytest.fixture
def admin_user(db):
    """Create an admin user and return (user, auth_headers) tuple."""
    user = User(google_id="g-admin", email="admin@test.com", name="Admin", role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user_id=user.id, email=user.email, role=user.role)
    return user, {"Authorization": f"Bearer {token}"}
```

**Step 2: Fix any failing tests by adding auth headers**

Existing tests that hit protected endpoints will now return 401. Add auth headers from the fixture to each test that calls the API.

**Step 3: Run full test suite**

Run: `cd backend && pytest tests/ -v --tb=short`
Expected: All tests PASS.

Run: `cd frontend && npx vitest run`
Expected: All tests PASS (frontend tests mock fetch, so auth shouldn't break them).

**Step 4: Commit**

```bash
git add backend/tests/ frontend/src/components/__tests__/
git commit -m "test: update existing tests to work with auth enforcement"
```

---

## Task 13: Update Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `backend/.env.example` (already done in Task 1)

**Step 1: Update CLAUDE.md**

Add an "Authentication" section after "Critical Architectural Rules" documenting:
- The 4 roles and their permissions
- The auth flow (Google OAuth → JWT)
- The `get_current_user` and `require_role()` dependency pattern
- New env vars required

**Step 2: Update README.md**

- Add "Authentication" section in Quick Start explaining Google Cloud Console setup
- Update the environment variables section with the new vars
- Document the 4 roles and first-user-is-admin behavior

**Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: add authentication setup and RBAC documentation"
```
