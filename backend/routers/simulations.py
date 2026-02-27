"""
Simulation (God Mode) endpoints.

Each endpoint injects a chaos scenario into the system and streams Glass Box
logs to connected dashboards via Socket.io.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db, engine
from database.models import (
    Part, Supplier, DemandForecast, AgentLog, Base, BOMEntry, Inventory,
)
from agents.aura import detect_demand_spike
from agents.dispatcher import triage_demand_spike
from agents.part_agent import monitor_all_components, monitor_part
from agents.core_guard import calculate_net_requirements, calculate_blast_radius, ring_fence_inventory
from agents.ghost_writer import process_buy_orders
from agents.eagle_eye import inspect_batch
from agents.data_integrity import run_full_integrity_check
from schemas import (
    SpikeResponse, SupplyShockResponse, QualityFailResponse,
    CascadeFailureResponse, ConstitutionBreachResponse,
    FullBlackoutResponse, SlowBleedResponse, InventoryDecayResponse,
    ResetResponse,
)

router = APIRouter(prefix="/api/simulate", tags=["simulations"])

# Socket.io and log delay are stored on app.state by main.py.
# These module-level references are set once at startup via init_sio().
_app_state = None


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

@router.post("/spike", response_model=SpikeResponse)
async def simulate_demand_spike(
    sku: str = "FL-001-T",
    multiplier: float = Query(default=3.0, ge=1.0, le=100.0, description="Demand multiplier (1x–100x)"),
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
        raise HTTPException(status_code=404, detail=f"No forecast found for {sku}")

    spiked_qty = int(forecast.forecast_qty * multiplier)

    # ---------------------------------------------------------------
    # PRD §9: 5-Step Execution Loop
    # Step 1: AURA — Demand spike detection (Trigger Event)
    # ---------------------------------------------------------------
    aura_result = detect_demand_spike(db, sku, spiked_qty)
    all_logs.extend(aura_result["logs"])
    await emit_logs(aura_result["logs"])

    if not aura_result["spike_detected"]:
        return {"status": "no_spike", "aura": aura_result, "logs": all_logs}

    # ---------------------------------------------------------------
    # Step 2: PART AGENT — Baseline Monitoring + Local Validation (PRD §9 Steps 1-3)
    # Each Part Agent checks its own runway and dynamic safety stock
    # ---------------------------------------------------------------
    part_agent_result = monitor_all_components(db, sku, spiked_qty)
    all_logs.extend(part_agent_result["logs"])
    await emit_logs(part_agent_result["logs"])

    # ---------------------------------------------------------------
    # Step 3: DISPATCHER — Triage components by criticality
    # ---------------------------------------------------------------
    dispatch_result = triage_demand_spike(db, sku, spiked_qty)
    all_logs.extend(dispatch_result["logs"])
    await emit_logs(dispatch_result["logs"])

    # ---------------------------------------------------------------
    # Step 4: CORE-GUARD — MRP explosion + ring-fencing (PRD §9 Steps 4-5)
    # Core-Guard receives verified Crisis Signals from Part Agent
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
    # Step 5: GHOST-WRITER — Draft Purchase Orders
    # ---------------------------------------------------------------
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]

    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    # Single atomic commit — all agent work (Aura, Part Agent, Dispatcher, Core-Guard, Ghost-Writer)
    # is flushed during execution; we commit once at the end of the simulation.
    db.commit()

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

@router.post("/supply-shock", response_model=SupplyShockResponse)
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

        log = _sys_log(db, f"Assessing impact: {part.part_id} ({part.description}) — primary supplier {supplier_name} offline.", "warning", agent="Core-Guard")
        all_logs.append(log)
        await emit_logs([log])

        log = _sys_log(db, f"Inventory check: {part.part_id} — on_hand={inv.on_hand}, safety_stock={inv.safety_stock}, available={inv.available}.", "info", agent="Core-Guard")
        all_logs.append(log)
        await emit_logs([log])

        # Order the actual shortfall (safety stock deficit), not just safety_stock blindly
        order_qty = max(inv.safety_stock - inv.available, inv.safety_stock)

        alternate = (
            db.query(Supplier)
            .filter(Supplier.id != supplier.id, Supplier.is_active == True)
            .order_by(Supplier.reliability_score.desc())
            .first()
        )

        if not alternate:
            log = _sys_log(db, f"CRITICAL: No alternate suppliers available for {part.part_id}!", "error", agent="Core-Guard")
            all_logs.append(log)
            await emit_logs([log])
            continue

        log = _sys_log(
            db,
            f"Switching {part.part_id} to alternate supplier: {alternate.name} "
            f"(reliability: {alternate.reliability_score}, lead time: {alternate.lead_time_days}d).",
            "info",
            agent="Core-Guard",
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
            "triggered_by": "Core-Guard",
        })

        log = _sys_log(
            db,
            f"Emergency BUY_ORDER: {order_qty}x {part.part_id} from {alternate.name} "
            f"@ ${round(order_qty * part.unit_cost, 2):.2f}.",
            "warning",
            agent="Core-Guard",
        )
        all_logs.append(log)
        await emit_logs([log])

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
async def simulate_quality_fail(
    part_id: str = "CH-101",
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
        aluforge.is_active = False
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
        raise HTTPException(status_code=404, detail="No forecast found for FL-001-T")

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
                .filter(Supplier.id != part.supplier_id, Supplier.is_active == True)
                .order_by(Supplier.reliability_score.desc())
                .first()
            )
            if alternate:
                log = _sys_log(
                    db,
                    f"Primary supplier {part.supplier.name} OFFLINE. Rerouting {order['part_id']} order to {alternate.name} (reliability: {alternate.reliability_score}).",
                    "warning",
                    agent="Core-Guard",
                )
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

@router.post("/full-blackout", response_model=FullBlackoutResponse)
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
# Scenario G: Slow Bleed
# ---------------------------------------------------------------------------

@router.post("/slow-bleed", response_model=SlowBleedResponse)
async def simulate_slow_bleed(
    part_id: str = Query(default="CH-101", description="Part ID to simulate slow bleed on"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario G: Simulate a gradual burn rate increase (Slow Bleed).

    The Part Agent is the ONLY agent that detects this invisible crisis —
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
    crisis_signal: dict[str, Any] | None = None

    for day_num, mult in enumerate(multipliers, start=1):
        simulated_rate = round(original_burn_rate * mult, 2)
        inv.daily_burn_rate = simulated_rate
        db.flush()

        log = _sys_log(
            db,
            f"Day {day_num}: Burn rate for {part_id} now {simulated_rate}/day "
            f"({mult:.3f}x baseline {original_burn_rate}/day).",
            "info",
            agent="Part-Agent",
        )
        all_logs.append(log)
        await emit_logs([log])

        # Part Agent monitors the SKU
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
            crisis_signal = result["crisis_signal"]

            log = _sys_log(
                db,
                f"SLOW BLEED DETECTED on Day {day_num}: Part Agent identified runway decline for {part_id}. "
                f"Burn rate crept from {original_burn_rate}/day to {simulated_rate}/day. "
                f"Escalating to Core-Guard.",
                "error",
                agent="Part-Agent",
            )
            all_logs.append(log)
            await emit_logs([log])

    # If handshake triggered: find parent finished good via BOM, run MRP + procurement
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}

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
                agent="Core-Guard",
            )
            all_logs.append(log)
            await emit_logs([log])

            # Run Core-Guard MRP for the parent SKU with current demand
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

            # Ghost-Writer processes any buy orders
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
                agent="Core-Guard",
            )
            all_logs.append(log)
            await emit_logs([log])

    # Restore original burn rate
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
async def simulate_inventory_decay(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario H: Inventory Decay — Ghost inventory and stale stock detection.

    3-act story:
      Act 1: Part Agent runs baseline check — everything looks fine.
      Act 2: Inject decay conditions, Data Integrity reveals ghost/suspect stock.
      Act 3: Part Agent re-evaluates with corrected inventory, triggers crisis if needed.
    """
    all_logs: list[dict[str, str]] = []

    log = _sys_log(
        db,
        "INVENTORY DECAY INITIATED: Checking FL-001-T components for ghost and suspect inventory.",
        "warning",
    )
    all_logs.append(log)
    await emit_logs([log])

    # ---------------------------------------------------------------
    # Act 1: Part Agent runs baseline check — everything looks fine
    # ---------------------------------------------------------------
    log = _sys_log(db, "Act 1: Part Agent baseline check on FL-001-T components...", "info")
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
    # Act 2: Inject decay conditions — Data Integrity reveals the truth
    # ---------------------------------------------------------------
    log = _sys_log(db, "Act 2: Injecting inventory decay conditions...", "warning")
    all_logs.append(log)
    await emit_logs([log])

    # Save original values for restoration
    ch101_inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
    lns505_inv = db.query(Inventory).join(Part).filter(Part.part_id == "LNS-505").first()

    original_ch101_consumption_date = ch101_inv.last_consumption_date if ch101_inv else None
    original_lns505_last_updated = lns505_inv.last_updated if lns505_inv else None

    # CH-101: Set last_consumption_date to 30 days ago (ghost: burn rate > 0 but no consumption)
    if ch101_inv:
        ch101_inv.last_consumption_date = datetime.now(timezone.utc) - timedelta(days=30)
        db.flush()
        log = _sys_log(
            db,
            f"Decay injected: CH-101 last_consumption_date set to 30 days ago "
            f"(ghost: burn rate {ch101_inv.daily_burn_rate}/day but no recorded consumption).",
            "warning",
            agent="System",
        )
        all_logs.append(log)
        await emit_logs([log])

    # LNS-505: Set last_updated to 200 days ago (suspect: no movement for 6+ months)
    if lns505_inv:
        lns505_inv.last_updated = datetime.now(timezone.utc) - timedelta(days=200)
        db.flush()
        log = _sys_log(
            db,
            f"Decay injected: LNS-505 last_updated set to 200 days ago "
            f"(suspect: no inventory movement for 6+ months).",
            "warning",
            agent="System",
        )
        all_logs.append(log)
        await emit_logs([log])

    # Run Data Integrity full check
    log = _sys_log(db, "Running Data Integrity Agent full scan...", "info", agent="Data-Integrity")
    all_logs.append(log)
    await emit_logs([log])

    integrity_result = run_full_integrity_check(db)
    all_logs.extend(integrity_result["logs"])
    await emit_logs(integrity_result["logs"])

    ghost_parts = integrity_result["ghost"]["ghost_parts"]
    suspect_parts = integrity_result["suspect"]["suspect_parts"]

    log = _sys_log(
        db,
        f"Data Integrity reveals: {len(ghost_parts)} ghost part(s), "
        f"{len(suspect_parts)} suspect part(s). Inventory cannot be trusted as-is.",
        "error" if (ghost_parts or suspect_parts) else "success",
    )
    all_logs.append(log)
    await emit_logs([log])

    # ---------------------------------------------------------------
    # Act 3: Part Agent re-evaluates with corrected inventory
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
                agent="Data-Integrity",
            )
            all_logs.append(log)
            await emit_logs([log])

    # Re-run Part Agent monitoring with corrected numbers
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
            f"after ghost inventory correction. Escalating to Core-Guard.",
            "error",
            agent="Part-Agent",
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
    if ch101_inv:
        ch101_inv.last_consumption_date = original_ch101_consumption_date
    if lns505_inv:
        lns505_inv.last_updated = original_lns505_last_updated
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
# Reset
# ---------------------------------------------------------------------------

@router.post("/reset", response_model=ResetResponse)
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
