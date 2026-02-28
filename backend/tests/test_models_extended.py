"""Tests for the extended models: SupplierContract, AlternateSupplier, multi-level BOM."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    AlternateSupplier,
    Base,
    BOMEntry,
    ContractStatus,
    ContractType,
    CriticalityLevel,
    Part,
    PartCategory,
    Supplier,
    SupplierContract,
    SupplierRegion,
    SupplierTier,
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
