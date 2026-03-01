"""
Auth router: Google OAuth2 login flow + /me endpoint.

Flow:
1. GET /api/auth/login      -> redirect to Google consent screen
2. GET /api/auth/callback   -> exchange code for user info, upsert user, issue JWT
3. GET /api/auth/me         -> return current user profile (requires JWT)
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
        # First user ever -> admin, otherwise viewer
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
