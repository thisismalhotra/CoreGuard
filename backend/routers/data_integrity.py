"""Data-integrity warnings endpoint -- surfaces ghost/suspect inventory."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from auth import get_current_user
from database.connection import get_db
from database.models import Inventory, Part, User
from rate_limit import limiter

router = APIRouter(prefix="/api", tags=["data-integrity"])


@router.get("/data-integrity/warnings")
@limiter.limit("60/minute")
def get_data_integrity_warnings(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict]:
    """Return inventory items that have integrity concerns."""
    warnings: list[dict] = []
    rows = (
        db.query(Inventory, Part)
        .join(Part, Inventory.part_id == Part.id)
        .all()
    )

    for item, part in rows:
        part_desc = part.description if part else f"Part #{item.part_id}"

        # Ghost inventory: on_hand > 0 but daily_burn_rate is 0 and no recent demand
        if item.on_hand > 0 and (item.daily_burn_rate or 0) == 0 and (item.reserved or 0) == 0:
            warnings.append({
                "part_id": part.part_id,
                "description": part_desc,
                "severity": "warning",
                "issue": "Ghost inventory",
                "detail": f"{item.on_hand} units on hand with zero burn rate and no reservations. May be stale.",
                "action": "Verify physical count and demand forecast.",
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
