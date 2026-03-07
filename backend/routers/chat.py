"""
AI Chat endpoint — natural language Q&A over supply chain data.

Uses Anthropic Claude to answer questions with real DB context.
Gracefully degrades to 503 if ANTHROPIC_API_KEY is not set.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user
from database.connection import get_db
from database.models import (
    AgentLog,
    DemandForecast,
    Inventory,
    OrderStatus,
    PurchaseOrder,
    QualityInspection,
    Supplier,
    User,
)
from rate_limit import limiter

router = APIRouter(prefix="/api", tags=["chat"])

CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-3-5-haiku-20241022")

SYSTEM_PROMPT = """You are Core-Guard AI, the intelligent assistant for an autonomous supply chain operating system managing the FL-001 Flashlight product line.

You have access to real-time supply chain data provided below. Answer questions accurately based on this data. Be concise and actionable. Use specific numbers from the data when relevant.

Key concepts:
- Safety Stock: minimum inventory level to prevent stockouts
- Available = On Hand - Reserved - Ring Fenced
- Daily Burn Rate: average daily consumption
- Runway: days of supply remaining (Available / Daily Burn Rate)
- Financial Constitution: POs over $5,000 require human approval (PENDING_APPROVAL status)
- Glass Box: all agent decisions are logged and visible in real-time

When you don't have enough data to answer, say so. Never fabricate numbers."""


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    response: str
    model: str


def _build_context(db: Session) -> str:
    """Build a snapshot of current DB state for the LLM context."""
    sections = []

    # Inventory summary
    inventory_rows = (
        db.query(Inventory)
        .options(joinedload(Inventory.part))
        .all()
    )
    if inventory_rows:
        inv_lines = ["## Current Inventory"]
        for inv in inventory_rows:
            part_id = inv.part.part_id if inv.part else f"id:{inv.part_id}"
            runway = round(inv.available / inv.daily_burn_rate, 1) if inv.daily_burn_rate > 0 else "N/A"
            inv_lines.append(
                f"- {part_id}: on_hand={inv.on_hand}, safety_stock={inv.safety_stock}, "
                f"reserved={inv.reserved}, ring_fenced={inv.ring_fenced}, "
                f"available={inv.available}, burn_rate={inv.daily_burn_rate}/day, "
                f"runway={runway} days"
            )
        sections.append("\n".join(inv_lines))

    # Purchase orders (recent 20)
    orders = (
        db.query(PurchaseOrder)
        .options(joinedload(PurchaseOrder.part), joinedload(PurchaseOrder.supplier))
        .order_by(PurchaseOrder.created_at.desc())
        .limit(20)
        .all()
    )
    if orders:
        po_lines = ["## Recent Purchase Orders (last 20)"]
        for po in orders:
            part_id = po.part.part_id if po.part else "?"
            supplier = po.supplier.name if po.supplier else "?"
            po_lines.append(
                f"- {po.po_number}: {po.quantity}x {part_id} from {supplier}, "
                f"${po.total_cost:,.2f}, status={po.status.value}, triggered_by={po.triggered_by}"
            )
        sections.append("\n".join(po_lines))

    # Suppliers
    suppliers = db.query(Supplier).all()
    if suppliers:
        sup_lines = ["## Suppliers"]
        for s in suppliers:
            sup_lines.append(
                f"- {s.name}: tier={s.tier.value if hasattr(s.tier, 'value') else s.tier}, "
                f"region={s.region.value if hasattr(s.region, 'value') else s.region}, "
                f"lead_time={s.lead_time_days}d, reliability={s.reliability_pct}%"
            )
        sections.append("\n".join(sup_lines))

    # Demand forecasts
    forecasts = (
        db.query(DemandForecast)
        .options(joinedload(DemandForecast.part))
        .all()
    )
    if forecasts:
        fc_lines = ["## Demand Forecasts"]
        for f in forecasts:
            part_id = f.part.part_id if f.part else f"id:{f.part_id}"
            fc_lines.append(
                f"- {part_id}: forecast={f.forecast_qty}, actual={f.actual_qty}, "
                f"period={f.period}, source={f.source}"
            )
        sections.append("\n".join(fc_lines))

    # Quality inspections (recent 10)
    inspections = (
        db.query(QualityInspection)
        .order_by(QualityInspection.inspected_at.desc())
        .limit(10)
        .all()
    )
    if inspections:
        qi_lines = ["## Recent Quality Inspections"]
        for qi in inspections:
            qi_lines.append(
                f"- Part={qi.part or '?'}, batch={qi.batch_size}, result={qi.result}, notes={qi.notes or 'none'}"
            )
        sections.append("\n".join(qi_lines))

    # KPI summary
    total_on_hand = sum(i.on_hand for i in inventory_rows) if inventory_rows else 0
    total_safety = sum(i.safety_stock for i in inventory_rows) if inventory_rows else 0
    health_pct = round((total_on_hand / total_safety * 100), 1) if total_safety > 0 else 0
    pending_count = db.query(PurchaseOrder).filter(PurchaseOrder.status == OrderStatus.PENDING_APPROVAL).count()
    total_orders = db.query(PurchaseOrder).count()

    sections.append(
        f"## KPIs\n"
        f"- Inventory Health: {health_pct}%\n"
        f"- Total On Hand: {total_on_hand}\n"
        f"- Total Safety Stock: {total_safety}\n"
        f"- Pending Approvals: {pending_count}\n"
        f"- Total Purchase Orders: {total_orders}"
    )

    # Recent agent logs (last 10)
    recent_logs = (
        db.query(AgentLog)
        .order_by(AgentLog.timestamp.desc())
        .limit(10)
        .all()
    )
    if recent_logs:
        log_lines = ["## Recent Agent Activity (last 10 logs)"]
        for log in recent_logs:
            ts = log.timestamp.strftime("%H:%M:%S") if log.timestamp else "?"
            log_lines.append(f"- [{ts}] {log.agent}: {log.message}")
        sections.append("\n".join(log_lines))

    return "\n\n".join(sections)


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    AI Chat — answer natural language questions about supply chain data.

    Builds a real-time DB context snapshot and sends it to Anthropic Claude.
    Returns 503 if ANTHROPIC_API_KEY is not configured.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI Chat is not configured. Set the ANTHROPIC_API_KEY environment variable.",
        )

    # Lazy import to avoid startup failure if package not installed
    try:
        import anthropic
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Anthropic SDK not installed. Run: pip install anthropic",
        )

    context = _build_context(db)

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=CHAT_MODEL,
            max_tokens=1024,
            system=f"{SYSTEM_PROMPT}\n\n# Current Supply Chain Data\n{context}",
            messages=[{"role": "user", "content": body.message}],
        )
        reply = response.content[0].text
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {str(e)}")

    return {"response": reply, "model": CHAT_MODEL}
