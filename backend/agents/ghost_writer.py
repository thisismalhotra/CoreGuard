"""
Ghost-Writer Agent — Procurement & Purchase Order Generation.

Receives BUY_ORDER actions from Core-Guard, validates against the Financial
Constitution ($5,000 spend limit), generates a PDF PO, and logs everything
for Glass Box visibility.

Rule C enforced here: total_cost > 5000 → PENDING_APPROVAL. The LLM cannot override this.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from pathlib import Path
from sqlalchemy.orm import Session

from database.models import (
    PurchaseOrder, Part, Supplier, AgentLog, OrderStatus,
)

AGENT_NAME = "Ghost-Writer"
FINANCIAL_CONSTITUTION_MAX_SPEND = 5000.00  # Rule C — hard-coded, LLM cannot override
PO_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "generated_pos"


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


def process_buy_orders(
    db: Session,
    buy_orders: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Process a list of BUY_ORDER actions from Core-Guard.

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

    logs.append(_log(db, f"Received {len(buy_orders)} BUY_ORDER(s) from Core-Guard."))

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

        po = PurchaseOrder(
            po_number=po_number,
            part_id=part.id,
            supplier_id=supplier_id,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            status=status,
            triggered_by=order.get("triggered_by", "Core-Guard"),
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

        # --- Generate PDF ---
        pdf_path = _generate_po_pdf(po_dict)
        if pdf_path:
            logs.append(_log(db, f"PDF generated: {pdf_path}", "success"))
        else:
            logs.append(_log(db, f"PDF generation skipped (fpdf2 not installed).", "warning"))

        logs.append(_log(
            db,
            f"PO {po_number} created: {quantity}x {part_id_str} | "
            f"${total_cost:.2f} | Status: {status.value}.",
            "success" if status == OrderStatus.APPROVED else "warning",
        ))

    db.commit()

    return {
        "purchase_orders": created_pos,
        "logs": logs,
    }


def _generate_po_pdf(po: dict[str, Any]) -> str | None:
    """Generate a simple PDF Purchase Order. Returns the file path or None if fpdf2 is missing."""
    try:
        from fpdf import FPDF
    except ImportError:
        return None

    PO_OUTPUT_DIR.mkdir(exist_ok=True)

    pdf = FPDF()
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
    pdf.cell(0, 8, "Generated by Ghost-Writer Agent | Core-Guard MVP", ln=True, align="C")

    filename = f"{po['po_number']}.pdf"
    filepath = PO_OUTPUT_DIR / filename
    pdf.output(str(filepath))

    return str(filepath)
