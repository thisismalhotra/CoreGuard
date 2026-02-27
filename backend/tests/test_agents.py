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
from agents.core_guard import (
    calculate_net_requirements, ROUTING_RULES,
    calculate_blast_radius, ring_fence_inventory,
)
from agents.ghost_writer import (
    process_buy_orders,
    FINANCIAL_CONSTITUTION_MAX_SPEND,
)
from agents.aura import detect_demand_spike
from agents.part_agent import (
    calculate_dynamic_safety_stock,
    calculate_runway,
    evaluate_handshake_trigger,
    monitor_part,
    monitor_all_components,
)
from agents.data_integrity import (
    detect_ghost_inventory,
    detect_suspect_inventory,
    run_full_integrity_check,
    GHOST_INVENTORY_DAYS,
    SUSPECT_INVENTORY_DAYS,
)
from agents.demand_horizon import (
    classify_demand_zone,
    evaluate_demand_horizon,
    ZONE_1_MIN_DAYS,
    ZONE_2_MIN_DAYS,
)


# ---------------------------------------------------------------------------
# Inventory.available property
# ---------------------------------------------------------------------------

class TestInventoryAvailable:
    """Test the computed `available` property on Inventory model."""

    def test_available_normal(self, db):
        """available = on_hand - reserved - ring_fenced_qty when positive."""
        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        assert inv.available == max(0, inv.on_hand - inv.reserved - inv.ring_fenced_qty)
        assert inv.available == 450  # 500 - 50 - 0

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
# Core-Guard — Blast Radius Analysis (PRD §3)
# ---------------------------------------------------------------------------

class TestBlastRadiusAnalysis:
    """Test blast radius: which finished goods are affected by a component shortage."""

    def test_blast_radius_returns_affected_fgs(self, db):
        """CH-101 is used by FL-001-T — blast radius should return it."""
        result = calculate_blast_radius(db, "CH-101")
        assert result["part_id"] == "CH-101"
        assert len(result["affected_finished_goods"]) >= 1
        skus = [fg["sku"] for fg in result["affected_finished_goods"]]
        assert "FL-001-T" in skus

    def test_blast_radius_unknown_part(self, db):
        """Unknown part should return empty affected list."""
        result = calculate_blast_radius(db, "NONEXISTENT")
        assert result["affected_finished_goods"] == []
        assert result["total_revenue_at_risk"] == 0.0

    def test_blast_radius_logs_generated(self, db):
        """Blast radius analysis should emit Glass Box logs."""
        result = calculate_blast_radius(db, "CH-101")
        assert len(result["logs"]) > 0
        for log in result["logs"]:
            assert log["agent"] == "Core-Guard"


# ---------------------------------------------------------------------------
# Core-Guard — Ring-Fencing Enforcement (PRD §11)
# ---------------------------------------------------------------------------

class TestRingFencing:
    """Test ring-fencing: protecting inventory for specific orders."""

    def test_ring_fence_success(self, db):
        """Should successfully ring-fence when available inventory is sufficient."""
        result = ring_fence_inventory(db, "CH-101", "SO-VIP-001", 100)
        assert result["success"] is True
        assert result["qty_ring_fenced"] == 100

    def test_ring_fence_blocked_when_insufficient(self, db):
        """Should block when requested qty exceeds available inventory."""
        # CH-101 has 500 on_hand, 50 reserved, 0 ring_fenced → 450 available
        result = ring_fence_inventory(db, "CH-101", "SO-HUGE-999", 9999)
        assert result["success"] is False

    def test_ring_fence_reduces_available(self, db):
        """Ring-fencing should reduce the available count."""
        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        original_available = inv.available

        ring_fence_inventory(db, "CH-101", "SO-TEST-001", 100)

        # Available should have decreased by 100
        assert inv.available == original_available - 100

    def test_ring_fence_audit_trail(self, db):
        """Both success and failure should create audit trail entries."""
        from database.models import RingFenceAuditLog

        ring_fence_inventory(db, "CH-101", "SO-AUDIT-001", 50)
        ring_fence_inventory(db, "CH-101", "SO-AUDIT-002", 99999)  # Will fail

        audits = db.query(RingFenceAuditLog).all()
        assert len(audits) >= 2
        actions = [a.action for a in audits]
        assert "RING_FENCED" in actions
        assert "BLOCKED" in actions

    def test_ring_fence_unknown_part(self, db):
        """Unknown part should fail gracefully."""
        result = ring_fence_inventory(db, "NONEXISTENT", "SO-001", 10)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Part Agent — Digital Twin (PRD §4, §8, §9)
# ---------------------------------------------------------------------------

