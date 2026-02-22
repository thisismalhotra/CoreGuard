"""
Agent metadata & DB viewer REST endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import (
    Supplier, Part, Inventory, BOMEntry, PurchaseOrder,
    DemandForecast, QualityInspection, AgentLog,
)
from schemas import (
    AgentMetadata, DBSupplierRow, DBPartRow, DBInventoryRow,
    DBBomRow, DBOrderRow, DBDemandForecastRow, DBQualityInspectionRow,
    DBAgentLogRow,
)

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/agents", response_model=list[AgentMetadata])
def get_agents() -> list[dict]:
    """Return metadata for all agents in the system."""
    return [
        {
            "name": "Aura",
            "role": "Demand Sensing Agent",
            "description": "Monitors real-time sales data and demand signals. Detects when actual demand deviates from forecast thresholds, triggering the agent chain.",
            "trigger": "Incoming demand data exceeds forecast by 20%+ (SPIKE_THRESHOLD = 1.2x)",
            "inputs": ["SKU identifier", "New actual demand quantity", "Demand forecast table"],
            "outputs": ["DEMAND_SPIKE event", "Spike multiplier", "Glass Box logs"],
            "downstream": "Dispatcher",
            "constitution": None,
            "rules": [
                "Stateless \u2014 reads DB state, never caches",
                "Pure Python math for spike detection (Rule B)",
                "Fires DEMAND_SPIKE when actual > forecast \u00d7 1.2",
                "Updates actual_qty in DemandForecast table",
            ],
            "color": "purple",
            "icon": "Radio",
            "source_file": "agents/aura.py",
        },
        {
            "name": "Dispatcher",
            "role": "Triage & Prioritisation Agent",
            "description": "Sits between Aura and Core-Guard. Analyses BOM components, scores each by criticality, lead-time sensitivity, and shortage severity, then hands Core-Guard a prioritised processing queue.",
            "trigger": "DEMAND_SPIKE event from Aura",
            "inputs": ["SKU identifier", "Demand quantity", "BOM table", "Part profiles (criticality, lead_time_sensitivity)"],
            "outputs": ["Prioritised component queue", "Risk assessment", "Glass Box logs"],
            "downstream": "Core-Guard",
            "constitution": None,
            "rules": [
                "Stateless \u2014 reads DB state, never caches",
                "Priority score = criticality_weight + (lead_time_sensitivity \u00d7 30) + (gap_severity \u00d7 20)",
                "CRITICAL parts: weight 100, HIGH: 75, MEDIUM: 50, LOW: 25",
                "Components sorted by priority score descending \u2014 highest first",
                "Flags CRITICAL components for expedited processing",
                "Provides risk assessment: total components, at-risk count, critical count",
            ],
            "color": "cyan",
            "icon": "GitBranch",
            "source_file": "agents/dispatcher.py",
        },
        {
            "name": "Core-Guard",
            "role": "MRP Logic Agent",
            "description": "The brain of the supply chain. Performs BOM explosion, calculates net material requirements using deterministic math, and applies criticality-based routing rules to decide procurement strategy.",
            "trigger": "Prioritised queue from Dispatcher, or direct invocation from simulation endpoints",
            "inputs": ["SKU identifier", "Demand quantity", "BOM table", "Inventory table", "Part criticality profiles"],
            "outputs": ["Shortage analysis", "REALLOCATE actions", "BUY_ORDER actions (with expedite flags)", "Glass Box logs"],
            "downstream": "Ghost-Writer",
            "constitution": None,
            "rules": [
                "Stateless \u2014 operates on DB state passed in",
                "All arithmetic done in Python (Rule B: never ask LLM to calculate)",
                "Net Requirement = (Demand \u00d7 BOM qty_per) - Available Inventory",
                "CRITICAL parts: 1.5x buffer, reallocation BLOCKED, EXPEDITED procurement",
                "HIGH parts: 1.25x buffer, reallocation allowed (with safeguards), EXPEDITED",
                "MEDIUM parts: exact gap, standard reallocation, normal procurement",
                "LOW parts: exact gap, free reallocation, no rush",
            ],
            "color": "blue",
            "icon": "Shield",
            "source_file": "agents/core_guard.py",
        },
        {
            "name": "Ghost-Writer",
            "role": "Procurement & PO Generation Agent",
            "description": "Receives BUY_ORDER actions from Core-Guard, validates spend against the Financial Constitution, creates Purchase Order records, and generates PDF documents.",
            "trigger": "BUY_ORDER actions from Core-Guard or Eagle-Eye",
            "inputs": ["List of BUY_ORDER actions", "Parts table", "Suppliers table"],
            "outputs": ["PurchaseOrder records", "PDF documents", "Glass Box logs"],
            "downstream": None,
            "constitution": "FINANCIAL GUARDRAIL (Rule C): If total_cost > $5,000, the PO status MUST be set to PENDING_APPROVAL. This is hard-coded and CANNOT be overridden by any LLM or agent. Human approval is required before funds can be committed.",
            "rules": [
                "Hard-coded spend limit: FINANCIAL_CONSTITUTION_MAX_SPEND = $5,000.00",
                "total_cost > $5,000 \u2192 OrderStatus.PENDING_APPROVAL (no exceptions)",
                "total_cost \u2264 $5,000 \u2192 OrderStatus.APPROVED (auto-approved)",
                "Generates PDF PO via fpdf2 to backend/generated_pos/",
                "Each PO gets a unique PO number (PO-XXXXXXXX)",
                "The LLM cannot override the financial constitution",
            ],
            "color": "emerald",
            "icon": "FileText",
            "source_file": "agents/ghost_writer.py",
        },
        {
            "name": "Eagle-Eye",
            "role": "Quality Inspection Agent",
            "description": "Simulates receiving physical shipments at the Digital Dock. Runs automated sensor scans against CAD spec tolerances. Passes or fails batches and triggers emergency remediation on failure.",
            "trigger": "Shipment arrival at Digital Dock (simulated via /simulate/quality-fail)",
            "inputs": ["Part ID", "Batch size", "CAD spec tolerances"],
            "outputs": ["PASS/FAIL inspection result", "Sensor readings", "BUY_ORDER actions (on fail)", "Glass Box logs"],
            "downstream": "Ghost-Writer (on failure)",
            "constitution": None,
            "rules": [
                "Stateless \u2014 operates on DB state passed in",
                "Compares sensor readings against hard-coded CAD_SPECS tolerances",
                "CH-101: hardness (8.0\u201310.0), dimension tolerance (\u00b10.05mm)",
                "SW-303: resistance (4.5\u20135.5\u03a9), cycle life (min 10,000)",
                "LNS-505: clarity (min 95%), focal length tolerance (\u00b10.1mm)",
                "FAIL \u2192 quarantine batch (stock NOT added), trigger emergency reorder",
                "PASS \u2192 add batch to inventory on_hand",
                "AI Handover: in production, would use Pinecone vector DB for CAD comparisons",
            ],
            "color": "orange",
            "icon": "Eye",
            "source_file": "agents/eagle_eye.py",
        },
    ]


# --- DB Viewer ---

@router.get("/db/suppliers", response_model=list[DBSupplierRow])
def db_suppliers(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Raw suppliers table dump."""
    rows = db.query(Supplier).order_by(Supplier.id).offset(offset).limit(limit).all()
    return [
        {"id": s.id, "name": s.name, "contact_email": s.contact_email,
         "lead_time_days": s.lead_time_days, "reliability_score": s.reliability_score,
         "is_active": bool(s.is_active)}
        for s in rows
    ]


