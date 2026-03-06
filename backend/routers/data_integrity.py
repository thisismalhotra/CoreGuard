"""Data-integrity warnings endpoint -- surfaces ghost/suspect inventory.

Uses the same detection logic as the Auditor agent (PRD §11):
- Ghost: burn_rate > 0 but no consumption recorded for 14+ days
- Dead stock: on_hand > 0, zero burn rate, zero reserved
- Below safety stock: available < safety_stock
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from auth import get_current_user
from database.connection import get_db
from database.models import Inventory, Part, User
from rate_limit import limiter

router = APIRouter(prefix="/api", tags=["data-integrity"])

GHOST_INVENTORY_DAYS = 14  # Matches agents/data_integrity.py threshold


@router.get("/data-integrity/warnings")
@limiter.limit("60/minute")
def get_data_integrity_warnings(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict]:
    """Return inventory items that have integrity concerns."""
    warnings: list[dict] = []
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Inventory, Part)
        .join(Part, Inventory.part_id == Part.id)
        .all()
    )

    for item, part in rows:
        part_desc = part.description if part else f"Part #{item.part_id}"

        # Ghost inventory (PRD §11): burn rate > 0 but no consumption for 14+ days.
        # Aligned with Auditor agent logic — the on-hand count may be inaccurate.
        if item.on_hand > 0 and (item.daily_burn_rate or 0) > 0:
            if item.last_consumption_date is None:
                days_since = GHOST_INVENTORY_DAYS + 1
            else:
                last_date = item.last_consumption_date
                if last_date.tzinfo is None:
                    last_date = last_date.replace(tzinfo=timezone.utc)
                days_since = (now - last_date).days

            if days_since >= GHOST_INVENTORY_DAYS:
                warnings.append({
                    "part_id": part.part_id,
                    "description": part_desc,
                    "severity": "warning",
                    "issue": "Ghost inventory",
                    "detail": (
                        f"{item.on_hand} units on hand, burn rate {item.daily_burn_rate}/day, "
                        f"but no consumption recorded for {days_since} days. Count may be inaccurate."
                    ),
                    "action": "Cycle count required — verify physical inventory.",
                })

        # Dead stock: on_hand > 0, zero burn rate, zero reserved — no demand at all
        if item.on_hand > 0 and (item.daily_burn_rate or 0) == 0 and (item.reserved or 0) == 0:
            warnings.append({
                "part_id": part.part_id,
                "description": part_desc,
                "severity": "info",
                "issue": "Dead stock",
                "detail": f"{item.on_hand} units on hand with zero burn rate and no reservations.",
                "action": "Review demand forecast or consider disposition.",
            })

        # Critical: below safety stock
        available = item.available  # @property: on_hand - reserved - ring_fenced_qty
        if available is not None and item.safety_stock is not None:
            if available < item.safety_stock:
                severity = "critical" if available < item.safety_stock * 0.5 else "warning"
                warnings.append({
                    "part_id": part.part_id,
                    "description": part_desc,
                    "severity": severity,
                    "issue": "Below safety stock",
                    "detail": f"Available: {available}, Safety Stock: {item.safety_stock}.",
                    "action": "Trigger replenishment or review safety stock level.",
                })

    return warnings
