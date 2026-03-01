"""
Simulation (God Mode) endpoints.

Each endpoint injects a chaos scenario into the system and streams Glass Box
logs to connected dashboards via Socket.io.
"""

import asyncio
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from agents.aura import detect_demand_spike
from agents.core_guard import calculate_blast_radius, calculate_net_requirements, ring_fence_inventory
from agents.data_integrity import run_full_integrity_check
from agents.demand_horizon import evaluate_demand_horizon
from agents.dispatcher import triage_demand_spike
from agents.eagle_eye import inspect_batch
from agents.ghost_writer import process_buy_orders
from agents.part_agent import monitor_all_components, monitor_part
from database.connection import engine, get_db
from database.models import (
    AgentLog,
    AlternateSupplier,
    Base,
    BOMEntry,
    DemandForecast,
    Inventory,
    Part,
    SalesOrder,
    SalesOrderStatus,
    Supplier,
    SupplierContract,
    SupplierRegion,
)
from rate_limit import limiter
from schemas import (
    CascadeFailureResponse,
    ConstitutionBreachResponse,
    ContractExhaustionResponse,
    DemandHorizonResponse,
    FullBlackoutResponse,
    InventoryDecayResponse,
    MilitarySurgeResponse,
    MOQTrapResponse,
    MultiSkuContentionResponse,
    NoSpikeResponse,
    QualityFailResponse,
    ResetResponse,
    SeasonalRampResponse,
    SemiconductorAllocationResponse,
    SlowBleedResponse,
    SpikeResponse,
    SupplyShockResponse,
    TariffShockResponse,
)

router = APIRouter(prefix="/api/simulate", tags=["simulations"])

# Socket.io and log delay are stored on app.state by main.py.
# These module-level references are set once at startup via init_sio().
_app_state = None

# Serialize destructive operations (reset) to prevent concurrent table drops
_reset_lock = threading.Lock()


def init_sio(app_state):
    """Called by main.py to store the app.state reference for Socket.io access."""
    global _app_state
    _app_state = app_state


async def emit_logs(logs: list[dict[str, str]]) -> None:
    """Broadcast Glass Box logs to all connected dashboard clients."""
    if _app_state is None:
        return
    sio = getattr(_app_state, "sio", None)
    if sio is None:
        return
    delay = getattr(_app_state, "log_delay_seconds", 2.0)
    for log in logs:
        await sio.emit("agent_log", log)
        await asyncio.sleep(delay)


def _sys_log(db: Session, msg: str, log_type: str = "info", agent: str = "System") -> dict:
    """Create a log entry. Agent name is consistent between DB record and emitted dict."""
    entry = AgentLog(agent=agent, message=msg, log_type=log_type)
    db.add(entry)
    db.flush()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "message": msg,
        "type": log_type,
    }


# ---------------------------------------------------------------------------
# Scenario A: Demand Spike
# ---------------------------------------------------------------------------

