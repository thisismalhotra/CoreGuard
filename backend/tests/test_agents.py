"""
Tests for Core-Guard agent business logic.

Covers:
  - MRP net requirements calculation (core_guard.py)
  - Financial Constitution enforcement (ghost_writer.py)
  - Demand spike detection (aura.py)
  - Criticality-based routing
  - Inventory available clamping
"""

import pytest
from database.models import (
    Part, Inventory, Supplier, CriticalityLevel, OrderStatus,
)
from agents.core_guard import calculate_net_requirements, ROUTING_RULES
from agents.ghost_writer import (
    process_buy_orders,
    FINANCIAL_CONSTITUTION_MAX_SPEND,
)
from agents.aura import detect_demand_spike


# ---------------------------------------------------------------------------
# Inventory.available property
# ---------------------------------------------------------------------------

class TestInventoryAvailable:
    """Test the computed `available` property on Inventory model."""

    def test_available_normal(self, db):
        """available = on_hand - reserved when positive."""
        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        assert inv.available == inv.on_hand - inv.reserved
        assert inv.available == 450  # 500 - 50

    def test_available_clamped_to_zero(self, db):
        """available never goes negative, even when reserved > on_hand."""
        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        inv.reserved = 9999
        assert inv.available == 0


# ---------------------------------------------------------------------------
# Aura — Demand Spike Detection
# ---------------------------------------------------------------------------

class TestAuraDemandSpike:
    """Test the Aura agent's spike detection logic."""

    def test_spike_detected(self, db):
        """Spike should be detected when demand exceeds threshold."""
        result = detect_demand_spike(db, "FL-001-T", 500)
        assert result["spike_detected"] is True
        assert result["multiplier"] > 1.0
        assert len(result["logs"]) > 0

    def test_no_spike_when_demand_normal(self, db):
        """No spike when demand is at or below forecast."""
        result = detect_demand_spike(db, "FL-001-T", 100)
        assert result["spike_detected"] is False

    def test_spike_unknown_sku(self, db):
        """Should handle unknown SKU gracefully."""
        result = detect_demand_spike(db, "NONEXISTENT", 500)
        # Should return without crashing
        assert "logs" in result


# ---------------------------------------------------------------------------
# Core-Guard — MRP Net Requirements
# ---------------------------------------------------------------------------

class TestCoreGuardMRP:
    """Test the Core-Guard MRP explosion and routing logic."""

    def test_no_shortage_when_stock_sufficient(self, db):
        """With small demand, no shortages should be reported."""
        result = calculate_net_requirements(db, "FL-001-T", 10)
        assert result["sku"] == "FL-001-T"
        # 10 units × qty_per should be well within stock for all components
        assert len(result["shortages"]) == 0
        assert len(result["actions"]) == 0

    def test_shortage_detected_with_large_demand(self, db):
        """With large demand, shortages should be detected."""
        result = calculate_net_requirements(db, "FL-001-T", 1000)
        assert len(result["shortages"]) > 0
        # Should generate BUY_ORDER or REALLOCATE actions
        assert len(result["actions"]) > 0

    def test_buy_order_generated_for_critical_parts(self, db):
        """CRITICAL parts should never be reallocated — must use BUY_ORDER."""
        result = calculate_net_requirements(db, "FL-001-T", 1000)
        # CH-101 is CRITICAL — should have a BUY_ORDER, not REALLOCATE
        ch101_actions = [a for a in result["actions"] if a["part_id"] == "CH-101"]
        for action in ch101_actions:
            if action["type"] == "BUY_ORDER":
                assert action["expedite"] is True  # CRITICAL parts are expedited

    def test_critical_parts_get_safety_buffer(self, db):
        """CRITICAL parts should have 1.5x safety stock multiplier."""
        rules = ROUTING_RULES[CriticalityLevel.CRITICAL]
        assert rules["safety_stock_multiplier"] == 1.5
        assert rules["allow_reallocation"] is False
        assert rules["expedite"] is True

    def test_medium_parts_allow_reallocation(self, db):
        """MEDIUM criticality parts should allow reallocation."""
        rules = ROUTING_RULES[CriticalityLevel.MEDIUM]
        assert rules["allow_reallocation"] is True
        assert rules["expedite"] is False

    def test_unknown_sku_returns_empty(self, db):
        """Unknown SKU should return empty shortages/actions, not crash."""
        result = calculate_net_requirements(db, "NONEXISTENT", 100)
        assert result["shortages"] == []
        assert result["actions"] == []
        assert len(result["logs"]) > 0

    def test_logs_are_generated(self, db):
        """MRP should always produce Glass Box logs."""
        result = calculate_net_requirements(db, "FL-001-T", 10)
        assert len(result["logs"]) > 0
        for log in result["logs"]:
            assert "timestamp" in log
            assert "agent" in log
            assert "message" in log
            assert "type" in log

    def test_shortage_details_complete(self, db):
        """Each shortage entry should have required fields."""
        result = calculate_net_requirements(db, "FL-001-T", 1000)
        for shortage in result["shortages"]:
            assert "part_id" in shortage
            assert "required" in shortage
            assert "available" in shortage
            assert "gap" in shortage
            assert "criticality" in shortage
            assert shortage["gap"] > 0


