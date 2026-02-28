# Realistic Seed Data Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform CoreGuard from a 5-part/3-supplier demo into a credible multi-product supply chain with ~55 parts, enriched suppliers, contracts, 3-level BOMs, seasonal demand forecasts, and 6 new simulation scenarios.

**Architecture:** Extend existing SQLAlchemy models with new fields and 3 new tables (SupplierContract, ScheduledRelease, AlternateSupplier). Rewrite seed.py with the Tactical Lighting Division dataset. Update Core-Guard's BOM explosion to handle recursive multi-level BOMs. Add new simulation endpoints. Update conftest.py to match.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy, SQLite, Pydantic, pytest

**Design Doc:** `docs/plans/2026-02-27-realistic-seed-data-design.md`

---

## Task 1: Extend Supplier Model

**Files:**
- Modify: `backend/database/models.py` (Supplier class, lines 45-58)

**Step 1: Add new enum for supplier tier and region**

Add these enums after the existing `PartCategory` enum (after line 27):

```python
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
```

**Step 2: Add new columns to Supplier model**

Add these columns to the `Supplier` class (after `is_active`, line 53):

```python
    tier = Column(SAEnum(SupplierTier), nullable=False, default=SupplierTier.TIER_2)
    region = Column(SAEnum(SupplierRegion), nullable=False, default=SupplierRegion.US)
    expedite_lead_time_days = Column(Integer, nullable=True)  # Faster option at premium
    minimum_order_qty = Column(Integer, nullable=False, default=1)  # MOQ
    capacity_per_month = Column(Integer, nullable=True)  # Production capacity ceiling
    payment_terms = Column(String(50), default="Net 30")
    certifications = Column(Text, default="[]")  # JSON array: ["ISO 9001", "ITAR", "RoHS"]
    risk_factors = Column(Text, default="[]")    # JSON array: ["single source", "geopolitical"]
```

**Step 3: Run tests to verify no regressions**

Run: `cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend && python -m pytest tests/ -x -q`
Expected: All existing tests pass (new columns have defaults, so no breakage).

**Step 4: Commit**

```bash
git add backend/database/models.py
git commit -m "feat: enrich Supplier model with tier, region, MOQ, capacity, certifications"
```

---

## Task 2: Add New Models (SupplierContract, ScheduledRelease, AlternateSupplier)

**Files:**
- Modify: `backend/database/models.py`

**Step 1: Add ContractType and ContractStatus enums**

Add after the `SupplierRegion` enum:

```python
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
```

**Step 2: Add SupplierContract model**

Add after the `Supplier` class:

```python
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
```

**Step 3: Add ScheduledRelease model**

```python
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
```

**Step 4: Add AlternateSupplier model**

```python
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
```

**Step 5: Run tests**

Run: `cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend && python -m pytest tests/ -x -q`
Expected: All pass. New tables are additive, no impact on existing data.

**Step 6: Commit**

```bash
git add backend/database/models.py
git commit -m "feat: add SupplierContract, ScheduledRelease, AlternateSupplier models"
```

---

## Task 3: Add PartCategory SUB_ASSEMBLY and Enhance DemandForecast

**Files:**
- Modify: `backend/database/models.py`

**Step 1: Add SUB_ASSEMBLY to PartCategory enum**

Change the `PartCategory` enum (line 23-26) to:

```python
class PartCategory(str, enum.Enum):
    FINISHED_GOOD = "Finished Good"
    SUB_ASSEMBLY = "Sub-Assembly"    # NEW: intermediate assemblies (SA-LED-100, SA-PWR-110)
    COMMON_CORE = "Common Core"
    COMPONENT = "Component"          # NEW: leaf-level purchased parts (LED-201, PCB-202)
    ACCESSORY = "Accessory"
    SERVICE = "Service"              # NEW: outsourced processes (anodizing, firmware flash)
```

**Step 2: Add new fields to DemandForecast**

Add these columns to the `DemandForecast` class (after `updated_at`, around line 161):

```python
    forecast_accuracy_pct = Column(Float, nullable=True)  # 0.0 - 1.0, computed from historical
    source = Column(String(30), default="HISTORICAL_AVG")  # HISTORICAL_AVG | SALES_PIPELINE | SEASONAL_ADJUSTMENT | MANUAL_OVERRIDE
    confidence_level = Column(String(10), default="MEDIUM")  # HIGH | MEDIUM | LOW
    notes = Column(Text, default="")
```

