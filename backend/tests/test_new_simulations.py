"""Integration tests for the 6 new simulation endpoints (Scenarios 10-15)."""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from database.models import (
    Base, Supplier, Part, Inventory, BOMEntry, DemandForecast, SalesOrder,
    SupplierContract, AlternateSupplier,
    PartCategory, CriticalityLevel, SalesOrderStatus,
    SupplierTier, SupplierRegion, ContractType, ContractStatus,
)
from database.connection import get_db
from main import app


@pytest.fixture
def client():
    """TestClient with thread-safe in-memory SQLite and minimal seed data."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    # --- Seed minimal data needed for simulation endpoints ---
    cree = Supplier(
        name="CREE Inc.", contact_email="sales@cree.com", lead_time_days=42,
        reliability_score=0.94, tier=SupplierTier.TIER_1, region=SupplierRegion.US,
        minimum_order_qty=500, capacity_per_month=15000, is_active=True,
    )
    luminus = Supplier(
        name="Luminus Devices", contact_email="sales@luminus.com", lead_time_days=56,
        reliability_score=0.86, tier=SupplierTier.TIER_1, region=SupplierRegion.US, is_active=True,
    )
    wurth = Supplier(
        name="Wurth Elektronik", contact_email="sales@wurth.com", lead_time_days=28,
        reliability_score=0.88, tier=SupplierTier.TIER_1, region=SupplierRegion.GERMANY, is_active=True,
    )
    samsung = Supplier(
        name="Samsung SDI", contact_email="orders@samsungsdi.com", lead_time_days=35,
        reliability_score=0.92, tier=SupplierTier.TIER_1, region=SupplierRegion.SOUTH_KOREA, is_active=True,
    )
    session.add_all([cree, luminus, wurth, samsung])
    session.flush()

    # Parts
    fl001t = Part(part_id="FL-001-T", description="Tactical Flashlight", category=PartCategory.FINISHED_GOOD, unit_cost=0.0, criticality=CriticalityLevel.CRITICAL)
    fl001s = Part(part_id="FL-001-S", description="Standard Flashlight", category=PartCategory.FINISHED_GOOD, unit_cost=0.0, criticality=CriticalityLevel.HIGH)
    led201 = Part(part_id="LED-201", description="CREE XHP70.3 HI", category=PartCategory.COMPONENT, unit_cost=11.50, supplier_id=cree.id, criticality=CriticalityLevel.CRITICAL)
    mcu241 = Part(part_id="MCU-241", description="Microcontroller (ATtiny1616)", category=PartCategory.COMPONENT, unit_cost=1.85, supplier_id=wurth.id, criticality=CriticalityLevel.CRITICAL)
    ch101 = Part(part_id="CH-101", description="Modular Chassis", category=PartCategory.COMMON_CORE, unit_cost=12.50, supplier_id=cree.id, criticality=CriticalityLevel.CRITICAL)
    # Sub-assemblies
    sa_led = Part(part_id="SA-LED-100", description="LED Module Assembly", category=PartCategory.SUB_ASSEMBLY, unit_cost=0.0, criticality=CriticalityLevel.CRITICAL)
    sa_elc = Part(part_id="SA-ELC-140", description="Electronics/Control Module", category=PartCategory.SUB_ASSEMBLY, unit_cost=0.0, criticality=CriticalityLevel.CRITICAL)
    # Headlamp
    hl002p = Part(part_id="HL-002-P", description="Pro Headlamp", category=PartCategory.FINISHED_GOOD, unit_cost=0.0, criticality=CriticalityLevel.HIGH)
    session.add_all([fl001t, fl001s, led201, mcu241, ch101, sa_led, sa_elc, hl002p])
    session.flush()

    # Inventory
    session.add_all([
        Inventory(part_id=fl001t.id, on_hand=0, safety_stock=0, reserved=0, ring_fenced_qty=0, daily_burn_rate=8.0),
        Inventory(part_id=fl001s.id, on_hand=0, safety_stock=0, reserved=0, ring_fenced_qty=0, daily_burn_rate=12.0),
        Inventory(part_id=led201.id, on_hand=1450, safety_stock=625, reserved=100, ring_fenced_qty=0, daily_burn_rate=34.0),
        Inventory(part_id=mcu241.id, on_hand=380, safety_stock=500, reserved=0, ring_fenced_qty=0, daily_burn_rate=34.0),
        Inventory(part_id=ch101.id, on_hand=500, safety_stock=200, reserved=50, ring_fenced_qty=0, daily_burn_rate=40.0),
        Inventory(part_id=hl002p.id, on_hand=80, safety_stock=30, reserved=0, ring_fenced_qty=0, daily_burn_rate=5.0),
    ])
    session.flush()

    # BOM: FL-001-T -> CH-101 (single-level), HL-002-P -> SA-LED-100 -> LED-201, SA-ELC-140 -> MCU-241
    session.add_all([
        BOMEntry(parent_id=fl001t.id, component_id=ch101.id, quantity_per=1),
        BOMEntry(parent_id=hl002p.id, component_id=sa_led.id, quantity_per=1),
        BOMEntry(parent_id=hl002p.id, component_id=sa_elc.id, quantity_per=1),
        BOMEntry(parent_id=sa_led.id, component_id=led201.id, quantity_per=1),
        BOMEntry(parent_id=sa_elc.id, component_id=mcu241.id, quantity_per=1),
    ])
    session.flush()

    # Demand forecast
    session.add(DemandForecast(part_id=fl001t.id, forecast_qty=100, actual_qty=0))
    session.flush()

    # Sales orders
    session.add_all([
        SalesOrder(order_number="SO-VIP-001", part_id=fl001t.id, quantity=50, priority="VIP", status=SalesOrderStatus.OPEN),
        SalesOrder(order_number="SO-STD-002", part_id=fl001s.id, quantity=100, priority="NORMAL", status=SalesOrderStatus.OPEN),
    ])
    session.flush()

    # Supplier contract
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

    # Alternate supplier
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

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    session.close()


class TestContractExhaustion:
    def test_contract_exhaustion_returns_success(self, client):
        resp = client.post("/api/simulate/contract-exhaustion?contract_number=BPA-CREE-2026")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "simulation_complete"
        assert data["scenario"] == "CONTRACT_EXHAUSTION"
        assert data["contract_number"] == "BPA-CREE-2026"
        assert len(data["logs"]) > 0

    def test_contract_exhaustion_unknown_contract(self, client):
        resp = client.post("/api/simulate/contract-exhaustion?contract_number=NONEXISTENT")
        assert resp.status_code == 404

    def test_contract_exhaustion_has_recommendation(self, client):
        resp = client.post("/api/simulate/contract-exhaustion?contract_number=BPA-CREE-2026")
        data = resp.json()
        assert data["recommendation"] in ("EXTEND", "SPOT_BUY", "RENEGOTIATE")
        assert data["remaining_qty"] >= 0
        assert data["remaining_value"] >= 0


class TestTariffShock:
    def test_tariff_shock_returns_success(self, client):
        resp = client.post("/api/simulate/tariff-shock?region=US&increase_pct=25")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "simulation_complete"
        assert data["scenario"] == "TARIFF_SHOCK"
        assert data["cost_increase_pct"] == 25.0
        assert len(data["logs"]) > 0

    def test_tariff_shock_invalid_region(self, client):
        resp = client.post("/api/simulate/tariff-shock?region=MARS&increase_pct=25")
        assert resp.status_code == 400

    def test_tariff_shock_finds_affected_parts(self, client):
        resp = client.post("/api/simulate/tariff-shock?region=US&increase_pct=30")
        data = resp.json()
        assert isinstance(data["affected_suppliers"], list)
        assert isinstance(data["affected_parts"], list)


class TestMOQTrap:
    def test_moq_trap_returns_success(self, client):
        resp = client.post("/api/simulate/moq-trap?part_id=LED-201&needed_qty=80")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "simulation_complete"
        assert data["scenario"] == "MOQ_TRAP"
        assert data["part_id"] == "LED-201"
        assert data["needed_qty"] == 80
        assert len(data["logs"]) > 0

    def test_moq_trap_unknown_part(self, client):
        resp = client.post("/api/simulate/moq-trap?part_id=NOPE&needed_qty=10")
        assert resp.status_code == 404

    def test_moq_trap_has_recommendation(self, client):
        resp = client.post("/api/simulate/moq-trap?part_id=LED-201&needed_qty=80")
        data = resp.json()
        assert data["recommendation"] in ("BUY_MOQ", "SMALL_LOT", "WAIT")
        assert data["moq"] >= 1
        assert data["carry_cost"] >= 0


class TestMilitarySurge:
    def test_military_surge_returns_success(self, client):
        resp = client.post("/api/simulate/military-surge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "simulation_complete"
        assert data["scenario"] == "MILITARY_SURGE"
        assert data["new_qty"] == data["original_qty"] * 2
        assert len(data["logs"]) > 0

    def test_military_surge_has_ring_fencing(self, client):
        resp = client.post("/api/simulate/military-surge")
        data = resp.json()
        assert isinstance(data["ring_fenced_parts"], list)
        assert isinstance(data["displaced_orders"], list)


class TestSemiconductorAllocation:
    def test_semiconductor_allocation_returns_success(self, client):
        resp = client.post("/api/simulate/semiconductor-allocation?part_id=MCU-241&capacity_reduction_pct=60")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "simulation_complete"
        assert data["scenario"] == "SEMICONDUCTOR_ALLOCATION"
        assert data["part_id"] == "MCU-241"
        assert data["reduced_capacity"] < data["original_capacity"]
        assert len(data["logs"]) > 0

    def test_semiconductor_allocation_unknown_part(self, client):
        resp = client.post("/api/simulate/semiconductor-allocation?part_id=NOPE")
        assert resp.status_code == 404

    def test_semiconductor_allocation_has_product_mix(self, client):
        resp = client.post("/api/simulate/semiconductor-allocation?part_id=MCU-241")
        data = resp.json()
        assert isinstance(data["affected_products"], list)
        assert isinstance(data["product_mix_recommendation"], list)


class TestSeasonalRamp:
    def test_seasonal_ramp_returns_success(self, client):
        resp = client.post("/api/simulate/seasonal-ramp?deviation_pct=40")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "simulation_complete"
        assert data["scenario"] == "SEASONAL_RAMP"
        assert data["forecast_deviation_pct"] == 40.0
        assert len(data["logs"]) > 0

    def test_seasonal_ramp_has_affected_products(self, client):
        resp = client.post("/api/simulate/seasonal-ramp?deviation_pct=40")
        data = resp.json()
        assert isinstance(data["affected_products"], list)
        assert isinstance(data["pre_positioned_parts"], list)
