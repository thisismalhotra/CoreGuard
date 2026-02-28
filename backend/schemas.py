"""
Pydantic request/response models for Core-Guard API.

Provides type-safe validation for all REST endpoints. Replaces the raw
dict[str, Any] returns with structured models for better documentation,
validation, and client-side type generation.
"""

from __future__ import annotations

from typing import Any, Optional
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
    ring_fenced: int = 0
    available: int
    daily_burn_rate: float = 0.0
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


class CreatePurchaseOrderRequest(BaseModel):
    """Request body for manually creating a purchase order."""
    part_id: str = Field(description="The part_id string (e.g., 'CH-101')")
    supplier_name: str = Field(description="Name of the supplier (e.g., 'AluForge')")
    quantity: int = Field(ge=1, description="Number of units to order")
    unit_cost: float = Field(ge=0.0, description="Cost per unit")


class UpdateOrderStatusRequest(BaseModel):
    """Request body for approving or rejecting a pending purchase order."""
    status: str = Field(
        description="New status: 'APPROVED' or 'CANCELLED'",
        pattern="^(APPROVED|CANCELLED)$",
    )


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
    shortages: list[ShortageDetail]
    actions: list[ActionDetail]


class SpikeProcurementResult(BaseModel):
    purchase_orders: list[PurchaseOrderSummary]


class SpikeResponse(BaseModel):
    status: str
    scenario: str = "DEMAND_SPIKE"
    sku: str
    multiplier: float
    aura: SpikeAuraResult
    mrp: SpikeMRPResult
    procurement: SpikeProcurementResult
    logs: list[GlassBoxLog]


class NoSpikeResponse(BaseModel):
    status: str = "no_spike"
    aura: dict[str, Any]
    logs: list[GlassBoxLog]


class SupplyShockResponse(BaseModel):
    status: str
    scenario: str = "SUPPLY_SHOCK"
    supplier: str
    affected_parts: list[str]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class QualityFailResponse(BaseModel):
    status: str
    scenario: str = "QUALITY_FAIL"
    part_id: str
    batch_size: int
    inspection_result: str
    failed_checks: list[str]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class CascadeFailureResponse(BaseModel):
    status: str
    scenario: str = "CASCADE_FAILURE"
    shortages: list[ShortageDetail]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class ConstitutionBreachResponse(BaseModel):
    status: str
    scenario: str = "CONSTITUTION_BREACH"
    blocked_pos: list[PurchaseOrderSummary]
    approved_pos: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class FullBlackoutResponse(BaseModel):
    status: str
    scenario: str = "FULL_BLACKOUT"
    suppliers_offline: int
    unresolved_shortages: list[ShortageDetail]
    logs: list[GlassBoxLog]