**Step 3: Run tests**

Run: `cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend && python -m pytest tests/ -x -q`
Expected: All pass. New enum values and columns are additive.

**Step 4: Commit**

```bash
git add backend/database/models.py
git commit -m "feat: add SUB_ASSEMBLY/COMPONENT/SERVICE part categories, enrich DemandForecast"
```

---

## Task 4: Write Tests for New Models

**Files:**
- Create: `backend/tests/test_models_extended.py`

**Step 1: Write tests for new model behavior**

```python
"""Tests for the extended models: SupplierContract, AlternateSupplier, multi-level BOM."""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base, Supplier, Part, Inventory, BOMEntry, SupplierContract,
    ScheduledRelease, AlternateSupplier,
    PartCategory, CriticalityLevel, SupplierTier, SupplierRegion,
    ContractType, ContractStatus, ReleaseStatus,
)


@pytest.fixture
def db():
    """Minimal DB for model tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestSupplierEnhancements:
    def test_supplier_tier_and_region(self, db):
        s = Supplier(
            name="CREE Inc.", lead_time_days=42,
            tier=SupplierTier.TIER_1, region=SupplierRegion.US,
            minimum_order_qty=500, capacity_per_month=15000,
        )
        db.add(s)
        db.flush()
        assert s.tier == SupplierTier.TIER_1
        assert s.region == SupplierRegion.US
        assert s.minimum_order_qty == 500

    def test_supplier_defaults(self, db):
        s = Supplier(name="Test", lead_time_days=5)
        db.add(s)
        db.flush()
        assert s.tier == SupplierTier.TIER_2
        assert s.region == SupplierRegion.US
        assert s.minimum_order_qty == 1


class TestSupplierContract:
    def test_contract_remaining_value(self, db):
        s = Supplier(name="CREE", lead_time_days=42)
        db.add(s)
        db.flush()
        c = SupplierContract(
            contract_number="BPA-CREE-2026",
            supplier_id=s.id,
            contract_type=ContractType.BLANKET_PO,
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            total_committed_value=180000.0,
            released_value=120000.0,
            total_committed_qty=15000,
            released_qty=10000,
        )
        db.add(c)
        db.flush()
        assert c.remaining_value == 60000.0
        assert c.remaining_qty == 5000

    def test_contract_status_lifecycle(self, db):
        s = Supplier(name="Samsung", lead_time_days=35)
        db.add(s)
        db.flush()
        c = SupplierContract(
            contract_number="BPA-SSDI-2026",
            supplier_id=s.id,
            contract_type=ContractType.BLANKET_PO,
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            status=ContractStatus.ACTIVE,
        )
        db.add(c)
        db.flush()
        assert c.status == ContractStatus.ACTIVE
        c.status = ContractStatus.EXPIRING
        db.flush()
        assert c.status == ContractStatus.EXPIRING


class TestAlternateSupplier:
    def test_alternate_supplier_cost_premium(self, db):
        cree = Supplier(name="CREE", lead_time_days=42)
        luminus = Supplier(name="Luminus Devices", lead_time_days=56)
        db.add_all([cree, luminus])
        db.flush()
        led = Part(part_id="LED-201", description="CREE XHP70.3 HI",
                   category=PartCategory.COMPONENT, unit_cost=11.50,
                   supplier_id=cree.id, criticality=CriticalityLevel.CRITICAL)
        db.add(led)
        db.flush()
        alt = AlternateSupplier(
            part_id=led.id,
            primary_supplier_id=cree.id,
            alternate_supplier_id=luminus.id,
            cost_premium_pct=22.0,
            lead_time_delta_days=14,
        )
        db.add(alt)
        db.flush()
        assert alt.cost_premium_pct == 22.0
        assert alt.lead_time_delta_days == 14


class TestMultiLevelBOM:
    def test_three_level_bom(self, db):
        """Verify 3-level BOM: FL-001-T -> SA-LED-100 -> LED-201"""
        s = Supplier(name="CREE", lead_time_days=42)
        db.add(s)
        db.flush()
        fl001t = Part(part_id="FL-001-T", description="Tactical Flashlight",
                      category=PartCategory.FINISHED_GOOD, criticality=CriticalityLevel.HIGH)
        sa_led = Part(part_id="SA-LED-100", description="LED Module Assembly",
                      category=PartCategory.SUB_ASSEMBLY, criticality=CriticalityLevel.HIGH)
        led_201 = Part(part_id="LED-201", description="CREE XHP70.3 HI",
                       category=PartCategory.COMPONENT, unit_cost=11.50,
                       supplier_id=s.id, criticality=CriticalityLevel.CRITICAL)
        db.add_all([fl001t, sa_led, led_201])
        db.flush()
        # Level 1: FL-001-T -> SA-LED-100
        bom1 = BOMEntry(parent_id=fl001t.id, component_id=sa_led.id, quantity_per=1)
        # Level 2: SA-LED-100 -> LED-201
        bom2 = BOMEntry(parent_id=sa_led.id, component_id=led_201.id, quantity_per=1)
        db.add_all([bom1, bom2])
        db.flush()
        # Verify parent->child links
        l1_entries = db.query(BOMEntry).filter(BOMEntry.parent_id == fl001t.id).all()
        assert len(l1_entries) == 1
        assert l1_entries[0].component.part_id == "SA-LED-100"
        l2_entries = db.query(BOMEntry).filter(BOMEntry.parent_id == sa_led.id).all()
        assert len(l2_entries) == 1
        assert l2_entries[0].component.part_id == "LED-201"
```

