"""
Core-Guard Agent — MRP (Material Requirements Planning) Logic.

This is the "brain" of the supply chain. It receives a DEMAND_SPIKE event,
calculates net requirements using pure Python math (Rule B: no LLM for arithmetic),
and decides whether to REALLOCATE from substitute SKUs or issue a BUY_ORDER.

Stateless: operates on DB state passed in. Emits structured logs for Glass Box visibility.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session

from database.models import (
    Part, Inventory, BOMEntry, DemandForecast, AgentLog, PartCategory,
)

AGENT_NAME = "Core-Guard"


def _log(db: Session, message: str, log_type: str = "info") -> dict[str, str]:
    """Persist a Glass Box log entry and return it for Socket.io emission."""
    entry = AgentLog(agent=AGENT_NAME, message=message, log_type=log_type)
    db.add(entry)
    db.flush()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": AGENT_NAME,
        "message": message,
        "type": log_type,
    }


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

        # Pure Python math — Rule B
        required = demand_qty * bom.quantity_per
        available = inventory.available if inventory else 0
        gap = required - available

        logs.append(_log(
            db,
            f"BOM check: {component.part_id} — need {required}, available {available}, gap {gap}.",
        ))

        if gap <= 0:
            logs.append(_log(db, f"{component.part_id}: Stock sufficient. No action needed.", "success"))
            continue

        # --- Shortage detected — try reallocation first ---
        shortages.append({
            "part_id": component.part_id,
            "required": required,
            "available": available,
            "gap": gap,
        })

        logs.append(_log(db, f"SHORTAGE: {component.part_id} short by {gap} units.", "warning"))

        # Check if other finished goods have unreserved stock of this component
        reallocation = _attempt_reallocation(db, part, component, gap, logs)

        if reallocation:
            actions.append(reallocation)
        else:
            # Cannot reallocate — issue a BUY_ORDER for Ghost-Writer
            buy_order = {
                "type": "BUY_ORDER",
                "part_id": component.part_id,
                "quantity": gap,
                "unit_cost": component.unit_cost,
                "total_cost": round(gap * component.unit_cost, 2),
                "supplier_id": component.supplier_id,
                "supplier_name": component.supplier.name if component.supplier else "Unknown",
                "triggered_by": AGENT_NAME,
            }
            actions.append(buy_order)
            logs.append(_log(
                db,
                f"Issuing BUY_ORDER: {gap}x {component.part_id} from {buy_order['supplier_name']} "
                f"@ ${buy_order['total_cost']:.2f}.",
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

    db.commit()

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
    Check if other finished goods using this component have excess inventory
    that can be reallocated to cover the gap.

    Only reallocates from lower-priority variants (FL-001-S before FL-001-T).
    """
    # Find other parents that use this same component
    other_bom_entries = (
        db.query(BOMEntry)
        .filter(
            BOMEntry.component_id == component.id,
            BOMEntry.parent_id != current_parent.id,
        )
        .all()
    )

    for other_bom in other_bom_entries:
        other_parent = other_bom.parent
        other_inventory = other_parent.inventory

        if not other_inventory:
            continue

        # Available surplus from the other variant's allocation
        surplus = other_inventory.available
        if surplus <= 0:
            continue

        reallocatable = min(surplus, gap)
        logs.append(_log(
            db,
            f"REALLOCATE: Moving {reallocatable} units of {component.part_id} "
            f"from {other_parent.part_id} reserve (available: {surplus}).",
            "success",
        ))

        # Update inventory: reserve stock from the donor variant
        other_inventory.reserved += reallocatable
        component_inventory = component.inventory
        if component_inventory:
            component_inventory.reserved += reallocatable

        if reallocatable >= gap:
            return {
                "type": "REALLOCATE",
                "part_id": component.part_id,
                "source_sku": other_parent.part_id,
                "quantity": reallocatable,
            }

    # Partial or no reallocation possible
    return None
