"""
Buyer Agent — Procurement & Purchase Order Generation.

Receives BUY_ORDER actions from Solver, validates against the Financial
Constitution ($5,000 spend limit), generates a PDF PO, and logs everything
for Glass Box visibility.

Rule C enforced here: total_cost > 5000 -> PENDING_APPROVAL. The LLM cannot override this.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from agents.utils import create_agent_log
from database.models import (
    OrderStatus,
    Part,
    PurchaseOrder,
)

AGENT_NAME = "Buyer"
FINANCIAL_CONSTITUTION_MAX_SPEND = 5000.00  # Rule C — hard-coded, LLM cannot override


def _log(db: Session, message: str, log_type: str = "info") -> dict[str, str]:
    """Persist a Glass Box log entry and return it for Socket.io emission."""
    return create_agent_log(db, AGENT_NAME, message, log_type)


def process_buy_orders(
    db: Session,
    buy_orders: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Process a list of BUY_ORDER actions from Solver.

    For each order:
      1. Validate cost against the Constitution.
      2. Create a PurchaseOrder record.
      3. Generate a PDF PO document.
      4. Emit Glass Box logs.

    Returns:
        {
            "purchase_orders": [PO dicts],
            "logs": [Glass Box log dicts],
        }
    """
    logs: list[dict[str, str]] = []
    created_pos: list[dict[str, Any]] = []

    logs.append(_log(db, f"Received {len(buy_orders)} BUY_ORDER(s) from Solver."))

    for order in buy_orders:
        if order.get("type") != "BUY_ORDER":
            continue

        part_id_str = order["part_id"]
        quantity = order["quantity"]
        unit_cost = order["unit_cost"]
        total_cost = order["total_cost"]
        supplier_id = order.get("supplier_id")
        supplier_name = order.get("supplier_name", "Unknown")

        logs.append(_log(
            db,
            f"Processing order: {quantity}x {part_id_str} from {supplier_name} @ ${total_cost:.2f}.",
        ))

        # --- Rule C: Financial Constitution check ---
        if total_cost > FINANCIAL_CONSTITUTION_MAX_SPEND:
            status = OrderStatus.PENDING_APPROVAL
            logs.append(_log(
                db,
                f"CONSTITUTION BLOCK: ${total_cost:.2f} exceeds ${FINANCIAL_CONSTITUTION_MAX_SPEND:.2f} limit. "
                f"Status set to PENDING_APPROVAL. Human approval required.",
                "warning",
            ))
        else:
            status = OrderStatus.APPROVED
            logs.append(_log(
                db,
                f"Cost ${total_cost:.2f} within Constitution limit. Auto-approved.",
                "success",
            ))

        # --- Create PO record ---
        po_number = f"PO-{uuid.uuid4().hex[:8].upper()}"

        part = db.query(Part).filter(Part.part_id == part_id_str).first()
        if not part:
            logs.append(_log(db, f"Part {part_id_str} not found. Skipping.", "error"))
            continue

        # Resolve supplier_id: fall back to the part's default supplier if missing
        if supplier_id is None:
            supplier_id = part.supplier_id
        if supplier_id is None:
            logs.append(_log(
                db,
                f"No supplier found for {part_id_str}. Skipping PO generation.",
                "error",
            ))
            continue

        po = PurchaseOrder(
            po_number=po_number,
            part_id=part.id,
            supplier_id=supplier_id,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            status=status,
            triggered_by=order.get("triggered_by", "Solver"),
        )
        db.add(po)
        db.flush()

        po_dict = {
            "po_number": po_number,
            "part_id": part_id_str,
            "supplier": supplier_name,
            "quantity": quantity,
            "unit_cost": unit_cost,
            "total_cost": total_cost,
            "status": status.value,
        }
        created_pos.append(po_dict)

        # --- Generate PDF (validate it can be created, but don't persist to disk) ---
        try:
            generate_po_pdf_bytes(po_dict)
            logs.append(_log(db, f"PDF available for download: {po_number}", "success"))
        except Exception:
            logs.append(_log(db, "PDF generation not available (fpdf2 not installed).", "warning"))

        logs.append(_log(
            db,
            f"PO {po_number} created: {quantity}x {part_id_str} | "
            f"${total_cost:.2f} | Status: {status.value}.",
            "success" if status == OrderStatus.APPROVED else "warning",
        ))

    # NOTE: No db.commit() here — the calling simulation endpoint owns the transaction.
    # Agents only flush() to get IDs; the single commit happens in the router.

    return {
        "purchase_orders": created_pos,
        "logs": logs,
    }


def generate_po_pdf_bytes(po: dict[str, Any]) -> bytes:
    """Generate a PDF Purchase Order and return the raw bytes."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.compress = False  # Keep text readable in raw bytes for content validation
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 15, "PURCHASE ORDER", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"PO Number: {po['po_number']}", ln=True)
    pdf.cell(0, 8, f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
    pdf.cell(0, 8, f"Status: {po['status']}", ln=True)
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Supplier: {po['supplier']}", ln=True)
    pdf.ln(3)

    # Line items table
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(50, 8, "Part ID", border=1)
    pdf.cell(40, 8, "Quantity", border=1, align="C")
    pdf.cell(40, 8, "Unit Cost", border=1, align="R")
    pdf.cell(50, 8, "Total", border=1, align="R")
    pdf.ln()

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(50, 8, po["part_id"], border=1)
    pdf.cell(40, 8, str(po["quantity"]), border=1, align="C")
    pdf.cell(40, 8, f"${po['unit_cost']:.2f}", border=1, align="R")
    pdf.cell(50, 8, f"${po['total_cost']:.2f}", border=1, align="R")
    pdf.ln(15)

    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 8, "Generated by Buyer Agent | Core-Guard MVP", ln=True, align="C")

    return bytes(pdf.output())
