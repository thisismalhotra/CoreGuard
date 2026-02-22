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
    BOMEntry, QualityInspection,
)
from agents.aura import detect_demand_spike
from agents.dispatcher import triage_demand_spike
from agents.core_guard import calculate_net_requirements
from agents.ghost_writer import process_buy_orders
from agents.eagle_eye import inspect_batch


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
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Configurable log delay (seconds between each log line in simulations)
LOG_DELAY_SECONDS: float = 2.0


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
        # Simulate real-world agent processing time
        await asyncio.sleep(LOG_DELAY_SECONDS)


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

    # Count distinct agents that have logged activity
    active_agents = db.query(AgentLog.agent).distinct().count()

    return {
        "inventory_health": round(total_on_hand / total_safety, 2) if total_safety > 0 else 0,
        "total_on_hand": total_on_hand,
        "total_safety_stock": total_safety,
        "active_threads": active_agents,
        "automation_rate": round(auto_approved / total_orders * 100, 1) if total_orders > 0 else 100.0,
        "total_orders": total_orders,
    }


# --- Settings ---

@app.get("/api/settings/log-delay")
def get_log_delay() -> dict[str, float]:
    """Return the current log delay setting."""
    return {"delay": LOG_DELAY_SECONDS}


@app.post("/api/settings/log-delay")
def set_log_delay(delay: float = 2.0) -> dict[str, float]:
    """Update the delay (in seconds) between each log line during simulations."""
    global LOG_DELAY_SECONDS
    # Clamp to reasonable range
    LOG_DELAY_SECONDS = max(0.5, min(delay, 5.0))
    return {"delay": LOG_DELAY_SECONDS}


# --- Agents Metadata ---