**Step 2: Run the new tests**

Run: `cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend && python -m pytest tests/test_models_extended.py -v`
Expected: All pass.

**Step 3: Commit**

```bash
git add backend/tests/test_models_extended.py
git commit -m "test: add tests for SupplierContract, AlternateSupplier, multi-level BOM"
```

---

## Task 5: Rewrite seed.py with Tactical Lighting Division Dataset

**Files:**
- Modify: `backend/seed.py` (complete rewrite of the `seed()` function body)

This is the largest task. The seed function should follow the exact same pattern as the current one (check for existing data, create entities, flush between sections) but with the full dataset from the design doc.

**Step 1: Rewrite `seed()` with the full supplier dataset**

Replace the `suppliers_data` list with the 22 enriched suppliers from the design doc. Each supplier now includes `tier`, `region`, `expedite_lead_time_days`, `minimum_order_qty`, `capacity_per_month`, `payment_terms`, `certifications`, `risk_factors`.

See the design doc `docs/plans/2026-02-27-realistic-seed-data-design.md` Section 3 for the complete supplier list.

**Step 2: Add the ~55 parts dataset**

Replace the `parts_data` list with all parts from the design doc. This includes:
- 6 finished goods (FL-001-T, FL-001-S, HL-002-P, HL-002-B, WL-003-R, WL-003-C)
- ~10 sub-assemblies (SA-LED-100, SA-PWR-110, SA-OPT-120, SA-BDY-130, SA-ELC-140, SA-PKG-150, SA-HBD-160, SA-HSG-170, SA-MNT-180, SA-ACT-190, SA-BDY-135, SA-ELC-145, SA-PKG-155, SA-PKG-158, SA-PWR-115)
- ~35 components (LED-201 through VLC-294)
- ~4 services (ANO-234, KNL-235, FW-244, RFL-224)

Each part must have: `part_id`, `description`, `category` (using new enums), `unit_cost`, `supplier_name`, `criticality`, `lead_time_sensitivity`, `substitute_pool_size`.

See design doc Section 2 for the complete BOM with unit costs.

**Step 3: Add 3-level BOM entries**

Replace the `bom_data` list with ~120 BOM entries representing:
- Level 1: Finished Good → Sub-Assembly (e.g., FL-001-T → SA-LED-100)
- Level 2: Sub-Assembly → Component (e.g., SA-LED-100 → LED-201, PCB-202, HS-203, TCP-204, MCR-205, RST-206)
- All 6 product variants with their specific BOMs (some share sub-assemblies, some have unique ones)

See design doc Section 2 for the complete BOM structure.

**Step 4: Add inventory records for all ~55 parts**

