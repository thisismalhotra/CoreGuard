# Google OAuth + RBAC Design

**Date:** 2026-03-01
**Status:** Approved

## Overview

Add Google OAuth login and role-based access control (RBAC) to Core-Guard. Backend handles the full OAuth flow, issues JWTs, and enforces permissions. User/role data stored in the existing SQLite database.

## Roles

Four roles: **Admin**, **Operator**, **Approver**, **Viewer**.

- First user to log in is auto-assigned Admin
- All subsequent users default to Viewer
- Admin promotes/demotes users from the UI

## Data Model

One new table in `coreguard.db`:

### `users`

| Column     | Type         | Notes                                    |
|------------|--------------|------------------------------------------|
| id         | INTEGER PK   | Auto-increment                           |
| google_id  | TEXT UNIQUE  | Google `sub` claim — stable identifier   |
| email      | TEXT UNIQUE  | From Google profile                      |
| name       | TEXT         | Display name                             |
| picture    | TEXT         | Avatar URL                               |
| role       | TEXT         | `admin`, `operator`, `viewer`, `approver` — default `viewer` |
| is_active  | BOOLEAN      | Admin can deactivate without deleting    |
| created_at | DATETIME     | Auto-set                                 |
| last_login | DATETIME     | Updated each login                       |

No separate roles table. Role is a simple enum column on the user.

## Auth Flow

1. User clicks "Sign in with Google" on `/login`
2. Frontend redirects to `GET /api/auth/login`
3. Backend redirects to Google OAuth consent screen
4. Google redirects back to `GET /api/auth/callback` with auth code
5. Backend exchanges code for Google user info
6. Backend upserts user in SQLite (first user → admin, otherwise → viewer)
7. Backend signs a JWT and redirects to `/?token=<jwt>`
8. Frontend extracts token, stores in localStorage, cleans URL

### JWT Payload

```json
{
  "sub": "user.id",
  "email": "user@gmail.com",
  "role": "operator",
  "exp": 1234567890
}
```

Token lifetime: 24 hours. No refresh token — user re-authenticates via Google after expiry.

### Socket.io Auth

JWT passed as `auth.token` on connect. Backend validates before accepting the connection.

## Backend Endpoints

### Auth Router (`/api/auth`)

| Method | Path               | Auth     | Description                        |
|--------|--------------------|---------|------------------------------------|
| GET    | `/api/auth/login`  | Public  | Redirects to Google OAuth          |
| GET    | `/api/auth/callback` | Public | Handles OAuth callback, issues JWT |
| GET    | `/api/auth/me`     | Any user | Returns current user profile + role |
| POST   | `/api/auth/logout` | Any user | Clears state (frontend-driven)     |

### Admin Endpoints

| Method | Path                        | Auth  | Description                 |
|--------|-----------------------------|-------|-----------------------------|
| GET    | `/api/admin/users`          | Admin | List all users              |
| PATCH  | `/api/admin/users/{id}/role`| Admin | Change a user's role        |
| PATCH  | `/api/admin/users/{id}/active` | Admin | Activate/deactivate user |

## Permission Matrix

| Action                              | Viewer | Operator | Approver | Admin |
|-------------------------------------|--------|----------|----------|-------|
| View dashboard, logs, KPIs          | Y      | Y        | Y        | Y     |
| View inventory, suppliers           | Y      | Y        | Y        | Y     |
| View DB tables                      | Y      | Y        | Y        | Y     |
| Trigger simulations (God Mode)      | -      | Y        | Y        | Y     |
| Create manual POs                   | -      | Y        | Y        | Y     |
| Approve/reject POs (PENDING_APPROVAL)| -     | -        | Y        | Y     |
| Reset database                      | -      | -        | -        | Y     |
| Manage users                        | -      | -        | -        | Y     |

### Enforcement

- `get_current_user` dependency — decodes JWT, loads user from DB, rejects if inactive
- `require_role(*roles)` dependency — checks user role against allowed roles
- Public endpoints: `/api/auth/login`, `/api/auth/callback`
- Any authenticated: all GET data endpoints
- Operator+: POST simulation endpoints, POST /api/orders
- Approver+: PATCH /api/orders/{po_number}
- Admin only: POST /api/simulate/reset, /api/admin/*

## Frontend Changes

### New

- `/login` page — "Sign in with Google" button
- `AuthProvider` context — stores JWT + user info, provides `useAuth()` hook
- `middleware.ts` — redirects unauthenticated users to `/login`
- User menu in header — avatar, name, role, logout

### Modified

- `api.ts` — attach `Authorization: Bearer <token>` to all requests; redirect to `/login` on 401
- `socket.ts` — pass `{ auth: { token } }` on connect
- `GodMode.tsx` — hidden for Viewers
- `DigitalDock.tsx` — approve/reject buttons hidden unless Approver or Admin
- `CommandCenter.tsx` — reset button hidden unless Admin

### No new frontend auth libraries

Raw fetch + localStorage. No next-auth.

## Backend Changes

### New Dependencies

- `authlib` — Google OAuth2 flow
- `python-jose[cryptography]` — JWT signing/verification
- `python-multipart` — required by FastAPI for OAuth

### New Files

- `backend/routers/auth.py` — login, callback, me, logout endpoints
- `backend/routers/admin.py` — user management endpoints
- `backend/auth.py` — `create_token()`, `decode_token()`, `get_current_user`, `require_role()`

### Modified Files

- `database/models.py` — add `User` model
- `main.py` — register auth + admin routers, Socket.io JWT validation on connect
- `routers/simulations.py` — add role dependencies
- `routers/orders.py` — add role dependencies
- All other routers — add `Depends(get_current_user)`
- `.env.example` — add Google OAuth + JWT env vars

### New Environment Variables

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
JWT_SECRET=...
FRONTEND_URL=http://localhost:3000
```

### CORS Update

Replace `allow_origins=["*"]` with `allow_origins=[FRONTEND_URL]`, set `allow_credentials=True`.
