"""
Shared test fixtures for Core-Guard backend tests.

Creates an in-memory SQLite database and seeds it with the FL-001 dataset
plus multi-product data so each test gets a clean, isolated DB state.
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base, Supplier, Part, Inventory, BOMEntry, DemandForecast, SalesOrder,
    SupplierContract, AlternateSupplier,
    PartCategory, CriticalityLevel, SalesOrderStatus,
    SupplierTier, SupplierRegion, ContractType, ContractStatus,
)


@pytest.fixture
def db():
    """Yield a fresh in-memory SQLite session with FL-001 seed data."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # --- Seed suppliers (original 3 + new enriched suppliers) ---
    aluforge = Supplier(name="AluForge", contact_email="sales@aluforge.com", lead_time_days=5, reliability_score=0.95, is_active=True)
    microconnect = Supplier(name="MicroConnect", contact_email="orders@microconnect.com", lead_time_days=7, reliability_score=0.90, is_active=True)
    precision_optic = Supplier(name="Precision Optic", contact_email="info@precisionoptic.com", lead_time_days=10, reliability_score=0.85, is_active=True)
    # New enriched suppliers for multi-product tests
    cree = Supplier(
        name="CREE Inc.", contact_email="sales@cree.com", lead_time_days=42,
        reliability_score=0.94, tier=SupplierTier.TIER_1, region=SupplierRegion.US,
        expedite_lead_time_days=28, minimum_order_qty=500, capacity_per_month=15000,
        certifications=json.dumps(["ISO 9001", "ITAR"]),
        risk_factors=json.dumps(["single source"]),
    )
    samsung = Supplier(
        name="Samsung SDI", contact_email="orders@samsungsdi.com", lead_time_days=35,
        reliability_score=0.92, tier=SupplierTier.TIER_1, region=SupplierRegion.SOUTH_KOREA,
        expedite_lead_time_days=21, minimum_order_qty=1000,
        risk_factors=json.dumps(["geopolitical"]),
    )
    wurth = Supplier(
        name="Wurth Elektronik", contact_email="sales@wurth.com", lead_time_days=28,
        reliability_score=0.88, tier=SupplierTier.TIER_1, region=SupplierRegion.GERMANY,
        expedite_lead_time_days=18, minimum_order_qty=250,
    )
    luminus = Supplier(
        name="Luminus Devices", contact_email="sales@luminus.com", lead_time_days=56,
        reliability_score=0.86, tier=SupplierTier.TIER_1, region=SupplierRegion.US,
    )
    session.add_all([aluforge, microconnect, precision_optic, cree, samsung, wurth, luminus])
    session.flush()

    # --- Seed parts (original 5 + new multi-level parts) ---
    fl001t = Part(part_id="FL-001-T", description="Tactical Flashlight", category=PartCategory.FINISHED_GOOD, unit_cost=0.0, criticality=CriticalityLevel.CRITICAL)
    fl001s = Part(part_id="FL-001-S", description="Standard Flashlight", category=PartCategory.FINISHED_GOOD, unit_cost=0.0, criticality=CriticalityLevel.HIGH)
    ch101 = Part(part_id="CH-101", description="Modular Chassis", category=PartCategory.COMMON_CORE, unit_cost=12.50, supplier_id=aluforge.id, criticality=CriticalityLevel.CRITICAL, lead_time_sensitivity=0.9, substitute_pool_size=1)
    sw303 = Part(part_id="SW-303", description="Switch Assembly", category=PartCategory.COMMON_CORE, unit_cost=4.75, supplier_id=microconnect.id, criticality=CriticalityLevel.HIGH, lead_time_sensitivity=0.6, substitute_pool_size=2)
    lns505 = Part(part_id="LNS-505", description="Optic Lens", category=PartCategory.COMMON_CORE, unit_cost=8.00, supplier_id=precision_optic.id, criticality=CriticalityLevel.MEDIUM, lead_time_sensitivity=0.5, substitute_pool_size=1)
    # Sub-assemblies for multi-level BOM tests
    sa_led = Part(part_id="SA-LED-100", description="LED Module Assembly", category=PartCategory.SUB_ASSEMBLY, unit_cost=0.0, criticality=CriticalityLevel.CRITICAL)
    sa_pwr = Part(part_id="SA-PWR-110", description="Power Module", category=PartCategory.SUB_ASSEMBLY, unit_cost=0.0, criticality=CriticalityLevel.HIGH)
    sa_elc = Part(part_id="SA-ELC-140", description="Electronics/Control Module", category=PartCategory.SUB_ASSEMBLY, unit_cost=0.0, criticality=CriticalityLevel.CRITICAL)
    # Leaf components
    led201 = Part(part_id="LED-201", description="CREE XHP70.3 HI", category=PartCategory.COMPONENT, unit_cost=11.50, supplier_id=cree.id, criticality=CriticalityLevel.CRITICAL, lead_time_sensitivity=0.95, substitute_pool_size=1)
    pcb202 = Part(part_id="PCB-202", description="LED Driver PCB", category=PartCategory.COMPONENT, unit_cost=3.20, supplier_id=wurth.id, criticality=CriticalityLevel.HIGH, lead_time_sensitivity=0.7, substitute_pool_size=2)
    bat211 = Part(part_id="BAT-211", description="18650 Li-Ion Cell", category=PartCategory.COMPONENT, unit_cost=4.75, supplier_id=samsung.id, criticality=CriticalityLevel.CRITICAL, lead_time_sensitivity=0.9, substitute_pool_size=1)
    mcu241 = Part(part_id="MCU-241", description="Microcontroller (ATtiny1616)", category=PartCategory.COMPONENT, unit_cost=1.85, supplier_id=wurth.id, criticality=CriticalityLevel.CRITICAL, lead_time_sensitivity=0.95, substitute_pool_size=1)
    gkt223 = Part(part_id="GKT-223", description="Lens O-Ring", category=PartCategory.COMPONENT, unit_cost=0.12, supplier_id=precision_optic.id, criticality=CriticalityLevel.LOW, lead_time_sensitivity=0.2, substitute_pool_size=2)
    # Headlamp finished good for contention tests
    hl002p = Part(part_id="HL-002-P", description="Pro Headlamp", category=PartCategory.FINISHED_GOOD, unit_cost=0.0, criticality=CriticalityLevel.HIGH)

    session.add_all([fl001t, fl001s, ch101, sw303, lns505,
                     sa_led, sa_pwr, sa_elc,
                     led201, pcb202, bat211, mcu241, gkt223,
                     hl002p])
    session.flush()

    # --- Seed inventory ---
    session.add_all([
        Inventory(part_id=fl001t.id, on_hand=0, safety_stock=0, reserved=0, ring_fenced_qty=0, daily_burn_rate=8.0),
        Inventory(part_id=fl001s.id, on_hand=0, safety_stock=0, reserved=0, ring_fenced_qty=0, daily_burn_rate=12.0),
        Inventory(part_id=ch101.id, on_hand=500, safety_stock=200, reserved=50, ring_fenced_qty=0, daily_burn_rate=40.0),
        Inventory(part_id=sw303.id, on_hand=800, safety_stock=300, reserved=100, ring_fenced_qty=0, daily_burn_rate=25.0),
        Inventory(part_id=lns505.id, on_hand=600, safety_stock=250, reserved=50, ring_fenced_qty=0, daily_burn_rate=18.0),
        # New component inventory
        Inventory(part_id=led201.id, on_hand=1450, safety_stock=625, reserved=100, ring_fenced_qty=0, daily_burn_rate=34.0),
        Inventory(part_id=pcb202.id, on_hand=900, safety_stock=375, reserved=50, ring_fenced_qty=0, daily_burn_rate=34.0),
        Inventory(part_id=bat211.id, on_hand=1100, safety_stock=540, reserved=50, ring_fenced_qty=0, daily_burn_rate=29.0),
        Inventory(part_id=mcu241.id, on_hand=380, safety_stock=500, reserved=0, ring_fenced_qty=0, daily_burn_rate=34.0),
        Inventory(part_id=gkt223.id, on_hand=2800, safety_stock=750, reserved=0, ring_fenced_qty=0, daily_burn_rate=34.0),
        Inventory(part_id=hl002p.id, on_hand=80, safety_stock=30, reserved=0, ring_fenced_qty=0, daily_burn_rate=5.0),
    ])
    session.flush()

    # --- Seed BOM ---
    # Original: FL-001-T uses all 3 legacy components (single-level, unchanged)
    session.add_all([
        BOMEntry(parent_id=fl001t.id, component_id=ch101.id, quantity_per=1),
        BOMEntry(parent_id=fl001t.id, component_id=sw303.id, quantity_per=2),
        BOMEntry(parent_id=fl001t.id, component_id=lns505.id, quantity_per=1),
    ])
    # Sub-assembly → component chains (Level 2, available for recursive BOM tests)
    session.add_all([
        # SA-LED-100 children
        BOMEntry(parent_id=sa_led.id, component_id=led201.id, quantity_per=1),
        BOMEntry(parent_id=sa_led.id, component_id=pcb202.id, quantity_per=1),
        # SA-PWR-110 children
        BOMEntry(parent_id=sa_pwr.id, component_id=bat211.id, quantity_per=1),
        # SA-ELC-140 children
        BOMEntry(parent_id=sa_elc.id, component_id=mcu241.id, quantity_per=1),
    ])
    # HL-002-P uses multi-level BOM (for contention and recursive BOM tests)
    session.add_all([
        BOMEntry(parent_id=hl002p.id, component_id=sa_led.id, quantity_per=1),
        BOMEntry(parent_id=hl002p.id, component_id=sa_pwr.id, quantity_per=1),
        BOMEntry(parent_id=hl002p.id, component_id=sa_elc.id, quantity_per=1),
    ])
    session.flush()

    # --- Seed demand forecast ---
    session.add(DemandForecast(part_id=fl001t.id, forecast_qty=100, actual_qty=0))
    session.flush()

    # --- Seed sales orders (for ring-fencing tests) ---
    session.add_all([
        SalesOrder(order_number="SO-VIP-001", part_id=fl001t.id, quantity=50, priority="VIP", status=SalesOrderStatus.OPEN),
        SalesOrder(order_number="SO-STD-002", part_id=fl001s.id, quantity=100, priority="NORMAL", status=SalesOrderStatus.OPEN),
    ])
    session.flush()

    # --- Seed supplier contract (for blanket PO tests) ---
    session.add(SupplierContract(
        contract_number="BPA-CREE-2026",
        supplier_id=cree.id,
        contract_type=ContractType.BLANKET_PO,
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        total_committed_value=180000.0,
        total_committed_qty=15000,
        released_value=120000.0,
        released_qty=10000,
        price_schedule=json.dumps([{"part_id": "LED-201", "unit_price": 11.50, "spot_price": 12.80}]),
        status=ContractStatus.ACTIVE,
    ))
    session.flush()

    # --- Seed alternate supplier mapping ---
    session.add(AlternateSupplier(
        part_id=led201.id,
        primary_supplier_id=cree.id,
        alternate_supplier_id=luminus.id,
        cost_premium_pct=22.0,
        lead_time_delta_days=14,
        notes="Lower lumen output",
    ))
    session.flush()

    session.commit()
    yield session
    session.close()