@app.get("/api/agents")
def get_agents() -> list[dict[str, Any]]:
    """Return metadata for all agents in the system."""
    return [
        {
            "name": "Aura",
            "role": "Demand Sensing Agent",
            "description": "Monitors real-time sales data and demand signals. Detects when actual demand deviates from forecast thresholds, triggering the agent chain.",
            "trigger": "Incoming demand data exceeds forecast by 20%+ (SPIKE_THRESHOLD = 1.2x)",
            "inputs": ["SKU identifier", "New actual demand quantity", "Demand forecast table"],
            "outputs": ["DEMAND_SPIKE event", "Spike multiplier", "Glass Box logs"],
            "downstream": "Dispatcher",
            "constitution": None,
            "rules": [
                "Stateless — reads DB state, never caches",
                "Pure Python math for spike detection (Rule B)",
                "Fires DEMAND_SPIKE when actual > forecast × 1.2",
                "Updates actual_qty in DemandForecast table",
            ],
            "color": "purple",
            "icon": "Radio",
            "source_file": "agents/aura.py",
        },
        {
            "name": "Dispatcher",
            "role": "Triage & Prioritisation Agent",
            "description": "Sits between Aura and Core-Guard. Analyses BOM components, scores each by criticality, lead-time sensitivity, and shortage severity, then hands Core-Guard a prioritised processing queue.",
            "trigger": "DEMAND_SPIKE event from Aura",
            "inputs": ["SKU identifier", "Demand quantity", "BOM table", "Part profiles (criticality, lead_time_sensitivity)"],
            "outputs": ["Prioritised component queue", "Risk assessment", "Glass Box logs"],
            "downstream": "Core-Guard",
            "constitution": None,
            "rules": [
                "Stateless — reads DB state, never caches",
                "Priority score = criticality_weight + (lead_time_sensitivity × 30) + (gap_severity × 20)",
                "CRITICAL parts: weight 100, HIGH: 75, MEDIUM: 50, LOW: 25",
                "Components sorted by priority score descending — highest first",
                "Flags CRITICAL components for expedited processing",
                "Provides risk assessment: total components, at-risk count, critical count",
            ],
            "color": "cyan",
            "icon": "GitBranch",
            "source_file": "agents/dispatcher.py",
        },
        {
            "name": "Core-Guard",
            "role": "MRP Logic Agent",
            "description": "The brain of the supply chain. Performs BOM explosion, calculates net material requirements using deterministic math, and applies criticality-based routing rules to decide procurement strategy.",
            "trigger": "Prioritised queue from Dispatcher, or direct invocation from simulation endpoints",
            "inputs": ["SKU identifier", "Demand quantity", "BOM table", "Inventory table", "Part criticality profiles"],
            "outputs": ["Shortage analysis", "REALLOCATE actions", "BUY_ORDER actions (with expedite flags)", "Glass Box logs"],
            "downstream": "Ghost-Writer",
            "constitution": None,
            "rules": [
                "Stateless — operates on DB state passed in",
                "All arithmetic done in Python (Rule B: never ask LLM to calculate)",
                "Net Requirement = (Demand × BOM qty_per) - Available Inventory",
                "CRITICAL parts: 1.5x buffer, reallocation BLOCKED, EXPEDITED procurement",
                "HIGH parts: 1.25x buffer, reallocation allowed (with safeguards), EXPEDITED",
                "MEDIUM parts: exact gap, standard reallocation, normal procurement",
                "LOW parts: exact gap, free reallocation, no rush",
            ],
            "color": "blue",
            "icon": "Shield",
            "source_file": "agents/core_guard.py",
        },
        {
            "name": "Ghost-Writer",
            "role": "Procurement & PO Generation Agent",
            "description": "Receives BUY_ORDER actions from Core-Guard, validates spend against the Financial Constitution, creates Purchase Order records, and generates PDF documents.",
            "trigger": "BUY_ORDER actions from Core-Guard or Eagle-Eye",
            "inputs": ["List of BUY_ORDER actions", "Parts table", "Suppliers table"],
            "outputs": ["PurchaseOrder records", "PDF documents", "Glass Box logs"],
            "downstream": None,
            "constitution": "FINANCIAL GUARDRAIL (Rule C): If total_cost > $5,000, the PO status MUST be set to PENDING_APPROVAL. This is hard-coded and CANNOT be overridden by any LLM or agent. Human approval is required before funds can be committed.",
            "rules": [
                "Hard-coded spend limit: FINANCIAL_CONSTITUTION_MAX_SPEND = $5,000.00",
                "total_cost > $5,000 → OrderStatus.PENDING_APPROVAL (no exceptions)",
                "total_cost ≤ $5,000 → OrderStatus.APPROVED (auto-approved)",
                "Generates PDF PO via fpdf2 to backend/generated_pos/",
                "Each PO gets a unique PO number (PO-XXXXXXXX)",
                "The LLM cannot override the financial constitution",
            ],
            "color": "emerald",
            "icon": "FileText",
            "source_file": "agents/ghost_writer.py",
        },
        {
            "name": "Eagle-Eye",
            "role": "Quality Inspection Agent",
            "description": "Simulates receiving physical shipments at the Digital Dock. Runs automated sensor scans against CAD spec tolerances. Passes or fails batches and triggers emergency remediation on failure.",
            "trigger": "Shipment arrival at Digital Dock (simulated via /simulate/quality-fail)",
            "inputs": ["Part ID", "Batch size", "CAD spec tolerances"],
            "outputs": ["PASS/FAIL inspection result", "Sensor readings", "BUY_ORDER actions (on fail)", "Glass Box logs"],
            "downstream": "Ghost-Writer (on failure)",
            "constitution": None,
            "rules": [
                "Stateless — operates on DB state passed in",
                "Compares sensor readings against hard-coded CAD_SPECS tolerances",
                "CH-101: hardness (8.0–10.0), dimension tolerance (±0.05mm)",
                "SW-303: resistance (4.5–5.5Ω), cycle life (min 10,000)",
                "LNS-505: clarity (min 95%), focal length tolerance (±0.1mm)",
                "FAIL → quarantine batch (stock NOT added), trigger emergency reorder",
                "PASS → add batch to inventory on_hand",
                "AI Handover: in production, would use Pinecone vector DB for CAD comparisons",
            ],
            "color": "orange",
            "icon": "Eye",
            "source_file": "agents/eagle_eye.py",
        },
    ]


# --- DB Viewer ---

