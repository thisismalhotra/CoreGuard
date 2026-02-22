"""
Purchase Order REST endpoints.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import PurchaseOrder, Part, Supplier, OrderStatus, AgentLog
from schemas import PurchaseOrderResponse, CreatePurchaseOrderRequest, UpdateOrderStatusRequest

router = APIRouter(prefix="/api", tags=["orders"])

# Rule C: Financial Constitution — hard-coded, LLM cannot override
FINANCIAL_CONSTITUTION_MAX_SPEND = 5000.00


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


@router.post("/orders", response_model=PurchaseOrderResponse)
def create_order(
    body: CreatePurchaseOrderRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Manually create a purchase order.

    Validates part and supplier exist, applies the Financial Constitution
    ($5,000 auto-approval limit), and persists the PO.
    """
    part = db.query(Part).filter(Part.part_id == body.part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail=f"Part '{body.part_id}' not found")

    supplier = db.query(Supplier).filter(Supplier.name == body.supplier_name).first()
    if not supplier:
        raise HTTPException(status_code=404, detail=f"Supplier '{body.supplier_name}' not found")

    total_cost = round(body.quantity * body.unit_cost, 2)

    # Rule C: Financial Constitution check
    if total_cost > FINANCIAL_CONSTITUTION_MAX_SPEND:
        status = OrderStatus.PENDING_APPROVAL
    else:
        status = OrderStatus.APPROVED

    po_number = f"PO-{uuid.uuid4().hex[:8].upper()}"

    po = PurchaseOrder(
        po_number=po_number,
        part_id=part.id,
        supplier_id=supplier.id,
        quantity=body.quantity,
        unit_cost=body.unit_cost,
        total_cost=total_cost,
        status=status,
        triggered_by="Manual",
    )
    db.add(po)
    db.commit()

    return {
        "po_number": po_number,
        "part_id": body.part_id,
        "supplier": body.supplier_name,
        "quantity": body.quantity,
        "unit_cost": body.unit_cost,
        "total_cost": total_cost,
        "status": status.value,
        "created_at": po.created_at.isoformat(),
        "triggered_by": "Manual",
    }


@router.patch("/orders/{po_number}", response_model=PurchaseOrderResponse)
async def update_order_status(
    po_number: str,
    body: UpdateOrderStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Approve or reject a purchase order that is pending human approval.

    Only allows transitions FROM PENDING_APPROVAL to APPROVED or CANCELLED.
    This is the human-in-the-loop step for the Financial Constitution (Rule C).

    Glass Box: Emits a structured log via Socket.io so the dashboard
    shows the approval/rejection in real-time.
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_number).first()
    if not po:
        raise HTTPException(status_code=404, detail=f"Purchase order '{po_number}' not found")

    if po.status != OrderStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update PO '{po_number}': current status is '{po.status.value}', "
                   f"only PENDING_APPROVAL orders can be approved or rejected.",
        )

    new_status = OrderStatus(body.status)
    po.status = new_status

    # --- Glass Box: Persist log to DB ---
    action_word = "APPROVED" if new_status == OrderStatus.APPROVED else "REJECTED"
    log_type = "success" if new_status == OrderStatus.APPROVED else "warning"
    log_msg = (
        f"PO {po_number} {action_word} by human operator — "
        f"{po.quantity}x {po.part.part_id} from {po.supplier.name} "
        f"(${po.total_cost:,.2f})"
    )
    log_entry = AgentLog(
        agent="Ghost-Writer",
        message=log_msg,
        log_type=log_type,
    )
    db.add(log_entry)
    db.commit()

    # --- Glass Box: Emit log via Socket.io for real-time dashboard ---
    sio = getattr(request.app.state, "sio", None)
    if sio is not None:
        log_payload = {
            "timestamp": log_entry.timestamp.isoformat() if log_entry.timestamp else datetime.now(timezone.utc).isoformat(),
            "agent": "Ghost-Writer",
            "message": log_msg,
            "type": log_type,
        }
        await sio.emit("agent_log", log_payload)

    return {
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
