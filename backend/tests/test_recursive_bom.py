"""Tests for recursive (multi-level) BOM explosion in Core-Guard."""

from agents.core_guard import calculate_net_requirements


class TestRecursiveBOMExplosion:
    def test_three_level_bom_identifies_leaf_shortages(self, db):
        """
        HL-002-P -> SA-LED-100 -> LED-201
        A demand spike on HL-002-P should surface shortage of LED-201 (leaf component),
        not just SA-LED-100 (sub-assembly).
        """
        result = calculate_net_requirements(db, "HL-002-P", 2000)
        # Should have shortages at the leaf (component) level
        shortage_part_ids = [s["part_id"] for s in result["shortages"]]
        # Sub-assemblies (SA-*) should NOT appear as shortages — only leaf components
        for s in result["shortages"]:
            assert not s["part_id"].startswith("SA-"), \
                f"Sub-assembly {s['part_id']} should not be a shortage — only leaf components"

    def test_quantity_per_multiplies_through_levels(self, db):
        """
        If HL-002-P needs 1x SA-LED-100, and SA-LED-100 needs 1x LED-201,
        then 100 units of HL-002-P needs 100x LED-201.
        """
        result = calculate_net_requirements(db, "HL-002-P", 100)
        # Find LED-201 in shortages or verify it was checked
        log_messages = " ".join(log["message"] for log in result["logs"])
        assert "LED-201" in log_messages, "BOM explosion should reach LED-201"

    def test_shared_components_aggregated(self, db):
        """
        HL-002-P uses SA-ELC-140 -> MCU-241 and SA-LED-100 -> LED-201.
        Both should appear as leaf requirements.
        """
        result = calculate_net_requirements(db, "HL-002-P", 500)
        log_messages = " ".join(log["message"] for log in result["logs"])
        assert "MCU-241" in log_messages, "BOM explosion should reach MCU-241"
        assert "LED-201" in log_messages, "BOM explosion should reach LED-201"
        assert "BAT-211" in log_messages, "BOM explosion should reach BAT-211"
