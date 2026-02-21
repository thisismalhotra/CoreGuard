"""
Core-Guard MVP — FastAPI + Socket.io Server.

Entry point for the backend. Provides:
  - REST endpoints for inventory and orders
  - Socket.io for real-time Glass Box log streaming
  - Simulation endpoints (God Mode) to inject chaos scenarios
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import socketio
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database.connection import init_db, get_db
from database.models import (
    Part, Inventory, PurchaseOrder, Supplier, AgentLog, DemandForecast,
)
from agents.aura import detect_demand_spike
from agents.core_guard import calculate_net_requirements
from agents.ghost_writer import process_buy_orders


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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.io on the ASGI app
socket_app = socketio.ASGIApp(sio, other_app=app)


# --- Socket.io events ---

@sio.event
async def connect(sid: str, environ: dict) -> None:
    print(f"Client connected: {sid}")


@sio.event
async def disconnect(sid: str) -> None:
    print(f"Client disconnected: {sid}")


async def emit_logs(logs: list[dict[str, str]]) -> None:
    """Broadcast Glass Box logs to all connected dashboard clients."""
    for log in logs:
        await sio.emit("agent_log", log)
        # Small delay so the frontend can render logs sequentially
        await asyncio.sleep(0.15)


# --- REST Endpoints ---

@app.get("/api/inventory")
def get_inventory(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return current inventory levels for all parts."""
    records = (
        db.query(Inventory, Part)
        .join(Part, Inventory.part_id == Part.id)
        .all()
    )
    return [
        {
            "part_id": part.part_id,
            "description": part.description,
            "category": part.category.value,
            "on_hand": inv.on_hand,
            "safety_stock": inv.safety_stock,
            "reserved": inv.reserved,
            "available": inv.available,
            "supplier": part.supplier.name if part.supplier else None,
        }
        for inv, part in records
    ]


@app.get("/api/orders")
def get_orders(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return all purchase orders."""
    orders = db.query(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).all()
    return [
        {
            "po_number": po.po_number,
            "part_id": po.part.part_id,
            "supplier": po.supplier.name,
            "quantity": po.quantity,
            "unit_cost": po.unit_cost,
            "total_cost": po.total_cost,
            "status": po.status.value,
            "created_at": po.created_at.isoformat(),
            "triggered_by": po.triggered_by,
        }
        for po in orders
    ]


@app.get("/api/suppliers")
def get_suppliers(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return all suppliers with their status."""
    suppliers = db.query(Supplier).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "lead_time_days": s.lead_time_days,
            "reliability_score": s.reliability_score,
            "is_active": bool(s.is_active),
        }
        for s in suppliers
    ]


@app.get("/api/logs")
def get_logs(limit: int = 50, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return recent agent logs (persisted Glass Box entries)."""
    logs = db.query(AgentLog).order_by(AgentLog.id.desc()).limit(limit).all()
    return [
        {
            "timestamp": log.timestamp.isoformat() if log.timestamp else "",
            "agent": log.agent,
            "message": log.message,
            "type": log.log_type,
        }
        for log in reversed(logs)  # Oldest first for display
    ]


@app.get("/api/kpis")
def get_kpis(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Dashboard KPIs for the Network Status tab."""
    total_inventory = db.query(Inventory).all()
    total_on_hand = sum(i.on_hand for i in total_inventory)
    total_safety = sum(i.safety_stock for i in total_inventory)

    orders = db.query(PurchaseOrder).all()
    auto_approved = sum(1 for o in orders if o.status.value == "APPROVED")
    total_orders = len(orders)

    return {
        "inventory_health": round(total_on_hand / total_safety, 2) if total_safety > 0 else 0,
        "total_on_hand": total_on_hand,
        "total_safety_stock": total_safety,
        "active_threads": 4,  # Number of agents in the system
        "automation_rate": round(auto_approved / total_orders * 100, 1) if total_orders > 0 else 100.0,
        "total_orders": total_orders,
    }


# --- Simulation Endpoints (God Mode) ---

@app.post("/api/simulate/spike")
async def simulate_demand_spike(
    sku: str = "FL-001-T",
    multiplier: float = 3.0,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario A: Simulate a demand spike.

    Full agent chain: Aura (detect) → Core-Guard (MRP) → Ghost-Writer (PO).
    All logs are streamed to the dashboard via Socket.io in real-time.
    """
    all_logs: list[dict[str, str]] = []

    # --- Step 1: Aura detects the spike ---
    forecast = (
        db.query(DemandForecast)
        .join(Part)
        .filter(Part.part_id == sku)
        .first()
    )
    if not forecast:
        return {"error": f"No forecast found for {sku}"}

    spiked_qty = int(forecast.forecast_qty * multiplier)

    aura_result = detect_demand_spike(db, sku, spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    if not aura_result["spike_detected"]:
        return {"status": "no_spike", "aura": aura_result, "logs": all_logs}

    # --- Step 2: Core-Guard calculates net requirements ---
    mrp_result = calculate_net_requirements(db, sku, spiked_qty)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # --- Step 3: Ghost-Writer processes buy orders ---
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]

    ghost_result = {"purchase_orders": [], "logs": []}
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    return {
        "status": "simulation_complete",
        "scenario": "DEMAND_SPIKE",
        "sku": sku,
        "multiplier": multiplier,
        "aura": {
            "spike_detected": aura_result["spike_detected"],
            "multiplier": aura_result["multiplier"],
        },
        "mrp": {
            "shortages": mrp_result["shortages"],
            "actions": mrp_result["actions"],
        },
        "procurement": {
            "purchase_orders": ghost_result["purchase_orders"],
        },
        "logs": all_logs,
    }


@app.post("/api/simulate/supply-shock")
async def simulate_supply_shock(
    supplier_name: str = "AluForge",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario B: Simulate a supplier going offline (e.g., factory fire).
    Deactivates the supplier and emits logs.
    """
    supplier = db.query(Supplier).filter(Supplier.name == supplier_name).first()
    if not supplier:
        return {"error": f"Supplier '{supplier_name}' not found"}

    supplier.is_active = 0
    db.commit()

    log = {
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "agent": "System",
        "message": f"SUPPLY SHOCK: {supplier_name} is now OFFLINE. Affected parts must be re-sourced.",
        "type": "error",
    }
    await sio.emit("agent_log", log)

    return {
        "status": "supplier_disabled",
        "supplier": supplier_name,
        "logs": [log],
    }


# --- ASGI entry point ---
# Use `socket_app` (not `app`) when running with uvicorn so Socket.io is mounted.
# Command: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