@router.post("/spike", response_model=Union[SpikeResponse, NoSpikeResponse])
@limiter.limit("5/minute")
async def simulate_demand_spike(
    request: Request,
    sku: str = "FL-001-T",
    multiplier: float = Query(default=3.0, ge=1.0, le=100.0, description="Demand multiplier (1x–100x)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario A: Simulate a demand spike.
    Full agent chain: Scout -> Router -> Solver -> Buyer.
    """
    all_logs: list[dict[str, str]] = []

    forecast = (
        db.query(DemandForecast)
        .join(Part)
        .filter(Part.part_id == sku)
        .first()
    )
    if not forecast:
        raise HTTPException(status_code=404, detail=f"No forecast found for {sku}")

    spiked_qty = int(forecast.forecast_qty * multiplier)

    # ---------------------------------------------------------------
    # PRD §9: 5-Step Execution Loop
    # Step 1: SCOUT — Demand spike detection (Trigger Event)
    # ---------------------------------------------------------------
    aura_result = detect_demand_spike(db, sku, spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    if not aura_result["spike_detected"]:
        return {"status": "no_spike", "scout": aura_result, "logs": all_logs}

    # ---------------------------------------------------------------
    # Step 2: PULSE — Baseline Monitoring + Local Validation (PRD §9 Steps 1-3)
    # Each Pulse agent checks its own runway and dynamic safety stock
    # ---------------------------------------------------------------
    part_agent_result = monitor_all_components(db, sku, spiked_qty)
    all_logs.extend(part_agent_result["logs"])
    await emit_logs(part_agent_result["logs"])

    # ---------------------------------------------------------------
    # Step 3: ROUTER — Triage components by criticality
    # ---------------------------------------------------------------
    dispatch_result = triage_demand_spike(db, sku, spiked_qty)
    all_logs.extend(dispatch_result["logs"])
    await emit_logs(dispatch_result["logs"])

    # ---------------------------------------------------------------
    # Step 4: SOLVER — MRP explosion + ring-fencing (PRD §9 Steps 4-5)
    # Solver receives verified Crisis Signals from Pulse
    # ---------------------------------------------------------------
    mrp_result = calculate_net_requirements(db, sku, spiked_qty)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # Ring-fence existing VIP order inventory (PRD §11)
    ring_fence_result = ring_fence_inventory(db, sku, "SO-VIP-001", min(50, spiked_qty // 10))
    all_logs.extend(ring_fence_result["logs"])
    await emit_logs(ring_fence_result["logs"])

    # Blast radius analysis for any components in shortage
    for shortage in mrp_result.get("shortages", []):
        blast_result = calculate_blast_radius(db, shortage["part_id"])
        all_logs.extend(blast_result["logs"])
        await emit_logs(blast_result["logs"])

    # ---------------------------------------------------------------
    # Step 5: BUYER — Draft Purchase Orders
    # ---------------------------------------------------------------
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]

    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    # Single atomic commit — all agent work (Scout, Pulse, Router, Solver, Buyer)
    # is flushed during execution; we commit once at the end of the simulation.
    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "DEMAND_SPIKE",
        "sku": sku,
        "multiplier": multiplier,
        "scout": {
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

@router.post("/supply-shock", response_model=SupplyShockResponse)
@limiter.limit("5/minute")
async def simulate_supply_shock(
    request: Request,
    supplier_name: str = "CREE Inc.",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario B: Simulate a supplier going offline (e.g., factory fire).
    """
    all_logs: list[dict[str, str]] = []

    supplier = db.query(Supplier).filter(Supplier.name == supplier_name).first()
    if not supplier:
        raise HTTPException(status_code=404, detail=f"Supplier '{supplier_name}' not found")

    # Step 1: Disable the supplier
    supplier.is_active = False
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

        log = _sys_log(db, f"Assessing impact: {part.part_id} ({part.description}) — primary supplier {supplier_name} offline.", "warning", agent="Solver")
        all_logs.append(log)
        await emit_logs([log])

        log = _sys_log(db, f"Inventory check: {part.part_id} — on_hand={inv.on_hand}, safety_stock={inv.safety_stock}, available={inv.available}.", "info", agent="Solver")
        all_logs.append(log)
        await emit_logs([log])

        # Order the actual shortfall (safety stock deficit), not just safety_stock blindly
        order_qty = max(inv.safety_stock - inv.available, inv.safety_stock)

        alternate = (
            db.query(Supplier)
            .filter(Supplier.id != supplier.id, Supplier.is_active.is_(True))
            .order_by(Supplier.reliability_score.desc())
            .first()
        )

        if not alternate:
            log = _sys_log(db, f"CRITICAL: No alternate suppliers available for {part.part_id}!", "error", agent="Solver")
            all_logs.append(log)
            await emit_logs([log])
            continue

        log = _sys_log(
            db,
            f"Switching {part.part_id} to alternate supplier: {alternate.name} "
            f"(reliability: {alternate.reliability_score}, lead time: {alternate.lead_time_days}d).",
            "info",
            agent="Solver",
        )
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
            "triggered_by": "Solver",
        })

        log = _sys_log(
            db,
            f"Emergency BUY_ORDER: {order_qty}x {part.part_id} from {alternate.name} "
            f"@ ${round(order_qty * part.unit_cost, 2):.2f}.",
            "warning",
            agent="Solver",
        )
        all_logs.append(log)
        await emit_logs([log])

    # Pulse: Recalculate runway with supplier offline
    for part in affected_parts:
        pa_result = monitor_part(db, part.part_id)
        all_logs.extend(pa_result["logs"])
        await emit_logs(pa_result["logs"])

    # Step 3: Buyer processes emergency POs
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if emergency_orders:
        ghost_result = process_buy_orders(db, emergency_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    # Re-enable the supplier so the simulation doesn't permanently corrupt DB state
    supplier.is_active = True
    db.flush()

    log = _sys_log(
        db,
        f"Supply shock simulation complete: {supplier_name} re-enabled. "
        f"{len(affected_parts)} part(s) were affected, "
        f"{len(ghost_result['purchase_orders'])} emergency PO(s) generated.",
        "success",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Single atomic commit for the entire supply-shock simulation
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

@router.post("/quality-fail", response_model=QualityFailResponse)
@limiter.limit("5/minute")
async def simulate_quality_fail(
    request: Request,
    part_id: str = "CH-231",
    batch_size: int = Query(default=150, ge=1, le=10000, description="Batch size (1–10,000)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario C: Simulate a batch failing quality inspection at the dock.
    """
    all_logs: list[dict[str, str]] = []

    inspection_result = inspect_batch(db, part_id, batch_size, force_fail=True)
    all_logs.extend(inspection_result["logs"])
    await emit_logs(inspection_result["logs"])

    # Pulse: Recalculate runway after quarantine reduces effective on-hand
    pa_result = monitor_part(db, part_id)
    all_logs.extend(pa_result["logs"])
    await emit_logs(pa_result["logs"])

    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    buy_orders = inspection_result.get("actions", [])
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    # Single atomic commit for the entire quality-fail simulation
    db.commit()

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

@router.post("/cascade-failure", response_model=CascadeFailureResponse)
@limiter.limit("5/minute")
async def simulate_cascade_failure(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario D: Demand spike hits while CREE Inc. is already offline.
    """
    all_logs: list[dict[str, str]] = []

    # Act 1: Knock out a critical supplier silently
    critical_supplier = db.query(Supplier).filter(Supplier.name == "CREE Inc.").first()
    if critical_supplier:
        critical_supplier.is_active = False
        db.flush()

    log = _sys_log(db, "CASCADE EVENT INITIATED: CREE Inc. goes offline at the same moment a 500% demand spike hits FL-001-T.", "error")
    all_logs.append(log)
    await emit_logs([log])

    log = _sys_log(db, "Two simultaneous crises detected. Agents mobilising...", "warning")
    all_logs.append(log)
    await emit_logs([log])

    # Act 2: Scout detects the spike
    forecast = db.query(DemandForecast).join(Part).filter(Part.part_id == "FL-001-T").first()
    if not forecast:
        raise HTTPException(status_code=404, detail="No forecast found for FL-001-T")

    spiked_qty = int(forecast.forecast_qty * 5.0)
    aura_result = detect_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    # Pulse: Baseline monitoring under dual crisis
    part_agent_result = monitor_all_components(db, "FL-001-T", spiked_qty)
    all_logs.extend(part_agent_result["logs"])
    await emit_logs(part_agent_result["logs"])

    # Act 2.5: Router triages
    dispatch_result = triage_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(dispatch_result["logs"])
    await emit_logs(dispatch_result["logs"])

    # Act 3: Solver runs MRP
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
                .filter(Supplier.id != part.supplier_id, Supplier.is_active.is_(True))
                .order_by(Supplier.reliability_score.desc())
                .first()
            )
            if alternate:
                log = _sys_log(
                    db,
                    f"Primary supplier {part.supplier.name} OFFLINE. Rerouting {order['part_id']} order to {alternate.name} (reliability: {alternate.reliability_score}).",
                    "warning",
                    agent="Solver",
                )
                all_logs.append(log)
                await emit_logs([log])
                order["supplier_id"] = alternate.id
                order["supplier_name"] = alternate.name
        rerouted_orders.append(order)

    # Act 5: Buyer handles all emergency POs
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

    # Single atomic commit for the entire cascade-failure simulation
    db.commit()

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

@router.post("/constitution-breach", response_model=ConstitutionBreachResponse)
@limiter.limit("5/minute")
async def simulate_constitution_breach(
    request: Request,
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
        raise HTTPException(status_code=404, detail="No forecast found for FL-001-T")

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
        f"Solver generated {len(buy_orders)} BUY_ORDER(s). Forwarding to Buyer for cost validation...",
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

@router.post("/full-blackout", response_model=FullBlackoutResponse)
@limiter.limit("5/minute")
async def simulate_full_blackout(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario F: ALL suppliers go offline. No PO can be generated.
    """
    all_logs: list[dict[str, str]] = []

    log = _sys_log(db, "FULL BLACKOUT INITIATED: Simulating catastrophic multi-supplier failure.", "error")
    all_logs.append(log)
    await emit_logs([log])

    all_suppliers = db.query(Supplier).all()
    for s in all_suppliers:
        s.is_active = False
    db.flush()

    log = _sys_log(db, f"BLACKOUT: All {len(all_suppliers)} suppliers are now OFFLINE. No procurement path exists.", "error")
    all_logs.append(log)
    await emit_logs([log])

    forecast = db.query(DemandForecast).join(Part).filter(Part.part_id == "FL-001-T").first()
    if not forecast:
        raise HTTPException(status_code=404, detail="No forecast found for FL-001-T")

    spiked_qty = int(forecast.forecast_qty * 4.0)
    aura_result = detect_demand_spike(db, "FL-001-T", spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    # Pulse: Assess runway with no supplier path
    part_agent_result = monitor_all_components(db, "FL-001-T", spiked_qty)
    all_logs.extend(part_agent_result["logs"])
    await emit_logs(part_agent_result["logs"])

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
            f"Solver attempting to source {order['quantity']}x {order['part_id']}... scanning {len(all_suppliers)} suppliers.",
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
        "SYSTEM HALT: Solver has exhausted all procurement options. "
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
# Scenario G: Slow Bleed
# ---------------------------------------------------------------------------

@router.post("/slow-bleed", response_model=SlowBleedResponse)
@limiter.limit("5/minute")
async def simulate_slow_bleed(
    request: Request,
    part_id: str = Query(default="CH-231", description="Part ID to simulate slow bleed on"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario G: Simulate a gradual burn rate increase (Slow Bleed).

    Pulse is the ONLY agent that detects this invisible crisis —
    no demand spike, no supplier failure — just a creeping burn rate increase
    that erodes runway day by day.
    """
    all_logs: list[dict[str, str]] = []

    # Locate the part and its inventory
    part = db.query(Part).filter(Part.part_id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail=f"Part '{part_id}' not found")

    inv = part.inventory
    if not inv:
        raise HTTPException(status_code=404, detail=f"No inventory record for '{part_id}'")

    log = _sys_log(
        db,
        f"SLOW BLEED INITIATED: Simulating gradual burn rate increase on {part_id} ({part.description}).",
        "warning",
    )
    all_logs.append(log)
    await emit_logs([log])

    original_burn_rate = inv.daily_burn_rate
    # 4 simulated "days" of increasing burn rate: 1x, 1.375x, 1.75x, 2.125x
    multipliers = [1.0, 1.375, 1.75, 2.125]
    runway_progression: list[dict[str, Any]] = []
    handshake_triggered = False
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}

    try:
        for day_num, mult in enumerate(multipliers, start=1):
            simulated_rate = round(original_burn_rate * mult, 2)
            inv.daily_burn_rate = simulated_rate
            db.flush()

            log = _sys_log(
                db,
                f"Day {day_num}: Burn rate for {part_id} now {simulated_rate}/day "
                f"({mult:.3f}x baseline {original_burn_rate}/day).",
                "info",
                agent="Pulse",
            )
            all_logs.append(log)
            await emit_logs([log])

            # Pulse monitors the SKU
            result = monitor_part(db, part_id)
            all_logs.extend(result["logs"])
            await emit_logs(result["logs"])

            runway_progression.append({
                "day": day_num,
                "burn_rate": simulated_rate,
                "runway_days": result["runway_days"],
                "handshake_triggered": result["handshake_triggered"],
            })

            if result["handshake_triggered"] and not handshake_triggered:
                handshake_triggered = True

                log = _sys_log(
                    db,
                    f"SLOW BLEED DETECTED on Day {day_num}: Pulse identified runway decline for {part_id}. "
                    f"Burn rate crept from {original_burn_rate}/day to {simulated_rate}/day. "
                    f"Escalating to Solver.",
                    "error",
                    agent="Pulse",
                )
                all_logs.append(log)
                await emit_logs([log])

        # If handshake triggered: find parent finished good via BOM, run MRP + procurement
        if handshake_triggered:
            # Find the parent finished good that uses this part
            bom_entry = db.query(BOMEntry).filter(BOMEntry.component_id == part.id).first()
            if bom_entry:
                parent_part = bom_entry.parent
                parent_sku = parent_part.part_id

                log = _sys_log(
                    db,
                    f"Tracing {part_id} upstream via BOM → parent finished good: {parent_sku} ({parent_part.description}).",
                    "info",
                    agent="Solver",
                )
                all_logs.append(log)
                await emit_logs([log])

                # Run Solver MRP for the parent SKU with current demand
                forecast = (
                    db.query(DemandForecast)
                    .join(Part)
                    .filter(Part.part_id == parent_sku)
                    .first()
                )
                demand_qty = forecast.forecast_qty if forecast else 200

                mrp_result = calculate_net_requirements(db, parent_sku, demand_qty)
                all_logs.extend(mrp_result["logs"])
                await emit_logs(mrp_result["logs"])

                # Buyer processes any buy orders
                buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
                if buy_orders:
                    ghost_result = process_buy_orders(db, buy_orders)
                    all_logs.extend(ghost_result["logs"])
                    await emit_logs(ghost_result["logs"])
            else:
                log = _sys_log(
                    db,
                    f"No parent finished good found for {part_id} in BOM. Cannot escalate upstream.",
                    "warning",
                    agent="Solver",
                )
                all_logs.append(log)
                await emit_logs([log])
    finally:
        # Restore original burn rate — even if an exception occurred
        inv.daily_burn_rate = original_burn_rate
        db.flush()

    summary_msg = (
        f"Slow Bleed simulation complete for {part_id}: "
        f"{len(multipliers)} days simulated, "
        f"handshake {'TRIGGERED' if handshake_triggered else 'not triggered'}, "
        f"{len(ghost_result['purchase_orders'])} PO(s) generated. "
        f"Burn rate restored to {original_burn_rate}/day."
    )
    log = _sys_log(db, summary_msg, "success" if not handshake_triggered else "warning")
    all_logs.append(log)
    await emit_logs([log])

    # Single atomic commit
    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "SLOW_BLEED",
        "part_id": part_id,
        "days_simulated": len(multipliers),
        "runway_progression": runway_progression,
        "handshake_triggered": handshake_triggered,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario H: Inventory Decay
# ---------------------------------------------------------------------------

@router.post("/inventory-decay", response_model=InventoryDecayResponse)
@limiter.limit("5/minute")
async def simulate_inventory_decay(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario H: Inventory Decay — Ghost inventory and stale stock detection.

    3-act story:
      Act 1: Pulse runs baseline check — everything looks fine.
      Act 2: Inject decay conditions, Auditor reveals ghost/suspect stock.
      Act 3: Pulse re-evaluates with corrected inventory, triggers crisis if needed.
    """
    all_logs: list[dict[str, str]] = []

    log = _sys_log(
        db,
        "INVENTORY DECAY INITIATED: Checking FL-001-T sub-assembly components for ghost and suspect inventory.",
        "warning",
    )
    all_logs.append(log)
    await emit_logs([log])

    # ---------------------------------------------------------------
    # Act 1: Pulse runs baseline check — everything looks fine
    # ---------------------------------------------------------------
    log = _sys_log(db, "Act 1: Pulse baseline check on FL-001-T components...", "info")
    all_logs.append(log)
    await emit_logs([log])

    baseline_result = monitor_all_components(db, "FL-001-T", 100)
    all_logs.extend(baseline_result["logs"])
    await emit_logs(baseline_result["logs"])

    log = _sys_log(
        db,
        f"Baseline complete: {len(baseline_result['component_reports'])} components checked, "
        f"{len(baseline_result['crisis_signals'])} crisis signals. System looks healthy.",
        "success",
    )
    all_logs.append(log)
    await emit_logs([log])

    # ---------------------------------------------------------------
    # Act 2: Inject decay conditions — Auditor reveals the truth
    # ---------------------------------------------------------------
    log = _sys_log(db, "Act 2: Injecting inventory decay conditions...", "warning")
    all_logs.append(log)
    await emit_logs([log])

    # Save original values for restoration
    ch231_inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-231").first()
    lns221_inv = db.query(Inventory).join(Part).filter(Part.part_id == "LNS-221").first()

    original_ch231_consumption_date = ch231_inv.last_consumption_date if ch231_inv else None
    original_lns221_last_updated = lns221_inv.last_updated if lns221_inv else None

    # CH-231: Set last_consumption_date to 30 days ago (ghost: burn rate > 0 but no consumption)
    if ch231_inv:
        ch231_inv.last_consumption_date = datetime.now(timezone.utc) - timedelta(days=30)
        db.flush()
        log = _sys_log(
            db,
            f"Decay injected: CH-231 last_consumption_date set to 30 days ago "
            f"(ghost: burn rate {ch231_inv.daily_burn_rate}/day but no recorded consumption).",
            "warning",
            agent="System",
        )
        all_logs.append(log)
        await emit_logs([log])

    # LNS-221: Set last_updated to 200 days ago (suspect: no movement for 6+ months)
    if lns221_inv:
        lns221_inv.last_updated = datetime.now(timezone.utc) - timedelta(days=200)
        db.flush()
        log = _sys_log(
            db,
            "Decay injected: LNS-221 last_updated set to 200 days ago "
            "(suspect: no inventory movement for 6+ months).",
            "warning",
            agent="System",
        )
        all_logs.append(log)
        await emit_logs([log])

    # Run Auditor full check
    log = _sys_log(db, "Running Auditor full scan...", "info", agent="Auditor")
    all_logs.append(log)
    await emit_logs([log])

    integrity_result = run_full_integrity_check(db)
    all_logs.extend(integrity_result["logs"])
    await emit_logs(integrity_result["logs"])

    ghost_parts = integrity_result["ghost"]["ghost_parts"]
    suspect_parts = integrity_result["suspect"]["suspect_parts"]

    log = _sys_log(
        db,
        f"Auditor reveals: {len(ghost_parts)} ghost part(s), "
        f"{len(suspect_parts)} suspect part(s). Inventory cannot be trusted as-is.",
        "error" if (ghost_parts or suspect_parts) else "success",
    )
    all_logs.append(log)
    await emit_logs([log])

    # ---------------------------------------------------------------
    # Act 3: Pulse re-evaluates with corrected inventory
    # ---------------------------------------------------------------
    log = _sys_log(
        db,
        "Act 3: Applying ghost discount (50% reduction) and re-evaluating...",
        "warning",
    )
    all_logs.append(log)
    await emit_logs([log])

    # For ghost parts, reduce on_hand by 50% (ghost discount pending physical count)
    original_on_hand_values: dict[str, int] = {}
    for ghost in ghost_parts:
        ghost_inv = db.query(Inventory).join(Part).filter(Part.part_id == ghost["part_id"]).first()
        if ghost_inv:
            original_on_hand_values[ghost["part_id"]] = ghost_inv.on_hand
            ghost_inv.on_hand = ghost_inv.on_hand // 2
            db.flush()
            log = _sys_log(
                db,
                f"Ghost discount applied: {ghost['part_id']} on_hand reduced from "
                f"{original_on_hand_values[ghost['part_id']]} to {ghost_inv.on_hand} "
                f"(50% reduction pending physical count).",
                "warning",
                agent="Auditor",
            )
            all_logs.append(log)
            await emit_logs([log])

    # Re-run Pulse monitoring with corrected numbers
    corrected_result = monitor_all_components(db, "FL-001-T", 100)
    all_logs.extend(corrected_result["logs"])
    await emit_logs(corrected_result["logs"])

    # Build corrected runway info
    corrected_runway: dict[str, Any] = {
        "component_reports": corrected_result["component_reports"],
        "crisis_signals": corrected_result["crisis_signals"],
    }

    # If crisis signals fire, run MRP + procurement
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if corrected_result["crisis_signals"]:
        log = _sys_log(
            db,
            f"CRISIS DETECTED: {len(corrected_result['crisis_signals'])} component(s) in crisis "
            f"after ghost inventory correction. Escalating to Solver.",
            "error",
            agent="Pulse",
        )
        all_logs.append(log)
        await emit_logs([log])

        from agents.core_guard import calculate_net_requirements
        from agents.ghost_writer import process_buy_orders

        forecast = db.query(DemandForecast).join(Part).filter(Part.part_id == "FL-001-T").first()
        demand_qty = forecast.forecast_qty if forecast else 100

        mrp_result = calculate_net_requirements(db, "FL-001-T", demand_qty)
        all_logs.extend(mrp_result["logs"])
        await emit_logs(mrp_result["logs"])

        buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
        if buy_orders:
            ghost_result = process_buy_orders(db, buy_orders)
            all_logs.extend(ghost_result["logs"])
            await emit_logs(ghost_result["logs"])

    # ---------------------------------------------------------------
    # Restore original values
    # ---------------------------------------------------------------
    if ch231_inv:
        ch231_inv.last_consumption_date = original_ch231_consumption_date
    if lns221_inv:
        lns221_inv.last_updated = original_lns221_last_updated
    for part_id_str, original_oh in original_on_hand_values.items():
        restored_inv = db.query(Inventory).join(Part).filter(Part.part_id == part_id_str).first()
        if restored_inv:
            restored_inv.on_hand = original_oh
    db.flush()

    summary = _sys_log(
        db,
        f"Inventory Decay simulation complete: "
        f"{len(ghost_parts)} ghost part(s), {len(suspect_parts)} suspect part(s) detected. "
        f"{len(ghost_result['purchase_orders'])} PO(s) generated. "
        f"Original inventory values restored.",
        "success" if not ghost_parts and not suspect_parts else "warning",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    # Single atomic commit
    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "INVENTORY_DECAY",
        "ghost_parts": ghost_parts,
        "suspect_parts": suspect_parts,
        "corrected_runway": corrected_runway,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario I: Multi-SKU Contention
# ---------------------------------------------------------------------------

@router.post("/multi-sku-contention", response_model=MultiSkuContentionResponse)
@limiter.limit("5/minute")
async def simulate_multi_sku_contention(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario I: Multi-SKU Contention — two products compete for shared components.

    FL-001-T (Tactical) demands 200 units, FL-001-S (Standard) demands 300 units.
    CH-231 is shared: 1x per Tactical, 1x per Standard = 500 chassis needed total.

    4-act story:
      Act 1: Pulse monitors CH-231 for FL-001-T demand — looks manageable.
      Act 2: Pulse monitors CH-231 for FL-001-S demand — still looks ok.
      Act 3: Contention detected — combined burn rate overwhelms CH-231 runway.
      Act 4: Solver applies criticality-based prioritization and procures.
    """
    all_logs: list[dict[str, str]] = []

    tactical_demand = 200
    standard_demand = 300
    shared_component = "CH-231"

    log = _sys_log(
        db,
        f"MULTI-SKU CONTENTION INITIATED: FL-001-T ({tactical_demand} units) and "
        f"FL-001-S ({standard_demand} units) competing for shared component {shared_component}.",
        "warning",
    )
    all_logs.append(log)
    await emit_logs([log])

    # ---------------------------------------------------------------
    # Act 1: Pulse monitors CH-231 for FL-001-T demand
    # ---------------------------------------------------------------
    log = _sys_log(db, f"Act 1: Pulse monitoring {shared_component} for FL-001-T demand ({tactical_demand} units × 1 per = {tactical_demand} chassis)...", "info")
    all_logs.append(log)
    await emit_logs([log])

    tactical_result = monitor_all_components(db, "FL-001-T", tactical_demand)
    all_logs.extend(tactical_result["logs"])
    await emit_logs(tactical_result["logs"])

    log = _sys_log(
        db,
        f"Act 1 complete: FL-001-T alone — {len(tactical_result['crisis_signals'])} crisis signal(s). "
        f"{shared_component} looks {'stressed' if tactical_result['crisis_signals'] else 'manageable'}.",
        "warning" if tactical_result["crisis_signals"] else "success",
    )
    all_logs.append(log)
    await emit_logs([log])

    # ---------------------------------------------------------------
    # Act 2: Pulse monitors CH-231 for FL-001-S demand
    # ---------------------------------------------------------------
    log = _sys_log(db, f"Act 2: Pulse monitoring {shared_component} for FL-001-S demand ({standard_demand} units × 1 per = {standard_demand} chassis)...", "info")
    all_logs.append(log)
    await emit_logs([log])

    standard_result = monitor_all_components(db, "FL-001-S", standard_demand)
    all_logs.extend(standard_result["logs"])
    await emit_logs(standard_result["logs"])

    log = _sys_log(
        db,
        f"Act 2 complete: FL-001-S alone — {len(standard_result['crisis_signals'])} crisis signal(s). "
        f"{shared_component} looks {'stressed' if standard_result['crisis_signals'] else 'ok in isolation'}.",
        "warning" if standard_result["crisis_signals"] else "success",
    )
    all_logs.append(log)
    await emit_logs([log])

    # ---------------------------------------------------------------
    # Act 3: Detect contention — combined burn rate from both SKUs
    # ---------------------------------------------------------------
    log = _sys_log(
        db,
        f"Act 3: CONTENTION DETECTION — calculating combined burn rate from both SKUs on {shared_component}...",
        "warning",
    )
    all_logs.append(log)
    await emit_logs([log])

    shared_inv = db.query(Inventory).join(Part).filter(Part.part_id == shared_component).first()
    if not shared_inv:
        raise HTTPException(status_code=404, detail=f"No inventory record for {shared_component}")

    original_burn_rate = shared_inv.daily_burn_rate

    # Combined daily burn: (200 Tactical × 1 chassis + 300 Standard × 1 chassis) / 30 days
    combined_additional_burn = (tactical_demand * 1 + standard_demand * 1) / 30.0
    contention_burn_rate = original_burn_rate + combined_additional_burn

    shared_inv.daily_burn_rate = contention_burn_rate
    db.flush()

    try:
        log = _sys_log(
            db,
            f"Combined burn rate for {shared_component}: {original_burn_rate:.1f}/day → {contention_burn_rate:.1f}/day "
            f"(+{combined_additional_burn:.1f} from {tactical_demand}×1 + {standard_demand}×1 = {tactical_demand + standard_demand} chassis over 30 days).",
            "error",
            agent="Pulse",
        )
        all_logs.append(log)
        await emit_logs([log])

        # Run Pulse on the contended component
        contention_result = monitor_part(db, shared_component)
        all_logs.extend(contention_result["logs"])
        await emit_logs(contention_result["logs"])

        log = _sys_log(
            db,
            f"CONTENTION DETECTED: {shared_component} runway under combined demand: "
            f"{contention_result['runway_days']}d. "
            f"Handshake {'TRIGGERED' if contention_result['handshake_triggered'] else 'not triggered'}.",
            "error" if contention_result["handshake_triggered"] else "warning",
            agent="Pulse",
        )
        all_logs.append(log)
        await emit_logs([log])
    finally:
        # Restore original burn rate — even if an exception occurred
        shared_inv.daily_burn_rate = original_burn_rate
        db.flush()

    # ---------------------------------------------------------------
    # Act 4: Solver applies criticality-based prioritization
    # ---------------------------------------------------------------
    log = _sys_log(
        db,
        "Act 4: Solver applying criticality-based prioritization for contending SKUs...",
        "info",
    )
    all_logs.append(log)
    await emit_logs([log])

    # FL-001-T is HIGH criticality (priority 1), FL-001-S is MEDIUM (priority 2)
    fl001t = db.query(Part).filter(Part.part_id == "FL-001-T").first()
    fl001s = db.query(Part).filter(Part.part_id == "FL-001-S").first()

    prioritization = []
    if fl001t:
        prioritization.append({
            "sku": "FL-001-T",
            "description": fl001t.description,
            "criticality": fl001t.criticality.value,
            "priority": 1,
            "demand": tactical_demand,
            "chassis_needed": tactical_demand * 1,
        })
    if fl001s:
        prioritization.append({
            "sku": "FL-001-S",
            "description": fl001s.description,
            "criticality": fl001s.criticality.value,
            "priority": 2,
            "demand": standard_demand,
            "chassis_needed": standard_demand * 1,
        })

    for item in prioritization:
        log = _sys_log(
            db,
            f"Priority {item['priority']}: {item['sku']} ({item['description']}) — "
            f"criticality [{item['criticality']}], "
            f"demand {item['demand']} units → {item['chassis_needed']} chassis needed.",
            "info",
            agent="Solver",
        )
        all_logs.append(log)
        await emit_logs([log])

    # Run MRP for combined demand (total chassis needed = 700)
    combined_demand = tactical_demand + standard_demand
    mrp_result = calculate_net_requirements(db, "FL-001-T", combined_demand)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # Buyer processes buy orders
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    summary = _sys_log(
        db,
        f"Multi-SKU Contention simulation complete: "
        f"FL-001-T ({tactical_demand}) + FL-001-S ({standard_demand}) = {combined_demand} units total. "
        f"{combined_demand} chassis needed, {len(ghost_result['purchase_orders'])} PO(s) generated.",
        "success" if ghost_result["purchase_orders"] else "warning",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    # Single atomic commit
    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "MULTI_SKU_CONTENTION",
        "contending_skus": ["FL-001-T", "FL-001-S"],
        "shared_component": shared_component,
        "combined_demand": combined_demand,
        "prioritization": prioritization,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario 10: Contract Exhaustion
# ---------------------------------------------------------------------------

@router.post("/contract-exhaustion", response_model=ContractExhaustionResponse)
@limiter.limit("5/minute")
async def simulate_contract_exhaustion(
    request: Request,
    contract_number: str = Query(default="BPA-CREE-2026"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario 10: Blanket PO is 90% consumed with months remaining.
    Buyer evaluates: extend contract vs. spot buy at premium.
    """
    all_logs: list[dict[str, str]] = []

    contract = db.query(SupplierContract).filter(
        SupplierContract.contract_number == contract_number
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_number}' not found")

    supplier = contract.supplier

    log = _sys_log(
        db,
        f"CONTRACT EXHAUSTION ANALYSIS: {contract_number} with {supplier.name}. "
        f"Remaining: {contract.remaining_qty} units, ${contract.remaining_value:,.2f}.",
        "warning",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Calculate forecast demand for remaining contract term
    import json
    price_schedule = json.loads(contract.price_schedule) if contract.price_schedule else []
    blanket_price = price_schedule[0]["unit_price"] if price_schedule else 0.0
    spot_price = price_schedule[0].get("spot_price", blanket_price * 1.15) if price_schedule else 0.0
    spot_premium_pct = round((spot_price - blanket_price) / blanket_price * 100, 1) if blanket_price > 0 else 0.0

    # Find parts covered by this contract's supplier
    parts = db.query(Part).filter(Part.supplier_id == supplier.id).all()
    forecast_demand = 0
    for p in parts:
        forecasts = db.query(DemandForecast).filter(DemandForecast.part_id == p.id).all()
        forecast_demand += sum(f.forecast_qty for f in forecasts)

    log = _sys_log(
        db,
        f"Forecast analysis: {forecast_demand} total units forecast across {len(parts)} part(s) "
        f"covered by {supplier.name}. Contract has {contract.remaining_qty} units remaining.",
        "info",
        agent="Solver",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Determine recommendation
    coverage_ratio = contract.remaining_qty / max(forecast_demand, 1)
    if coverage_ratio < 0.3:
        recommendation = "EXTEND"
        log = _sys_log(
            db,
            f"RECOMMENDATION: EXTEND contract — only {coverage_ratio:.0%} of forecast demand covered. "
            f"Spot buy premium would be {spot_premium_pct}%.",
            "warning",
            agent="Buyer",
        )
    elif coverage_ratio < 0.7:
        recommendation = "RENEGOTIATE"
        log = _sys_log(
            db,
            f"RECOMMENDATION: RENEGOTIATE — {coverage_ratio:.0%} coverage. "
            f"Consider volume increase to avoid spot buys at {spot_premium_pct}% premium.",
            "info",
            agent="Buyer",
        )
    else:
        recommendation = "SPOT_BUY"
        log = _sys_log(
            db,
            f"RECOMMENDATION: SPOT_BUY for overflow — {coverage_ratio:.0%} coverage is adequate. "
            f"Spot premium {spot_premium_pct}% acceptable for gap.",
            "info",
            agent="Buyer",
        )
    all_logs.append(log)
    await emit_logs([log])

    # Check for alternate suppliers
    alt_mappings = db.query(AlternateSupplier).filter(
        AlternateSupplier.primary_supplier_id == supplier.id
    ).all()
    if alt_mappings:
        for alt in alt_mappings:
            alt_supplier = db.query(Supplier).filter(Supplier.id == alt.alternate_supplier_id).first()
            if alt_supplier:
                log = _sys_log(
                    db,
                    f"Alternate supplier available: {alt_supplier.name} — "
                    f"+{alt.cost_premium_pct}% cost, +{alt.lead_time_delta_days}d lead time. "
                    f"Notes: {alt.notes or 'N/A'}.",
                    "info",
                    agent="Solver",
                )
                all_logs.append(log)
                await emit_logs([log])

    # Generate PO if contract is nearly exhausted
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if coverage_ratio < 0.5:
        gap_qty = forecast_demand - contract.remaining_qty
        buy_orders = [{
            "type": "BUY_ORDER",
            "part_id": parts[0].part_id if parts else "UNKNOWN",
            "quantity": gap_qty,
            "unit_cost": spot_price,
            "total_cost": round(gap_qty * spot_price, 2),
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "triggered_by": "Buyer",
        }]
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    summary = _sys_log(
        db,
        f"Contract exhaustion analysis complete: {contract_number} has {contract.remaining_qty} units "
        f"remaining (${contract.remaining_value:,.2f}). Recommendation: {recommendation}.",
        "success",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "CONTRACT_EXHAUSTION",
        "contract_number": contract_number,
        "supplier": supplier.name,
        "remaining_qty": contract.remaining_qty,
        "remaining_value": contract.remaining_value,
        "forecast_demand": forecast_demand,
        "recommendation": recommendation,
        "spot_buy_premium_pct": spot_premium_pct,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario 11: Tariff Shock
# ---------------------------------------------------------------------------

@router.post("/tariff-shock", response_model=TariffShockResponse)
@limiter.limit("5/minute")
async def simulate_tariff_shock(
    request: Request,
    region: str = Query(default="CHINA"),
    increase_pct: float = Query(default=25.0, ge=1.0, le=100.0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario 11: Tariff announcement on a region — costs jump overnight.
    Solver recalculates with new costs; Buyer evaluates alternates.
    """
    all_logs: list[dict[str, str]] = []

    # Map string to enum
    try:
        target_region = SupplierRegion(region)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown region '{region}'. Valid: {[r.value for r in SupplierRegion]}")

    log = _sys_log(
        db,
        f"TARIFF SHOCK: {increase_pct}% tariff increase on all suppliers in {region}.",
        "error",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Find affected suppliers
    affected_suppliers = db.query(Supplier).filter(Supplier.region == target_region).all()
    affected_supplier_names = [s.name for s in affected_suppliers]

    if not affected_suppliers:
        log = _sys_log(db, f"No suppliers found in region {region}.", "info")
        all_logs.append(log)
        await emit_logs([log])
        db.commit()
        return {
            "status": "simulation_complete",
            "scenario": "TARIFF_SHOCK",
            "affected_suppliers": [],
            "cost_increase_pct": increase_pct,
            "affected_parts": [],
            "alternate_options": [],
            "procurement": [],
            "logs": all_logs,
        }

    log = _sys_log(
        db,
        f"Found {len(affected_suppliers)} supplier(s) in {region}: {', '.join(affected_supplier_names)}.",
        "warning",
        agent="Solver",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Find affected parts and calculate new costs
    affected_parts: list[str] = []
    alternate_options: list[dict[str, Any]] = []
    buy_orders: list[dict[str, Any]] = []

    for supplier in affected_suppliers:
        parts = db.query(Part).filter(Part.supplier_id == supplier.id).all()
        for p in parts:
            affected_parts.append(p.part_id)
            tariffed_cost = round(p.unit_cost * (1 + increase_pct / 100), 2)

            log = _sys_log(
                db,
                f"Tariff impact: {p.part_id} ({p.description}) — "
                f"cost ${p.unit_cost:.2f} → ${tariffed_cost:.2f} (+{increase_pct}%).",
                "warning",
                agent="Solver",
            )
            all_logs.append(log)
            await emit_logs([log])

            # Check for alternate suppliers outside the tariffed region
            alt_mappings = db.query(AlternateSupplier).filter(
                AlternateSupplier.part_id == p.id,
                AlternateSupplier.primary_supplier_id == supplier.id,
            ).all()

            for alt in alt_mappings:
                alt_supplier = db.query(Supplier).filter(Supplier.id == alt.alternate_supplier_id).first()
                if alt_supplier and alt_supplier.region != target_region:
                    alt_cost = round(p.unit_cost * (1 + alt.cost_premium_pct / 100), 2)
                    option = {
                        "supplier": alt_supplier.name,
                        "part_id": p.part_id,
                        "new_cost": alt_cost,
                        "tariffed_cost": tariffed_cost,
                        "lead_time": alt_supplier.lead_time_days + alt.lead_time_delta_days,
                        "saves_money": alt_cost < tariffed_cost,
                    }
                    alternate_options.append(option)

                    if alt_cost < tariffed_cost:
                        log = _sys_log(
                            db,
                            f"SWITCH RECOMMENDED: {p.part_id} to {alt_supplier.name} ({alt_supplier.region.value}) — "
                            f"${alt_cost:.2f} vs tariffed ${tariffed_cost:.2f}. "
                            f"Savings: ${tariffed_cost - alt_cost:.2f}/unit.",
                            "success",
                            agent="Buyer",
                        )
                    else:
                        log = _sys_log(
                            db,
                            f"Alternate {alt_supplier.name} for {p.part_id}: ${alt_cost:.2f} vs tariffed ${tariffed_cost:.2f} — "
                            f"not cheaper, but avoids tariff risk.",
                            "info",
                            agent="Buyer",
                        )
                    all_logs.append(log)
                    await emit_logs([log])

                    # Generate a PO if switching is cheaper
                    if alt_cost < tariffed_cost:
                        inv = p.inventory
                        order_qty = inv.safety_stock if inv else 100
                        buy_orders.append({
                            "type": "BUY_ORDER",
                            "part_id": p.part_id,
                            "quantity": order_qty,
                            "unit_cost": alt_cost,
                            "total_cost": round(order_qty * alt_cost, 2),
                            "supplier_id": alt_supplier.id,
                            "supplier_name": alt_supplier.name,
                            "triggered_by": "Buyer",
                        })

    # Buyer processes POs
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    summary = _sys_log(
        db,
        f"Tariff shock analysis complete: {len(affected_parts)} part(s) affected, "
        f"{len(alternate_options)} alternate option(s) evaluated, "
        f"{len(ghost_result['purchase_orders'])} PO(s) generated.",
        "success",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "TARIFF_SHOCK",
        "affected_suppliers": affected_supplier_names,
        "cost_increase_pct": increase_pct,
        "affected_parts": affected_parts,
        "alternate_options": alternate_options,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario 12: MOQ Trap
# ---------------------------------------------------------------------------

@router.post("/moq-trap", response_model=MOQTrapResponse)
@limiter.limit("5/minute")
async def simulate_moq_trap(
    request: Request,
    part_id: str = Query(default="LED-201"),
    needed_qty: int = Query(default=80, ge=1),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario 12: Need fewer units than MOQ — buy excess or pay small-lot premium?
    """
    all_logs: list[dict[str, str]] = []

    part = db.query(Part).filter(Part.part_id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail=f"Part '{part_id}' not found")

    supplier = part.supplier
    if not supplier:
        raise HTTPException(status_code=404, detail=f"No supplier for part '{part_id}'")

    moq = supplier.minimum_order_qty

    log = _sys_log(
        db,
        f"MOQ TRAP ANALYSIS: Need {needed_qty}x {part_id} ({part.description}), "
        f"but supplier {supplier.name} MOQ is {moq}.",
        "warning",
    )
    all_logs.append(log)
    await emit_logs([log])

    excess_qty = max(0, moq - needed_qty)
    carry_cost_per_unit_month = part.unit_cost * 0.02  # 2% monthly carrying cost
    carry_cost = round(excess_qty * carry_cost_per_unit_month * 6, 2)  # 6 months carry

    # Small-lot premium: 15% surcharge for ordering below MOQ
    small_lot_premium_pct = 15.0
    small_lot_unit_cost = round(part.unit_cost * (1 + small_lot_premium_pct / 100), 2)
    small_lot_total = round(needed_qty * small_lot_unit_cost, 2)
    moq_total = round(moq * part.unit_cost, 2)

    log = _sys_log(
        db,
        f"Option A — BUY_MOQ: Order {moq} units at ${part.unit_cost:.2f}/unit = ${moq_total:.2f}. "
        f"Excess: {excess_qty} units, 6-month carry cost: ${carry_cost:.2f}.",
        "info",
        agent="Buyer",
    )
    all_logs.append(log)
    await emit_logs([log])

    log = _sys_log(
        db,
        f"Option B — SMALL_LOT: Order {needed_qty} units at ${small_lot_unit_cost:.2f}/unit (+{small_lot_premium_pct}%) = "
        f"${small_lot_total:.2f}. No excess inventory.",
        "info",
        agent="Buyer",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Determine recommendation
    moq_effective_cost = moq_total + carry_cost
    if needed_qty >= moq:
        recommendation = "BUY_MOQ"
        log = _sys_log(
            db,
            f"RECOMMENDATION: BUY_MOQ — needed qty ({needed_qty}) meets or exceeds MOQ ({moq}).",
            "success",
            agent="Buyer",
        )
    elif moq_effective_cost < small_lot_total:
        recommendation = "BUY_MOQ"
        log = _sys_log(
            db,
            f"RECOMMENDATION: BUY_MOQ — total cost with carry (${moq_effective_cost:.2f}) is less than "
            f"small-lot (${small_lot_total:.2f}). Absorb excess.",
            "info",
            agent="Buyer",
        )
    elif excess_qty > needed_qty * 3:
        recommendation = "WAIT"
        log = _sys_log(
            db,
            f"RECOMMENDATION: WAIT — MOQ ({moq}) is >3x needed qty ({needed_qty}). "
            f"Defer purchase and consolidate with next demand cycle.",
            "warning",
            agent="Buyer",
        )
    else:
        recommendation = "SMALL_LOT"
        log = _sys_log(
            db,
            f"RECOMMENDATION: SMALL_LOT — small-lot premium (${small_lot_total:.2f}) is cheaper than "
            f"MOQ + carry (${moq_effective_cost:.2f}).",
            "info",
            agent="Buyer",
        )
    all_logs.append(log)
    await emit_logs([log])

    # Generate PO based on recommendation
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if recommendation != "WAIT":
        order_qty = moq if recommendation == "BUY_MOQ" else needed_qty
        unit_cost = part.unit_cost if recommendation == "BUY_MOQ" else small_lot_unit_cost
        buy_orders = [{
            "type": "BUY_ORDER",
            "part_id": part.part_id,
            "quantity": order_qty,
            "unit_cost": unit_cost,
            "total_cost": round(order_qty * unit_cost, 2),
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "triggered_by": "Buyer",
        }]
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "MOQ_TRAP",
        "part_id": part_id,
        "needed_qty": needed_qty,
        "moq": moq,
        "excess_qty": excess_qty,
        "carry_cost": carry_cost,
        "small_lot_premium": small_lot_premium_pct,
        "recommendation": recommendation,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario 13: Military Surge
# ---------------------------------------------------------------------------

@router.post("/military-surge", response_model=MilitarySurgeResponse)
@limiter.limit("5/minute")
async def simulate_military_surge(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario 13: VIP military order doubles, 21-day deadline.
    Router triages VIP priority; Solver ring-fences across product lines.
    """
    all_logs: list[dict[str, str]] = []

    # Find the VIP military order
    mil_order = db.query(SalesOrder).filter(SalesOrder.priority == "VIP").first()
    if not mil_order:
        # Fallback: use highest priority order
        mil_order = db.query(SalesOrder).filter(SalesOrder.status == SalesOrderStatus.OPEN).first()
    if not mil_order:
        raise HTTPException(status_code=404, detail="No open military/VIP order found")

    original_qty = mil_order.quantity
    new_qty = original_qty * 2
    deadline_days = 21

    log = _sys_log(
        db,
        f"MILITARY SURGE: Order {mil_order.order_number} doubles from {original_qty} to {new_qty} units. "
        f"Deadline: {deadline_days} days. Priority: {mil_order.priority}.",
        "error",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Get the part for this order
    part = db.query(Part).filter(Part.id == mil_order.part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found for military order")

    sku = part.part_id

    # Run MRP for the new demand
    log = _sys_log(
        db,
        f"Solver running MRP for surge demand: {new_qty}x {sku} ({part.description}).",
        "info",
        agent="Solver",
    )
    all_logs.append(log)
    await emit_logs([log])

    mrp_result = calculate_net_requirements(db, sku, new_qty)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # Ring-fence inventory for the military order
    ring_fenced_parts: list[dict[str, Any]] = []
    bom_entries = db.query(BOMEntry).filter(BOMEntry.parent_id == part.id).all()

    for bom in bom_entries:
        component = bom.component
        ring_qty = min(new_qty * bom.quantity_per, component.inventory.available if component.inventory else 0)
        if ring_qty > 0:
            rf_result = ring_fence_inventory(db, component.part_id, mil_order.order_number, ring_qty)
            all_logs.extend(rf_result["logs"])
            await emit_logs(rf_result["logs"])
            ring_fenced_parts.append({
                "part_id": component.part_id,
                "qty_ring_fenced": rf_result["qty_ring_fenced"],
                "success": rf_result["success"],
            })

    # Identify displaced orders (other open orders competing for same parts)
    displaced_orders: list[dict[str, Any]] = []
    other_orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.id != mil_order.id,
            SalesOrder.status == SalesOrderStatus.OPEN,
        )
        .all()
    )

    for order in other_orders:
        order_part = db.query(Part).filter(Part.id == order.part_id).first()
        if order_part:
            # Check if this order uses any of the same components
            order_bom = db.query(BOMEntry).filter(BOMEntry.parent_id == order_part.id).all()
            shared = [b.component.part_id for b in order_bom for rb in bom_entries
                      if b.component_id == rb.component_id]
            if shared:
                displaced_orders.append({
                    "order_number": order.order_number,
                    "sku": order_part.part_id,
                    "quantity": order.quantity,
                    "priority": order.priority,
                    "shared_components": list(set(shared)),
                })
                log = _sys_log(
                    db,
                    f"DISPLACED: Order {order.order_number} ({order_part.part_id}, {order.quantity} units, "
                    f"priority: {order.priority}) may be delayed — shares {', '.join(set(shared))} with military surge.",
                    "warning",
                    agent="Solver",
                )
                all_logs.append(log)
                await emit_logs([log])

    # Buyer processes buy orders
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    summary = _sys_log(
        db,
        f"Military surge response complete: {mil_order.order_number} scaled to {new_qty} units. "
        f"{len(ring_fenced_parts)} component(s) ring-fenced, {len(displaced_orders)} order(s) displaced, "
        f"{len(ghost_result['purchase_orders'])} PO(s) generated.",
        "success",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "MILITARY_SURGE",
        "order_number": mil_order.order_number,
        "original_qty": original_qty,
        "new_qty": new_qty,
        "deadline_days": deadline_days,
        "ring_fenced_parts": ring_fenced_parts,
        "displaced_orders": displaced_orders,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario 14: Semiconductor Allocation
# ---------------------------------------------------------------------------

@router.post("/semiconductor-allocation", response_model=SemiconductorAllocationResponse)
@limiter.limit("5/minute")
async def simulate_semiconductor_allocation(
    request: Request,
    part_id: str = Query(default="MCU-241"),
    capacity_reduction_pct: float = Query(default=60.0, ge=10.0, le=90.0),
    allocation_weeks: int = Query(default=26, ge=4, le=52),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario 14: Supplier announces allocation — capacity drops significantly.
    Pulse recalculates runway; system evaluates product mix prioritization.
    """
    all_logs: list[dict[str, str]] = []

    part = db.query(Part).filter(Part.part_id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail=f"Part '{part_id}' not found")

    supplier = part.supplier
    original_capacity = supplier.capacity_per_month if supplier and supplier.capacity_per_month else 1000
    reduced_capacity = int(original_capacity * (1 - capacity_reduction_pct / 100))

    log = _sys_log(
        db,
        f"SEMICONDUCTOR ALLOCATION: {supplier.name if supplier else 'Unknown'} announces {capacity_reduction_pct}% "
        f"capacity reduction on {part_id} ({part.description}). "
        f"Capacity: {original_capacity}/month → {reduced_capacity}/month for {allocation_weeks} weeks.",
        "error",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Pulse: Recalculate runway with reduced supply rate
    inv = part.inventory
    if inv:
        log = _sys_log(
            db,
            f"Current inventory: {part_id} on_hand={inv.on_hand}, safety_stock={inv.safety_stock}, "
            f"burn_rate={inv.daily_burn_rate}/day. Allocation period: {allocation_weeks} weeks.",
            "info",
            agent="Pulse",
        )
        all_logs.append(log)
        await emit_logs([log])

        days_in_allocation = allocation_weeks * 7
        total_supply_during_allocation = reduced_capacity * (allocation_weeks / 4.33)
        total_demand_during_allocation = inv.daily_burn_rate * days_in_allocation
        projected_gap = total_demand_during_allocation - (inv.available + total_supply_during_allocation)

        log = _sys_log(
            db,
            f"Projection over {allocation_weeks} weeks: demand={total_demand_during_allocation:.0f}, "
            f"supply={total_supply_during_allocation:.0f} + on_hand={inv.available}. "
            f"Gap: {projected_gap:.0f} units.",
            "error" if projected_gap > 0 else "success",
            agent="Pulse",
        )
        all_logs.append(log)
        await emit_logs([log])

    # Find all finished goods that use this part (affected products)
    bom_entries = db.query(BOMEntry).filter(BOMEntry.component_id == part.id).all()
    affected_products: list[str] = []
    product_mix: list[dict[str, Any]] = []

    for bom in bom_entries:
        parent = bom.parent
        # Walk up if parent is a sub-assembly
        parent_bom = db.query(BOMEntry).filter(BOMEntry.component_id == parent.id).all()
        if parent_bom:
            for pb in parent_bom:
                fg = pb.parent
                if fg.part_id not in affected_products:
                    affected_products.append(fg.part_id)
                    product_mix.append({
                        "sku": fg.part_id,
                        "description": fg.description,
                        "criticality": fg.criticality.value,
                        "qty_per": bom.quantity_per * pb.quantity_per,
                    })
        else:
            if parent.part_id not in affected_products:
                affected_products.append(parent.part_id)
                product_mix.append({
                    "sku": parent.part_id,
                    "description": parent.description,
                    "criticality": parent.criticality.value,
                    "qty_per": bom.quantity_per,
                })

    # Sort by criticality for product mix recommendation
    crit_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    product_mix.sort(key=lambda x: crit_order.get(x["criticality"], 99))

    for i, pm in enumerate(product_mix, 1):
        monthly_allocation = reduced_capacity // max(len(product_mix), 1)
        pm["monthly_allocation"] = monthly_allocation
        pm["priority"] = i
        log = _sys_log(
            db,
            f"Product mix priority {i}: {pm['sku']} ({pm['description']}) — "
            f"criticality [{pm['criticality']}], {pm['qty_per']}x per unit. "
            f"Allocated: {monthly_allocation}/month.",
            "info",
            agent="Solver",
        )
        all_logs.append(log)
        await emit_logs([log])

    # Run MRP for the highest-priority affected product
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if affected_products:
        mrp_result = calculate_net_requirements(db, affected_products[0], 200)
        all_logs.extend(mrp_result["logs"])
        await emit_logs(mrp_result["logs"])

        buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
        if buy_orders:
            ghost_result = process_buy_orders(db, buy_orders)
            all_logs.extend(ghost_result["logs"])
            await emit_logs(ghost_result["logs"])

    summary = _sys_log(
        db,
        f"Semiconductor allocation analysis complete: {part_id} capacity reduced {capacity_reduction_pct}% "
        f"for {allocation_weeks} weeks. {len(affected_products)} product(s) affected, "
        f"{len(ghost_result['purchase_orders'])} PO(s) generated.",
        "success",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "SEMICONDUCTOR_ALLOCATION",
        "part_id": part_id,
        "original_capacity": original_capacity,
        "reduced_capacity": reduced_capacity,
        "allocation_weeks": allocation_weeks,
        "affected_products": affected_products,
        "product_mix_recommendation": product_mix,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario 15: Seasonal Ramp
# ---------------------------------------------------------------------------

@router.post("/seasonal-ramp", response_model=SeasonalRampResponse)
@limiter.limit("5/minute")
async def simulate_seasonal_ramp(
    request: Request,
    deviation_pct: float = Query(default=40.0, ge=10.0, le=100.0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario 15: Peak season orders arrive above forecast.
    Scout detects deviation; Solver pre-positions inventory.
    """
    all_logs: list[dict[str, str]] = []

    log = _sys_log(
        db,
        f"SEASONAL RAMP: Actual demand exceeding forecast by {deviation_pct}% across product lines.",
        "warning",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Find all products with demand forecasts
    forecasts = db.query(DemandForecast).all()
    affected_products: list[str] = []
    pre_positioned_parts: list[dict[str, Any]] = []
    all_purchase_orders: list[dict[str, Any]] = []

    # Group forecasts by part
    parts_with_forecasts: dict[int, list[DemandForecast]] = {}
    for f in forecasts:
        parts_with_forecasts.setdefault(f.part_id, []).append(f)

    for part_id, part_forecasts in parts_with_forecasts.items():
        part = db.query(Part).filter(Part.id == part_id).first()
        if not part:
            continue

        # Only process finished goods
        from database.models import PartCategory
        if part.category != PartCategory.FINISHED_GOOD:
            continue

        total_forecast = sum(f.forecast_qty for f in part_forecasts)
        actual_demand = int(total_forecast * (1 + deviation_pct / 100))
        deviation_units = actual_demand - total_forecast

        if part.part_id not in affected_products:
            affected_products.append(part.part_id)

        log = _sys_log(
            db,
            f"Scout detects forecast deviation: {part.part_id} ({part.description}) — "
            f"forecast {total_forecast}, actual demand ~{actual_demand} (+{deviation_pct}%, +{deviation_units} units).",
            "warning",
            agent="Scout",
        )
        all_logs.append(log)
        await emit_logs([log])

        # Run MRP for the excess demand
        mrp_result = calculate_net_requirements(db, part.part_id, actual_demand)
        all_logs.extend(mrp_result["logs"])
        await emit_logs(mrp_result["logs"])

        # Track pre-positioned parts (components that need ordering)
        for shortage in mrp_result.get("shortages", []):
            pre_positioned_parts.append({
                "part_id": shortage["part_id"],
                "parent_sku": part.part_id,
                "gap": shortage["gap"],
                "criticality": shortage["criticality"],
            })

        # Buyer processes buy orders for this product
        buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
        if buy_orders:
            ghost_result = process_buy_orders(db, buy_orders)
            all_logs.extend(ghost_result["logs"])
            await emit_logs(ghost_result["logs"])
            all_purchase_orders.extend(ghost_result["purchase_orders"])

    summary = _sys_log(
        db,
        f"Seasonal ramp analysis complete: {deviation_pct}% above forecast. "
        f"{len(affected_products)} product(s) affected, "
        f"{len(pre_positioned_parts)} component(s) need pre-positioning.",
        "success",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "SEASONAL_RAMP",
        "forecast_deviation_pct": deviation_pct,
        "affected_products": affected_products,
        "pre_positioned_parts": pre_positioned_parts,
        "procurement": all_purchase_orders,
        "logs": all_logs,
    }


# ---------------------------------------------------------------------------
# Scenario 16: Demand Horizon Zone Classification (PRD §10)
# ---------------------------------------------------------------------------

@router.post("/demand-horizon", response_model=DemandHorizonResponse)
@limiter.limit("5/minute")
async def simulate_demand_horizon(
    request: Request,
    part_id: str = Query(default="CH-231", description="Part to evaluate"),
    demand_qty: int = Query(default=500, description="Quantity demanded"),
    days_until_needed: int = Query(default=30, description="Days until demand must be fulfilled"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    PRD §10: Classify a demand signal into one of three horizon zones
    and determine the appropriate agent response.

    Zone 1 (6+ months): Scout advisory only, no PO.
    Zone 2 (2-5 months): Solver + Buyer, standard PO.
    Zone 3 (<60 days): Pulse + Solver, expedited PO, secondary supplier.
    """
    part = db.query(Part).filter(Part.part_id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail=f"Part '{part_id}' not found")

    result = evaluate_demand_horizon(db, part_id, demand_qty, days_until_needed)
    db.commit()

    await emit_logs(result["logs"])

    return {
        "status": "simulation_complete",
        **{k: v for k, v in result.items() if k != "logs"},
        "logs": result["logs"],
    }


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

@router.post("/reset", response_model=ResetResponse)
@limiter.limit("2/minute")
async def simulate_reset(
    request: Request,
    db: Session = Depends(get_db),
    x_reset_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Reset the database to a clean FL-001 state for fresh demos."""
    expected_token = os.getenv("RESET_TOKEN")
    if expected_token and x_reset_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Reset-Token header.")

    if not _reset_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A reset is already in progress. Please wait.")

    try:
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
    finally:
        _reset_lock.release()

    return {"status": "reset_complete", "message": "Database wiped and re-seeded with FL-001 data."}
