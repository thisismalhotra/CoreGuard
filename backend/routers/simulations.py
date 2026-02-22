"""
Simulation (God Mode) endpoints.

Each endpoint injects a chaos scenario into the system and streams Glass Box
logs to connected dashboards via Socket.io.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import get_db, engine
from database.models import (
    Part, Supplier, DemandForecast, AgentLog, Base,
)
from agents.aura import detect_demand_spike
from agents.dispatcher import triage_demand_spike
from agents.core_guard import calculate_net_requirements
from agents.ghost_writer import process_buy_orders
from agents.eagle_eye import inspect_batch

router = APIRouter(prefix="/api/simulate", tags=["simulations"])

# These will be set by main.py after Socket.io is initialised
_sio = None
_get_log_delay = None


def init_sio(sio, get_log_delay_fn):
    """Called by main.py to inject the Socket.io server and log delay getter."""
    global _sio, _get_log_delay
    _sio = sio
    _get_log_delay = get_log_delay_fn


async def emit_logs(logs: list[dict[str, str]]) -> None:
    """Broadcast Glass Box logs to all connected dashboard clients."""
    if _sio is None:
        return
    delay = _get_log_delay() if _get_log_delay else 2.0
    for log in logs:
        await _sio.emit("agent_log", log)
        await asyncio.sleep(delay)


def _sys_log(db: Session, msg: str, log_type: str = "info") -> dict:
    """Create a System-level log entry."""
    entry = AgentLog(agent="System", message=msg, log_type=log_type)
    db.add(entry)
    db.flush()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "System",
        "message": msg,
        "type": log_type,
    }


# ---------------------------------------------------------------------------
# Scenario A: Demand Spike
# ---------------------------------------------------------------------------

@router.post("/spike")
async def simulate_demand_spike(
    sku: str = "FL-001-T",
    multiplier: float = 3.0,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario A: Simulate a demand spike.
    Full agent chain: Aura -> Dispatcher -> Core-Guard -> Ghost-Writer.
    """
    all_logs: list[dict[str, str]] = []

    forecast = (
        db.query(DemandForecast)
        .join(Part)
        .filter(Part.part_id == sku)
        .first()
    )
    if not forecast:
        return {"error": f"No forecast found for {sku}"}

    spiked_qty = int(forecast.forecast_qty * multiplier)

    # Step 1: Aura detects the spike
    aura_result = detect_demand_spike(db, sku, spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    if not aura_result["spike_detected"]:
        return {"status": "no_spike", "aura": aura_result, "logs": all_logs}

    # Step 2: Dispatcher triages components by criticality
    dispatch_result = triage_demand_spike(db, sku, spiked_qty)
    all_logs.extend(dispatch_result["logs"])
    await emit_logs(dispatch_result["logs"])

    # Step 3: Core-Guard calculates net requirements
    mrp_result = calculate_net_requirements(db, sku, spiked_qty)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # Step 4: Ghost-Writer processes buy orders
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]

    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
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


# ---------------------------------------------------------------------------
# Scenario B: Supply Shock
# ---------------------------------------------------------------------------