Replace `inventory_data` with records for every part. Key parts with built-in tension:
- MCU-241: on_hand=380, safety_stock=500 (BELOW SAFETY)
- LNS-221: on_hand=420, safety_stock=500 (BELOW SAFETY)
- CH-231: on_hand=280, safety_stock=225 (JUST ABOVE)
- LED-201: on_hand=1450, safety_stock=625 (TIGHT — 5.5 weeks vs 6-week lead)

See design doc Section 4 for the complete inventory table.

**Step 5: Add enriched sales orders**

Replace `sales_order_data` with the 6 realistic orders:
- SO-MIL-001: 200x WL-003-R (VIP, 30 days) — military contract
- SO-AMZ-002: 500x FL-001-S (NORMAL, 45 days) — Amazon FBA
- SO-REI-003: 150x HL-002-P (NORMAL, 60 days) — REI seasonal
- SO-LEO-004: 300x FL-001-T (EXPEDITED, 21 days) — law enforcement
- SO-DLR-005: 50x FL-001-T (NORMAL, 90 days) — dealer network
- SO-OEM-006: 100x SA-LED-100 (NORMAL, 45 days) — OEM sub-assembly sale

**Step 6: Add demand forecasts with seasonal history**

Replace `forecast_data` with the 7-period × 5-product forecast dataset from the design doc, including `source`, `confidence_level`, and `forecast_accuracy_pct` for historical periods.

**Step 7: Add supplier contracts**

Add a new section seeding the 6 contracts from the design doc (BPA-CREE-2026, BPA-SSDI-2026, FW-WURTH-2026, SPT-APEX, CSG-MCMASTER, BPA-ENG-2026).

**Step 8: Add alternate supplier mappings**

Add the 8 alternate supplier pairs from the design doc (CREE→Luminus, Samsung→LG, etc.).

**Step 9: Delete old database and re-seed**

Run:
```bash
cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend
rm -f coreguard.db
python seed.py
```
Expected: Clean seed with summary showing ~55 parts, ~22 suppliers, ~120 BOM entries, etc.

**Step 10: Run all tests**

Run: `cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend && python -m pytest tests/ -x -q`
Note: Existing tests use conftest.py (in-memory DB), not seed.py, so they should still pass. If any fail due to enum changes, fix them.

**Step 11: Commit**

```bash
git add backend/seed.py
git commit -m "feat: rewrite seed.py with Tactical Lighting Division dataset (55 parts, 3-level BOM)"
```

---

## Task 6: Update conftest.py for Multi-Product Tests

**Files:**
- Modify: `backend/tests/conftest.py`

**Step 1: Update imports**

Add new model imports:

```python
from database.models import (
    Base, Supplier, Part, Inventory, BOMEntry, DemandForecast, SalesOrder,
    SupplierContract, AlternateSupplier,
    PartCategory, CriticalityLevel, SalesOrderStatus,
    SupplierTier, SupplierRegion, ContractType, ContractStatus,
)
```

**Step 2: Extend the `db` fixture**

Keep the existing fixture structure but add:
- 2-3 additional suppliers (enough to test multi-tier and alternate supplier logic)
- 2-3 sub-assembly parts (SA-LED-100, SA-PWR-110)
- 4-5 component parts (LED-201, PCB-202, BAT-211, MCU-241, GKT-223)
- Multi-level BOM entries (FL-001-T → SA-LED-100 → LED-201)
- 1 headlamp finished good (HL-002-P) with shared components for contention tests
- 1 supplier contract for blanket PO tests
- 1 alternate supplier mapping

The fixture should be backwards-compatible — existing test assertions about FL-001-T, CH-101, SW-303, LNS-505 must still hold. Add new parts without removing old ones.

**Step 3: Run all existing tests**

Run: `cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend && python -m pytest tests/ -v`
Expected: All existing tests pass. New fixture data is additive.

**Step 4: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: extend conftest with multi-product fixture data for new BOM tests"
```

---

## Task 7: Add Recursive BOM Explosion to Core-Guard

**Files:**
- Modify: `backend/agents/core_guard.py`
- Create: `backend/tests/test_recursive_bom.py`

**Step 1: Write failing test for recursive BOM explosion**

```python
"""Tests for recursive (multi-level) BOM explosion in Core-Guard."""

from agents.core_guard import calculate_net_requirements