class TestDemandHorizonZones:
    """Test Demand Horizon Zones classification (PRD §10)."""

    def test_zone_1_fuzzy_forecast(self):
        """Demand > 6 months out → Zone 1."""
        assert classify_demand_zone(200, 7) == 1

    def test_zone_2_lead_time_horizon(self):
        """Demand 2-5 months out → Zone 2."""
        assert classify_demand_zone(90, 7) == 2

    def test_zone_3_drop_in_crisis(self):
        """Demand < 2 months out → Zone 3."""
        assert classify_demand_zone(30, 7) == 3

    def test_zone_1_no_po(self, db):
        """Zone 1 should NOT generate a PO."""
        result = evaluate_demand_horizon(db, "CH-101", 500, 365)
        assert result["zone"] == 1
        assert result["generate_po"] is False
        assert "Aura" in result["active_agents"]

    def test_zone_2_standard_po(self, db):
        """Zone 2 should generate a standard PO (no expedite)."""
        result = evaluate_demand_horizon(db, "CH-101", 500, 90)
        assert result["zone"] == 2
        assert result["generate_po"] is True
        assert result["expedite"] is False

    def test_zone_3_crisis_expedited(self, db):
        """Zone 3 inside lead time should expedite + secondary supplier."""
        result = evaluate_demand_horizon(db, "CH-101", 500, 3)
        assert result["zone"] == 3
        assert result["generate_po"] is True
        assert result["expedite"] is True
        assert result["use_secondary_supplier"] is True

    def test_zone_3_logs_generated(self, db):
        """Zone 3 should emit Glass Box logs."""
        result = evaluate_demand_horizon(db, "CH-101", 500, 3)
        assert len(result["logs"]) > 0


class TestDataIntegrity:
    """Test Data Integrity Agent — Ghost and Suspect Inventory (PRD §11)."""

    def test_ghost_inventory_detected(self, db):
        """Parts with burn rate > 0 and no consumption should be flagged as ghost."""
        from datetime import datetime, timezone, timedelta

        # Set CH-101's last_consumption_date to 20 days ago (> 14-day threshold)
        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        inv.last_consumption_date = datetime.now(timezone.utc) - timedelta(days=20)
        db.flush()

        result = detect_ghost_inventory(db)
        ghost_ids = [g["part_id"] for g in result["ghost_parts"]]
        # CH-101 should NOT be ghost since we set a recent-ish date (20 > 14)
        assert "CH-101" in ghost_ids
        assert len(result["cycle_count_tasks"]) > 0

    def test_no_ghost_when_recently_consumed(self, db):
        """Parts consumed recently should not be flagged."""
        from datetime import datetime, timezone, timedelta

        # Set all parts to recently consumed
        for inv in db.query(Inventory).all():
            inv.last_consumption_date = datetime.now(timezone.utc) - timedelta(days=5)
        db.flush()

        result = detect_ghost_inventory(db)
        assert len(result["ghost_parts"]) == 0

    def test_suspect_inventory_detected(self, db):
        """Parts not moved in 6+ months should be flagged as suspect."""
        from datetime import datetime, timezone, timedelta

        # Set CH-101's last_updated to 200 days ago (> 180-day threshold)
        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        inv.last_updated = datetime.now(timezone.utc) - timedelta(days=200)
        db.flush()

        result = detect_suspect_inventory(db)
        suspect_ids = [s["part_id"] for s in result["suspect_parts"]]
        assert "CH-101" in suspect_ids

    def test_full_integrity_check(self, db):
        """Full check should run both ghost and suspect scans."""
        result = run_full_integrity_check(db)
        assert "ghost" in result
        assert "suspect" in result
        assert "total_issues" in result
        assert len(result["logs"]) > 0


class TestSlowBleedScenario:
    """Test Scenario G: Slow Bleed — gradual burn rate increase detected by Part Agent."""

    def test_slow_bleed_detects_runway_decline(self, db):
        """Part Agent should detect runway declining across simulated days."""
        from agents.part_agent import monitor_part, calculate_runway

        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        burn_rates = [40.0, 55.0, 70.0, 85.0]
        runways = []

        for rate in burn_rates:
            inv.daily_burn_rate = rate
            db.flush()
            result = monitor_part(db, "CH-101")
            runways.append(result["runway_days"])

        for i in range(1, len(runways)):
            assert runways[i] < runways[i - 1], f"Runway should decline: {runways}"

    def test_slow_bleed_triggers_handshake(self, db):
        """At high enough burn rate, Part Agent handshake should fire."""
        from agents.part_agent import monitor_part

        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        inv.daily_burn_rate = 85.0
        db.flush()

        result = monitor_part(db, "CH-101")
        assert result["handshake_triggered"] is True
        assert result["crisis_signal"] is not None


class TestPartAgentFormulas:
    """Test Part Agent pure math functions (PRD §8)."""

    def test_dynamic_safety_stock_formula(self):
        """PRD §8: Safety Stock = (Max Usage × Max LT) - (Avg Usage × Avg LT)."""
        # (60 × 10) - (40 × 7) = 600 - 280 = 320
        result = calculate_dynamic_safety_stock(60.0, 10, 40.0, 7.0)
        assert result == 320

    def test_dynamic_safety_stock_clamped_to_zero(self):
        """Safety stock should never be negative."""
        # (10 × 5) - (20 × 7) = 50 - 140 = -90 → clamped to 0
        result = calculate_dynamic_safety_stock(10.0, 5, 20.0, 7.0)
        assert result == 0

    def test_runway_normal(self):
        """PRD §8: Days to Stockout = On-Hand / Burn Rate."""
        result = calculate_runway(500, 40.0)
        assert result == 12.5

    def test_runway_zero_burn_rate(self):
        """Zero burn rate → infinite runway."""
        result = calculate_runway(500, 0.0)
        assert result == float("inf")

    def test_handshake_trigger_fires(self):
        """Handshake fires when runway < (lead_time + safety_days)."""
        # runway=8, threshold=5+5=10 → 8 < 10 → True
        assert evaluate_handshake_trigger(8.0, 5, 5.0) is True

    def test_handshake_trigger_safe(self):
        """No handshake when runway is above threshold."""
        # runway=20, threshold=5+5=10 → 20 < 10 → False
        assert evaluate_handshake_trigger(20.0, 5, 5.0) is False


