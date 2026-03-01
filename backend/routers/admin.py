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
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "role": user.role,
        "is_active": user.is_active,
    }
