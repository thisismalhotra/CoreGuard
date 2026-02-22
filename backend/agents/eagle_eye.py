"""
Eagle-Eye Agent — Quality Inspection.

Simulates receiving a physical shipment at the Digital Dock and comparing it
against spec tolerances. Passes or fails the batch and triggers remediation
if it fails (quarantine + emergency reorder via Core-Guard → Ghost-Writer).

Stateless: operates on DB state passed in. Emits structured logs for Glass Box visibility.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from database.models import Part, Inventory, AgentLog, QualityInspection, InspectionResult

AGENT_NAME = "Eagle-Eye"

# CAD Spec tolerances (simulated — would normally come from Pinecone vector DB)
CAD_SPECS = {
    "CH-101": {"hardness_min": 8.0, "hardness_max": 10.0, "dimension_tolerance_mm": 0.05},
    "SW-303": {"resistance_min": 4.5, "resistance_max": 5.5, "cycle_life_min": 10000},
    "LNS-505": {"clarity_min": 95.0, "focal_length_mm": 25.0, "focal_tolerance_mm": 0.1},
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


def inspect_batch(
    db: Session,
    part_id: str,
    batch_size: int,
    force_fail: bool = True,
) -> dict[str, Any]:
    """
    Simulate a quality inspection of an incoming shipment.

    Steps:
      1. Retrieve CAD specs for the part.
      2. Simulate sensor readings for the batch.
      3. Compare readings against spec tolerances.
      4. Pass or Fail the batch.
      5. If FAIL: quarantine stock, trigger emergency reorder.

    Args:
        force_fail: Set True for God Mode simulation to guarantee a dramatic failure.

    Returns:
        {
            "result": "PASS"|"FAIL",
            "part_id": str,
            "batch_size": int,
            "readings": dict,
            "actions": list,
            "logs": list,
        }
    """
    logs: list[dict[str, str]] = []
    actions: list[dict[str, Any]] = []

    part = db.query(Part).filter(Part.part_id == part_id).first()
    if not part:
        logs.append(_log(db, f"Part {part_id} not found in database.", "error"))
        return {"result": "ERROR", "part_id": part_id, "logs": logs}

    logs.append(_log(db, f"Shipment arrived at Digital Dock: {batch_size}x {part_id} ({part.description})."))
    logs.append(_log(db, f"Retrieving CAD spec tolerances for {part_id} from spec database..."))

    spec = CAD_SPECS.get(part_id)
    if not spec:
        logs.append(_log(db, f"No CAD spec found for {part_id}. Manual inspection required.", "warning"))
        return {"result": "PENDING", "part_id": part_id, "logs": logs}

    # --- AI Handover: In production, sensor readings would be compared against
    # Pinecone vector embeddings of CAD drawings. Here we simulate the readings. ---
    logs.append(_log(db, f"Running automated sensor scan on {batch_size} units..."))

    readings: dict[str, Any] = {}
    failed_checks: list[str] = []

    if part_id == "CH-101":
        hardness = round(random.uniform(6.5, 7.8) if force_fail else random.uniform(8.5, 9.5), 2)
        dimension_error = round(random.uniform(0.12, 0.18) if force_fail else random.uniform(0.01, 0.04), 3)
        readings = {"hardness": hardness, "dimension_error_mm": dimension_error}

        logs.append(_log(db, f"Sensor readings: hardness={hardness} (spec: {spec['hardness_min']}–{spec['hardness_max']}), "
                         f"dimension_error={dimension_error}mm (tolerance: ±{spec['dimension_tolerance_mm']}mm)."))

        if not (spec["hardness_min"] <= hardness <= spec["hardness_max"]):
            failed_checks.append(f"Hardness {hardness} out of spec [{spec['hardness_min']}–{spec['hardness_max']}]")
        if dimension_error > spec["dimension_tolerance_mm"]:
            failed_checks.append(f"Dimension error {dimension_error}mm exceeds tolerance {spec['dimension_tolerance_mm']}mm")

    elif part_id == "SW-303":
        resistance = round(random.uniform(6.0, 7.5) if force_fail else random.uniform(4.7, 5.3), 2)
        cycle_life = int(random.uniform(3000, 5000) if force_fail else random.uniform(12000, 15000))
        readings = {"resistance_ohms": resistance, "cycle_life": cycle_life}

        logs.append(_log(db, f"Sensor readings: resistance={resistance}Ω (spec: {spec['resistance_min']}–{spec['resistance_max']}Ω), "
                         f"cycle_life={cycle_life} (min: {spec['cycle_life_min']})."))

        if not (spec["resistance_min"] <= resistance <= spec["resistance_max"]):
            failed_checks.append(f"Resistance {resistance}Ω out of spec")
        if cycle_life < spec["cycle_life_min"]:
            failed_checks.append(f"Cycle life {cycle_life} below minimum {spec['cycle_life_min']}")

    elif part_id == "LNS-505":
        clarity = round(random.uniform(70.0, 80.0) if force_fail else random.uniform(96.0, 99.0), 1)
        focal_error = round(random.uniform(0.3, 0.5) if force_fail else random.uniform(0.02, 0.08), 3)
        readings = {"clarity_pct": clarity, "focal_error_mm": focal_error}

        logs.append(_log(db, f"Sensor readings: clarity={clarity}% (min: {spec['clarity_min']}%), "
                         f"focal_error={focal_error}mm (tolerance: ±{spec['focal_tolerance_mm']}mm)."))

        if clarity < spec["clarity_min"]:
            failed_checks.append(f"Clarity {clarity}% below minimum {spec['clarity_min']}%")
        if focal_error > spec["focal_tolerance_mm"]:
            failed_checks.append(f"Focal error {focal_error}mm exceeds tolerance")

    # --- Determine result ---
    result = InspectionResult.FAIL if failed_checks else InspectionResult.PASS
    notes = "; ".join(failed_checks) if failed_checks else "All checks passed."

    inspection = QualityInspection(
        part_id=part.id,
        batch_size=batch_size,
        result=result,
        notes=notes,
    )
    db.add(inspection)
    db.flush()

    if result == InspectionResult.PASS:
        logs.append(_log(db, f"PASS: All {batch_size} units of {part_id} meet spec. Batch cleared for inventory.", "success"))
        inv = part.inventory
        if inv:
            inv.on_hand += batch_size
            logs.append(_log(db, f"Inventory updated: {part_id} on_hand increased by {batch_size} to {inv.on_hand}.", "success"))
    else:
        logs.append(_log(db, f"FAIL: {len(failed_checks)} spec violation(s) detected.", "error"))
        for check in failed_checks:
            logs.append(_log(db, f"  ✗ {check}", "error"))

        # Quarantine: do not add to inventory, mark as reserved to flag the issue
        logs.append(_log(db, f"Quarantining entire batch of {batch_size}x {part_id}. Stock NOT added to inventory.", "warning"))

        # Trigger emergency reorder
        logs.append(_log(db, f"Eagle-Eye escalating to Core-Guard: requesting emergency reorder of {batch_size}x {part_id}.", "warning"))

        actions.append({
            "type": "BUY_ORDER",
            "part_id": part_id,
            "quantity": batch_size,
            "unit_cost": part.unit_cost,
            "total_cost": round(batch_size * part.unit_cost, 2),
            "supplier_id": part.supplier_id,
            "supplier_name": part.supplier.name if part.supplier else "Unknown",
            "triggered_by": AGENT_NAME,
        })

    # NOTE: No db.commit() here — the calling simulation endpoint owns the transaction.
    # Agents only flush() to get IDs; the single commit happens in the router.

    return {
        "result": result.value,
        "part_id": part_id,
        "batch_size": batch_size,
        "readings": readings,
        "failed_checks": failed_checks,
        "actions": actions,
        "logs": logs,
    }
