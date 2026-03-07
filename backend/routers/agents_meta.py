"""
Agent metadata & DB viewer REST endpoints.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session, joinedload

from agents.utils import enum_val
from auth import get_current_user
from database.connection import get_db
from database.models import (
    AgentLog,
    AlternateSupplier,
    BOMEntry,
    DemandForecast,
    Inventory,
    InventoryHealthRecord,
    Part,
    PurchaseOrder,
    QualityInspection,
    RingFenceAuditLog,
    SalesOrder,
    ScheduledRelease,
    Supplier,
    SupplierContract,
    User,
)
from rate_limit import limiter
from schemas import (
    AgentMetadata,
    DBAgentLogRow,
    DBAlternateSupplierRow,
    DBBomRow,
    DBDemandForecastRow,
    DBInventoryHealthRow,
    DBInventoryRow,
    DBOrderRow,
    DBPartRow,
    DBQualityInspectionRow,
    DBRingFenceAuditRow,
    DBSalesOrderRow,
    DBScheduledReleaseRow,
    DBSupplierContractRow,
    DBSupplierRow,
)

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/agents", response_model=list[AgentMetadata])
@limiter.limit("60/minute")
def get_agents(request: Request, current_user: User = Depends(get_current_user)) -> list[dict]:
    """Return metadata for all agents in the system."""
    return [
        {
            "name": "Pulse",
            "role": "Digital Twin / SKU Sentinel",
            "description": "Each Pulse agent acts as a digital twin for a single SKU. Continuously monitors on-hand levels, calculates dynamic safety stock, computes real-time runway (days to stockout), and triggers a handshake to Solver when runway drops below the threshold.",
            "trigger": "Demand spike event or continuous monitoring cycle",
            "inputs": ["Part ID", "On-Hand inventory", "Daily burn rate (trailing 3-day velocity)", "Supplier lead time"],
            "outputs": ["Dynamic safety stock", "Runway (days to stockout)", "Crisis Signal (handshake to Solver)", "Glass Box logs"],
            "downstream": "Solver (via handshake)",
            "constitution": None,
            "rules": [
                "Dynamic Safety Stock = (Max Daily Usage × Max Lead Time) - (Avg Daily Usage × Avg Lead Time)",
                "Runway = On-Hand / Trailing 3-Day Velocity (NOT monthly forecast average — PRD §8)",
                "Handshake Trigger: if runway < (supplier_lead_time + safety_stock_days)",
                "Sends verified Crisis Signal (not raw data) to Solver",
                "Stateless — operates on DB state, never caches",
            ],
            "color": "yellow",
            "icon": "Cpu",
            "source_file": "agents/part_agent.py",
        },
        {
            "name": "Scout",
            "role": "Demand Sensing Agent",
            "description": "Monitors real-time sales data and demand signals. Detects when actual demand deviates from forecast thresholds, triggering the agent chain.",
            "trigger": "Incoming demand data exceeds forecast by 20%+ (SPIKE_THRESHOLD = 1.2x)",
            "inputs": ["SKU identifier", "New actual demand quantity", "Demand forecast table"],
            "outputs": ["DEMAND_SPIKE event", "Spike multiplier", "Glass Box logs"],
            "downstream": "Router",
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
            "name": "Router",
            "role": "Triage & Prioritisation Agent",
            "description": "Sits between Scout and Solver. Analyses BOM components, scores each by criticality, lead-time sensitivity, and shortage severity, then hands Solver a prioritised processing queue.",
            "trigger": "DEMAND_SPIKE event from Scout",
            "inputs": ["SKU identifier", "Demand quantity", "BOM table", "Part profiles (criticality, lead_time_sensitivity)"],
            "outputs": ["Prioritised component queue", "Risk assessment", "Glass Box logs"],
            "downstream": "Solver",
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
            "name": "Solver",
            "role": "MRP Logic Agent",
            "description": "The brain of the supply chain. Performs BOM explosion, calculates net material requirements using deterministic math, and applies criticality-based routing rules to decide procurement strategy.",
            "trigger": "Prioritised queue from Router, or direct invocation from simulation endpoints",
            "inputs": ["SKU identifier", "Demand quantity", "BOM table", "Inventory table", "Part criticality profiles"],
            "outputs": ["Shortage analysis", "REALLOCATE actions", "BUY_ORDER actions (with expedite flags)", "Glass Box logs"],
            "downstream": "Buyer",
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
            "name": "Buyer",
            "role": "Procurement & PO Generation Agent",
            "description": "Receives BUY_ORDER actions from Solver, validates spend against the Financial Constitution, creates Purchase Order records, and generates PDF documents.",
            "trigger": "BUY_ORDER actions from Solver or Inspector",
            "inputs": ["List of BUY_ORDER actions", "Parts table", "Suppliers table"],
            "outputs": ["PurchaseOrder records", "PDF documents", "Glass Box logs"],
            "downstream": None,
            "constitution": "FINANCIAL GUARDRAIL (Rule C): If total_cost > $5,000, the PO status MUST be set to PENDING_APPROVAL. This is hard-coded and CANNOT be overridden by any LLM or agent. Human approval is required before funds can be committed.",
            "rules": [
                "Hard-coded spend limit: FINANCIAL_CONSTITUTION_MAX_SPEND = $5,000.00",
                "total_cost > $5,000 \u2192 OrderStatus.PENDING_APPROVAL (no exceptions)",
                "total_cost \u2264 $5,000 \u2192 OrderStatus.APPROVED (auto-approved)",
                "Generates PDF PO via fpdf2 (on-demand, in-memory)",
                "Each PO gets a unique PO number (PO-XXXXXXXX)",
                "The LLM cannot override the financial constitution",
            ],
            "color": "emerald",
            "icon": "FileText",
            "source_file": "agents/ghost_writer.py",
        },
        {
            "name": "Inspector",
            "role": "Quality Inspection Agent",
            "description": "Simulates receiving physical shipments at the Digital Dock. Runs automated sensor scans against CAD spec tolerances. Passes or fails batches and triggers emergency remediation on failure.",
            "trigger": "Shipment arrival at Digital Dock (simulated via /simulate/quality-fail)",
            "inputs": ["Part ID", "Batch size", "CAD spec tolerances"],
            "outputs": ["PASS/FAIL inspection result", "Sensor readings", "BUY_ORDER actions (on fail)", "Glass Box logs"],
            "downstream": "Buyer (on failure)",
            "constitution": None,
            "rules": [
                "Stateless \u2014 operates on DB state passed in",
                "Compares sensor readings against hard-coded CAD_SPECS tolerances",
                "CH-231: hardness (8.0\u201310.0), dimension tolerance (\u00b10.05mm)",
                "SW-232: resistance (4.5\u20135.5\u03a9), cycle life (min 10,000)",
                "LNS-221: clarity (min 95%), focal length tolerance (\u00b10.1mm)",
                "FAIL \u2192 quarantine batch (stock NOT added), trigger emergency reorder",
                "PASS \u2192 add batch to inventory on_hand",
                "AI Handover: in production, would use Pinecone vector DB for CAD comparisons",
            ],
            "color": "orange",
            "icon": "Eye",
            "source_file": "agents/eagle_eye.py",
        },
        {
            "name": "Auditor",
            "role": "Inventory Health Monitor",
            "description": "Ensures inventory data is trustworthy by scanning for ghost inventory (scheduled consumption but no deductions) and suspect inventory (no movement for 6+ months). Generates cycle count and physical count tasks.",
            "trigger": "Scheduled scan or manual invocation",
            "inputs": ["Inventory table", "Last consumption dates", "Daily burn rates"],
            "outputs": ["Ghost inventory flags", "Suspect inventory flags", "Cycle count tasks", "Physical count tasks", "Glass Box logs"],
            "downstream": None,
            "constitution": None,
            "rules": [
                "Ghost Inventory: if burn_rate > 0 and no consumption for 14+ days → flag + cycle count",
                "Suspect Inventory: if on_hand > 0 and no movement for 180+ days → flag + physical count",
                "Flagged parts write InventoryHealthRecord entries (GHOST/SUSPECT)",
                "Ghost inventory should be blocked from MRP calculations",
            ],
            "color": "red",
            "icon": "ShieldAlert",
            "source_file": "agents/data_integrity.py",
        },
        {
            "name": "Lookout",
            "role": "Demand Zone Classifier",
            "description": "Classifies incoming demand signals into three horizon zones (PRD §10) and routes them to the appropriate agent behaviour. Determines whether to advise, procure, or expedite.",
            "trigger": "New demand signal / forecast update",
            "inputs": ["Part ID", "Demand quantity", "Days until needed", "Supplier lead time"],
            "outputs": ["Zone classification (1/2/3)", "Active agents list", "Recommended action", "Secondary supplier (Zone 3)", "Glass Box logs"],
            "downstream": "Scout (Z1) / Solver+Buyer (Z2) / Pulse+Solver (Z3)",
            "constitution": None,
            "rules": [
                "Zone 1 (6-12+ months): Scout advisory only, NO POs generated",
                "Zone 2 (2-5 months): Solver BOM explosion + Buyer standard POs",
                "Zone 3 (< lead time): Pulse defends, Buyer pivots to secondary supplier",
                "Zone 3 POs are always expedited with cost-vs-risk trade-off",
            ],
            "color": "amber",
            "icon": "Layers",
            "source_file": "agents/demand_horizon.py",
        },
    ]


# --- DB Viewer ---

@router.get("/db/suppliers", response_model=list[DBSupplierRow])
@limiter.limit("60/minute")
def db_suppliers(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw suppliers table dump."""
    rows = db.query(Supplier).order_by(Supplier.id).offset(offset).limit(limit).all()
    return [
        {"id": s.id, "name": s.name, "contact_email": s.contact_email,
         "lead_time_days": s.lead_time_days, "reliability_score": s.reliability_score,
         "is_active": bool(s.is_active),
         "tier": enum_val(s.tier) if s.tier else None,
         "region": enum_val(s.region) if s.region else None,
         "expedite_lead_time_days": s.expedite_lead_time_days,
         "minimum_order_qty": s.minimum_order_qty,
         "capacity_per_month": s.capacity_per_month,
         "payment_terms": s.payment_terms}
        for s in rows
    ]