class TestRecursiveBOMExplosion:
    def test_three_level_bom_identifies_leaf_shortages(self, db):
        """
        FL-001-T -> SA-LED-100 -> LED-201
        A demand spike on FL-001-T should surface shortage of LED-201 (leaf component),
        not just SA-LED-100 (sub-assembly).
        """
        result = calculate_net_requirements(db, "FL-001-T", 2000)
        # Should have shortages at the leaf (component) level
        shortage_part_ids = [s["part_id"] for s in result["shortages"]]
        # LED-201 is a leaf component with inventory — it should appear if short
        # Sub-assemblies (SA-LED-100) should NOT appear as shortages (they're virtual)
        for s in result["shortages"]:
            assert not s["part_id"].startswith("SA-"), \
                f"Sub-assembly {s['part_id']} should not be a shortage — only leaf components"

    def test_quantity_per_multiplies_through_levels(self, db):
        """
        If FL-001-T needs 1x SA-LED-100, and SA-LED-100 needs 1x LED-201,
        then 100 units of FL-001-T needs 100x LED-201.
        """
        result = calculate_net_requirements(db, "FL-001-T", 100)
        # Find LED-201 in shortages or verify it was checked
        log_messages = " ".join(log["message"] for log in result["logs"])
        assert "LED-201" in log_messages, "BOM explosion should reach LED-201"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend && python -m pytest tests/test_recursive_bom.py -v`
Expected: FAIL — current BOM explosion only does single-level.

**Step 3: Implement recursive BOM explosion**

In `backend/agents/core_guard.py`, modify `calculate_net_requirements()` to walk the BOM tree recursively. Add a helper function:

```python
def _explode_bom(db: Session, part_id: int, demand_qty: int) -> list[dict]:
    """
    Recursively explode BOM to find leaf-level component requirements.

    Returns list of {"part": Part, "inventory": Inventory, "required": int, "bom_path": str}
    for every leaf component (no children in BOM).
    """
    bom_entries = db.query(BOMEntry).filter(BOMEntry.parent_id == part_id).all()

    if not bom_entries:
        # Leaf node — this is a purchasable component
        part = db.query(Part).filter(Part.id == part_id).first()
        inventory = part.inventory if part else None
        return [{"part": part, "inventory": inventory, "required": demand_qty}]

    leaf_requirements = []
    for bom in bom_entries:
        child_qty = demand_qty * bom.quantity_per
        child_leaves = _explode_bom(db, bom.component_id, child_qty)
        leaf_requirements.extend(child_leaves)

    # Aggregate requirements for the same part (shared components across sub-assemblies)
    aggregated = {}
    for req in leaf_requirements:
        pid = req["part"].part_id
        if pid in aggregated:
            aggregated[pid]["required"] += req["required"]
        else:
            aggregated[pid] = req
    return list(aggregated.values())
```

Then update the main `calculate_net_requirements()` function to use `_explode_bom()` instead of the single-level BOM query.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend && python -m pytest tests/test_recursive_bom.py tests/test_agents.py -v`
Expected: All pass, including existing tests.

**Step 5: Commit**

```bash
git add backend/agents/core_guard.py backend/tests/test_recursive_bom.py
git commit -m "feat: implement recursive BOM explosion for multi-level material planning"
```

---

## Task 8: Add Response Schemas for New Scenarios

**Files:**
- Modify: `backend/schemas.py`

**Step 1: Add Pydantic models for new simulation responses**

Add these after the existing simulation response schemas:

```python
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
    procurement: ProcurementResult
    logs: list[GlassBoxLog]


class TariffShockResponse(BaseModel):
    """Response for Scenario 11: Tariff Shock."""
    status: str
    scenario: str = "TARIFF_SHOCK"
    affected_suppliers: list[str]
    cost_increase_pct: float
    affected_parts: list[str]
    alternate_options: list[dict]  # [{supplier, part_id, new_cost, lead_time}]
    procurement: ProcurementResult
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
    procurement: ProcurementResult
    logs: list[GlassBoxLog]


class MilitarySurgeResponse(BaseModel):
    """Response for Scenario 13: Military Surge."""
    status: str
    scenario: str = "MILITARY_SURGE"
    order_number: str
    original_qty: int
    new_qty: int
    deadline_days: int
    ring_fenced_parts: list[dict]
    displaced_orders: list[dict]
    procurement: ProcurementResult
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
    product_mix_recommendation: list[dict]
    procurement: ProcurementResult
    logs: list[GlassBoxLog]


class SeasonalRampResponse(BaseModel):
    """Response for Scenario 15: Seasonal Ramp."""
    status: str
    scenario: str = "SEASONAL_RAMP"
    forecast_deviation_pct: float
    affected_products: list[str]
    pre_positioned_parts: list[dict]
    procurement: ProcurementResult
    logs: list[GlassBoxLog]
```

