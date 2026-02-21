"""
Seed script for Core-Guard MVP.

Populates the FL-001 Flashlight dataset:
  - 22 Suppliers (3 primary + 19 alternates)
  - 5 Parts (2 Finished Goods + 3 Common Core components)
  - BOM entries linking Finished Goods to their components
  - Starting inventory levels
  - Baseline demand forecasts

Run: python seed.py
"""

import sys
from pathlib import Path

# Ensure the backend package is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.connection import init_db, SessionLocal
from database.models import (
    Supplier, Part, Inventory, BOMEntry, DemandForecast,
    PartCategory,
)


def seed() -> None:
    init_db()
    db = SessionLocal()

    # Guard against double-seeding
    if db.query(Supplier).first():
        print("Database already seeded. Delete coreguard.db to re-seed.")
        db.close()
        return

    # ---------------------------------------------------------------
    # 1. SUPPLIERS (22 vendors per PRD §4)
    # ---------------------------------------------------------------
    suppliers_data = [
        # Primary suppliers (matched to Ground Truth parts)
        {"name": "AluForge", "contact_email": "sales@aluforge.com", "lead_time_days": 5, "reliability_score": 0.97},
        {"name": "MicroConnect", "contact_email": "orders@microconnect.com", "lead_time_days": 3, "reliability_score": 0.95},
        {"name": "Precision Optic", "contact_email": "supply@precisionoptic.com", "lead_time_days": 7, "reliability_score": 0.98},
        # Alternate suppliers
        {"name": "MetalWorks Inc", "contact_email": "info@metalworks.com", "lead_time_days": 8, "reliability_score": 0.90},
        {"name": "CastRight", "contact_email": "sales@castright.com", "lead_time_days": 10, "reliability_score": 0.88},
        {"name": "SteelEdge", "contact_email": "procurement@steeledge.com", "lead_time_days": 6, "reliability_score": 0.92},
        {"name": "CircuitPro", "contact_email": "orders@circuitpro.com", "lead_time_days": 4, "reliability_score": 0.93},
        {"name": "SwitchTech", "contact_email": "b2b@switchtech.com", "lead_time_days": 5, "reliability_score": 0.91},
        {"name": "NanoSwitch", "contact_email": "sales@nanoswitch.com", "lead_time_days": 6, "reliability_score": 0.89},
        {"name": "LensKraft", "contact_email": "supply@lenskraft.com", "lead_time_days": 9, "reliability_score": 0.94},
        {"name": "OptiClear", "contact_email": "orders@opticlear.com", "lead_time_days": 8, "reliability_score": 0.90},
        {"name": "PhotonLens", "contact_email": "sales@photonlens.com", "lead_time_days": 7, "reliability_score": 0.92},
        {"name": "BrightPath", "contact_email": "info@brightpath.com", "lead_time_days": 5, "reliability_score": 0.88},
        {"name": "AlloyCast", "contact_email": "orders@alloycast.com", "lead_time_days": 7, "reliability_score": 0.87},
        {"name": "TitanShell", "contact_email": "sales@titanshell.com", "lead_time_days": 12, "reliability_score": 0.85},
        {"name": "MicroRelay", "contact_email": "b2b@microrelay.com", "lead_time_days": 4, "reliability_score": 0.93},
        {"name": "ElectraSwitch", "contact_email": "info@electraswitch.com", "lead_time_days": 3, "reliability_score": 0.96},
        {"name": "GlassWave", "contact_email": "supply@glasswave.com", "lead_time_days": 11, "reliability_score": 0.86},
        {"name": "CoreSupply Co", "contact_email": "orders@coresupply.com", "lead_time_days": 6, "reliability_score": 0.91},
        {"name": "RapidParts", "contact_email": "sales@rapidparts.com", "lead_time_days": 2, "reliability_score": 0.94},
        {"name": "VectorMetal", "contact_email": "procurement@vectormetal.com", "lead_time_days": 8, "reliability_score": 0.89},
        {"name": "FluxComponents", "contact_email": "info@fluxcomp.com", "lead_time_days": 5, "reliability_score": 0.92},
    ]

    suppliers = {}
    for s in suppliers_data:
        supplier = Supplier(**s)
        db.add(supplier)
        db.flush()
        suppliers[s["name"]] = supplier

    # ---------------------------------------------------------------
    # 2. PARTS (FL-001 Ground Truth — CLAUDE.md §Data Model)
    # ---------------------------------------------------------------
    parts_data = [
        {"part_id": "FL-001-T", "description": "Tactical Flashlight", "category": PartCategory.FINISHED_GOOD, "unit_cost": 0.0, "supplier_name": None},
        {"part_id": "FL-001-S", "description": "Standard Flashlight", "category": PartCategory.FINISHED_GOOD, "unit_cost": 0.0, "supplier_name": None},
        {"part_id": "CH-101", "description": "Modular Chassis", "category": PartCategory.COMMON_CORE, "unit_cost": 12.50, "supplier_name": "AluForge"},
        {"part_id": "SW-303", "description": "Switch Assembly", "category": PartCategory.COMMON_CORE, "unit_cost": 4.75, "supplier_name": "MicroConnect"},
        {"part_id": "LNS-505", "description": "Optic Lens", "category": PartCategory.COMMON_CORE, "unit_cost": 8.30, "supplier_name": "Precision Optic"},
    ]

    parts = {}
    for p in parts_data:
        supplier_name = p.pop("supplier_name")
        part = Part(
            **p,
            supplier_id=suppliers[supplier_name].id if supplier_name else None,
        )
        db.add(part)
        db.flush()
        parts[part.part_id] = part

    # ---------------------------------------------------------------
    # 3. BILL OF MATERIALS
    # Both FL-001-T and FL-001-S share CH-101, SW-303, LNS-505.
    # Tactical uses 2x chassis (reinforced body), Standard uses 1x.
    # ---------------------------------------------------------------
    bom_data = [
        # Tactical Flashlight BOM
        {"parent": "FL-001-T", "component": "CH-101", "qty": 2},
        {"parent": "FL-001-T", "component": "SW-303", "qty": 1},
        {"parent": "FL-001-T", "component": "LNS-505", "qty": 1},
        # Standard Flashlight BOM
        {"parent": "FL-001-S", "component": "CH-101", "qty": 1},
        {"parent": "FL-001-S", "component": "SW-303", "qty": 1},
        {"parent": "FL-001-S", "component": "LNS-505", "qty": 1},
    ]

    for b in bom_data:
        entry = BOMEntry(
            parent_id=parts[b["parent"]].id,
            component_id=parts[b["component"]].id,
            quantity_per=b["qty"],
        )
        db.add(entry)

    # ---------------------------------------------------------------
    # 4. INVENTORY (Starting levels for simulation)
    # ---------------------------------------------------------------
    inventory_data = [
        {"part_id": "CH-101", "on_hand": 500, "safety_stock": 200, "reserved": 100},
        {"part_id": "SW-303", "on_hand": 800, "safety_stock": 300, "reserved": 50},
        {"part_id": "LNS-505", "on_hand": 350, "safety_stock": 150, "reserved": 75},
        # Finished goods track assembled units
        {"part_id": "FL-001-T", "on_hand": 120, "safety_stock": 50, "reserved": 0},
        {"part_id": "FL-001-S", "on_hand": 300, "safety_stock": 100, "reserved": 0},
    ]

    for inv in inventory_data:
        record = Inventory(
            part_id=parts[inv["part_id"]].id,
            on_hand=inv["on_hand"],
            safety_stock=inv["safety_stock"],
            reserved=inv["reserved"],
        )
        db.add(record)

    # ---------------------------------------------------------------
    # 5. DEMAND FORECASTS (Baseline — simulation will spike these)
    # ---------------------------------------------------------------
    forecast_data = [
        {"part_id": "FL-001-T", "forecast_qty": 100, "actual_qty": 100},
        {"part_id": "FL-001-S", "forecast_qty": 200, "actual_qty": 200},
    ]

    for f in forecast_data:
        forecast = DemandForecast(
            part_id=parts[f["part_id"]].id,
            forecast_qty=f["forecast_qty"],
            actual_qty=f["actual_qty"],
        )
        db.add(forecast)

    db.commit()
    db.close()

    print("Seeded Core-Guard database successfully.")
    print(f"  - {len(suppliers_data)} suppliers")
    print(f"  - {len(parts_data)} parts")
    print(f"  - {len(bom_data)} BOM entries")
    print(f"  - {len(inventory_data)} inventory records")
    print(f"  - {len(forecast_data)} demand forecasts")


if __name__ == "__main__":
    seed()
