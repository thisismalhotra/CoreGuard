"""
Core-Guard MVP — FastAPI + Socket.io Server.

Slim entry point that wires together routers and Socket.io.
All endpoint logic lives in the `routers/` package.

Run: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
"""

from dotenv import load_dotenv

load_dotenv()

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

import socketio

# --- Structured logging setup ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from auth import decode_token
from database.connection import SessionLocal, init_db
from database.models import Supplier
from rate_limit import limiter
from routers import admin as admin_router
from routers import agents_meta, chat, data_upload, inventory, kpis, orders, simulations
from routers import auth as auth_router
from routers.data_integrity import router as data_integrity_router
from seed import _do_seed

logger = logging.getLogger(__name__)

# --- Socket.io setup ---
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://coreguard-frontend.onrender.com",
    ],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Auto-seed if database is empty (first deploy)
    db = SessionLocal()
    try:
        if not db.query(Supplier).first():
            logger.info("Empty database detected — auto-seeding FL-001 dataset")
            _do_seed(db)
            db.commit()
            logger.info("Auto-seed complete")
    except Exception:
        db.rollback()
        logger.exception("Auto-seed failed")
    finally:
        db.close()
    yield


app = FastAPI(
    title="Core-Guard MVP",
    description="Autonomous Supply Chain Operating System — Glass Box Simulation",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Trust reverse proxy headers (Render, Railway, etc.) so request.url_for()
# generates https:// URLs for OAuth callbacks.
if os.getenv("DATABASE_URL"):  # proxy exists in production
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

app.add_middleware(SessionMiddleware, secret_key=os.getenv("JWT_SECRET", "dev-secret"))

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Build allowed origins: always include localhost + explicit production URL
_allowed_origins = [
    FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://coreguard-frontend.onrender.com",
]
# Deduplicate while preserving order
_allowed_origins = list(dict.fromkeys(_allowed_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Health check (for Render / load balancer probes) ---
@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


# --- Register routers ---
app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(inventory.router)
app.include_router(orders.router)
app.include_router(kpis.router)
app.include_router(agents_meta.router)
app.include_router(simulations.router)
app.include_router(data_integrity_router)
app.include_router(data_upload.router)
app.include_router(chat.router)

# --- Store Socket.io and settings on app.state for thread-safe access ---
app.state.sio = sio
app.state.log_delay_seconds = 2.0
simulations.init_sio(app.state)

# --- Mount Socket.io on the ASGI app ---
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


# --- Socket.io events ---

@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None) -> bool:
    """Validate JWT on Socket.io connection and join user-specific room."""
    if not auth or not auth.get("token"):
        logger.warning("Socket connection rejected: no auth token (sid=%s)", sid)
        return False
    try:
        payload = decode_token(auth["token"])
        user_id = payload.get("user_id")
        logger.info("Client connected: sid=%s user=%s", sid, user_id)

        # Join user-specific room for targeted emissions (future use)
        if user_id:
            await sio.enter_room(sid, f"user_{user_id}")

        # All authenticated users join the dashboard room for shared Glass Box logs
        await sio.enter_room(sid, "dashboard")
        return True
    except Exception:
        logger.warning("Socket connection rejected: invalid token (sid=%s)", sid)
        return False


@sio.event
async def disconnect(sid: str) -> None:
    logger.info("Client disconnected: %s", sid)


# --- ASGI entry point ---
# Use `socket_app` (not `app`) when running with uvicorn so Socket.io is mounted.
# Command: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