**Step 2: Commit**

```bash
git add backend/schemas.py
git commit -m "feat: add Pydantic response schemas for 6 new simulation scenarios"
```

---

## Task 9: Implement New Simulation Endpoints

**Files:**
- Modify: `backend/routers/simulations.py`

**Step 1: Add Scenario 10 — Contract Exhaustion**

```python
@router.post("/simulate/contract-exhaustion", response_model=ContractExhaustionResponse)
async def simulate_contract_exhaustion(
    contract_number: str = Query(default="BPA-CREE-2026"),
    db: Session = Depends(get_db),
):
    """
    Scenario 10: Blanket PO is 90% consumed with months remaining.
    Ghost-Writer evaluates: extend contract vs. spot buy at premium.
    """
```

Implement by:
1. Look up the contract by number
2. Calculate remaining vs. forecasted demand for remaining term
3. Compare blanket price vs. alternate supplier spot price
4. Emit Glass Box logs showing the analysis
5. Return recommendation

**Step 2: Add Scenario 11 — Tariff Shock**

```python
@router.post("/simulate/tariff-shock", response_model=TariffShockResponse)
async def simulate_tariff_shock(
    region: str = Query(default="CHINA"),
    increase_pct: float = Query(default=25.0, ge=1.0, le=100.0),
    db: Session = Depends(get_db),
):
    """
    Scenario 11: Tariff announcement on a region — costs jump overnight.
    Core-Guard recalculates with new costs; Ghost-Writer evaluates US alternates.
    """
```

Implement by:
1. Find all suppliers in the target region
2. Recalculate part costs with tariff
3. Find alternate suppliers outside the region
4. Compare tariffed cost vs. alternate supplier cost
5. Generate POs for parts where switching is cheaper

**Step 3: Add Scenario 12 — MOQ Trap**

```python
@router.post("/simulate/moq-trap", response_model=MOQTrapResponse)
async def simulate_moq_trap(
    part_id: str = Query(default="LED-201"),
    needed_qty: int = Query(default=80, ge=1),
    db: Session = Depends(get_db),
):
    """
    Scenario 12: Need fewer units than MOQ — buy excess or pay small-lot premium?
    """
```

**Step 4: Add Scenario 13 — Military Surge**

```python
@router.post("/simulate/military-surge", response_model=MilitarySurgeResponse)
async def simulate_military_surge(
    db: Session = Depends(get_db),
):
    """
    Scenario 13: SO-MIL-001 doubles from 200 to 400 units, 21-day deadline.
    Dispatcher triages VIP priority; Core-Guard ring-fences across product lines.
    """
```

**Step 5: Add Scenario 14 — Semiconductor Allocation**

```python
@router.post("/simulate/semiconductor-allocation", response_model=SemiconductorAllocationResponse)
async def simulate_semiconductor_allocation(
    part_id: str = Query(default="MCU-241"),
    capacity_reduction_pct: float = Query(default=60.0, ge=10.0, le=90.0),
    allocation_weeks: int = Query(default=26, ge=4, le=52),
    db: Session = Depends(get_db),
):
    """
    Scenario 14: Supplier announces allocation — capacity drops 60%.
    Part Agent recalculates runway; system evaluates product mix prioritization.
    """
```

**Step 6: Add Scenario 15 — Seasonal Ramp**

```python
@router.post("/simulate/seasonal-ramp", response_model=SeasonalRampResponse)
async def simulate_seasonal_ramp(
    deviation_pct: float = Query(default=40.0, ge=10.0, le=100.0),
    db: Session = Depends(get_db),
):
    """
    Scenario 15: Peak season orders arrive above forecast.
    AURA detects deviation; Core-Guard pre-positions inventory.
    """
```

**Step 7: Write integration tests for each new endpoint**

Create: `backend/tests/test_new_simulations.py`

