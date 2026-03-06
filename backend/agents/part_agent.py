"""
Pulse Agent — Digital Twin for every SKU.

PRD §4, §8, §9: The Pulse Agent continuously monitors each SKU's health,
calculates dynamic safety stock, real-time runway (days to stockout),
and triggers a handshake to Solver when runway drops below the
supplier lead time + safety stock buffer.

Formulas (PRD §8 — all implemented in pure Python per Rule B):
  - Dynamic Safety Stock = (Max Daily Usage × Max Lead Time) - (Avg Daily Usage × Avg Lead Time)
  - Real-Time Runway = Current On-Hand / Trailing 3-Day Velocity
  - Handshake Trigger: if runway < (supplier_lead_time + safety_stock_days) -> initiate_handshake()

Stateless: operates on DB state passed in. Emits structured logs for Glass Box visibility.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from agents.utils import create_agent_log
from database.models import BOMEntry, Part

AGENT_NAME = "Pulse"


def _log(db: Session, message: str, log_type: str = "info") -> dict[str, str]:
    """Persist a Glass Box log entry and return it for Socket.io emission."""
    return create_agent_log(db, AGENT_NAME, message, log_type)


def calculate_dynamic_safety_stock(
    max_daily_usage: float,
    max_lead_time_days: int,
    avg_daily_usage: float,
    avg_lead_time_days: float,
) -> int:
    """
    PRD §8: Dynamic Safety Stock formula.

    Safety Stock = (Max Daily Usage × Max Lead Time) - (Avg Daily Usage × Avg Lead Time)

    All arithmetic in Python (Rule B). Returns integer units.
    """
    safety = (max_daily_usage * max_lead_time_days) - (avg_daily_usage * avg_lead_time_days)
    return max(0, int(safety))


def calculate_runway(on_hand: int, daily_burn_rate: float) -> float:
    """
    PRD §8: Real-Time Runway.

    Days to Stockout = Current On-Hand / Trailing 3-Day Velocity.

    NOTE: PRD explicitly states NOT to use monthly forecast averages.
    Use the trailing 3-day physical burn rate (stored on Inventory model).
    Returns float days. Returns infinity if burn rate is zero.
    """
    if daily_burn_rate <= 0:
        return float("inf")
    return on_hand / daily_burn_rate


def evaluate_handshake_trigger(
    runway_days: float,
    supplier_lead_time_days: int,
    safety_stock_days: float,
) -> bool:
    """
    PRD §8: Handshake Trigger Condition (Pulse Agent -> Solver).

    if runway < (supplier_lead_time + safety_stock_days):
        initiate_handshake(...)

    Returns True if handshake should be initiated.
    """
    threshold = supplier_lead_time_days + safety_stock_days
    return runway_days < threshold


def monitor_part(
    db: Session,
    part_id_str: str,
    burn_rate_override: float | None = None,
) -> dict[str, Any]:
    """
    PRD §9 Step 1-3: Baseline Monitoring + Local Validation.

    Runs the Part Agent's full health check for a single SKU:
      1. Calculate dynamic safety stock
      2. Calculate real-time runway
      3. Evaluate handshake trigger
      4. Emit Glass Box logs for every step

    Returns:
        {
            "part_id": str,
            "on_hand": int,
            "daily_burn_rate": float,
            "runway_days": float,
            "dynamic_safety_stock": int,
            "current_safety_stock": int,
            "supplier_lead_time_days": int,
            "handshake_triggered": bool,
            "crisis_signal": dict | None,  # Only if handshake triggered
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []

    # --- Locate the part ---
    part = db.query(Part).filter(Part.part_id == part_id_str).first()
    if not part:
        logs.append(_log(db, f"Part {part_id_str} not found in database.", "error"))
        return {
            "part_id": part_id_str, "handshake_triggered": False,
            "crisis_signal": None, "logs": logs,
        }

    inventory = part.inventory
    if not inventory:
        logs.append(_log(db, f"No inventory record for {part_id_str}.", "error"))
        return {
            "part_id": part_id_str, "handshake_triggered": False,
            "crisis_signal": None, "logs": logs,
        }

    # Use override if provided (avoids mutating the model during simulations)
    effective_burn_rate = burn_rate_override if burn_rate_override is not None else inventory.daily_burn_rate

    logs.append(_log(
        db,
        f"Monitoring {part_id_str} ({part.description}): on_hand={inventory.on_hand}, "
        f"burn_rate={effective_burn_rate}/day, safety_stock={inventory.safety_stock}.",
    ))

    # --- Step 1: Calculate Dynamic Safety Stock (PRD §8) ---
    # For MVP, we estimate max/avg from the burn rate and supplier lead time
    supplier_lead_time = part.supplier.lead_time_days if part.supplier else 7
    avg_daily_usage = effective_burn_rate
    # Max daily usage estimated as 1.5x average (spike scenario)
    max_daily_usage = avg_daily_usage * 1.5
    # Max lead time estimated as supplier lead + 3 days buffer
    max_lead_time = supplier_lead_time + 3
    avg_lead_time = float(supplier_lead_time)

    dynamic_ss = calculate_dynamic_safety_stock(
        max_daily_usage, max_lead_time, avg_daily_usage, avg_lead_time,
    )

    logs.append(_log(
        db,
        f"Dynamic Safety Stock for {part_id_str}: {dynamic_ss} units "
        f"(formula: ({max_daily_usage:.1f} × {max_lead_time}) - ({avg_daily_usage:.1f} × {avg_lead_time:.1f}) "
        f"= {max_daily_usage * max_lead_time:.0f} - {avg_daily_usage * avg_lead_time:.0f}).",
    ))

    # --- Step 2: Calculate Real-Time Runway (PRD §8) ---
    runway = calculate_runway(inventory.on_hand, effective_burn_rate)

    if runway == float("inf"):
        logs.append(_log(db, f"{part_id_str}: Zero burn rate — infinite runway (no consumption).", "info"))
    else:
        runway_status = "success" if runway > (supplier_lead_time * 2) else "warning" if runway > supplier_lead_time else "error"
        logs.append(_log(
            db,
            f"Runway for {part_id_str}: {runway:.1f} days "
            f"(on_hand={inventory.on_hand} / burn_rate={effective_burn_rate}/day). "
            f"Supplier lead time: {supplier_lead_time} days.",
            runway_status,
        ))

    # --- Step 3: Evaluate Handshake Trigger (PRD §8) ---
    safety_stock_days = inventory.safety_stock / max(effective_burn_rate, 0.01)
    handshake = evaluate_handshake_trigger(runway, supplier_lead_time, safety_stock_days)

    crisis_signal = None
    if handshake:
        crisis_signal = {
            "part_id": part_id_str,
            "on_hand": inventory.on_hand,
            "burn_rate": effective_burn_rate,
            "runway_days": round(runway, 1),
            "safety_stock": inventory.safety_stock,
            "supplier_lead_time_days": supplier_lead_time,
            "threshold_days": round(supplier_lead_time + safety_stock_days, 1),
        }
        logs.append(_log(
            db,
            f"HANDSHAKE TRIGGERED for {part_id_str}: runway ({runway:.1f}d) < "
            f"threshold ({supplier_lead_time}d lead + {safety_stock_days:.1f}d safety = "
            f"{supplier_lead_time + safety_stock_days:.1f}d). "
            f"Initiating Solver handshake with verified Crisis Signal.",
            "warning",
        ))
    else:
        logs.append(_log(
            db,
            f"{part_id_str}: Runway ({runway:.1f}d) is above threshold "
            f"({supplier_lead_time + safety_stock_days:.1f}d). No action needed.",
            "success",
        ))

    return {
        "part_id": part_id_str,
        "on_hand": inventory.on_hand,
        "daily_burn_rate": effective_burn_rate,
        "runway_days": round(runway, 2) if runway != float("inf") else None,
        "dynamic_safety_stock": dynamic_ss,
        "current_safety_stock": inventory.safety_stock,
        "supplier_lead_time_days": supplier_lead_time,
        "handshake_triggered": handshake,
        "crisis_signal": crisis_signal,
        "logs": logs,
    }


def monitor_all_components(
    db: Session,
    sku: str,
    demand_qty: int,
) -> dict[str, Any]:
    """
    PRD §9 Steps 1-3: Run Pulse Agent monitoring for all BOM components of a finished good.

    Simulates the demand impact on each component's burn rate before evaluating.
    Returns aggregated results for all components with triggered handshakes.

    Args:
        db: Database session
        sku: Finished good SKU (e.g., "FL-001-T")
        demand_qty: The demand quantity driving the check

    Returns:
        {
            "sku": str,
            "demand_qty": int,
            "component_reports": [monitor_part results],
            "crisis_signals": [signals where handshake_triggered == True],
            "logs": [all Glass Box logs],
        }
    """
    logs: list[dict[str, str]] = []

    part = db.query(Part).filter(Part.part_id == sku).first()
    if not part:
        logs.append(_log(db, f"SKU {sku} not found.", "error"))
        return {"sku": sku, "demand_qty": demand_qty, "component_reports": [],
                "crisis_signals": [], "logs": logs}

    bom_entries = db.query(BOMEntry).filter(BOMEntry.parent_id == part.id).all()
    if not bom_entries:
        logs.append(_log(db, f"No BOM entries for {sku}.", "warning"))
        return {"sku": sku, "demand_qty": demand_qty, "component_reports": [],
                "crisis_signals": [], "logs": logs}

    logs.append(_log(
        db,
        f"Pulse Agent scanning {len(bom_entries)} components for {sku} "
        f"(demand: {demand_qty} units)...",
    ))

    component_reports = []
    crisis_signals = []

    for bom in bom_entries:
        component = bom.component
        inv = component.inventory

        # Calculate simulated burn rate without mutating the model.
        # This avoids a race condition where db.flush() inside monitor_part
        # would persist the inflated value, visible to concurrent readers.
        simulated_burn: float | None = None
        if inv:
            additional_daily = (demand_qty * bom.quantity_per) / 30.0  # Spread over ~30 days
            original_burn = inv.daily_burn_rate
            simulated_burn = original_burn + additional_daily

            logs.append(_log(
                db,
                f"Simulating demand impact on {component.part_id}: "
                f"burn rate {original_burn:.1f} → {simulated_burn:.1f}/day "
                f"(+{additional_daily:.1f} from {demand_qty}x{bom.quantity_per} demand).",
            ))

        report = monitor_part(db, component.part_id, burn_rate_override=simulated_burn)
        component_reports.append(report)
        logs.extend(report["logs"])

        if report["handshake_triggered"] and report["crisis_signal"]:
            crisis_signals.append(report["crisis_signal"])

    if crisis_signals:
        logs.append(_log(
            db,
            f"Pulse Agent complete: {len(crisis_signals)}/{len(bom_entries)} components "
            f"triggered HANDSHAKE. Forwarding Crisis Signals to Solver.",
            "warning",
        ))
    else:
        logs.append(_log(
            db,
            f"Pulse Agent complete: All {len(bom_entries)} components within safe runway. "
            f"No handshake needed.",
            "success",
        ))

    return {
        "sku": sku,
        "demand_qty": demand_qty,
        "component_reports": component_reports,
        "crisis_signals": crisis_signals,
        "logs": logs,
    }
