"""
Core-Guard Agent — MRP (Material Requirements Planning) Logic.

This is the "brain" of the supply chain. It receives a DEMAND_SPIKE event,
calculates net requirements using pure Python math (Rule B: no LLM for arithmetic),
and decides whether to REALLOCATE from substitute SKUs or issue a BUY_ORDER.

Stateless: operates on DB state passed in. Emits structured logs for Glass Box visibility.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from database.models import (
    Part, BOMEntry, Inventory, CriticalityLevel,
    RingFenceAuditLog, SalesOrder,
)
from agents.utils import create_agent_log

AGENT_NAME = "Core-Guard"

# Criticality-based routing rules — determines procurement strategy per part
ROUTING_RULES = {
    CriticalityLevel.CRITICAL: {
        "safety_stock_multiplier": 1.5,   # Order 50% extra buffer for critical parts
        "allow_reallocation": False,       # Never reallocate from other SKUs — too risky
        "expedite": True,                  # Prefer fastest supplier (lowest lead time)
    },
    CriticalityLevel.HIGH: {
        "safety_stock_multiplier": 1.25,   # Order 25% extra buffer
        "allow_reallocation": True,        # Can reallocate but only if surplus > safety_stock
        "expedite": True,                  # Prefer fast suppliers
    },
    CriticalityLevel.MEDIUM: {
        "safety_stock_multiplier": 1.0,    # Order exact gap
        "allow_reallocation": True,        # Standard reallocation allowed
        "expedite": False,                 # Use cheapest/most reliable supplier
    },
    CriticalityLevel.LOW: {
        "safety_stock_multiplier": 1.0,    # Order exact gap
        "allow_reallocation": True,        # Freely reallocate
        "expedite": False,                 # No rush
    },
}


def _log(db: Session, message: str, log_type: str = "info") -> dict[str, str]:
    """Persist a Glass Box log entry and return it for Socket.io emission."""
    return create_agent_log(db, AGENT_NAME, message, log_type)


def calculate_net_requirements(
    db: Session,
    sku: str,
    demand_qty: int,
) -> dict[str, Any]:
    """
    MRP explosion for a single finished-good SKU.

    Returns:
        {
            "sku": str,
            "demand_qty": int,
            "shortages": [{"part_id": str, "required": int, "available": int, "gap": int}],
            "actions": [{"type": "REALLOCATE"|"BUY_ORDER", ...}],
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []

    # --- Locate the finished good ---
    part = db.query(Part).filter(Part.part_id == sku).first()
    if not part:
        logs.append(_log(db, f"SKU {sku} not found in database.", "error"))
        return {"sku": sku, "demand_qty": demand_qty, "shortages": [], "actions": [], "logs": logs}

    logs.append(_log(db, f"Received demand spike: {demand_qty} units of {sku} ({part.description})."))

    # --- BOM explosion: what components do we need? ---
    bom_entries = db.query(BOMEntry).filter(BOMEntry.parent_id == part.id).all()
    if not bom_entries:
        logs.append(_log(db, f"No BOM found for {sku}. Cannot calculate requirements.", "warning"))
        return {"sku": sku, "demand_qty": demand_qty, "shortages": [], "actions": [], "logs": logs}

    shortages: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    for bom in bom_entries:
        component = bom.component
        inventory = component.inventory

        # Look up criticality-based routing rules for this component
        routing = ROUTING_RULES.get(component.criticality, ROUTING_RULES[CriticalityLevel.MEDIUM])

        # Pure Python math — Rule B
        required = demand_qty * bom.quantity_per
        available = inventory.available if inventory else 0
        gap = required - available

        logs.append(_log(
            db,
            f"BOM check: {component.part_id} [{component.criticality.value}] — "
            f"need {required}, available {available}, gap {gap}.",
        ))

        if gap <= 0:
            logs.append(_log(db, f"{component.part_id}: Stock sufficient. No action needed.", "success"))
            continue

        # Apply safety stock multiplier — CRITICAL parts get extra buffer
        order_qty = int(gap * routing["safety_stock_multiplier"])
        if order_qty > gap:
            logs.append(_log(
                db,
                f"Criticality [{component.criticality.value}]: Adding {routing['safety_stock_multiplier']}x buffer → "
                f"ordering {order_qty} (gap was {gap}).",
                "info",
            ))

        shortages.append({
            "part_id": component.part_id,
            "required": required,
            "available": available,
            "gap": gap,
            "criticality": component.criticality.value,
        })

        logs.append(_log(db, f"SHORTAGE: {component.part_id} short by {gap} units.", "warning"))

        # --- Routing decision based on criticality ---
        reallocation = None
        if routing["allow_reallocation"]:
            reallocation = _attempt_reallocation(db, part, component, order_qty, logs)
        else:
            logs.append(_log(
                db,
                f"Reallocation BLOCKED for {component.part_id} — criticality [{component.criticality.value}] "
                f"forbids stock transfers. Must procure externally.",
                "warning",
            ))

        if reallocation:
            actions.append(reallocation)
            remaining = reallocation.get("remaining", 0)
            if remaining > 0:
                # Partial reallocation — issue a BUY_ORDER for only the uncovered gap
                buy_qty = int(remaining * routing["safety_stock_multiplier"])
                buy_order = {
                    "type": "BUY_ORDER",
                    "part_id": component.part_id,
                    "quantity": buy_qty,
                    "unit_cost": component.unit_cost,
                    "total_cost": round(buy_qty * component.unit_cost, 2),
                    "supplier_id": component.supplier_id,
                    "supplier_name": component.supplier.name if component.supplier else "Unknown",
                    "triggered_by": AGENT_NAME,
                    "expedite": routing["expedite"],
                    "criticality": component.criticality.value,
                }
                actions.append(buy_order)
                logs.append(_log(
                    db,
                    f"Issuing BUY_ORDER for remaining gap: {buy_qty}x {component.part_id} from {buy_order['supplier_name']} "
                    f"@ ${buy_order['total_cost']:.2f}"
                    f"{' [EXPEDITED]' if routing['expedite'] else ''}.",
                    "info",
                ))
        else:
            # Cannot reallocate — issue a BUY_ORDER for full order quantity
            buy_order = {
                "type": "BUY_ORDER",
                "part_id": component.part_id,
                "quantity": order_qty,
                "unit_cost": component.unit_cost,
                "total_cost": round(order_qty * component.unit_cost, 2),
                "supplier_id": component.supplier_id,
                "supplier_name": component.supplier.name if component.supplier else "Unknown",
                "triggered_by": AGENT_NAME,
                "expedite": routing["expedite"],
                "criticality": component.criticality.value,
            }
            actions.append(buy_order)
            logs.append(_log(
                db,
                f"Issuing BUY_ORDER: {order_qty}x {component.part_id} from {buy_order['supplier_name']} "
                f"@ ${buy_order['total_cost']:.2f}"
                f"{' [EXPEDITED]' if routing['expedite'] else ''}.",
                "info",
            ))

    if not shortages:
        logs.append(_log(db, f"All components for {sku} are in stock. No procurement needed.", "success"))
    else:
        logs.append(_log(
            db,
            f"MRP complete for {sku}: {len(shortages)} shortage(s), {len(actions)} action(s) generated.",
            "info",
        ))

    # NOTE: No db.commit() here — the calling simulation endpoint owns the transaction.
    # Agents only flush() to get IDs; the single commit happens in the router.

    return {
        "sku": sku,
        "demand_qty": demand_qty,
        "shortages": shortages,
        "actions": actions,
        "logs": logs,
    }


def _attempt_reallocation(
    db: Session,
    current_parent: Part,
    component: Part,
    gap: int,
    logs: list[dict[str, str]],
) -> dict[str, Any] | None:
    """
    Check if the component itself has surplus inventory that can be reallocated
    from reserves held against other finished goods.

    The reallocation logic works on the COMPONENT's inventory, not the parent
    finished good's inventory. We check other parents that use this component
    and determine if any of their reserved allocations can be transferred.

    Returns a REALLOCATE action if enough surplus exists, or None if a
    BUY_ORDER is still needed (partial reallocations are logged but not
    returned as actions — the remaining gap generates a buy order).
    """
    component_inventory = component.inventory
    if not component_inventory:
        return None

    # The component's own surplus: stock above safety stock that isn't reserved
    # Safety stock acts as floor — we never reallocate below it
    surplus_above_safety = component_inventory.available - component_inventory.safety_stock

    if surplus_above_safety <= 0:
        logs.append(_log(
            db,
            f"Reallocation check: {component.part_id} has no surplus above safety stock "
            f"(available={component_inventory.available}, safety={component_inventory.safety_stock}). "
            f"Cannot reallocate.",
            "info",
        ))
        return None

    reallocatable = min(surplus_above_safety, gap)

    # Find which other parent's allocation we're borrowing from (for logging)
    other_bom_entries = (
        db.query(BOMEntry)
        .filter(
            BOMEntry.component_id == component.id,
            BOMEntry.parent_id != current_parent.id,
        )
        .all()
    )

    donor_names = [e.parent.part_id for e in other_bom_entries if e.parent]

    logs.append(_log(
        db,
        f"REALLOCATE: Moving {reallocatable} units of {component.part_id} "
        f"from surplus pool (donors: {', '.join(donor_names) or 'general stock'}, "
        f"surplus above safety: {surplus_above_safety}).",
        "success",
    ))

    # Reserve the reallocated stock so it's no longer "available"
    component_inventory.reserved += reallocatable
    component_inventory.last_updated = datetime.now(timezone.utc)

    if reallocatable >= gap:
        return {
            "type": "REALLOCATE",
            "part_id": component.part_id,
            "source_sku": donor_names[0] if donor_names else "general_stock",
            "quantity": reallocatable,
            "remaining": 0,
        }

    # Partial reallocation — return the action with `remaining` so the caller
    # can issue a BUY_ORDER for only the uncovered gap (not the full order_qty).
    remaining = gap - reallocatable
    logs.append(_log(
        db,
        f"Partial reallocation: {reallocatable}/{gap} units covered. "
        f"Remaining {remaining} units must be procured externally.",
        "warning",
    ))
    return {
        "type": "REALLOCATE",
        "part_id": component.part_id,
        "source_sku": donor_names[0] if donor_names else "general_stock",
        "quantity": reallocatable,
        "remaining": remaining,
    }


# ---------------------------------------------------------------------------
# PRD §3 Step 3: Blast Radius Analysis
# ---------------------------------------------------------------------------

def calculate_blast_radius(
    db: Session,
    part_id_str: str,
) -> dict[str, Any]:
    """
    PRD §3: Returns all finished goods that require this part, with revenue at risk.

    For each finished good that uses the given component, calculates:
      - Units at risk = min(inventory.available, demand from this component)
      - Revenue at risk = units_at_risk × finished_good_unit_cost (estimated)

    Returns:
        {
            "part_id": str,
            "affected_finished_goods": [
                {"sku": str, "description": str, "qty_per": int, "revenue_at_risk": float}
            ],
            "total_revenue_at_risk": float,
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []

    component = db.query(Part).filter(Part.part_id == part_id_str).first()
    if not component:
        logs.append(_log(db, f"Part {part_id_str} not found.", "error"))
        return {"part_id": part_id_str, "affected_finished_goods": [],
                "total_revenue_at_risk": 0.0, "logs": logs}

    # Find all finished goods that use this component
    bom_entries = (
        db.query(BOMEntry)
        .filter(BOMEntry.component_id == component.id)
        .all()
    )

    if not bom_entries:
        logs.append(_log(db, f"No finished goods depend on {part_id_str}.", "info"))
        return {"part_id": part_id_str, "affected_finished_goods": [],
                "total_revenue_at_risk": 0.0, "logs": logs}

    logs.append(_log(
        db,
        f"Blast radius analysis for {part_id_str}: "
        f"found {len(bom_entries)} finished good(s) that require this component.",
    ))

    affected = []
    total_revenue = 0.0

    # Revenue estimates per finished good (for MVP, these are realistic estimates)
    REVENUE_PER_UNIT = {
        "FL-001-T": 150.00,   # Tactical flashlight retail
        "FL-001-S": 75.00,    # Standard flashlight retail
    }

    for bom in bom_entries:
        parent = bom.parent
        parent_inv = parent.inventory

        # How many finished goods can we NOT build due to this shortage?
        component_inv = component.inventory
        component_available = component_inv.available if component_inv else 0
        parent_available = parent_inv.on_hand if parent_inv else 0

        # Units at risk: the finished goods we have committed/forecast but can't build
        unit_revenue = REVENUE_PER_UNIT.get(parent.part_id, 100.00)
        # Estimate units affected based on safety stock gap
        units_at_risk = max(0, (parent_inv.safety_stock if parent_inv else 0) - parent_available)
        # Also factor in demand: if component is short, all committed FGs are at risk
        if component_inv and component_available < component_inv.safety_stock:
            shortage_units = component_inv.safety_stock - component_available
            fg_units_affected = shortage_units // max(bom.quantity_per, 1)
            units_at_risk = max(units_at_risk, fg_units_affected)

        revenue_at_risk = round(units_at_risk * unit_revenue, 2)
        total_revenue += revenue_at_risk

        affected.append({
            "sku": parent.part_id,
            "description": parent.description,
            "qty_per": bom.quantity_per,
            "units_at_risk": units_at_risk,
            "revenue_at_risk": revenue_at_risk,
        })

        risk_level = "error" if revenue_at_risk > 10000 else "warning" if revenue_at_risk > 0 else "info"
        logs.append(_log(
            db,
            f"Blast radius: {parent.part_id} ({parent.description}) — "
            f"uses {bom.quantity_per}x {part_id_str}, "
            f"{units_at_risk} units at risk, "
            f"${revenue_at_risk:,.2f} revenue at risk.",
            risk_level,
        ))

    logs.append(_log(
        db,
        f"Blast radius complete: {len(affected)} finished good(s) impacted. "
        f"Total revenue at risk: ${total_revenue:,.2f}.",
        "error" if total_revenue > 50000 else "warning" if total_revenue > 0 else "success",
    ))

    return {
        "part_id": part_id_str,
        "affected_finished_goods": affected,
        "total_revenue_at_risk": total_revenue,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# PRD §11: Ring-Fencing Enforcement
# ---------------------------------------------------------------------------

def ring_fence_inventory(
    db: Session,
    part_id_str: str,
    order_ref: str,
    qty: int,
) -> dict[str, Any]:
    """
    PRD §11: Ring-fence inventory for a specific order.

    1. Check available (on_hand - reserved - ring_fenced_qty) >= qty
    2. If yes: increment ring_fenced_qty, log success, return True
    3. If no: emit "error" log with conflict details, return False

    All attempts (success or block) are logged to RingFenceAuditLog.

    Returns:
        {
            "success": bool,
            "part_id": str,
            "order_ref": str,
            "qty_requested": int,
            "qty_ring_fenced": int,
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []

    part = db.query(Part).filter(Part.part_id == part_id_str).first()
    if not part or not part.inventory:
        logs.append(_log(db, f"Ring-fence failed: {part_id_str} not found.", "error"))
        return {"success": False, "part_id": part_id_str, "order_ref": order_ref,
                "qty_requested": qty, "qty_ring_fenced": 0, "logs": logs}

    inv = part.inventory
    available_for_fencing = inv.available  # on_hand - reserved - ring_fenced_qty

    if available_for_fencing >= qty:
        # Success: ring-fence the units
        inv.ring_fenced_qty += qty
        inv.last_updated = datetime.now(timezone.utc)

        # Audit trail
        audit = RingFenceAuditLog(
            part_id=part_id_str,
            order_ref=order_ref,
            attempted_by=order_ref,
            qty_requested=qty,
            qty_ring_fenced=inv.ring_fenced_qty,
            action="RING_FENCED",
            message=f"Successfully ring-fenced {qty} units for {order_ref}.",
        )
        db.add(audit)
        db.flush()

        logs.append(_log(
            db,
            f"Ring-fenced {qty}x {part_id_str} for order {order_ref}. "
            f"Total ring-fenced: {inv.ring_fenced_qty}. "
            f"Remaining available: {inv.available}.",
            "success",
        ))

        return {"success": True, "part_id": part_id_str, "order_ref": order_ref,
                "qty_requested": qty, "qty_ring_fenced": inv.ring_fenced_qty, "logs": logs}
    else:
        # Block: not enough inventory
        audit = RingFenceAuditLog(
            part_id=part_id_str,
            order_ref=order_ref,
            attempted_by=order_ref,
            qty_requested=qty,
            qty_ring_fenced=inv.ring_fenced_qty,
            action="BLOCKED",
            message=(
                f"BLOCKED: Cannot ring-fence {qty} units for {order_ref}. "
                f"Only {available_for_fencing} available "
                f"(on_hand={inv.on_hand}, reserved={inv.reserved}, ring_fenced={inv.ring_fenced_qty})."
            ),
        )
        db.add(audit)
        db.flush()

        logs.append(_log(
            db,
            f"RING-FENCE BLOCKED: {order_ref} requested {qty}x {part_id_str}, "
            f"but only {available_for_fencing} available. "
            f"{inv.ring_fenced_qty} units already ring-fenced for other orders.",
            "error",
        ))

        return {"success": False, "part_id": part_id_str, "order_ref": order_ref,
                "qty_requested": qty, "qty_ring_fenced": inv.ring_fenced_qty, "logs": logs}
