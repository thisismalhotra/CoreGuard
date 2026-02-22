"""
Pydantic request/response models for Core-Guard API.

Provides type-safe validation for all REST endpoints. Replaces the raw
dict[str, Any] returns with structured models for better documentation,
validation, and client-side type generation.

Note: Uses Optional[X] syntax for Python 3.9 compatibility.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared / Reusable
# ---------------------------------------------------------------------------

class GlassBoxLog(BaseModel):
    """A single Glass Box log entry emitted by an agent."""
    timestamp: str
    agent: str
    message: str
    type: str = Field(description="info | warning | success | error")


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

class InventoryItemResponse(BaseModel):
    part_id: str
    description: str
    category: str
    on_hand: int
    safety_stock: int
    reserved: int
    available: int
    supplier: Optional[str] = None


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------

class PurchaseOrderResponse(BaseModel):
    po_number: str
    part_id: str
    supplier: str
    quantity: int
    unit_cost: float
    total_cost: float
    status: str
    created_at: str
    triggered_by: str


class PurchaseOrderSummary(BaseModel):
    """Compact PO summary returned inside simulation results."""
    po_number: str
    part_id: str
    supplier: str
    quantity: int
    unit_cost: float
    total_cost: float
    status: str


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

class SupplierResponse(BaseModel):
    id: int
    name: str
    lead_time_days: int
    reliability_score: float
    is_active: bool


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

class KPIsResponse(BaseModel):
    inventory_health: float
    total_on_hand: int
    total_safety_stock: int
    active_threads: int
    automation_rate: float
    total_orders: int


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class LogDelayResponse(BaseModel):
    delay: float


# ---------------------------------------------------------------------------
# Simulation Results
# ---------------------------------------------------------------------------

class ShortageDetail(BaseModel):
    part_id: str
    required: int
    available: int
    gap: int
    criticality: str


class ActionDetail(BaseModel):
    type: str
    part_id: str
    quantity: int
    unit_cost: Optional[float] = None
    total_cost: Optional[float] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    source_sku: Optional[str] = None
    triggered_by: Optional[str] = None
    expedite: Optional[bool] = None
    criticality: Optional[str] = None


class SpikeAuraResult(BaseModel):
    spike_detected: bool
    multiplier: float


class SpikeMRPResult(BaseModel):
    shortages: List[ShortageDetail]
    actions: List[ActionDetail]


class SpikeProcurementResult(BaseModel):
    purchase_orders: List[PurchaseOrderSummary]


class SpikeResponse(BaseModel):
    status: str
    scenario: str = "DEMAND_SPIKE"
    sku: str
    multiplier: float
    aura: SpikeAuraResult
    mrp: SpikeMRPResult
    procurement: SpikeProcurementResult
    logs: List[GlassBoxLog]


class NoSpikeResponse(BaseModel):
    status: str = "no_spike"
    aura: Dict[str, Any]
    logs: List[GlassBoxLog]


class SupplyShockResponse(BaseModel):
    status: str
    scenario: str = "SUPPLY_SHOCK"
    supplier: str
    affected_parts: List[str]
    procurement: List[PurchaseOrderSummary]
    logs: List[GlassBoxLog]


class QualityFailResponse(BaseModel):
    status: str
    scenario: str = "QUALITY_FAIL"
    part_id: str
    batch_size: int
    inspection_result: str
    failed_checks: List[str]
    procurement: List[PurchaseOrderSummary]
    logs: List[GlassBoxLog]


class CascadeFailureResponse(BaseModel):
    status: str
    scenario: str = "CASCADE_FAILURE"
    shortages: List[ShortageDetail]
    procurement: List[PurchaseOrderSummary]
    logs: List[GlassBoxLog]


class ConstitutionBreachResponse(BaseModel):
    status: str
    scenario: str = "CONSTITUTION_BREACH"
    blocked_pos: List[PurchaseOrderSummary]
    approved_pos: List[PurchaseOrderSummary]
    logs: List[GlassBoxLog]


class FullBlackoutResponse(BaseModel):
    status: str
    scenario: str = "FULL_BLACKOUT"
    suppliers_offline: int
    unresolved_shortages: List[ShortageDetail]
    logs: List[GlassBoxLog]


class ResetResponse(BaseModel):
    status: str
    message: str


class ErrorResponse(BaseModel):
    error: str


# ---------------------------------------------------------------------------
# DB Viewer (raw table dumps)
# ---------------------------------------------------------------------------

class DBSupplierRow(BaseModel):
    id: int
    name: str
    contact_email: Optional[str] = None
    lead_time_days: int
    reliability_score: float
    is_active: bool


class DBPartRow(BaseModel):
    id: int
    part_id: str
    description: str
    category: str
    unit_cost: float
    criticality: str
    lead_time_sensitivity: float
    substitute_pool_size: int
    supplier: Optional[str] = None


class DBInventoryRow(BaseModel):
    id: int
    part: Optional[str] = None
    on_hand: int
    safety_stock: int
    reserved: int
    available: int
    last_updated: Optional[str] = None


class DBBomRow(BaseModel):
    id: int
    parent: Optional[str] = None
    component: Optional[str] = None
    quantity_per: int


class DBOrderRow(BaseModel):
    id: int
    po_number: str
    part: Optional[str] = None
    supplier: Optional[str] = None
    quantity: int
    unit_cost: float
    total_cost: float
    status: str
    triggered_by: Optional[str] = None
    created_at: Optional[str] = None


class DBDemandForecastRow(BaseModel):
    id: int
    part: Optional[str] = None
    forecast_qty: int
    actual_qty: int
    period: Optional[str] = None
    updated_at: Optional[str] = None


class DBQualityInspectionRow(BaseModel):
    id: int
    part: Optional[str] = None
    batch_size: int
    result: str
    notes: Optional[str] = None
    inspected_at: Optional[str] = None


class DBAgentLogRow(BaseModel):
    id: int
    agent: str
    message: str
    log_type: str
    timestamp: Optional[str] = None


# ---------------------------------------------------------------------------
# Agents Metadata
# ---------------------------------------------------------------------------

class AgentMetadata(BaseModel):
    name: str
    role: str
    description: str
    trigger: str
    inputs: List[str]
    outputs: List[str]
    downstream: Optional[str] = None
    constitution: Optional[str] = None
    rules: List[str]
    color: str
    icon: str
    source_file: str