class SlowBleedResponse(BaseModel):
    status: str
    scenario: str = "SLOW_BLEED"
    part_id: str
    days_simulated: int
    runway_progression: list[dict[str, Any]]
    handshake_triggered: bool
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class InventoryDecayResponse(BaseModel):
    status: str
    scenario: str = "INVENTORY_DECAY"
    ghost_parts: list[dict[str, Any]]
    suspect_parts: list[dict[str, Any]]
    corrected_runway: dict[str, Any]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class MultiSkuContentionResponse(BaseModel):
    status: str
    scenario: str = "MULTI_SKU_CONTENTION"
    contending_skus: list[str]
    shared_component: str
    combined_demand: int
    prioritization: list[dict[str, Any]]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class ContractExhaustionResponse(BaseModel):
    """Response for Scenario 10: Contract Exhaustion."""
    status: str
    scenario: str = "CONTRACT_EXHAUSTION"
    contract_number: str
    supplier: str
    remaining_qty: int
    remaining_value: float
    forecast_demand: int
    recommendation: str  # "EXTEND" | "SPOT_BUY" | "RENEGOTIATE"
    spot_buy_premium_pct: float
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class TariffShockResponse(BaseModel):
    """Response for Scenario 11: Tariff Shock."""
    status: str
    scenario: str = "TARIFF_SHOCK"
    affected_suppliers: list[str]
    cost_increase_pct: float
    affected_parts: list[str]
    alternate_options: list[dict[str, Any]]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class MOQTrapResponse(BaseModel):
    """Response for Scenario 12: MOQ Trap."""
    status: str
    scenario: str = "MOQ_TRAP"
    part_id: str
    needed_qty: int
    moq: int
    excess_qty: int
    carry_cost: float
    small_lot_premium: float
    recommendation: str  # "BUY_MOQ" | "SMALL_LOT" | "WAIT"
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class MilitarySurgeResponse(BaseModel):
    """Response for Scenario 13: Military Surge."""
    status: str
    scenario: str = "MILITARY_SURGE"
    order_number: str
    original_qty: int
    new_qty: int
    deadline_days: int
    ring_fenced_parts: list[dict[str, Any]]
    displaced_orders: list[dict[str, Any]]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class SemiconductorAllocationResponse(BaseModel):
    """Response for Scenario 14: Semiconductor Allocation."""
    status: str
    scenario: str = "SEMICONDUCTOR_ALLOCATION"
    part_id: str
    original_capacity: int
    reduced_capacity: int
    allocation_weeks: int
    affected_products: list[str]
    product_mix_recommendation: list[dict[str, Any]]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class SeasonalRampResponse(BaseModel):
    """Response for Scenario 15: Seasonal Ramp."""
    status: str
    scenario: str = "SEASONAL_RAMP"
    forecast_deviation_pct: float
    affected_products: list[str]
    pre_positioned_parts: list[dict[str, Any]]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class DemandHorizonResponse(BaseModel):
    """Response for Demand Horizon zone classification (PRD §10)."""
    status: str
    scenario: str = "DEMAND_HORIZON"
    part_id: str
    demand_qty: int
    days_until_needed: int
    zone: int
    zone_name: str
    active_agents: list[str]
    recommended_action: str
    generate_po: bool
    expedite: bool
    use_secondary_supplier: bool
    secondary_supplier: Optional[dict[str, Any]] = None
    logs: list[GlassBoxLog]


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
    tier: Optional[str] = None
    region: Optional[str] = None
    expedite_lead_time_days: Optional[int] = None
    minimum_order_qty: int = 1
    capacity_per_month: Optional[int] = None
    payment_terms: Optional[str] = None


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
    ring_fenced_qty: int = 0
    daily_burn_rate: float = 0.0
    available: int
    last_updated: Optional[str] = None
    last_consumption_date: Optional[str] = None


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
    forecast_accuracy_pct: Optional[float] = None
    source: Optional[str] = None
    confidence_level: Optional[str] = None
    notes: Optional[str] = None


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


class DBSalesOrderRow(BaseModel):
    id: int
    order_number: str
    part: Optional[str] = None
    quantity: int
    status: str
    priority: str
    created_at: Optional[str] = None


class DBRingFenceAuditRow(BaseModel):
    id: int
    part_id: str
    order_ref: str
    attempted_by: str
    qty_requested: int
    qty_ring_fenced: int
    action: str
    message: Optional[str] = None
    timestamp: Optional[str] = None


class DBInventoryHealthRow(BaseModel):
    id: int
    part_id: str
    flag: str
    resolved: bool
    notes: Optional[str] = None
    detected_at: Optional[str] = None


class DBSupplierContractRow(BaseModel):
    id: int
    contract_number: str
    supplier: Optional[str] = None
    contract_type: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_committed_value: Optional[float] = None
    total_committed_qty: Optional[int] = None
    released_value: float = 0.0
    released_qty: int = 0
    remaining_value: float = 0.0
    remaining_qty: int = 0
    status: str


class DBScheduledReleaseRow(BaseModel):
    id: int
    release_number: str
    contract: Optional[str] = None
    part: Optional[str] = None
    quantity: int
    requested_delivery_date: Optional[str] = None
    actual_delivery_date: Optional[str] = None
    status: str


class DBAlternateSupplierRow(BaseModel):
    id: int
    part: Optional[str] = None
    primary_supplier: Optional[str] = None
    alternate_supplier: Optional[str] = None
    cost_premium_pct: float
    lead_time_delta_days: int
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Agents Metadata
# ---------------------------------------------------------------------------

class AgentMetadata(BaseModel):
    name: str
    role: str
    description: str
    trigger: str
    inputs: list[str]
    outputs: list[str]
    downstream: Optional[str] = None
    constitution: Optional[str] = None
    rules: list[str]
    color: str
    icon: str
    source_file: str