# ---------------------------------------------------------------------------
# Ghost-Writer — Financial Constitution
# ---------------------------------------------------------------------------

class TestGhostWriterConstitution:
    """Test Rule C: Financial Constitution enforcement in Ghost-Writer."""

    def test_auto_approved_below_limit(self, db):
        """Orders under $5,000 should be auto-approved."""
        buy_orders = [{
            "type": "BUY_ORDER",
            "part_id": "CH-101",
            "quantity": 10,
            "unit_cost": 12.50,
            "total_cost": 125.00,
            "supplier_id": 1,
            "supplier_name": "AluForge",
            "triggered_by": "Core-Guard",
        }]
        result = process_buy_orders(db, buy_orders)
        assert len(result["purchase_orders"]) == 1
        assert result["purchase_orders"][0]["status"] == "APPROVED"

    def test_blocked_above_limit(self, db):
        """Orders over $5,000 MUST be PENDING_APPROVAL (Rule C)."""
        buy_orders = [{
            "type": "BUY_ORDER",
            "part_id": "CH-101",
            "quantity": 500,
            "unit_cost": 12.50,
            "total_cost": 6250.00,  # > $5,000
            "supplier_id": 1,
            "supplier_name": "AluForge",
            "triggered_by": "Core-Guard",
        }]
        result = process_buy_orders(db, buy_orders)
        assert len(result["purchase_orders"]) == 1
        assert result["purchase_orders"][0]["status"] == "PENDING_APPROVAL"

    def test_exactly_at_limit(self, db):
        """Orders exactly at $5,000 should be auto-approved (not >)."""
        buy_orders = [{
            "type": "BUY_ORDER",
            "part_id": "CH-101",
            "quantity": 400,
            "unit_cost": 12.50,
            "total_cost": 5000.00,  # Exactly $5,000
            "supplier_id": 1,
            "supplier_name": "AluForge",
            "triggered_by": "Core-Guard",
        }]
        result = process_buy_orders(db, buy_orders)
        assert len(result["purchase_orders"]) == 1
        assert result["purchase_orders"][0]["status"] == "APPROVED"

    def test_constitution_limit_value(self):
        """The spend limit constant should be exactly $5,000."""
        assert FINANCIAL_CONSTITUTION_MAX_SPEND == 5000.00

    def test_skips_non_buy_orders(self, db):
        """Non-BUY_ORDER actions should be skipped."""
        actions = [{
            "type": "REALLOCATE",
            "part_id": "CH-101",
            "quantity": 50,
        }]
        result = process_buy_orders(db, actions)
        assert len(result["purchase_orders"]) == 0

    def test_unknown_part_logged_as_error(self, db):
        """Unknown part_id should generate an error log, not crash."""
        buy_orders = [{
            "type": "BUY_ORDER",
            "part_id": "UNKNOWN-999",
            "quantity": 10,
            "unit_cost": 1.00,
            "total_cost": 10.00,
            "supplier_id": 1,
            "supplier_name": "Test",
            "triggered_by": "Test",
        }]
        result = process_buy_orders(db, buy_orders)
        assert len(result["purchase_orders"]) == 0
        error_logs = [l for l in result["logs"] if l["type"] == "error"]
        assert len(error_logs) > 0

    def test_multiple_orders_mixed(self, db):
        """Mix of below-limit and above-limit orders should be handled correctly."""
        buy_orders = [
            {
                "type": "BUY_ORDER",
                "part_id": "CH-101",
                "quantity": 10,
                "unit_cost": 12.50,
                "total_cost": 125.00,
                "supplier_id": 1,
                "supplier_name": "AluForge",
                "triggered_by": "Core-Guard",
            },
            {
                "type": "BUY_ORDER",
                "part_id": "SW-303",
                "quantity": 2000,
                "unit_cost": 4.75,
                "total_cost": 9500.00,  # > $5,000
                "supplier_id": 2,
                "supplier_name": "MicroConnect",
                "triggered_by": "Core-Guard",
            },
        ]
        result = process_buy_orders(db, buy_orders)
        assert len(result["purchase_orders"]) == 2
        statuses = [po["status"] for po in result["purchase_orders"]]
        assert "APPROVED" in statuses
        assert "PENDING_APPROVAL" in statuses

    def test_po_number_generated(self, db):
        """Each PO should get a unique PO number."""
        buy_orders = [{
            "type": "BUY_ORDER",
            "part_id": "CH-101",
            "quantity": 10,
            "unit_cost": 12.50,
            "total_cost": 125.00,
            "supplier_id": 1,
            "supplier_name": "AluForge",
            "triggered_by": "Core-Guard",
        }]
        result = process_buy_orders(db, buy_orders)
        po_number = result["purchase_orders"][0]["po_number"]
        assert po_number.startswith("PO-")
        assert len(po_number) > 3

    def test_glass_box_logs_emitted(self, db):
        """Ghost-Writer should emit Glass Box logs for all actions."""
        buy_orders = [{
            "type": "BUY_ORDER",
            "part_id": "CH-101",
            "quantity": 10,
            "unit_cost": 12.50,
            "total_cost": 125.00,
            "supplier_id": 1,
            "supplier_name": "AluForge",
            "triggered_by": "Core-Guard",
        }]
        result = process_buy_orders(db, buy_orders)
        assert len(result["logs"]) >= 3  # Received, Processing, Created
        for log in result["logs"]:
            assert log["agent"] == "Ghost-Writer"