@router.get("/db/parts", response_model=list[DBPartRow])
@limiter.limit("60/minute")
def db_parts(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw parts table dump."""
    rows = db.query(Part).options(joinedload(Part.supplier)).order_by(Part.id).offset(offset).limit(limit).all()
    return [
        {"id": p.id, "part_id": p.part_id, "description": p.description,
         "category": enum_val(p.category), "unit_cost": p.unit_cost,
         "criticality": enum_val(p.criticality), "lead_time_sensitivity": p.lead_time_sensitivity,
         "substitute_pool_size": p.substitute_pool_size,
         "supplier": p.supplier.name if p.supplier else None}
        for p in rows
    ]


@router.get("/db/inventory", response_model=list[DBInventoryRow])
@limiter.limit("60/minute")
def db_inventory(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw inventory table dump."""
    rows = db.query(Inventory).options(joinedload(Inventory.part)).order_by(Inventory.id).offset(offset).limit(limit).all()
    return [
        {"id": inv.id, "part": inv.part.part_id if inv.part else None,
         "on_hand": inv.on_hand, "safety_stock": inv.safety_stock,
         "reserved": inv.reserved, "ring_fenced_qty": inv.ring_fenced_qty,
         "daily_burn_rate": inv.daily_burn_rate, "available": inv.available,
         "last_updated": inv.last_updated.isoformat() if inv.last_updated else None,
         "last_consumption_date": inv.last_consumption_date.isoformat() if inv.last_consumption_date else None}
        for inv in rows
    ]


@router.get("/db/bom", response_model=list[DBBomRow])
@limiter.limit("60/minute")
def db_bom(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw BOM table dump."""
    rows = db.query(BOMEntry).options(joinedload(BOMEntry.parent), joinedload(BOMEntry.component)).order_by(BOMEntry.id).offset(offset).limit(limit).all()
    return [
        {"id": b.id,
         "parent": b.parent.part_id if b.parent else None,
         "component": b.component.part_id if b.component else None,
         "quantity_per": b.quantity_per}
        for b in rows
    ]


@router.get("/db/orders", response_model=list[DBOrderRow])
@limiter.limit("60/minute")
def db_orders(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw purchase_orders table dump."""
    rows = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.part), joinedload(PurchaseOrder.supplier)).order_by(PurchaseOrder.id).offset(offset).limit(limit).all()
    return [
        {"id": po.id, "po_number": po.po_number,
         "part": po.part.part_id if po.part else None,
         "supplier": po.supplier.name if po.supplier else None,
         "quantity": po.quantity, "unit_cost": po.unit_cost,
         "total_cost": po.total_cost, "status": enum_val(po.status),
         "triggered_by": po.triggered_by,
         "created_at": po.created_at.isoformat() if po.created_at else None}
        for po in rows
    ]


