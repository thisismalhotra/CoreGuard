"""
Lookout Agent — Demand Horizon Zones — PRD §10.

Classifies incoming demand signals into three zones and routes them to
the appropriate agent behaviour:

  Zone 1 — Fuzzy Forecast (6-12+ months)
    Active Agents: Scout only
    Behaviour: Advise on blanket agreements / capacity reservations. NO POs generated.

  Zone 2 — Lead Time Horizon (2-5 months)
    Active Agents: Solver + Buyer
    Behaviour: Forecast consumption begins. BOM explosion. Standard POs to primary suppliers.

  Zone 3 — Inside Lead Time (Drop-In Crisis) (< supplier lead time)
    Active Agents: Pulse + Solver
    Behaviour: Pulse defends ring-fenced inventory. Buyer pivots to
               fastest secondary supplier with expedited PO + cost-vs-risk trade-off.

Stateless: operates on DB state passed in. Emits structured logs for Glass Box visibility.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from agents.utils import create_agent_log
from database.models import Part, Supplier

AGENT_NAME = "Lookout"

# Zone boundaries in days
ZONE_1_MIN_DAYS = 180    # 6 months
ZONE_2_MIN_DAYS = 60     # 2 months
# Zone 3 = anything < supplier lead time (dynamic per part)


def _log(db: Session, message: str, log_type: str = "info") -> dict[str, str]:
    return create_agent_log(db, AGENT_NAME, message, log_type)


def classify_demand_zone(
    days_until_needed: int,
    supplier_lead_time_days: int,
) -> int:
    """
    Classify demand into a horizon zone (PRD §10).

    Returns:
        1 = Fuzzy Forecast (6–12+ months)
        2 = Lead Time Horizon (2–5 months)
        3 = Inside Lead Time / Drop-In Crisis (< supplier lead time)
    """
    if days_until_needed >= ZONE_1_MIN_DAYS:
        return 1
    elif days_until_needed >= ZONE_2_MIN_DAYS:
        return 2
    else:
        return 3


def evaluate_demand_horizon(
    db: Session,
    part_id_str: str,
    demand_qty: int,
    days_until_needed: int,
) -> dict[str, Any]:
    """
    PRD §10: Evaluate demand signal and determine zone-appropriate response.

    Args:
        db: Database session
        part_id_str: Part ID (e.g., "CH-231")
        demand_qty: Quantity demanded
        days_until_needed: How many days until the demand must be fulfilled

    Returns:
        {
            "part_id": str,
            "demand_qty": int,
            "days_until_needed": int,
            "zone": int (1, 2, or 3),
            "zone_name": str,
            "active_agents": [str],
            "recommended_action": str,
            "generate_po": bool,
            "expedite": bool,
            "use_secondary_supplier": bool,
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []

    part = db.query(Part).filter(Part.part_id == part_id_str).first()
    if not part:
        logs.append(_log(db, f"Part {part_id_str} not found.", "error"))
        return {
            "part_id": part_id_str, "demand_qty": demand_qty,
            "days_until_needed": days_until_needed, "zone": 0,
            "zone_name": "UNKNOWN", "active_agents": [],
            "recommended_action": "Part not found",
            "generate_po": False, "expedite": False,
            "use_secondary_supplier": False, "logs": logs,
        }

    supplier_lead_time = part.supplier.lead_time_days if part.supplier else 7
    zone = classify_demand_zone(days_until_needed, supplier_lead_time)

    # --- Zone 1: Fuzzy Forecast (6-12+ months) ---
    if zone == 1:
        zone_name = "FUZZY_FORECAST"
        active_agents = ["Scout"]
        recommended_action = (
            f"Advisory only — demand for {demand_qty}x {part_id_str} is {days_until_needed} days out. "
            f"Monitor forecast trends. Consider blanket agreement or capacity reservation. "
            f"NO Purchase Order generated. Cash preserved."
        )
        generate_po = False
        expedite = False
        use_secondary = False

        logs.append(_log(
            db,
            f"ZONE 1 (Fuzzy Forecast): {part_id_str} demand of {demand_qty} units "
            f"is {days_until_needed} days away (> {ZONE_1_MIN_DAYS}d threshold). "
            f"Scout monitoring only — no PO action.",
            "info",
        ))

    # --- Zone 2: Lead Time Horizon (2-5 months) ---
    elif zone == 2:
        zone_name = "LEAD_TIME_HORIZON"
        active_agents = ["Solver", "Buyer"]
        recommended_action = (
            f"Standard procurement — demand for {demand_qty}x {part_id_str} "
            f"falls within lead time horizon ({days_until_needed} days). "
            f"Solver to explode BOM and calculate net requirements. "
            f"Buyer to draft standard PO to primary supplier."
        )
        generate_po = True
        expedite = False
        use_secondary = False

        logs.append(_log(
            db,
            f"ZONE 2 (Lead Time Horizon): {part_id_str} demand of {demand_qty} units "
            f"in {days_until_needed} days ({ZONE_2_MIN_DAYS}-{ZONE_1_MIN_DAYS}d range). "
            f"Solver + Buyer activated. Standard PO to primary supplier.",
            "info",
        ))

    # --- Zone 3: Inside Lead Time / Drop-In Crisis ---
    else:
        zone_name = "DROP_IN_CRISIS"
        active_agents = ["Pulse", "Solver", "Buyer"]
        is_inside_lead_time = days_until_needed < supplier_lead_time

        if is_inside_lead_time:
            # True drop-in crisis: demand inside supplier lead time
            recommended_action = (
                f"CRISIS: Demand for {demand_qty}x {part_id_str} needed in {days_until_needed} days "
                f"but supplier lead time is {supplier_lead_time} days. "
                f"Pulse defending ring-fenced inventory. "
                f"Buyer pivoting to fastest secondary supplier with expedited PO."
            )
            use_secondary = True
            logs.append(_log(
                db,
                f"ZONE 3 (DROP-IN CRISIS): {part_id_str} demand of {demand_qty} units "
                f"in {days_until_needed} days — INSIDE supplier lead time of {supplier_lead_time} days! "
                f"Pulse + Solver activated. Switching to secondary supplier.",
                "error",
            ))
        else:
            # Near-term but not inside lead time
            recommended_action = (
                f"Urgent procurement — demand for {demand_qty}x {part_id_str} in {days_until_needed} days. "
                f"Solver to run expedited MRP. Buyer to draft PO to primary supplier."
            )
            use_secondary = False
            logs.append(_log(
                db,
                f"ZONE 3 (Near-Term): {part_id_str} demand of {demand_qty} units "
                f"in {days_until_needed} days (< {ZONE_2_MIN_DAYS}d). "
                f"Expedited procurement path activated.",
                "warning",
            ))

        generate_po = True
        expedite = True

    # Find secondary supplier if needed
    secondary_supplier = None
    if use_secondary and part.supplier:
        secondary = (
            db.query(Supplier)
            .filter(
                Supplier.id != part.supplier_id,
                Supplier.is_active.is_(True),
            )
            .order_by(Supplier.lead_time_days.asc())  # Fastest first for crisis
            .first()
        )
        if secondary:
            secondary_supplier = {
                "name": secondary.name,
                "lead_time_days": secondary.lead_time_days,
                "reliability_score": secondary.reliability_score,
            }
            logs.append(_log(
                db,
                f"Secondary supplier identified for {part_id_str}: {secondary.name} "
                f"(lead time: {secondary.lead_time_days}d, reliability: {secondary.reliability_score}).",
                "info",
            ))

    return {
        "part_id": part_id_str,
        "demand_qty": demand_qty,
        "days_until_needed": days_until_needed,
        "zone": zone,
        "zone_name": zone_name,
        "active_agents": active_agents,
        "recommended_action": recommended_action,
        "generate_po": generate_po,
        "expedite": expedite,
        "use_secondary_supplier": use_secondary,
        "secondary_supplier": secondary_supplier,
        "logs": logs,
    }