@router.get("/db/parts", response_model=list[DBPartRow])
def db_parts(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Raw parts table dump."""
    rows = db.query(Part).order_by(Part.id).offset(offset).limit(limit).all()
    return [
        {"id": p.id, "part_id": p.part_id, "description": p.description,
         "category": p.category.value, "unit_cost": p.unit_cost,
         "criticality": p.criticality.value, "lead_time_sensitivity": p.lead_time_sensitivity,
         "substitute_pool_size": p.substitute_pool_size,
         "supplier": p.supplier.name if p.supplier else None}
        for p in rows
    ]


@router.get("/db/inventory", response_model=list[DBInventoryRow])
def db_inventory(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Raw inventory table dump."""
    rows = db.query(Inventory).order_by(Inventory.id).offset(offset).limit(limit).all()
    return [
        {"id": inv.id, "part": inv.part.part_id if inv.part else None,
         "on_hand": inv.on_hand, "safety_stock": inv.safety_stock,
         "reserved": inv.reserved, "available": inv.available,
         "last_updated": inv.last_updated.isoformat() if inv.last_updated else None}
        for inv in rows
    ]


@router.get("/db/bom", response_model=list[DBBomRow])
def db_bom(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Raw BOM table dump."""
    rows = db.query(BOMEntry).order_by(BOMEntry.id).offset(offset).limit(limit).all()
    return [
        {"id": b.id,
         "parent": b.parent.part_id if b.parent else None,
         "component": b.component.part_id if b.component else None,
         "quantity_per": b.quantity_per}
        for b in rows
    ]


@router.get("/db/orders", response_model=list[DBOrderRow])
def db_orders(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Raw purchase_orders table dump."""
    rows = db.query(PurchaseOrder).order_by(PurchaseOrder.id).offset(offset).limit(limit).all()
    return [
        {"id": po.id, "po_number": po.po_number,
         "part": po.part.part_id if po.part else None,
         "supplier": po.supplier.name if po.supplier else None,
         "quantity": po.quantity, "unit_cost": po.unit_cost,
         "total_cost": po.total_cost, "status": po.status.value,
         "triggered_by": po.triggered_by,
         "created_at": po.created_at.isoformat() if po.created_at else None}
        for po in rows
    ]


@router.get("/db/demand_forecast", response_model=list[DBDemandForecastRow])
def db_demand_forecast(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Raw demand_forecast table dump."""
    rows = db.query(DemandForecast).order_by(DemandForecast.id).offset(offset).limit(limit).all()
    return [
        {"id": d.id, "part": d.part.part_id if d.part else None,
         "forecast_qty": d.forecast_qty, "actual_qty": d.actual_qty,
         "period": d.period,
         "updated_at": d.updated_at.isoformat() if d.updated_at else None}
        for d in rows
    ]


@router.get("/db/quality_inspections", response_model=list[DBQualityInspectionRow])
def db_quality_inspections(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Raw quality_inspections table dump."""
    rows = db.query(QualityInspection).order_by(QualityInspection.id).offset(offset).limit(limit).all()
    return [
        {"id": q.id, "part": q.part.part_id if q.part else None,
         "batch_size": q.batch_size, "result": q.result.value,
         "notes": q.notes,
         "inspected_at": q.inspected_at.isoformat() if q.inspected_at else None}
        for q in rows
    ]


@router.get("/db/agent_logs", response_model=list[DBAgentLogRow])
def db_agent_logs(
    db: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Raw agent_logs table dump."""
    rows = db.query(AgentLog).order_by(AgentLog.id.desc()).offset(offset).limit(limit).all()
    return [
        {"id": log.id, "agent": log.agent, "message": log.message,
         "log_type": log.log_type,
         "timestamp": log.timestamp.isoformat() if log.timestamp else None}
        for log in rows
    ]
