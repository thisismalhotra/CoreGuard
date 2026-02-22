"""
Inventory & Supplier REST endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Inventory, Part, Supplier
from schemas import InventoryItemResponse, SupplierResponse

router = APIRouter(prefix="/api", tags=["inventory"])


@router.get("/inventory", response_model=list[InventoryItemResponse])
def get_inventory(db: Session = Depends(get_db)) -> list[dict]:
    """Return current inventory levels for all parts."""
    records = (
        db.query(Inventory, Part)
        .join(Part, Inventory.part_id == Part.id)
        .all()
    )
    return [
        {
            "part_id": part.part_id,
            "description": part.description,
            "category": part.category.value,
            "on_hand": inv.on_hand,
            "safety_stock": inv.safety_stock,
            "reserved": inv.reserved,
            "available": inv.available,
            "supplier": part.supplier.name if part.supplier else None,
        }
        for inv, part in records
    ]


@router.get("/suppliers", response_model=list[SupplierResponse])
def get_suppliers(db: Session = Depends(get_db)) -> list[dict]:
    """Return all suppliers with their status."""
    suppliers = db.query(Supplier).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "lead_time_days": s.lead_time_days,
            "reliability_score": s.reliability_score,
            "is_active": bool(s.is_active),
        }
        for s in suppliers
    ]
