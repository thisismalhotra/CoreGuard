"""
Data Integrity Agent — Ghost Inventory & Suspect Inventory Detection.

PRD §11: Ensures inventory data is trustworthy by detecting anomalies:

1. Ghost Inventory Detection:
   If scheduled consumption > 0 but system deductions == 0 for 14 consecutive days:
   → Block that On-Hand value from MRP calculations
   → Generate a Cycle Count Task for the warehouse manager
   → Emit a warning log

2. Suspect Inventory Detection:
   If a part has not moved in 6 months but count is non-zero:
   → Flag as "Suspect Inventory"
   → Generate a physical count task
   → Emit a warning log

Stateless: operates on DB state passed in. Emits structured logs for Glass Box visibility.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from agents.utils import create_agent_log
from database.models import (
    Inventory,
    InventoryFlag,
    InventoryHealthRecord,
)

AGENT_NAME = "Data-Integrity"

# Thresholds (PRD §11)
GHOST_INVENTORY_DAYS = 14    # No consumption for 14+ days despite scheduled demand
SUSPECT_INVENTORY_DAYS = 180  # No movement for 6+ months


def _log(db: Session, message: str, log_type: str = "info") -> dict[str, str]:
    """Persist a Glass Box log entry and return it for Socket.io emission."""
    return create_agent_log(db, AGENT_NAME, message, log_type)


def detect_ghost_inventory(
    db: Session,
    reference_date: datetime | None = None,
) -> dict[str, Any]:
    """
    PRD §11: Ghost Inventory Detection.

    Scans all inventory records for parts where:
    - daily_burn_rate > 0 (there IS scheduled consumption)
    - last_consumption_date is either None or > GHOST_INVENTORY_DAYS ago

    This means units are supposedly being consumed but the system never
    recorded a deduction — the on-hand count may be inaccurate.

    Returns:
        {
            "ghost_parts": [{"part_id": str, "on_hand": int, "days_since_consumption": int}],
            "cycle_count_tasks": [{"part_id": str, "task": str}],
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []
    now = reference_date or datetime.now(timezone.utc)

    logs.append(_log(db, "Starting ghost inventory scan (PRD §11)..."))

    all_inventory = db.query(Inventory).all()
    ghost_parts = []
    cycle_count_tasks = []

    for inv in all_inventory:
        part = inv.part
        if not part:
            continue

        # Only check parts with scheduled consumption (burn rate > 0)
        if inv.daily_burn_rate <= 0:
            continue

        # Check if last consumption was too long ago
        if inv.last_consumption_date is None:
            days_since = GHOST_INVENTORY_DAYS + 1  # Assume ghost if never consumed
        else:
            # Ensure both are timezone-aware for subtraction
            last_date = inv.last_consumption_date
            if last_date.tzinfo is None:
                last_date = last_date.replace(tzinfo=timezone.utc)
            days_since = (now - last_date).days

        if days_since >= GHOST_INVENTORY_DAYS and inv.on_hand > 0:
            ghost_parts.append({
                "part_id": part.part_id,
                "on_hand": inv.on_hand,
                "daily_burn_rate": inv.daily_burn_rate,
                "days_since_consumption": days_since,
            })

            # Create cycle count task
            task = (
                f"CYCLE COUNT REQUIRED: {part.part_id} ({part.description}) — "
                f"on_hand={inv.on_hand} but no consumption recorded for {days_since} days "
                f"despite burn rate of {inv.daily_burn_rate}/day."
            )
            cycle_count_tasks.append({"part_id": part.part_id, "task": task})

            # Flag in DB
            health_record = InventoryHealthRecord(
                part_id=part.part_id,
                flag=InventoryFlag.GHOST,
                notes=task,
            )
            db.add(health_record)

            logs.append(_log(
                db,
                f"GHOST INVENTORY: {part.part_id} — {inv.on_hand} units on hand, "
                f"burn rate {inv.daily_burn_rate}/day, but NO deductions for {days_since} days. "
                f"Blocking from MRP. Generating cycle count task.",
                "warning",
            ))

    if not ghost_parts:
        logs.append(_log(db, "Ghost inventory scan complete: No anomalies detected.", "success"))
    else:
        logs.append(_log(
            db,
            f"Ghost inventory scan complete: {len(ghost_parts)} part(s) flagged. "
            f"{len(cycle_count_tasks)} cycle count task(s) generated.",
            "warning",
        ))

    db.flush()

    return {
        "ghost_parts": ghost_parts,
        "cycle_count_tasks": cycle_count_tasks,
        "logs": logs,
    }


def detect_suspect_inventory(
    db: Session,
    reference_date: datetime | None = None,
) -> dict[str, Any]:
    """
    PRD §11: Suspect Inventory Detection.

    Scans all inventory records for parts where:
    - on_hand > 0 (count is non-zero)
    - last_updated is > SUSPECT_INVENTORY_DAYS ago (no movement for 6+ months)

    Returns:
        {
            "suspect_parts": [{"part_id": str, "on_hand": int, "days_since_movement": int}],
            "physical_count_tasks": [{"part_id": str, "task": str}],
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []
    now = reference_date or datetime.now(timezone.utc)

    logs.append(_log(db, "Starting suspect inventory scan (PRD §11)..."))

    all_inventory = db.query(Inventory).all()
    suspect_parts = []
    physical_count_tasks = []

    for inv in all_inventory:
        part = inv.part
        if not part:
            continue

        if inv.on_hand <= 0:
            continue

        # Check last movement date
        if inv.last_updated is None:
            days_since = SUSPECT_INVENTORY_DAYS + 1
        else:
            last_date = inv.last_updated
            if last_date.tzinfo is None:
                last_date = last_date.replace(tzinfo=timezone.utc)
            days_since = (now - last_date).days

        if days_since >= SUSPECT_INVENTORY_DAYS:
            suspect_parts.append({
                "part_id": part.part_id,
                "on_hand": inv.on_hand,
                "days_since_movement": days_since,
            })

            task = (
                f"PHYSICAL COUNT REQUIRED: {part.part_id} ({part.description}) — "
                f"on_hand={inv.on_hand} but no inventory movement for {days_since} days."
            )
            physical_count_tasks.append({"part_id": part.part_id, "task": task})

            # Flag in DB
            health_record = InventoryHealthRecord(
                part_id=part.part_id,
                flag=InventoryFlag.SUSPECT,
                notes=task,
            )
            db.add(health_record)

            logs.append(_log(
                db,
                f"SUSPECT INVENTORY: {part.part_id} — {inv.on_hand} units on hand, "
                f"but no movement for {days_since} days (threshold: {SUSPECT_INVENTORY_DAYS} days). "
                f"Generating physical count task.",
                "warning",
            ))

    if not suspect_parts:
        logs.append(_log(db, "Suspect inventory scan complete: No anomalies detected.", "success"))
    else:
        logs.append(_log(
            db,
            f"Suspect inventory scan complete: {len(suspect_parts)} part(s) flagged. "
            f"{len(physical_count_tasks)} physical count task(s) generated.",
            "warning",
        ))

    db.flush()

    return {
        "suspect_parts": suspect_parts,
        "physical_count_tasks": physical_count_tasks,
        "logs": logs,
    }


def run_full_integrity_check(
    db: Session,
    reference_date: datetime | None = None,
) -> dict[str, Any]:
    """
    Run both ghost and suspect inventory scans in sequence.

    Returns combined results and logs.
    """
    logs: list[dict[str, str]] = []

    logs.append(_log(db, "=== DATA INTEGRITY CHECK (PRD §11) ==="))

    ghost_result = detect_ghost_inventory(db, reference_date)
    logs.extend(ghost_result["logs"])

    suspect_result = detect_suspect_inventory(db, reference_date)
    logs.extend(suspect_result["logs"])

    total_issues = len(ghost_result["ghost_parts"]) + len(suspect_result["suspect_parts"])
    summary_type = "warning" if total_issues > 0 else "success"
    logs.append(_log(
        db,
        f"Data integrity check complete: {total_issues} issue(s) found "
        f"({len(ghost_result['ghost_parts'])} ghost, {len(suspect_result['suspect_parts'])} suspect).",
        summary_type,
    ))

    return {
        "ghost": ghost_result,
        "suspect": suspect_result,
        "total_issues": total_issues,
        "logs": logs,
    }
