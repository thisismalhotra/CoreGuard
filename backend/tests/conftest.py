"""
Shared test fixtures for Core-Guard backend tests.

Creates an in-memory SQLite database and seeds it with the FL-001 dataset
so each test gets a clean, isolated DB state.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base, Supplier, Part, Inventory, BOMEntry, DemandForecast, SalesOrder,
    PartCategory, CriticalityLevel, SalesOrderStatus,
)


@pytest.fixture
def db():
    """Yield a fresh in-memory SQLite session with FL-001 seed data."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # --- Seed suppliers ---
    aluforge = Supplier(name="AluForge", contact_email="sales@aluforge.com", lead_time_days=5, reliability_score=0.95, is_active=True)
    microconnect = Supplier(name="MicroConnect", contact_email="orders@microconnect.com", lead_time_days=7, reliability_score=0.90, is_active=True)
    precision_optic = Supplier(name="Precision Optic", contact_email="info@precisionoptic.com", lead_time_days=10, reliability_score=0.85, is_active=True)
    session.add_all([aluforge, microconnect, precision_optic])
    session.flush()

    # --- Seed parts ---
    fl001t = Part(part_id="FL-001-T", description="Tactical Flashlight", category=PartCategory.FINISHED_GOOD, unit_cost=0.0, criticality=CriticalityLevel.CRITICAL)
    fl001s = Part(part_id="FL-001-S", description="Standard Flashlight", category=PartCategory.FINISHED_GOOD, unit_cost=0.0, criticality=CriticalityLevel.HIGH)
    ch101 = Part(part_id="CH-101", description="Modular Chassis", category=PartCategory.COMMON_CORE, unit_cost=12.50, supplier_id=aluforge.id, criticality=CriticalityLevel.CRITICAL, lead_time_sensitivity=0.9, substitute_pool_size=1)
    sw303 = Part(part_id="SW-303", description="Switch Assembly", category=PartCategory.COMMON_CORE, unit_cost=4.75, supplier_id=microconnect.id, criticality=CriticalityLevel.HIGH, lead_time_sensitivity=0.6, substitute_pool_size=2)
    lns505 = Part(part_id="LNS-505", description="Optic Lens", category=PartCategory.COMMON_CORE, unit_cost=8.00, supplier_id=precision_optic.id, criticality=CriticalityLevel.MEDIUM, lead_time_sensitivity=0.5, substitute_pool_size=1)
    session.add_all([fl001t, fl001s, ch101, sw303, lns505])
    session.flush()

    # --- Seed inventory (includes PRD §8 daily_burn_rate and §11 ring_fenced_qty) ---
    session.add_all([
        Inventory(part_id=fl001t.id, on_hand=0, safety_stock=0, reserved=0, ring_fenced_qty=0, daily_burn_rate=8.0),
        Inventory(part_id=fl001s.id, on_hand=0, safety_stock=0, reserved=0, ring_fenced_qty=0, daily_burn_rate=12.0),
        Inventory(part_id=ch101.id, on_hand=500, safety_stock=200, reserved=50, ring_fenced_qty=0, daily_burn_rate=40.0),
        Inventory(part_id=sw303.id, on_hand=800, safety_stock=300, reserved=100, ring_fenced_qty=0, daily_burn_rate=25.0),
        Inventory(part_id=lns505.id, on_hand=600, safety_stock=250, reserved=50, ring_fenced_qty=0, daily_burn_rate=18.0),
    ])
    session.flush()

    # --- Seed BOM (FL-001-T uses all 3 components) ---
    session.add_all([
        BOMEntry(parent_id=fl001t.id, component_id=ch101.id, quantity_per=1),
        BOMEntry(parent_id=fl001t.id, component_id=sw303.id, quantity_per=2),
        BOMEntry(parent_id=fl001t.id, component_id=lns505.id, quantity_per=1),
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

    session.commit()
    yield session
    session.close()
