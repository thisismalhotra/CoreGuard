"""
Core-Guard MVP — FastAPI + Socket.io Server.

Slim entry point that wires together routers and Socket.io.
All endpoint logic lives in the `routers/` package.

Run: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from auth import decode_token
from database.connection import init_db
from rate_limit import limiter
from routers import admin as admin_router, agents_meta, auth as auth_router, inventory, kpis, orders, simulations
from routers.data_integrity import router as data_integrity_router

logger = logging.getLogger(__name__)

# --- Socket.io setup ---
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Core-Guard MVP",
    description="Autonomous Supply Chain Operating System — Glass Box Simulation",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("JWT_SECRET", "dev-secret"))

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register routers ---
app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(inventory.router)
app.include_router(orders.router)
app.include_router(kpis.router)
app.include_router(agents_meta.router)
app.include_router(simulations.router)
app.include_router(data_integrity_router)

# --- Store Socket.io and settings on app.state for thread-safe access ---
app.state.sio = sio
app.state.log_delay_seconds = 2.0
simulations.init_sio(app.state)

# --- Mount Socket.io on the ASGI app ---
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


# --- Socket.io events ---

@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None) -> bool:
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


@sio.event
async def disconnect(sid: str) -> None:
    logger.info("Client disconnected: %s", sid)


# --- ASGI entry point ---
# Use `socket_app` (not `app`) when running with uvicorn so Socket.io is mounted.
# Command: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
