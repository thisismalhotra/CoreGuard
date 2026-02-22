"""
Aura Agent — Demand Sensing.

Monitors sales data and detects when actual demand exceeds forecast threshold.
Fires a DEMAND_SPIKE event when Sales > Forecast * 1.2 (per PRD §3.3.1).

Stateless: reads DB state, emits logs, returns spike detection result.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from database.models import Part, DemandForecast
from agents.utils import create_agent_log

AGENT_NAME = "Aura"
SPIKE_THRESHOLD = 1.2  # Fire DEMAND_SPIKE when actual > forecast * threshold


def _log(db: Session, message: str, log_type: str = "info") -> dict[str, str]:
    """Persist a Glass Box log entry and return it for Socket.io emission."""
    return create_agent_log(db, AGENT_NAME, message, log_type)


def detect_demand_spike(
    db: Session,
    sku: str,
    new_actual_qty: int,
) -> dict[str, Any]:
    """
    Simulate a demand reading for a given SKU.

    Updates actual_qty in the forecast table, then checks if the spike
    threshold has been breached.

    Returns:
        {
            "spike_detected": bool,
            "sku": str,
            "forecast_qty": int,
            "actual_qty": int,
            "multiplier": float,
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []

    part = db.query(Part).filter(Part.part_id == sku).first()
    if not part:
        logs.append(_log(db, f"SKU {sku} not found.", "error"))
        return {"spike_detected": False, "sku": sku, "logs": logs}

    forecast = db.query(DemandForecast).filter(DemandForecast.part_id == part.id).first()
    if not forecast:
        logs.append(_log(db, f"No forecast data for {sku}.", "error"))
        return {"spike_detected": False, "sku": sku, "logs": logs}

    logs.append(_log(db, f"Scanning demand signal for {sku} ({part.description})..."))

    # Update actual demand (simulated injection)
    forecast.actual_qty = new_actual_qty
    forecast.updated_at = datetime.now(timezone.utc)
    db.flush()

    multiplier = round(forecast.actual_qty / forecast.forecast_qty, 2) if forecast.forecast_qty > 0 else 0.0
    spike_detected = forecast.actual_qty > forecast.forecast_qty * SPIKE_THRESHOLD

    logs.append(_log(
        db,
        f"Demand reading: forecast={forecast.forecast_qty}, actual={forecast.actual_qty}, "
        f"multiplier={multiplier}x (threshold={SPIKE_THRESHOLD}x).",
    ))

    if spike_detected:
        logs.append(_log(
            db,
            f"DEMAND_SPIKE detected for {sku}! Actual demand is {multiplier}x forecast. "
            f"Escalating to Core-Guard MRP Agent.",
            "warning",
        ))
    else:
        logs.append(_log(
            db,
            f"Demand for {sku} is within normal range. No action required.",
            "success",
        ))

    # NOTE: No db.commit() here — the calling simulation endpoint owns the transaction.
    # Agents only flush() to get IDs; the single commit happens in the router.

    return {
        "spike_detected": spike_detected,
        "sku": sku,
        "forecast_qty": forecast.forecast_qty,
        "actual_qty": forecast.actual_qty,
        "multiplier": multiplier,
        "logs": logs,
    }