@app.get("/api/db/suppliers")
def db_suppliers(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Raw suppliers table dump."""
    rows = db.query(Supplier).order_by(Supplier.id).all()
    return [
        {"id": s.id, "name": s.name, "contact_email": s.contact_email,
         "lead_time_days": s.lead_time_days, "reliability_score": s.reliability_score,
         "is_active": bool(s.is_active)}
        for s in rows
    ]


@app.get("/api/db/parts")
def db_parts(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Raw parts table dump."""
    rows = db.query(Part).order_by(Part.id).all()
    return [
        {"id": p.id, "part_id": p.part_id, "description": p.description,
         "category": p.category.value, "unit_cost": p.unit_cost,
         "criticality": p.criticality.value, "lead_time_sensitivity": p.lead_time_sensitivity,
         "substitute_pool_size": p.substitute_pool_size,
         "supplier": p.supplier.name if p.supplier else None}
        for p in rows
    ]


@app.get("/api/db/inventory")
def db_inventory(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Raw inventory table dump."""
    rows = db.query(Inventory).order_by(Inventory.id).all()
    return [
        {"id": inv.id, "part": inv.part.part_id if inv.part else None,
         "on_hand": inv.on_hand, "safety_stock": inv.safety_stock,
         "reserved": inv.reserved, "available": inv.available,
         "last_updated": inv.last_updated.isoformat() if inv.last_updated else None}
        for inv in rows
    ]


@app.get("/api/db/bom")
def db_bom(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Raw BOM table dump."""
    rows = db.query(BOMEntry).order_by(BOMEntry.id).all()
    return [
        {"id": b.id,
         "parent": b.parent.part_id if b.parent else None,
         "component": b.component.part_id if b.component else None,
         "quantity_per": b.quantity_per}
        for b in rows
    ]


@app.get("/api/db/orders")
def db_orders(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Raw purchase_orders table dump."""
    rows = db.query(PurchaseOrder).order_by(PurchaseOrder.id).all()
    return [
        {"id": po.id, "po_number": po.po_number,
         "part": po.part.part_id if po.part else None,
         "supplier": po.supplier.name if po.supplier else None,
         "quantity": po.quantity, "unit_cost": po.unit_cost,
         "total_cost": po.total_cost, "status": po.status.value,
         "triggered_by": po.triggered_by,
         "created_at": po.created_at.isoformat() if po.created_at else None}
        for po in rows
    ]


@app.get("/api/db/demand_forecast")
def db_demand_forecast(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Raw demand_forecast table dump."""
    rows = db.query(DemandForecast).order_by(DemandForecast.id).all()
    return [
        {"id": d.id, "part": d.part.part_id if d.part else None,
         "forecast_qty": d.forecast_qty, "actual_qty": d.actual_qty,
         "period": d.period,
         "updated_at": d.updated_at.isoformat() if d.updated_at else None}
        for d in rows
    ]


@app.get("/api/db/quality_inspections")
def db_quality_inspections(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Raw quality_inspections table dump."""
    rows = db.query(QualityInspection).order_by(QualityInspection.id).all()
    return [
        {"id": q.id, "part": q.part.part_id if q.part else None,
         "batch_size": q.batch_size, "result": q.result.value,
         "notes": q.notes,
         "inspected_at": q.inspected_at.isoformat() if q.inspected_at else None}
        for q in rows
    ]


@app.get("/api/db/agent_logs")
def db_agent_logs(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Raw agent_logs table dump."""
    rows = db.query(AgentLog).order_by(AgentLog.id.desc()).limit(200).all()
    return [
        {"id": log.id, "agent": log.agent, "message": log.message,
         "log_type": log.log_type,
         "timestamp": log.timestamp.isoformat() if log.timestamp else None}
        for log in rows
    ]


# --- Simulation Endpoints (God Mode) ---

@app.post("/api/simulate/spike")
async def simulate_demand_spike(
    sku: str = "FL-001-T",
    multiplier: float = 3.0,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario A: Simulate a demand spike.

    Full agent chain: Aura → Dispatcher → Core-Guard → Ghost-Writer.
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

    # --- Step 2: Dispatcher triages components by criticality ---
    dispatch_result = triage_demand_spike(db, sku, spiked_qty)
    all_logs.extend(dispatch_result["logs"])
    await emit_logs(dispatch_result["logs"])

    # --- Step 3: Core-Guard calculates net requirements (now criticality-aware) ---
    mrp_result = calculate_net_requirements(db, sku, spiked_qty)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # --- Step 4: Ghost-Writer processes buy orders ---
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

    Full chain: Disable supplier → Identify affected parts → Core-Guard checks
    if current inventory can cover safety stock → Ghost-Writer issues emergency
    POs from alternate suppliers if needed.
    """
    from datetime import datetime, timezone

    all_logs: list[dict[str, str]] = []

    supplier = db.query(Supplier).filter(Supplier.name == supplier_name).first()
    if not supplier:
        return {"error": f"Supplier '{supplier_name}' not found"}

    # --- Step 1: Disable the supplier ---
    supplier.is_active = 0
    db.flush()

    shock_log = AgentLog(
        agent="System",
        message=f"SUPPLY SHOCK: {supplier_name} is now OFFLINE. Initiating emergency response.",
        log_type="error",
    )
    db.add(shock_log)
    db.flush()
    shock_dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "System",
        "message": shock_log.message,
        "type": "error",
    }
    all_logs.append(shock_dict)
    await emit_logs([shock_dict])

    # --- Step 2: Identify affected parts and assess impact ---
    affected_parts = db.query(Part).filter(Part.supplier_id == supplier.id).all()
    emergency_orders: list[dict[str, Any]] = []

    for part in affected_parts:
        inv = part.inventory
        if not inv:
            continue

        # Log the impact assessment
        impact_log = AgentLog(
            agent="Core-Guard",
            message=f"Assessing impact: {part.part_id} ({part.description}) — "
                    f"primary supplier {supplier_name} offline.",
            log_type="warning",
        )
        db.add(impact_log)
        db.flush()
        impact_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Core-Guard",
            "message": impact_log.message,
            "type": "warning",
        }
        all_logs.append(impact_dict)
        await emit_logs([impact_dict])

        # Check if current stock is below safety threshold
        status_log = AgentLog(
            agent="Core-Guard",
            message=f"Inventory check: {part.part_id} — on_hand={inv.on_hand}, "
                    f"safety_stock={inv.safety_stock}, available={inv.available}.",
            log_type="info",
        )
        db.add(status_log)
        db.flush()
        status_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Core-Guard",
            "message": status_log.message,
            "type": "info",
        }
        all_logs.append(status_dict)
        await emit_logs([status_dict])

        # With supplier offline, we need to secure safety stock from alternates
        # Order enough to cover safety stock buffer
        order_qty = inv.safety_stock  # Replenish full safety stock from alternate

        # Find an alternate supplier for this part category
        alternate = (
            db.query(Supplier)
            .filter(
                Supplier.id != supplier.id,
                Supplier.is_active == 1,
            )
            .order_by(Supplier.reliability_score.desc())
            .first()
        )

        if not alternate:
            no_alt_log = AgentLog(
                agent="Core-Guard",
                message=f"CRITICAL: No alternate suppliers available for {part.part_id}!",
                log_type="error",
            )
            db.add(no_alt_log)
            db.flush()
            no_alt_dict = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "Core-Guard",
                "message": no_alt_log.message,
                "type": "error",
            }
            all_logs.append(no_alt_dict)
            await emit_logs([no_alt_dict])
            continue

        switch_log = AgentLog(
            agent="Core-Guard",
            message=f"Switching {part.part_id} to alternate supplier: {alternate.name} "
                    f"(reliability: {alternate.reliability_score}, lead time: {alternate.lead_time_days}d).",
            log_type="info",
        )
        db.add(switch_log)
        db.flush()
        switch_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Core-Guard",
            "message": switch_log.message,
            "type": "info",
        }
        all_logs.append(switch_dict)
        await emit_logs([switch_dict])

        # Build emergency BUY_ORDER
        emergency_orders.append({
            "type": "BUY_ORDER",
            "part_id": part.part_id,
            "quantity": order_qty,
            "unit_cost": part.unit_cost,
            "total_cost": round(order_qty * part.unit_cost, 2),
            "supplier_id": alternate.id,
            "supplier_name": alternate.name,
            "triggered_by": "Core-Guard",
        })

        order_log = AgentLog(
            agent="Core-Guard",
            message=f"Emergency BUY_ORDER: {order_qty}x {part.part_id} from {alternate.name} "
                    f"@ ${round(order_qty * part.unit_cost, 2):.2f}.",
            log_type="warning",
        )
        db.add(order_log)
        db.flush()
        order_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Core-Guard",
            "message": order_log.message,
            "type": "warning",
        }
        all_logs.append(order_dict)
        await emit_logs([order_dict])

    db.commit()

    # --- Step 3: Ghost-Writer processes emergency POs ---
    ghost_result = {"purchase_orders": [], "logs": []}
    if emergency_orders:
        ghost_result = process_buy_orders(db, emergency_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    # Final summary
    summary_log = AgentLog(
        agent="System",
        message=f"Supply shock response complete: {supplier_name} disabled, "
                f"{len(affected_parts)} part(s) affected, "
                f"{len(ghost_result['purchase_orders'])} emergency PO(s) generated.",
        log_type="success",
    )
    db.add(summary_log)
    db.commit()
    summary_dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "System",
        "message": summary_log.message,
        "type": "success",
    }
    all_logs.append(summary_dict)
    await emit_logs([summary_dict])

    return {
        "status": "simulation_complete",
        "scenario": "SUPPLY_SHOCK",
        "supplier": supplier_name,
        "affected_parts": [p.part_id for p in affected_parts],
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


@app.post("/api/simulate/quality-fail")
async def simulate_quality_fail(
    part_id: str = "CH-101",
    batch_size: int = 150,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario C: Simulate a batch of parts failing quality inspection at the dock.

    Full chain: Eagle-Eye inspects → detects failures → quarantines batch →
    triggers emergency reorder via Ghost-Writer.
    """
    all_logs: list[dict[str, str]] = []

    # Eagle-Eye inspects the batch (force_fail=True for simulation drama)
    inspection_result = inspect_batch(db, part_id, batch_size, force_fail=True)
    all_logs.extend(inspection_result["logs"])
    await emit_logs(inspection_result["logs"])

    # If failed, Ghost-Writer processes the emergency reorder
    ghost_result = {"purchase_orders": [], "logs": []}
    buy_orders = inspection_result.get("actions", [])
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    return {
        "status": "simulation_complete",
        "scenario": "QUALITY_FAIL",
        "part_id": part_id,
        "batch_size": batch_size,
        "inspection_result": inspection_result["result"],
        "failed_checks": inspection_result.get("failed_checks", []),
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


@app.post("/api/simulate/cascade-failure")
async def simulate_cascade_failure(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario D: Cascade Failure — demand spike hits while AluForge is already offline.
    Core-Guard must simultaneously handle reallocation AND source from alternates.
    Tests multi-agent coordination under compounding stress.
    """
    from datetime import datetime, timezone
    all_logs: list[dict[str, str]] = []

    def _sys_log(msg: str, log_type: str = "info") -> dict:
        entry = AgentLog(agent="System", message=msg, log_type=log_type)
        db.add(entry)
        db.flush()
        return {"timestamp": datetime.now(timezone.utc).isoformat(), "agent": "System", "message": msg, "type": log_type}

    # --- Act 1: Knock out AluForge silently first ---
    aluforge = db.query(Supplier).filter(Supplier.name == "AluForge").first()
    if aluforge:
        aluforge.is_active = 0
        db.flush()

    log = _sys_log("CASCADE EVENT INITIATED: AluForge goes offline at the same moment a 500% demand spike hits FL-001-T.", "error")
    all_logs.append(log)
    await emit_logs([log])

    log = _sys_log("Two simultaneous crises detected. Agents mobilising...", "warning")
    all_logs.append(log)
    await emit_logs([log])

    # --- Act 2: Aura detects the spike ---
    forecast = db.query(DemandForecast).join(Part).filter(Part.part_id == "FL-001-T").first()
    if not forecast:
        return {"error": "No forecast found for FL-001-T"}

    spiked_qty = int(forecast.forecast_qty * 5.0)
    aura_result = detect_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    # --- Act 2.5: Dispatcher triages under compounding stress ---
    dispatch_result = triage_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(dispatch_result["logs"])
    await emit_logs(dispatch_result["logs"])

    # --- Act 3: Core-Guard runs MRP — will find CH-101 shortage AND no primary supplier ---
    mrp_result = calculate_net_requirements(db, "FL-001-T", spiked_qty)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # --- Act 4: For BUY_ORDERs involving AluForge, reroute to best alternate ---
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
    rerouted_orders = []
    for order in buy_orders:
        part = db.query(Part).filter(Part.part_id == order["part_id"]).first()
        if part and part.supplier and not part.supplier.is_active:
            # Primary supplier offline — find alternate
            alternate = (
                db.query(Supplier)
                .filter(Supplier.id != part.supplier_id, Supplier.is_active == 1)
                .order_by(Supplier.reliability_score.desc())
                .first()
            )
            if alternate:
                reroute_log = AgentLog(
                    agent="Core-Guard",
                    message=f"Primary supplier {part.supplier.name} OFFLINE. Rerouting {order['part_id']} order to {alternate.name} (reliability: {alternate.reliability_score}).",
                    log_type="warning",
                )
                db.add(reroute_log)
                db.flush()
                reroute_dict = {"timestamp": datetime.now(timezone.utc).isoformat(), "agent": "Core-Guard", "message": reroute_log.message, "type": "warning"}
                all_logs.append(reroute_dict)
                await emit_logs([reroute_dict])
                order["supplier_id"] = alternate.id
                order["supplier_name"] = alternate.name
        rerouted_orders.append(order)

    # --- Act 5: Ghost-Writer handles all emergency POs ---
    ghost_result = {"purchase_orders": [], "logs": []}
    if rerouted_orders:
        ghost_result = process_buy_orders(db, rerouted_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    summary = _sys_log(
        f"Cascade failure contained: {len(mrp_result['shortages'])} shortage(s) resolved, "
        f"{len(ghost_result['purchase_orders'])} PO(s) issued across alternate suppliers.",
        "success",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    return {
        "status": "simulation_complete",
        "scenario": "CASCADE_FAILURE",
        "shortages": mrp_result["shortages"],
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


@app.post("/api/simulate/constitution-breach")
async def simulate_constitution_breach(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario E: Constitution Breach — force a PO that exceeds the $5,000 spend limit.
    Ghost-Writer must block it and flag PENDING_APPROVAL. Human intervention required.
    Demonstrates the hard-coded financial guardrail cannot be bypassed by agents.
    """
    from datetime import datetime, timezone
    all_logs: list[dict[str, str]] = []

    def _sys_log(msg: str, log_type: str = "info") -> dict:
        entry = AgentLog(agent="System", message=msg, log_type=log_type)
        db.add(entry)
        db.flush()
        return {"timestamp": datetime.now(timezone.utc).isoformat(), "agent": "System", "message": msg, "type": log_type}

    log = _sys_log("CONSTITUTION BREACH TEST: Simulating 800% demand spike to force a PO exceeding the $5,000 financial guardrail.", "warning")
    all_logs.append(log)
    await emit_logs([log])

    # 8x spike on FL-001-T — forces massive CH-101 buy that blows the budget
    forecast = db.query(DemandForecast).join(Part).filter(Part.part_id == "FL-001-T").first()
    if not forecast:
        return {"error": "No forecast found for FL-001-T"}

    spiked_qty = int(forecast.forecast_qty * 8.0)

    aura_result = detect_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    dispatch_result = triage_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(dispatch_result["logs"])
    await emit_logs(dispatch_result["logs"])

    mrp_result = calculate_net_requirements(db, "FL-001-T", spiked_qty)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]

    log = _sys_log(
        f"Core-Guard generated {len(buy_orders)} BUY_ORDER(s). Forwarding to Ghost-Writer for cost validation...",
        "info",
    )
    all_logs.append(log)
    await emit_logs([log])

    ghost_result = {"purchase_orders": [], "logs": []}
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    # Identify blocked orders
    blocked = [po for po in ghost_result["purchase_orders"] if po["status"] == "PENDING_APPROVAL"]
    approved = [po for po in ghost_result["purchase_orders"] if po["status"] == "APPROVED"]

    if blocked:
        log = _sys_log(
            f"CONSTITUTION ENFORCED: {len(blocked)} PO(s) blocked — total spend exceeds $5,000 limit. "
            f"Human approval required before funds can be committed. {len(approved)} PO(s) auto-approved.",
            "error",
        )
    else:
        log = _sys_log("All POs within budget — constitution not breached at this spike level.", "success")
    all_logs.append(log)
    await emit_logs([log])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "CONSTITUTION_BREACH",
        "blocked_pos": blocked,
        "approved_pos": approved,
        "logs": all_logs,
    }


@app.post("/api/simulate/full-blackout")
async def simulate_full_blackout(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario F: Full Blackout — ALL suppliers for CH-101 go offline.
    Core-Guard exhausts every option and raises a CRITICAL alert.
    No PO can be generated. Human escalation required.
    """
    from datetime import datetime, timezone
    all_logs: list[dict[str, str]] = []

    def _sys_log(msg: str, log_type: str = "info") -> dict:
        entry = AgentLog(agent="System", message=msg, log_type=log_type)
        db.add(entry)
        db.flush()
        return {"timestamp": datetime.now(timezone.utc).isoformat(), "agent": "System", "message": msg, "type": log_type}

    log = _sys_log("FULL BLACKOUT INITIATED: Simulating catastrophic multi-supplier failure for CH-101.", "error")
    all_logs.append(log)
    await emit_logs([log])

    # Take ALL suppliers offline
    all_suppliers = db.query(Supplier).all()
    for s in all_suppliers:
        s.is_active = 0
    db.flush()

    log = _sys_log(f"BLACKOUT: All {len(all_suppliers)} suppliers are now OFFLINE. No procurement path exists.", "error")
    all_logs.append(log)
    await emit_logs([log])

    # Now trigger a demand spike — agents will find no way out
    forecast = db.query(DemandForecast).join(Part).filter(Part.part_id == "FL-001-T").first()
    if not forecast:
        return {"error": "No forecast found for FL-001-T"}

    spiked_qty = int(forecast.forecast_qty * 4.0)
    aura_result = detect_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    dispatch_result = triage_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(dispatch_result["logs"])
    await emit_logs(dispatch_result["logs"])

    mrp_result = calculate_net_requirements(db, "FL-001-T", spiked_qty)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # Try to source — every alternate will fail
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]

    for order in buy_orders:
        log = _sys_log(
            f"Core-Guard attempting to source {order['quantity']}x {order['part_id']}... scanning {len(all_suppliers)} suppliers.",
            "warning",
        )
        all_logs.append(log)
        await emit_logs([log])

        # Simulate checking each supplier and finding none active
        for supplier in all_suppliers[:3]:  # Show first 3 attempts for drama
            log = _sys_log(f"  Checking {supplier.name}... STATUS: OFFLINE.", "error")
            all_logs.append(log)
            await emit_logs([log])

        log = _sys_log(
            f"CRITICAL: No active supplier found for {order['part_id']}. "
            f"All {len(all_suppliers)} vendors offline. Cannot generate PO.",
            "error",
        )
        all_logs.append(log)
        await emit_logs([log])

    # Final escalation alert
    log = _sys_log(
        "SYSTEM HALT: Core-Guard has exhausted all procurement options. "
        "Manual intervention required. Escalating to COO.",
        "error",
    )
    all_logs.append(log)
    await emit_logs([log])

    log = _sys_log(
        f"Production of FL-001-T at risk. Estimated stock-out in {(500 // max(spiked_qty // 30, 1))} days at current demand.",
        "error",
    )
    all_logs.append(log)
    await emit_logs([log])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "FULL_BLACKOUT",
        "suppliers_offline": len(all_suppliers),
        "unresolved_shortages": mrp_result["shortages"],
        "logs": all_logs,
    }


@app.post("/api/simulate/reset")
async def simulate_reset(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reset the database to a clean FL-001 state for fresh demos."""
    from database.models import Base, QualityInspection
    from database.connection import engine
    from seed import seed

    # Drop and recreate all tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db.close()

    # Re-seed
    seed()

    return {"status": "reset_complete", "message": "Database wiped and re-seeded with FL-001 data."}


# --- ASGI entry point ---
# Use `socket_app` (not `app`) when running with uvicorn so Socket.io is mounted.
# Command: uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