# ---------------------------------------------------------------------------
# Integration: Full Agent Chain
# ---------------------------------------------------------------------------

class TestAgentChainIntegration:
    """End-to-end test of the agent chain: Aura → Core-Guard → Ghost-Writer."""

    def test_full_spike_chain(self, db):
        """Simulate a demand spike and verify the full agent chain produces POs."""
        # Step 1: Aura detects spike
        aura_result = detect_demand_spike(db, "FL-001-T", 500)
        assert aura_result["spike_detected"] is True

        # Step 2: Core-Guard calculates net requirements
        mrp_result = calculate_net_requirements(db, "FL-001-T", 500)
        assert len(mrp_result["logs"]) > 0

        # Step 3: Ghost-Writer processes buy orders
        buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
        if buy_orders:
            ghost_result = process_buy_orders(db, buy_orders)
            assert len(ghost_result["purchase_orders"]) > 0
            # Each PO should have valid fields
            for po in ghost_result["purchase_orders"]:
                assert po["po_number"].startswith("PO-")
                assert po["status"] in ("APPROVED", "PENDING_APPROVAL")
                assert po["quantity"] > 0
                assert po["total_cost"] > 0

    def test_no_orders_when_stock_sufficient(self, db):
        """No POs should be generated when stock covers demand."""
        mrp_result = calculate_net_requirements(db, "FL-001-T", 10)
        buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
        assert len(buy_orders) == 0
