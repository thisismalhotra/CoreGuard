"""
Core-Guard MVP — FastAPI + Socket.io Server.

Slim entry point that wires together routers and Socket.io.
All endpoint logic lives in the `routers/` package.

Run: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.connection import init_db
from routers import inventory, orders, kpis, agents_meta, simulations


# --- Socket.io setup ---
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # Wildcard origins + credentials=True is invalid per CORS spec
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register routers ---
app.include_router(inventory.router)
app.include_router(orders.router)
app.include_router(kpis.router)
app.include_router(agents_meta.router)
app.include_router(simulations.router)

# --- Store Socket.io and settings on app.state for thread-safe access ---
app.state.sio = sio
app.state.log_delay_seconds = 2.0
simulations.init_sio(app.state)

# --- Mount Socket.io on the ASGI app ---
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


# --- Socket.io events ---

@sio.event
async def connect(sid: str, environ: dict) -> None:
    print(f"Client connected: {sid}")


@sio.event
async def disconnect(sid: str) -> None:
    print(f"Client disconnected: {sid}")


# --- ASGI entry point ---
# Use `socket_app` (not `app`) when running with uvicorn so Socket.io is mounted.
# Command: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