@router.post("/supply-shock")
async def simulate_supply_shock(
    supplier_name: str = "AluForge",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario B: Simulate a supplier going offline (e.g., factory fire).
    """
    all_logs: list[dict[str, str]] = []

    supplier = db.query(Supplier).filter(Supplier.name == supplier_name).first()
    if not supplier:
        return {"error": f"Supplier '{supplier_name}' not found"}

    # Step 1: Disable the supplier
    supplier.is_active = 0
    db.flush()

    log = _sys_log(db, f"SUPPLY SHOCK: {supplier_name} is now OFFLINE. Initiating emergency response.", "error")
    all_logs.append(log)
    await emit_logs([log])

    # Step 2: Identify affected parts and assess impact
    affected_parts = db.query(Part).filter(Part.supplier_id == supplier.id).all()
    emergency_orders: list[dict[str, Any]] = []

    for part in affected_parts:
        inv = part.inventory
        if not inv:
            continue

        log = _sys_log(db, f"Assessing impact: {part.part_id} ({part.description}) — primary supplier {supplier_name} offline.", "warning")
        log["agent"] = "Core-Guard"
        all_logs.append(log)
        await emit_logs([log])

        log = _sys_log(db, f"Inventory check: {part.part_id} — on_hand={inv.on_hand}, safety_stock={inv.safety_stock}, available={inv.available}.", "info")
        log["agent"] = "Core-Guard"
        all_logs.append(log)
        await emit_logs([log])

        order_qty = inv.safety_stock

        alternate = (
            db.query(Supplier)
            .filter(Supplier.id != supplier.id, Supplier.is_active == 1)
            .order_by(Supplier.reliability_score.desc())
            .first()
        )

        if not alternate:
            log = _sys_log(db, f"CRITICAL: No alternate suppliers available for {part.part_id}!", "error")
            log["agent"] = "Core-Guard"
            all_logs.append(log)
            await emit_logs([log])
            continue

        log = _sys_log(
            db,
            f"Switching {part.part_id} to alternate supplier: {alternate.name} "
            f"(reliability: {alternate.reliability_score}, lead time: {alternate.lead_time_days}d).",
            "info",
        )
        log["agent"] = "Core-Guard"
        all_logs.append(log)
        await emit_logs([log])

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

        log = _sys_log(
            db,
            f"Emergency BUY_ORDER: {order_qty}x {part.part_id} from {alternate.name} "
            f"@ ${round(order_qty * part.unit_cost, 2):.2f}.",
            "warning",
        )
        log["agent"] = "Core-Guard"
        all_logs.append(log)
        await emit_logs([log])

    db.commit()

    # Step 3: Ghost-Writer processes emergency POs
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if emergency_orders:
        ghost_result = process_buy_orders(db, emergency_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    summary = _sys_log(
        db,
        f"Supply shock response complete: {supplier_name} disabled, "
        f"{len(affected_parts)} part(s) affected, "
        f"{len(ghost_result['purchase_orders'])} emergency PO(s) generated.",
        "success",
    )
    all_logs.append(summary)
    await emit_logs([summary])
    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "SUPPLY_SHOCK",
        "supplier": supplier_name,
        "affected_parts": [p.part_id for p in affected_parts],
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario C: Quality Fail
# ---------------------------------------------------------------------------

@router.post("/quality-fail")
async def simulate_quality_fail(
    part_id: str = "CH-101",
    batch_size: int = 150,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario C: Simulate a batch failing quality inspection at the dock.
    """
    all_logs: list[dict[str, str]] = []

    inspection_result = inspect_batch(db, part_id, batch_size, force_fail=True)
    all_logs.extend(inspection_result["logs"])
    await emit_logs(inspection_result["logs"])

    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
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


# ---------------------------------------------------------------------------
# Scenario D: Cascade Failure
# ---------------------------------------------------------------------------

@router.post("/cascade-failure")
async def simulate_cascade_failure(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario D: Demand spike hits while AluForge is already offline.
    """
    all_logs: list[dict[str, str]] = []

    # Act 1: Knock out AluForge silently
    aluforge = db.query(Supplier).filter(Supplier.name == "AluForge").first()
    if aluforge:
        aluforge.is_active = 0
        db.flush()

    log = _sys_log(db, "CASCADE EVENT INITIATED: AluForge goes offline at the same moment a 500% demand spike hits FL-001-T.", "error")
    all_logs.append(log)
    await emit_logs([log])

    log = _sys_log(db, "Two simultaneous crises detected. Agents mobilising...", "warning")
    all_logs.append(log)
    await emit_logs([log])

    # Act 2: Aura detects the spike
    forecast = db.query(DemandForecast).join(Part).filter(Part.part_id == "FL-001-T").first()
    if not forecast:
        return {"error": "No forecast found for FL-001-T"}

    spiked_qty = int(forecast.forecast_qty * 5.0)
    aura_result = detect_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    # Act 2.5: Dispatcher triages
    dispatch_result = triage_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(dispatch_result["logs"])
    await emit_logs(dispatch_result["logs"])

    # Act 3: Core-Guard runs MRP
    mrp_result = calculate_net_requirements(db, "FL-001-T", spiked_qty)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # Act 4: Reroute BUY_ORDERs from offline suppliers
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
    rerouted_orders = []
    for order in buy_orders:
        part = db.query(Part).filter(Part.part_id == order["part_id"]).first()
        if part and part.supplier and not part.supplier.is_active:
            alternate = (
                db.query(Supplier)
                .filter(Supplier.id != part.supplier_id, Supplier.is_active == 1)
                .order_by(Supplier.reliability_score.desc())
                .first()
            )
            if alternate:
                log = _sys_log(
                    db,
                    f"Primary supplier {part.supplier.name} OFFLINE. Rerouting {order['part_id']} order to {alternate.name} (reliability: {alternate.reliability_score}).",
                    "warning",
                )
                log["agent"] = "Core-Guard"
                all_logs.append(log)
                await emit_logs([log])
                order["supplier_id"] = alternate.id
                order["supplier_name"] = alternate.name
        rerouted_orders.append(order)

    # Act 5: Ghost-Writer handles all emergency POs
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if rerouted_orders:
        ghost_result = process_buy_orders(db, rerouted_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    summary = _sys_log(
        db,
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


# ---------------------------------------------------------------------------
# Scenario E: Constitution Breach
# ---------------------------------------------------------------------------

@router.post("/constitution-breach")
async def simulate_constitution_breach(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario E: Force a PO exceeding the $5,000 spend limit.
    """
    all_logs: list[dict[str, str]] = []

    log = _sys_log(db, "CONSTITUTION BREACH TEST: Simulating 800% demand spike to force a PO exceeding the $5,000 financial guardrail.", "warning")
    all_logs.append(log)
    await emit_logs([log])

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
        db,
        f"Core-Guard generated {len(buy_orders)} BUY_ORDER(s). Forwarding to Ghost-Writer for cost validation...",
        "info",
    )
    all_logs.append(log)
    await emit_logs([log])

    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    blocked = [po for po in ghost_result["purchase_orders"] if po["status"] == "PENDING_APPROVAL"]
    approved = [po for po in ghost_result["purchase_orders"] if po["status"] == "APPROVED"]

    if blocked:
        log = _sys_log(
            db,
            f"CONSTITUTION ENFORCED: {len(blocked)} PO(s) blocked \u2014 total spend exceeds $5,000 limit. "
            f"Human approval required before funds can be committed. {len(approved)} PO(s) auto-approved.",
            "error",
        )
    else:
        log = _sys_log(db, "All POs within budget \u2014 constitution not breached at this spike level.", "success")
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


# ---------------------------------------------------------------------------
# Scenario F: Full Blackout
# ---------------------------------------------------------------------------

@router.post("/full-blackout")
async def simulate_full_blackout(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario F: ALL suppliers go offline. No PO can be generated.
    """
    all_logs: list[dict[str, str]] = []

    log = _sys_log(db, "FULL BLACKOUT INITIATED: Simulating catastrophic multi-supplier failure for CH-101.", "error")
    all_logs.append(log)
    await emit_logs([log])

    all_suppliers = db.query(Supplier).all()
    for s in all_suppliers:
        s.is_active = 0
    db.flush()

    log = _sys_log(db, f"BLACKOUT: All {len(all_suppliers)} suppliers are now OFFLINE. No procurement path exists.", "error")
    all_logs.append(log)
    await emit_logs([log])

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

    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]

    for order in buy_orders:
        log = _sys_log(
            db,
            f"Core-Guard attempting to source {order['quantity']}x {order['part_id']}... scanning {len(all_suppliers)} suppliers.",
            "warning",
        )
        all_logs.append(log)
        await emit_logs([log])

        for supplier in all_suppliers[:3]:
            log = _sys_log(db, f"  Checking {supplier.name}... STATUS: OFFLINE.", "error")
            all_logs.append(log)
            await emit_logs([log])

        log = _sys_log(
            db,
            f"CRITICAL: No active supplier found for {order['part_id']}. "
            f"All {len(all_suppliers)} vendors offline. Cannot generate PO.",
            "error",
        )
        all_logs.append(log)
        await emit_logs([log])

    log = _sys_log(
        db,
        "SYSTEM HALT: Core-Guard has exhausted all procurement options. "
        "Manual intervention required. Escalating to COO.",
        "error",
    )
    all_logs.append(log)
    await emit_logs([log])

    log = _sys_log(
        db,
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


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

@router.post("/reset")
async def simulate_reset(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reset the database to a clean FL-001 state for fresh demos."""
    from seed import seed

    # Close the DI-provided session FIRST so no connections hold table locks
    db.close()

    # Dispose all pooled connections to ensure a clean slate
    engine.dispose()

    # Drop and recreate all tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Re-seed using a fresh session (seed() creates its own session internally)
    seed()

    return {"status": "reset_complete", "message": "Database wiped and re-seeded with FL-001 data."}
