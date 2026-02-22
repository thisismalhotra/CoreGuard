"""
Dispatcher Agent — Triage & Prioritisation.

Sits between Aura and Core-Guard. When multiple SKUs experience demand spikes
simultaneously (or multiple shortages compound), the Dispatcher triages them
by criticality and lead-time sensitivity before handing off to Core-Guard.

This prevents the system from processing low-priority parts first while
critical components wait in the queue.

Stateless: reads DB state, emits logs, returns a prioritised action plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from database.models import (
    Part, BOMEntry, AgentLog, CriticalityLevel,
)

AGENT_NAME = "Dispatcher"

# Priority weights — higher = processed first
CRITICALITY_WEIGHT = {
    CriticalityLevel.CRITICAL: 100,
    CriticalityLevel.HIGH: 75,
    CriticalityLevel.MEDIUM: 50,
    CriticalityLevel.LOW: 25,
}


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


def triage_demand_spike(
    db: Session,
    sku: str,
    demand_qty: int,
) -> dict[str, Any]:
    """
    Analyse a demand spike and produce a prioritised processing plan.

    Steps:
      1. Identify the finished good and explode its BOM.
      2. Score each component by: criticality weight + lead_time_sensitivity +
         inventory gap severity.
      3. Return components sorted by priority (highest first) so Core-Guard
         handles critical shortages before lower-priority ones.

    Returns:
        {
            "sku": str,
            "demand_qty": int,
            "priority_queue": [{"part_id", "priority_score", "criticality", ...}],
            "assessment": {"total_components", "at_risk", "critical_count"},
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []

    logs.append(_log(db, f"Dispatcher received spike alert: {demand_qty} units of {sku}. Initiating triage..."))

    # --- Locate the finished good ---
    part = db.query(Part).filter(Part.part_id == sku).first()
    if not part:
        logs.append(_log(db, f"SKU {sku} not found.", "error"))
        return {"sku": sku, "demand_qty": demand_qty, "priority_queue": [], "assessment": {}, "logs": logs}

    # --- BOM explosion for impact assessment ---
    bom_entries = db.query(BOMEntry).filter(BOMEntry.parent_id == part.id).all()
    if not bom_entries:
        logs.append(_log(db, f"No BOM for {sku}. Passing through to Core-Guard.", "warning"))
        return {"sku": sku, "demand_qty": demand_qty, "priority_queue": [], "assessment": {}, "logs": logs}

    # --- Score each component ---
    scored_components: list[dict[str, Any]] = []
    at_risk = 0
    critical_count = 0

    for bom in bom_entries:
        component = bom.component
        inventory = component.inventory

        required = demand_qty * bom.quantity_per
        available = inventory.available if inventory else 0
        gap = required - available
        gap_severity = max(0, gap) / max(required, 1)  # 0.0 = no gap, 1.0 = total shortfall

        # Priority score: criticality weight + lead_time urgency + gap severity
        crit_weight = CRITICALITY_WEIGHT.get(component.criticality, 50)
        priority_score = round(
            crit_weight
            + (component.lead_time_sensitivity * 30)  # Up to 30 extra points for time-sensitive parts
            + (gap_severity * 20),                     # Up to 20 extra points for severe shortages
            1,
        )

        is_at_risk = gap > 0
        if is_at_risk:
            at_risk += 1
        if component.criticality == CriticalityLevel.CRITICAL:
            critical_count += 1

        scored_components.append({
            "part_id": component.part_id,
            "description": component.description,
            "criticality": component.criticality.value,
            "lead_time_sensitivity": component.lead_time_sensitivity,
            "required": required,
            "available": available,
            "gap": max(0, gap),
            "gap_severity": round(gap_severity, 2),
            "priority_score": priority_score,
            "at_risk": is_at_risk,
            "substitute_pool_size": component.substitute_pool_size,
        })

    # Sort by priority score descending — highest priority first
    scored_components.sort(key=lambda x: x["priority_score"], reverse=True)

    # --- Log the triage results ---
    logs.append(_log(
        db,
        f"Triage complete: {len(scored_components)} components assessed, "
        f"{at_risk} at risk, {critical_count} CRITICAL.",
    ))

    for i, comp in enumerate(scored_components, 1):
        risk_label = "AT RISK" if comp["at_risk"] else "OK"
        logs.append(_log(
            db,
            f"  #{i} [{comp['criticality']}] {comp['part_id']} — "
            f"priority={comp['priority_score']}, gap={comp['gap']}, status={risk_label}.",
            "warning" if comp["at_risk"] else "info",
        ))

    if critical_count > 0:
        logs.append(_log(
            db,
            f"ALERT: {critical_count} CRITICAL component(s) in shortage. "
            f"Dispatcher recommending expedited processing order to Core-Guard.",
            "warning",
        ))

    logs.append(_log(db, f"Handing prioritised queue to Core-Guard for MRP processing."))

    # NOTE: No db.commit() here — the calling simulation endpoint owns the transaction.
    # Agents only flush() to get IDs; the single commit happens in the router.

    return {
        "sku": sku,
        "demand_qty": demand_qty,
        "priority_queue": scored_components,
        "assessment": {
            "total_components": len(scored_components),
            "at_risk": at_risk,
            "critical_count": critical_count,
        },
        "logs": logs,
    }