@router.get("/db/demand_forecast", response_model=list[DBDemandForecastRow])
@limiter.limit("60/minute")
def db_demand_forecast(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw demand_forecast table dump."""
    rows = db.query(DemandForecast).options(joinedload(DemandForecast.part)).order_by(DemandForecast.id).offset(offset).limit(limit).all()
    return [
        {"id": d.id, "part": d.part.part_id if d.part else None,
         "forecast_qty": d.forecast_qty, "actual_qty": d.actual_qty,
         "period": d.period,
         "updated_at": d.updated_at.isoformat() if d.updated_at else None,
         "forecast_accuracy_pct": d.forecast_accuracy_pct,
         "source": d.source, "confidence_level": d.confidence_level,
         "notes": d.notes}
        for d in rows
    ]


@router.get("/db/quality_inspections", response_model=list[DBQualityInspectionRow])
@limiter.limit("60/minute")
def db_quality_inspections(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw quality_inspections table dump."""
    rows = db.query(QualityInspection).options(joinedload(QualityInspection.part)).order_by(QualityInspection.id).offset(offset).limit(limit).all()
    return [
        {"id": q.id, "part": q.part.part_id if q.part else None,
         "batch_size": q.batch_size, "result": enum_val(q.result),
         "notes": q.notes,
         "inspected_at": q.inspected_at.isoformat() if q.inspected_at else None}
        for q in rows
    ]


@router.get("/db/agent_logs", response_model=list[DBAgentLogRow])
@limiter.limit("60/minute")
def db_agent_logs(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw agent_logs table dump."""
    rows = db.query(AgentLog).order_by(AgentLog.id.desc()).offset(offset).limit(limit).all()
    return [
        {"id": log.id, "agent": log.agent, "message": log.message,
         "log_type": log.log_type,
         "timestamp": log.timestamp.isoformat() if log.timestamp else None}
        for log in rows
    ]


@router.get("/db/sales_orders", response_model=list[DBSalesOrderRow])
@limiter.limit("60/minute")
def db_sales_orders(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw sales_orders table dump."""
    rows = db.query(SalesOrder).options(joinedload(SalesOrder.part)).order_by(SalesOrder.id).offset(offset).limit(limit).all()
    return [
        {"id": so.id, "order_number": so.order_number,
         "part": so.part.part_id if so.part else None,
         "quantity": so.quantity, "status": enum_val(so.status),
         "priority": so.priority,
         "created_at": so.created_at.isoformat() if so.created_at else None}
        for so in rows
    ]


@router.get("/db/ring_fence_audit", response_model=list[DBRingFenceAuditRow])
@limiter.limit("60/minute")
def db_ring_fence_audit(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw ring_fence_audit table dump."""
    rows = db.query(RingFenceAuditLog).order_by(RingFenceAuditLog.id.desc()).offset(offset).limit(limit).all()
    return [
        {"id": r.id, "part_id": r.part_id, "order_ref": r.order_ref,
         "attempted_by": r.attempted_by, "qty_requested": r.qty_requested,
         "qty_ring_fenced": r.qty_ring_fenced, "action": r.action,
         "message": r.message,
         "timestamp": r.timestamp.isoformat() if r.timestamp else None}
        for r in rows
    ]


@router.get("/db/inventory_health", response_model=list[DBInventoryHealthRow])
@limiter.limit("60/minute")
def db_inventory_health(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw inventory_health table dump."""
    rows = db.query(InventoryHealthRecord).order_by(InventoryHealthRecord.id.desc()).offset(offset).limit(limit).all()
    return [
        {"id": h.id, "part_id": h.part_id, "flag": enum_val(h.flag),
         "resolved": bool(h.resolved), "notes": h.notes,
         "detected_at": h.detected_at.isoformat() if h.detected_at else None}
        for h in rows
    ]


@router.get("/db/supplier_contracts", response_model=list[DBSupplierContractRow])
@limiter.limit("60/minute")
def db_supplier_contracts(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw supplier_contracts table dump."""
    rows = db.query(SupplierContract).options(joinedload(SupplierContract.supplier)).order_by(SupplierContract.id).offset(offset).limit(limit).all()
    return [
        {"id": c.id, "contract_number": c.contract_number,
         "supplier": c.supplier.name if c.supplier else None,
         "contract_type": enum_val(c.contract_type),
         "start_date": c.start_date.isoformat() if c.start_date else None,
         "end_date": c.end_date.isoformat() if c.end_date else None,
         "total_committed_value": c.total_committed_value,
         "total_committed_qty": c.total_committed_qty,
         "released_value": c.released_value, "released_qty": c.released_qty,
         "remaining_value": c.remaining_value, "remaining_qty": c.remaining_qty,
         "status": enum_val(c.status)}
        for c in rows
    ]


@router.get("/db/scheduled_releases", response_model=list[DBScheduledReleaseRow])
@limiter.limit("60/minute")
def db_scheduled_releases(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw scheduled_releases table dump."""
    rows = db.query(ScheduledRelease).options(joinedload(ScheduledRelease.contract), joinedload(ScheduledRelease.part)).order_by(ScheduledRelease.id).offset(offset).limit(limit).all()
    return [
        {"id": r.id, "release_number": r.release_number,
         "contract": r.contract.contract_number if r.contract else None,
         "part": r.part.part_id if r.part else None,
         "quantity": r.quantity,
         "requested_delivery_date": r.requested_delivery_date.isoformat() if r.requested_delivery_date else None,
         "actual_delivery_date": r.actual_delivery_date.isoformat() if r.actual_delivery_date else None,
         "status": enum_val(r.status)}
        for r in rows
    ]


@router.get("/db/alternate_suppliers", response_model=list[DBAlternateSupplierRow])
@limiter.limit("60/minute")
def db_alternate_suppliers(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Raw alternate_suppliers table dump."""
    rows = (
        db.query(AlternateSupplier)
        .options(
            joinedload(AlternateSupplier.part),
            joinedload(AlternateSupplier.primary_supplier),
            joinedload(AlternateSupplier.alternate_supplier),
        )
        .order_by(AlternateSupplier.id).offset(offset).limit(limit).all()
    )
    return [
        {"id": a.id,
         "part": a.part.part_id if a.part else None,
         "primary_supplier": a.primary_supplier.name if a.primary_supplier else None,
         "alternate_supplier": a.alternate_supplier.name if a.alternate_supplier else None,
         "cost_premium_pct": a.cost_premium_pct,
         "lead_time_delta_days": a.lead_time_delta_days,
         "notes": a.notes}
        for a in rows
    ]
