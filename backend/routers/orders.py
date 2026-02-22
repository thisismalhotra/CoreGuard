"""
Purchase Order REST endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import PurchaseOrder
from schemas import PurchaseOrderResponse

router = APIRouter(prefix="/api", tags=["orders"])


@router.get("/orders", response_model=list[PurchaseOrderResponse])
def get_orders(db: Session = Depends(get_db)) -> list[dict]:
    """Return all purchase orders."""
    orders = db.query(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).all()
    return [
        {
            "po_number": po.po_number,
            "part_id": po.part.part_id,
            "supplier": po.supplier.name,
            "quantity": po.quantity,
            "unit_cost": po.unit_cost,
            "total_cost": po.total_cost,
            "status": po.status.value,
            "created_at": po.created_at.isoformat(),
            "triggered_by": po.triggered_by,
        }
        for po in orders
    ]
