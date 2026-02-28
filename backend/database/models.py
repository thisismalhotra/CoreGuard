"""
SQLAlchemy models for Core-Guard MVP.

Ground Truth: FL-001 Flashlight dataset.
All parts, BOMs, suppliers, and orders are modeled here.
Foreign keys enforce referential integrity between Parts <-> Suppliers.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


# --- Enums ---

class SupplierTier(str, enum.Enum):
    TIER_1 = "TIER_1"    # Direct/Strategic (CREE, Samsung SDI)
    TIER_2 = "TIER_2"    # Specialty Component (PCB fabs, CNC shops)
    TIER_3 = "TIER_3"    # Commodity/Consumable (fasteners, packaging)
    SERVICE = "SERVICE"  # Outsourced Process (anodizing, firmware)


class SupplierRegion(str, enum.Enum):
    US = "US"
    CHINA = "CHINA"
    TAIWAN = "TAIWAN"
    SOUTH_KOREA = "SOUTH_KOREA"
    GERMANY = "GERMANY"
    MEXICO = "MEXICO"


class ContractType(str, enum.Enum):
    BLANKET_PO = "BLANKET_PO"        # Volume commitment at negotiated price
    SPOT_BUY = "SPOT_BUY"            # One-off purchase at market rate
    CONSIGNMENT = "CONSIGNMENT"      # Vendor-managed inventory, pay on pull
    FRAMEWORK = "FRAMEWORK"          # Tiered pricing by quarterly volume


class ContractStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRING = "EXPIRING"    # Within 60 days of end_date
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ReleaseStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    LATE = "LATE"


class PartCategory(str, enum.Enum):
    FINISHED_GOOD = "Finished Good"
    SUB_ASSEMBLY = "Sub-Assembly"    # Intermediate assemblies (SA-LED-100, SA-PWR-110)
    COMMON_CORE = "Common Core"
    COMPONENT = "Component"          # Leaf-level purchased parts (LED-201, PCB-202)
    ACCESSORY = "Accessory"
    SERVICE = "Service"              # Outsourced processes (anodizing, firmware flash)


class OrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PENDING_APPROVAL = "PENDING_APPROVAL"  # Triggered when cost > $5,000 (Constitution)
    SENT = "SENT"
    CANCELLED = "CANCELLED"


class InspectionResult(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"


# --- Models ---

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    contact_email = Column(String(200))
    lead_time_days = Column(Integer, nullable=False, default=7)
    reliability_score = Column(Float, default=0.95)  # 0.0 - 1.0
    is_active = Column(Boolean, default=True)  # Simulates supplier going offline (Supply Shock)
    tier = Column(SAEnum(SupplierTier), nullable=False, default=SupplierTier.TIER_2)
    region = Column(SAEnum(SupplierRegion), nullable=False, default=SupplierRegion.US)
    expedite_lead_time_days = Column(Integer, nullable=True)  # Faster option at premium
    minimum_order_qty = Column(Integer, nullable=False, default=1)  # MOQ
    capacity_per_month = Column(Integer, nullable=True)  # Production capacity ceiling
    payment_terms = Column(String(50), default="Net 30")
    certifications = Column(Text, default="[]")  # JSON array: ["ISO 9001", "ITAR", "RoHS"]
    risk_factors = Column(Text, default="[]")    # JSON array: ["single source", "geopolitical"]

    parts = relationship("Part", back_populates="supplier")

    def __repr__(self) -> str:
        return f"<Supplier {self.name}>"


class SupplierContract(Base):
    """Tracks blanket POs, framework agreements, and consignment arrangements."""
    __tablename__ = "supplier_contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_number = Column(String(50), nullable=False, unique=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    contract_type = Column(SAEnum(ContractType), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    total_committed_value = Column(Float, nullable=True)   # Dollar amount commitment
    total_committed_qty = Column(Integer, nullable=True)    # Quantity commitment
    released_value = Column(Float, nullable=False, default=0.0)
    released_qty = Column(Integer, nullable=False, default=0)
    price_schedule = Column(Text, default="[]")  # JSON: [{"part_id": "LED-201", "unit_price": 11.50}]
    payment_terms = Column(String(50), default="Net 30")
    penalty_clause = Column(Text, default="")
    status = Column(SAEnum(ContractStatus), nullable=False, default=ContractStatus.ACTIVE)

    supplier = relationship("Supplier")

    @property
    def remaining_value(self) -> float:
        return (self.total_committed_value or 0) - self.released_value

    @property
    def remaining_qty(self) -> int:
        return (self.total_committed_qty or 0) - self.released_qty

    def __repr__(self) -> str:
        return f"<Contract {self.contract_number}: {self.contract_type.value} [{self.status.value}]>"


class ScheduledRelease(Base):
    """Call-offs against a blanket PO or framework agreement."""
    __tablename__ = "scheduled_releases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    release_number = Column(String(50), nullable=False, unique=True)
    contract_id = Column(Integer, ForeignKey("supplier_contracts.id"), nullable=False)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    requested_delivery_date = Column(DateTime, nullable=False)
    actual_delivery_date = Column(DateTime, nullable=True)
    status = Column(SAEnum(ReleaseStatus), nullable=False, default=ReleaseStatus.SCHEDULED)

    contract = relationship("SupplierContract")
    part = relationship("Part")

    def __repr__(self) -> str:
        return f"<Release {self.release_number}: {self.quantity}x [{self.status.value}]>"


class AlternateSupplier(Base):
    """Maps primary → alternate supplier pairs with cost/lead-time deltas."""
    __tablename__ = "alternate_suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    primary_supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    alternate_supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    cost_premium_pct = Column(Float, nullable=False, default=0.0)  # e.g., 22.0 means +22%
    lead_time_delta_days = Column(Integer, nullable=False, default=0)  # Positive = slower
    notes = Column(Text, default="")

    part = relationship("Part")
    primary_supplier = relationship("Supplier", foreign_keys=[primary_supplier_id])
    alternate_supplier = relationship("Supplier", foreign_keys=[alternate_supplier_id])

    def __repr__(self) -> str:
        return f"<AltSupplier {self.part_id}: +{self.cost_premium_pct}% cost>"


class CriticalityLevel(str, enum.Enum):
    CRITICAL = "CRITICAL"        # Production halts without this part
    HIGH = "HIGH"                # Significant impact, limited substitutes
    MEDIUM = "MEDIUM"            # Moderate impact, substitutes available
    LOW = "LOW"                  # Minimal impact, easily sourced


class Part(Base):
    __tablename__ = "parts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    part_id = Column(String(20), nullable=False, unique=True)  # e.g., CH-101
    description = Column(String(200), nullable=False)
    category = Column(SAEnum(PartCategory), nullable=False)
    unit_cost = Column(Float, nullable=False, default=0.0)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)  # Nullable for Finished Goods

    # Part profile fields — used by Dispatcher and Core-Guard for prioritisation
    criticality = Column(SAEnum(CriticalityLevel), nullable=False, default=CriticalityLevel.MEDIUM)
    lead_time_sensitivity = Column(Float, nullable=False, default=0.5)  # 0.0 (tolerant) to 1.0 (urgent)
    substitute_pool_size = Column(Integer, nullable=False, default=0)   # How many alternate suppliers exist

    supplier = relationship("Supplier", back_populates="parts")
    inventory = relationship("Inventory", back_populates="part", uselist=False)
    bom_entries = relationship("BOMEntry", back_populates="component", foreign_keys="BOMEntry.component_id")

    def __repr__(self) -> str:
        return f"<Part {self.part_id}: {self.description}>"


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False, unique=True)
    on_hand = Column(Integer, nullable=False, default=0)
    safety_stock = Column(Integer, nullable=False, default=0)
    reserved = Column(Integer, nullable=False, default=0)  # Allocated to existing orders
    ring_fenced_qty = Column(Integer, nullable=False, default=0)  # PRD §12: units protected for specific orders
    daily_burn_rate = Column(Float, nullable=False, default=0.0)  # PRD §8: trailing 3-day velocity
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_consumption_date = Column(DateTime, nullable=True)  # PRD §11: ghost inventory detection

    part = relationship("Part", back_populates="inventory")

    @property
    def available(self) -> int:
        """Unreserved stock available for new orders. Clamped to 0 minimum."""
        return max(0, self.on_hand - self.reserved - self.ring_fenced_qty)

    def __repr__(self) -> str:
        return f"<Inventory {self.part.part_id if self.part else '?'}: {self.on_hand} on hand>"


class BOMEntry(Base):
    """Bill of Materials — links a Finished Good to its components."""
    __tablename__ = "bom"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("parts.id"), nullable=False)  # The Finished Good
    component_id = Column(Integer, ForeignKey("parts.id"), nullable=False)  # The raw part
    quantity_per = Column(Integer, nullable=False, default=1)  # How many components per parent

    parent = relationship("Part", foreign_keys=[parent_id])
    component = relationship("Part", foreign_keys=[component_id], back_populates="bom_entries")

    def __repr__(self) -> str:
        return f"<BOM {self.parent_id} -> {self.component_id} x{self.quantity_per}>"


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_number = Column(String(50), nullable=False, unique=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    status = Column(SAEnum(OrderStatus), nullable=False, default=OrderStatus.DRAFT)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    triggered_by = Column(String(50), default="SYSTEM")  # Which agent created this

    part = relationship("Part")
    supplier = relationship("Supplier")

    def __repr__(self) -> str:
        return f"<PO {self.po_number}: {self.quantity}x @ ${self.total_cost} [{self.status.value}]>"


class DemandForecast(Base):
    """Stores current and simulated demand for finished goods."""
    __tablename__ = "demand_forecast"

    id = Column(Integer, primary_key=True, autoincrement=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    forecast_qty = Column(Integer, nullable=False, default=0)
    actual_qty = Column(Integer, nullable=False, default=0)  # Injected by simulation
    period = Column(String(20), default=lambda: f"{datetime.now(timezone.utc).year}-Q{(datetime.now(timezone.utc).month - 1) // 3 + 1}")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    forecast_accuracy_pct = Column(Float, nullable=True)  # 0.0 - 1.0, computed from historical
    source = Column(String(30), default="HISTORICAL_AVG")  # HISTORICAL_AVG | SALES_PIPELINE | SEASONAL_ADJUSTMENT | MANUAL_OVERRIDE
    confidence_level = Column(String(10), default="MEDIUM")  # HIGH | MEDIUM | LOW
    notes = Column(Text, default="")

    part = relationship("Part")

    def __repr__(self) -> str:
        return f"<Demand {self.part_id}: forecast={self.forecast_qty}, actual={self.actual_qty}>"


class QualityInspection(Base):
    """Tracks shipment inspections at the Digital Dock."""
    __tablename__ = "quality_inspections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    batch_size = Column(Integer, nullable=False)
    result = Column(SAEnum(InspectionResult), default=InspectionResult.PENDING)
    notes = Column(Text, default="")
    inspected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    part = relationship("Part")

    def __repr__(self) -> str:
        return f"<Inspection {self.part_id}: {self.result.value}>"


class SalesOrderStatus(str, enum.Enum):
    OPEN = "OPEN"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


class SalesOrder(Base):
    """PRD §12 Step 1: Tracks customer sales orders that drive demand."""
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(String(50), nullable=False, unique=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(SAEnum(SalesOrderStatus), nullable=False, default=SalesOrderStatus.OPEN)
    priority = Column(String(20), default="NORMAL")  # NORMAL | VIP | EXPEDITED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    part = relationship("Part")

    def __repr__(self) -> str:
        return f"<SalesOrder {self.order_number}: {self.quantity}x [{self.status.value}]>"


class RingFenceAuditLog(Base):
    """PRD §11: Audit trail for ring-fencing enforcement — logs every override attempt."""
    __tablename__ = "ring_fence_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    part_id = Column(String(20), nullable=False)
    order_ref = Column(String(50), nullable=False)  # Sales order that owns the ring-fenced stock
    attempted_by = Column(String(50), nullable=False)  # Order/agent that tried to pull stock
    qty_requested = Column(Integer, nullable=False)
    qty_ring_fenced = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # BLOCKED | APPROVED | RING_FENCED
    message = Column(Text, default="")

    def __repr__(self) -> str:
        return f"<RingFenceAudit {self.part_id}: {self.action} by {self.attempted_by}>"


class InventoryFlag(str, enum.Enum):
    GHOST = "GHOST"          # PRD §11: scheduled consumption > 0 but no deductions for 14 days
    SUSPECT = "SUSPECT"      # PRD §11: part not moved in 6 months but count > 0
    NORMAL = "NORMAL"


class InventoryHealthRecord(Base):
    """PRD §11: Tracks data integrity flags (ghost inventory, suspect inventory)."""
    __tablename__ = "inventory_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    part_id = Column(String(20), nullable=False)
    flag = Column(SAEnum(InventoryFlag), nullable=False, default=InventoryFlag.NORMAL)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved = Column(Boolean, default=False)
    notes = Column(Text, default="")

    def __repr__(self) -> str:
        return f"<InventoryHealth {self.part_id}: {self.flag.value}>"


class AgentLog(Base):
    """Persists the Glass Box logs so they survive page refreshes."""
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    agent = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    log_type = Column(String(20), nullable=False, default="info")  # info|warning|success|error