Each test should:
1. Call the endpoint
2. Assert response status is "success"
3. Assert logs are non-empty
4. Assert scenario-specific fields are populated

**Step 8: Run all tests**

Run: `cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend && python -m pytest tests/ -v`
Expected: All pass.

**Step 9: Commit**

```bash
git add backend/routers/simulations.py backend/schemas.py backend/tests/test_new_simulations.py
git commit -m "feat: add 6 new simulation scenarios (contract, tariff, MOQ, military, semiconductor, seasonal)"
```

---

## Task 10: Update Frontend API Client and GodMode UI

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/GodMode.tsx`

**Step 1: Add API methods for new scenarios**

Add to `api.ts`:

```typescript
async simulateContractExhaustion(contractNumber: string = "BPA-CREE-2026") {
  return this.post(`/api/simulate/contract-exhaustion?contract_number=${contractNumber}`);
},

async simulateTariffShock(region: string = "CHINA", increasePct: number = 25) {
  return this.post(`/api/simulate/tariff-shock?region=${region}&increase_pct=${increasePct}`);
},

async simulateMoqTrap(partId: string = "LED-201", neededQty: number = 80) {
  return this.post(`/api/simulate/moq-trap?part_id=${partId}&needed_qty=${neededQty}`);
},

async simulateMilitarySurge() {
  return this.post("/api/simulate/military-surge");
},

async simulateSemiconductorAllocation(partId: string = "MCU-241", reductionPct: number = 60) {
  return this.post(`/api/simulate/semiconductor-allocation?part_id=${partId}&capacity_reduction_pct=${reductionPct}`);
},

async simulateSeasonalRamp(deviationPct: number = 40) {
  return this.post(`/api/simulate/seasonal-ramp?deviation_pct=${deviationPct}`);
},
```

**Step 2: Add 6 new scenario buttons to GodMode.tsx**

Add a new section "Supply Chain Scenarios" with buttons for the 6 new scenarios, following the existing button pattern in the component.

Each button should:
- Have a unique icon and color
- Call the corresponding API method
- Show running/success/error status
- Call `onSwitchToLogs()` when triggered

**Step 3: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/GodMode.tsx
git commit -m "feat: add frontend triggers for 6 new simulation scenarios"
```

---

## Task 11: Update InventoryCards for Expanded Part List

**Files:**
- Modify: `frontend/src/components/InventoryCards.tsx`

**Step 1: Add category filtering/grouping**

With ~55 parts, the inventory grid needs grouping. Add tabs or collapsible sections:
- Finished Goods
- Sub-Assemblies
- Components
- Services

**Step 2: Add supplier tier badge**

Show the supplier tier (T1/T2/T3/SVC) next to the supplier name on each card.

**Step 3: Verify with dev server**

Start the dev server and verify the inventory cards display correctly with the expanded dataset.

**Step 4: Commit**

```bash
git add frontend/src/components/InventoryCards.tsx
git commit -m "feat: add category grouping and supplier tier badges to inventory cards"
```

---

## Task 12: Final Integration Test and Cleanup

**Files:**
- Run: all tests
- Run: seed + backend + frontend

**Step 1: Delete old database and re-seed**

```bash
cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend
rm -f coreguard.db
python seed.py
```

**Step 2: Run full test suite**

```bash
cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend
python -m pytest tests/ -v --tb=short
```
Expected: All tests pass.

**Step 3: Start backend and verify API**

```bash
cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/backend
uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
```

Verify in browser or curl:
- `GET /api/inventory` returns ~55 parts
- `GET /api/suppliers` returns enriched supplier data
- `POST /api/simulate/spike?sku=FL-001-T&multiplier=3` runs with multi-level BOM

**Step 4: Start frontend and verify UI**

```bash
cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/frontend
npm run dev
```

Verify:
- Inventory cards show all parts grouped by category
- GodMode shows all 15 simulation scenarios
- Running a simulation streams logs correctly

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration fixes for realistic seed data"
```

**Step 6: Run lint**

```bash
cd /Users/thisismalhotra/projects/ClaudeCode/CoreGuard/frontend
npm run lint
```
Fix any lint errors.

**Step 7: Final commit**

```bash
git add -A
git commit -m "chore: lint fixes and final cleanup for realistic seed data feature"
```