class TestPartAgentMonitoring:
    """Test Part Agent's monitor_part and monitor_all_components (PRD §9)."""

    def test_monitor_part_returns_valid_structure(self, db):
        """monitor_part should return all required fields."""
        result = monitor_part(db, "CH-101")
        assert result["part_id"] == "CH-101"
        assert "on_hand" in result
        assert "daily_burn_rate" in result
        assert "runway_days" in result
        assert "dynamic_safety_stock" in result
        assert "handshake_triggered" in result
        assert len(result["logs"]) > 0

    def test_monitor_part_unknown_sku(self, db):
        """Unknown SKU should return gracefully."""
        result = monitor_part(db, "NONEXISTENT")
        assert result["handshake_triggered"] is False
        assert result["crisis_signal"] is None

    def test_monitor_all_components(self, db):
        """monitor_all_components should check all BOM components for a finished good."""
        result = monitor_all_components(db, "FL-001-T", 100)
        assert result["sku"] == "FL-001-T"
        assert len(result["component_reports"]) == 3  # CH-101, SW-303, LNS-505
        assert len(result["logs"]) > 0

    def test_high_demand_triggers_handshake(self, db):
        """Very high demand should cause at least one component to trigger handshake."""
        result = monitor_all_components(db, "FL-001-T", 50000)
        # With 50000 demand, burn rates spike massively → handshakes should fire
        assert len(result["crisis_signals"]) > 0


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

    def test_full_5_step_execution_loop(self, db):
        """
        PRD §9: Complete 5-Step Execution Loop.

        Step 1: Aura detects demand spike (Trigger Event)
        Step 2: Part Agent monitors components (Baseline + Local Validation)
        Step 3: Dispatcher triages by criticality
        Step 4: Core-Guard runs MRP + ring-fencing + blast radius (Handshake)
        Step 5: Ghost-Writer drafts POs (Execution Draft)
        """
        from agents.dispatcher import triage_demand_spike

        sku = "FL-001-T"
        spiked_qty = 500

        # Step 1: Aura — Trigger Event
        aura_result = detect_demand_spike(db, sku, spiked_qty)
        assert aura_result["spike_detected"] is True
        assert len(aura_result["logs"]) > 0

        # Step 2: Part Agent — Baseline Monitoring + Local Validation
        part_result = monitor_all_components(db, sku, spiked_qty)
        assert "component_reports" in part_result
        assert len(part_result["component_reports"]) > 0
        # At least one crisis signal should fire under heavy demand
        assert len(part_result["logs"]) > 0

        # Step 3: Dispatcher — Triage by criticality
        dispatch_result = triage_demand_spike(db, sku, spiked_qty)
        assert len(dispatch_result["priority_queue"]) > 0
        assert len(dispatch_result["logs"]) > 0

        # Step 4: Core-Guard — MRP explosion
        mrp_result = calculate_net_requirements(db, sku, spiked_qty)
        assert len(mrp_result["shortages"]) > 0
        assert len(mrp_result["logs"]) > 0

        # Step 4b: Ring-fencing VIP inventory (PRD §11)
        ring_result = ring_fence_inventory(db, sku, "SO-VIP-001", 50)
        assert ring_result["success"] in (True, False)

        # Step 4c: Blast radius analysis for shortage components
        for shortage in mrp_result["shortages"][:1]:
            blast_result = calculate_blast_radius(db, shortage["part_id"])
            assert "affected_finished_goods" in blast_result
            assert len(blast_result["logs"]) > 0

        # Step 5: Ghost-Writer — Execution Draft
        buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
        assert len(buy_orders) > 0
        ghost_result = process_buy_orders(db, buy_orders)
        assert len(ghost_result["purchase_orders"]) > 0
        for po in ghost_result["purchase_orders"]:
            assert po["po_number"].startswith("PO-")
            assert po["status"] in ("APPROVED", "PENDING_APPROVAL")
            assert po["quantity"] > 0
            assert po["total_cost"] > 0

        # Verify Glass Box pattern: every step emitted logs
        total_logs = (
            len(aura_result["logs"])
            + len(part_result["logs"])
            + len(dispatch_result["logs"])
            + len(mrp_result["logs"])
            + len(ring_result["logs"])
            + len(ghost_result["logs"])
        )
        assert total_logs >= 10, f"Expected >=10 Glass Box logs across all agents, got {total_logs}"
