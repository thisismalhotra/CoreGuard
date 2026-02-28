"""
Seed script for Core-Guard MVP — Tactical Lighting Division.

Populates the full multi-product dataset:
  - 22 Suppliers (enriched with tier, region, MOQ, capacity)
  - ~55 Parts (6 finished goods, ~15 sub-assemblies, ~30 components, ~4 services)
  - ~120 BOM entries (3-level: FG → SA → Component)
  - Inventory records with built-in tension
  - 6 Sales orders (military, Amazon, REI, law enforcement, dealer, OEM)
  - 35 Demand forecasts (7 periods × 5 products)
  - 6 Supplier contracts
  - 8 Alternate supplier mappings

Run: python seed.py
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Ensure the backend package is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.connection import init_db, SessionLocal
from database.models import (
    Supplier, Part, Inventory, BOMEntry, DemandForecast, SalesOrder,
    SupplierContract, AlternateSupplier,
    PartCategory, CriticalityLevel, SalesOrderStatus,
    SupplierTier, SupplierRegion, ContractType, ContractStatus,
)


def seed() -> None:
    init_db()
    db = SessionLocal()

    # Guard against double-seeding
    if db.query(Supplier).first():
        logger.info("Database already seeded. Delete coreguard.db to re-seed.")
        db.close()
        return

    # ---------------------------------------------------------------
    # 1. SUPPLIERS (22 vendors — enriched with tier, region, MOQ, capacity)
    # ---------------------------------------------------------------
    suppliers_data = [
        {"name": "CREE Inc.", "contact_email": "sales@cree.com", "lead_time_days": 42,
         "reliability_score": 0.94, "tier": SupplierTier.TIER_1, "region": SupplierRegion.US,
         "expedite_lead_time_days": 28, "minimum_order_qty": 500, "capacity_per_month": 15000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "ITAR"]),
         "risk_factors": json.dumps(["single source"])},
        {"name": "Samsung SDI", "contact_email": "orders@samsungsdi.com", "lead_time_days": 35,
         "reliability_score": 0.92, "tier": SupplierTier.TIER_1, "region": SupplierRegion.SOUTH_KOREA,
         "expedite_lead_time_days": 21, "minimum_order_qty": 1000, "capacity_per_month": 50000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "UL"]),
         "risk_factors": json.dumps(["geopolitical"])},
        {"name": "Wurth Elektronik", "contact_email": "sales@wurth.com", "lead_time_days": 28,
         "reliability_score": 0.88, "tier": SupplierTier.TIER_1, "region": SupplierRegion.GERMANY,
         "expedite_lead_time_days": 18, "minimum_order_qty": 250, "capacity_per_month": 100000,
         "payment_terms": "2/10 Net 30", "certifications": json.dumps(["ISO 9001", "IATF 16949", "RoHS"]),
         "risk_factors": json.dumps(["semiconductor allocation"])},
        {"name": "Kingbright", "contact_email": "sales@kingbright.com", "lead_time_days": 21,
         "reliability_score": 0.91, "tier": SupplierTier.TIER_1, "region": SupplierRegion.TAIWAN,
         "expedite_lead_time_days": 14, "minimum_order_qty": 2000, "capacity_per_month": 200000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "RoHS"]),
         "risk_factors": json.dumps([])},
        {"name": "ShenZhen FastPCB", "contact_email": "orders@fastpcb.cn", "lead_time_days": 18,
         "reliability_score": 0.85, "tier": SupplierTier.TIER_2, "region": SupplierRegion.CHINA,
         "expedite_lead_time_days": 10, "minimum_order_qty": 100, "capacity_per_month": 10000,
         "payment_terms": "50% upfront", "certifications": json.dumps(["ISO 9001", "UL"]),
         "risk_factors": json.dumps(["tariff risk"])},
        {"name": "Jiangsu OptiMold", "contact_email": "supply@optimold.cn", "lead_time_days": 25,
         "reliability_score": 0.83, "tier": SupplierTier.TIER_2, "region": SupplierRegion.CHINA,
         "expedite_lead_time_days": 16, "minimum_order_qty": 500, "capacity_per_month": 20000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps(["tariff risk"])},
        {"name": "Apex CNC Works", "contact_email": "quotes@apexcnc.com", "lead_time_days": 14,
         "reliability_score": 0.90, "tier": SupplierTier.TIER_2, "region": SupplierRegion.US,
         "expedite_lead_time_days": 7, "minimum_order_qty": 50, "capacity_per_month": 3000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "ITAR", "AS9100"]),
         "risk_factors": json.dumps(["capacity constrained"])},
        {"name": "Precision Die Cast", "contact_email": "sales@precisiondc.mx", "lead_time_days": 21,
         "reliability_score": 0.87, "tier": SupplierTier.TIER_2, "region": SupplierRegion.MEXICO,
         "expedite_lead_time_days": 14, "minimum_order_qty": 200, "capacity_per_month": 5000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps([])},
        {"name": "Dongguan SwitchTech", "contact_email": "b2b@dgswitchtech.cn", "lead_time_days": 20,
         "reliability_score": 0.82, "tier": SupplierTier.TIER_2, "region": SupplierRegion.CHINA,
         "expedite_lead_time_days": 12, "minimum_order_qty": 300, "capacity_per_month": 15000,
         "payment_terms": "50% upfront", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps(["tariff risk"])},
        {"name": "Parker Hannifin", "contact_email": "seals@parker.com", "lead_time_days": 7,
         "reliability_score": 0.96, "tier": SupplierTier.TIER_3, "region": SupplierRegion.US,
         "expedite_lead_time_days": 3, "minimum_order_qty": 1000, "capacity_per_month": 500000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "AS9100"]),
         "risk_factors": json.dumps([])},
        {"name": "McMaster-Carr", "contact_email": "orders@mcmaster.com", "lead_time_days": 3,
         "reliability_score": 0.99, "tier": SupplierTier.TIER_3, "region": SupplierRegion.US,
         "expedite_lead_time_days": 1, "minimum_order_qty": 1, "capacity_per_month": None,
         "payment_terms": "Net 30", "certifications": json.dumps([]),
         "risk_factors": json.dumps([])},
        {"name": "Uline", "contact_email": "orders@uline.com", "lead_time_days": 5,
         "reliability_score": 0.97, "tier": SupplierTier.TIER_3, "region": SupplierRegion.US,
         "expedite_lead_time_days": 3, "minimum_order_qty": 500, "capacity_per_month": None,
         "payment_terms": "Net 30", "certifications": json.dumps([]),
         "risk_factors": json.dumps([])},
        {"name": "Shenzhen CableWorks", "contact_email": "sales@szcableworks.cn", "lead_time_days": 15,
         "reliability_score": 0.84, "tier": SupplierTier.TIER_3, "region": SupplierRegion.CHINA,
         "expedite_lead_time_days": 8, "minimum_order_qty": 200, "capacity_per_month": 30000,
         "payment_terms": "50% upfront", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps(["tariff risk"])},
        {"name": "YKK / National Molding", "contact_email": "industrial@ykk.com", "lead_time_days": 10,
         "reliability_score": 0.93, "tier": SupplierTier.TIER_3, "region": SupplierRegion.US,
         "expedite_lead_time_days": 5, "minimum_order_qty": 500, "capacity_per_month": 50000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps([])},
        {"name": "MIL-SPEC Coatings", "contact_email": "jobs@milspeccoatings.com", "lead_time_days": 10,
         "reliability_score": 0.91, "tier": SupplierTier.SERVICE, "region": SupplierRegion.US,
         "expedite_lead_time_days": 5, "minimum_order_qty": 100, "capacity_per_month": 8000,
         "payment_terms": "Net 30", "certifications": json.dumps(["MIL-A-8625", "ITAR"]),
         "risk_factors": json.dumps(["batch scheduling"])},
        {"name": "FlashTech Solutions", "contact_email": "fw@flashtech.com", "lead_time_days": 2,
         "reliability_score": 0.98, "tier": SupplierTier.SERVICE, "region": SupplierRegion.US,
         "expedite_lead_time_days": 1, "minimum_order_qty": 1, "capacity_per_month": 10000,
         "payment_terms": "Net 15", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps(["in-house capability"])},
        {"name": "OptiCoat Ltd", "contact_email": "coatings@opticoat.tw", "lead_time_days": 15,
         "reliability_score": 0.89, "tier": SupplierTier.SERVICE, "region": SupplierRegion.TAIWAN,
         "expedite_lead_time_days": 8, "minimum_order_qty": 300, "capacity_per_month": 20000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps([])},
        {"name": "Pelican Products", "contact_email": "oem@pelican.com", "lead_time_days": 12,
         "reliability_score": 0.95, "tier": SupplierTier.TIER_3, "region": SupplierRegion.US,
         "expedite_lead_time_days": 6, "minimum_order_qty": 50, "capacity_per_month": 5000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps([])},
        {"name": "LaserMark Inc.", "contact_email": "jobs@lasermark.com", "lead_time_days": 5,
         "reliability_score": 0.94, "tier": SupplierTier.SERVICE, "region": SupplierRegion.US,
         "expedite_lead_time_days": 2, "minimum_order_qty": 100, "capacity_per_month": 15000,
         "payment_terms": "Net 15", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps([])},
        {"name": "REF-Tech", "contact_email": "sales@reftech.com", "lead_time_days": 8,
         "reliability_score": 0.92, "tier": SupplierTier.TIER_3, "region": SupplierRegion.US,
         "expedite_lead_time_days": 4, "minimum_order_qty": 500, "capacity_per_month": 25000,
         "payment_terms": "Net 30", "certifications": json.dumps([]),
         "risk_factors": json.dumps([])},
        {"name": "SLP-306 Vendor", "contact_email": "sales@slpvendor.com", "lead_time_days": 5,
         "reliability_score": 0.96, "tier": SupplierTier.TIER_3, "region": SupplierRegion.US,
         "expedite_lead_time_days": 2, "minimum_order_qty": 1000, "capacity_per_month": 100000,
         "payment_terms": "Net 30", "certifications": json.dumps([]),
         "risk_factors": json.dumps([])},
        {"name": "Energizer Industrial", "contact_email": "oem@energizer.com", "lead_time_days": 14,
         "reliability_score": 0.95, "tier": SupplierTier.TIER_1, "region": SupplierRegion.US,
         "expedite_lead_time_days": 7, "minimum_order_qty": 500, "capacity_per_month": 100000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "UL"]),
         "risk_factors": json.dumps([])},
        {"name": "STMicroelectronics", "contact_email": "sales@st.com", "lead_time_days": 30,
         "reliability_score": 0.87, "tier": SupplierTier.TIER_1, "region": SupplierRegion.GERMANY,
         "expedite_lead_time_days": 20, "minimum_order_qty": 100, "capacity_per_month": 50000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "IATF 16949", "AEC-Q100"]),
         "risk_factors": json.dumps(["semiconductor allocation"])},
        # Alternate suppliers (not primary for any part, used in AlternateSupplier table)
        {"name": "Luminus Devices", "contact_email": "sales@luminus.com", "lead_time_days": 56,
         "reliability_score": 0.86, "tier": SupplierTier.TIER_1, "region": SupplierRegion.US,
         "expedite_lead_time_days": 35, "minimum_order_qty": 250, "capacity_per_month": 8000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps([])},
        {"name": "LG Energy Solution", "contact_email": "b2b@lgensol.com", "lead_time_days": 42,
         "reliability_score": 0.90, "tier": SupplierTier.TIER_1, "region": SupplierRegion.SOUTH_KOREA,
         "expedite_lead_time_days": 28, "minimum_order_qty": 1000, "capacity_per_month": 40000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "UL"]),
         "risk_factors": json.dumps(["geopolitical"])},
        {"name": "PCBWay", "contact_email": "orders@pcbway.com", "lead_time_days": 18,
         "reliability_score": 0.84, "tier": SupplierTier.TIER_2, "region": SupplierRegion.CHINA,
         "expedite_lead_time_days": 10, "minimum_order_qty": 100, "capacity_per_month": 8000,
         "payment_terms": "50% upfront", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps(["tariff risk"])},
        {"name": "Advanced Circuits", "contact_email": "sales@4pcb.com", "lead_time_days": 10,
         "reliability_score": 0.93, "tier": SupplierTier.TIER_2, "region": SupplierRegion.US,
         "expedite_lead_time_days": 5, "minimum_order_qty": 25, "capacity_per_month": 5000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "ITAR"]),
         "risk_factors": json.dumps([])},
        {"name": "Proto Labs", "contact_email": "quotes@protolabs.com", "lead_time_days": 7,
         "reliability_score": 0.91, "tier": SupplierTier.TIER_2, "region": SupplierRegion.US,
         "expedite_lead_time_days": 3, "minimum_order_qty": 1, "capacity_per_month": 2000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "AS9100"]),
         "risk_factors": json.dumps([])},
        {"name": "Marco Rubber", "contact_email": "sales@marcorubber.com", "lead_time_days": 9,
         "reliability_score": 0.90, "tier": SupplierTier.TIER_3, "region": SupplierRegion.US,
         "expedite_lead_time_days": 5, "minimum_order_qty": 500, "capacity_per_month": 100000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001"]),
         "risk_factors": json.dumps(["custom tooling needed"])},
        {"name": "Digi-Key", "contact_email": "orders@digikey.com", "lead_time_days": 14,
         "reliability_score": 0.97, "tier": SupplierTier.TIER_2, "region": SupplierRegion.US,
         "expedite_lead_time_days": 3, "minimum_order_qty": 1, "capacity_per_month": None,
         "payment_terms": "Net 30", "certifications": json.dumps([]),
         "risk_factors": json.dumps(["no allocation guarantee"])},
        {"name": "C&K Switches", "contact_email": "sales@ckswitches.com", "lead_time_days": 15,
         "reliability_score": 0.92, "tier": SupplierTier.TIER_2, "region": SupplierRegion.US,
         "expedite_lead_time_days": 8, "minimum_order_qty": 100, "capacity_per_month": 20000,
         "payment_terms": "Net 30", "certifications": json.dumps(["ISO 9001", "IATF 16949"]),
         "risk_factors": json.dumps([])},
    ]

    suppliers = {}
    for s in suppliers_data:
        supplier = Supplier(**s)
        db.add(supplier)
        db.flush()
        suppliers[s["name"]] = supplier

    # ---------------------------------------------------------------
    # 2. PARTS (~55 parts: 6 FG, ~15 SA, ~30 components, ~4 services)
    # ---------------------------------------------------------------
    parts_data = [
        # --- Finished Goods (6) ---
        {"part_id": "FL-001-T", "description": "Tactical Flashlight", "category": PartCategory.FINISHED_GOOD,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.9, "substitute_pool_size": 0},
        {"part_id": "FL-001-S", "description": "Standard Flashlight", "category": PartCategory.FINISHED_GOOD,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 0},
        {"part_id": "HL-002-P", "description": "Pro Headlamp", "category": PartCategory.FINISHED_GOOD,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.8, "substitute_pool_size": 0},
        {"part_id": "HL-002-B", "description": "Basic Headlamp", "category": PartCategory.FINISHED_GOOD,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 0},
        {"part_id": "WL-003-R", "description": "Weapon-Mounted Light (Rifle)", "category": PartCategory.FINISHED_GOOD,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.CRITICAL, "lead_time_sensitivity": 0.95, "substitute_pool_size": 0},
        {"part_id": "WL-003-C", "description": "Weapon-Mounted Light (Compact)", "category": PartCategory.FINISHED_GOOD,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.8, "substitute_pool_size": 0},

        # --- Sub-Assemblies (~15) ---
        {"part_id": "SA-LED-100", "description": "LED Module Assembly", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.CRITICAL, "lead_time_sensitivity": 0.9, "substitute_pool_size": 0},
        {"part_id": "SA-PWR-110", "description": "Power Module", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.8, "substitute_pool_size": 0},
        {"part_id": "SA-OPT-120", "description": "Optics Assembly", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.8, "substitute_pool_size": 0},
        {"part_id": "SA-BDY-130", "description": "Body Assembly", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.6, "substitute_pool_size": 0},
        {"part_id": "SA-ELC-140", "description": "Electronics/Control Module", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.CRITICAL, "lead_time_sensitivity": 0.9, "substitute_pool_size": 0},
        {"part_id": "SA-PKG-150", "description": "Packaging & Accessories (Flashlight)", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 0},
        {"part_id": "SA-HBD-160", "description": "Headband Assembly", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 0},
        {"part_id": "SA-HSG-170", "description": "Lamp Housing", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.6, "substitute_pool_size": 0},
        {"part_id": "SA-MNT-180", "description": "Picatinny Mount Assembly", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.8, "substitute_pool_size": 0},
        {"part_id": "SA-ACT-190", "description": "Activation System", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 0},
        {"part_id": "SA-BDY-135", "description": "Weapon Light Body", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.6, "substitute_pool_size": 0},
        {"part_id": "SA-ELC-145", "description": "Weapon Light Electronics", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.CRITICAL, "lead_time_sensitivity": 0.9, "substitute_pool_size": 0},
        {"part_id": "SA-PKG-155", "description": "Packaging (Headlamp)", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 0},
        {"part_id": "SA-PKG-158", "description": "Packaging (Weapon Light)", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 0},
        {"part_id": "SA-PWR-115", "description": "Power Module (CR123A)", "category": PartCategory.SUB_ASSEMBLY,
         "unit_cost": 0.0, "supplier_name": None,
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 0},

        # --- Components (~35) ---
        # LED Module components
        {"part_id": "LED-201", "description": "CREE XHP70.3 HI LED Emitter", "category": PartCategory.COMPONENT,
         "unit_cost": 11.50, "supplier_name": "CREE Inc.",
         "criticality": CriticalityLevel.CRITICAL, "lead_time_sensitivity": 0.95, "substitute_pool_size": 1},
        {"part_id": "PCB-202", "description": "LED Driver PCB (Constant Current)", "category": PartCategory.COMPONENT,
         "unit_cost": 3.20, "supplier_name": "ShenZhen FastPCB",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 2},
        {"part_id": "HS-203", "description": "Machined Aluminum Heat Sink", "category": PartCategory.COMPONENT,
         "unit_cost": 2.80, "supplier_name": "Apex CNC Works",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 1},
        {"part_id": "TCP-204", "description": "Thermal Compound Paste (0.5g)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.35, "supplier_name": "McMaster-Carr",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 3},
        {"part_id": "MCR-205", "description": "MCPCB Star Board (20mm)", "category": PartCategory.COMPONENT,
         "unit_cost": 1.10, "supplier_name": "Kingbright",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 2},
        {"part_id": "RST-206", "description": "Current Sense Resistor (SMD)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.08, "supplier_name": "Wurth Elektronik",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 3},
        # Power Module components
        {"part_id": "BAT-211", "description": "18650 Li-Ion Cell (3500mAh)", "category": PartCategory.COMPONENT,
         "unit_cost": 4.75, "supplier_name": "Samsung SDI",
         "criticality": CriticalityLevel.CRITICAL, "lead_time_sensitivity": 0.9, "substitute_pool_size": 1},
        {"part_id": "PCB-212", "description": "Battery Protection Circuit (BMS)", "category": PartCategory.COMPONENT,
         "unit_cost": 1.85, "supplier_name": "ShenZhen FastPCB",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 2},
        {"part_id": "SPR-213", "description": "Gold-Plated Contact Springs (pair)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.45, "supplier_name": "McMaster-Carr",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 3},
        {"part_id": "USB-214", "description": "USB-C Charging Port Assembly", "category": PartCategory.COMPONENT,
         "unit_cost": 2.10, "supplier_name": "Shenzhen CableWorks",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 1},
        {"part_id": "IND-215", "description": "Power Indicator LED (RGB)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.22, "supplier_name": "Kingbright",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 3},
        {"part_id": "WRH-216", "description": "Internal Wiring Harness (22AWG)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.90, "supplier_name": "Shenzhen CableWorks",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.4, "substitute_pool_size": 2},
        # Optics Assembly components
        {"part_id": "LNS-221", "description": "TIR Optic Lens (Polycarbonate)", "category": PartCategory.COMPONENT,
         "unit_cost": 1.60, "supplier_name": "Jiangsu OptiMold",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.8, "substitute_pool_size": 1},
        {"part_id": "BZL-222", "description": "Stainless Steel Bezel Ring", "category": PartCategory.COMPONENT,
         "unit_cost": 3.40, "supplier_name": "Jiangsu OptiMold",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 1},
        {"part_id": "GKT-223", "description": "Lens O-Ring (Buna-N, 28mm)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.12, "supplier_name": "Parker Hannifin",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 2},
        {"part_id": "RET-225", "description": "Centering Retainer Ring", "category": PartCategory.COMPONENT,
         "unit_cost": 0.40, "supplier_name": "Jiangsu OptiMold",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.3, "substitute_pool_size": 2},
        # Body Assembly components
        {"part_id": "CH-231", "description": "Body Tube (6061-T6 Aluminum)", "category": PartCategory.COMPONENT,
         "unit_cost": 8.50, "supplier_name": "Apex CNC Works",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.8, "substitute_pool_size": 1},
        {"part_id": "SW-232", "description": "Reverse-Click Tail Switch Assembly", "category": PartCategory.COMPONENT,
         "unit_cost": 3.20, "supplier_name": "Dongguan SwitchTech",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 1},
        {"part_id": "CLP-233", "description": "Deep Carry Pocket Clip (Spring Steel)", "category": PartCategory.COMPONENT,
         "unit_cost": 1.15, "supplier_name": "YKK / National Molding",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 2},
        {"part_id": "THD-236", "description": "Lubricated Thread Insert (Brass)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.65, "supplier_name": "McMaster-Carr",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 3},
        {"part_id": "GKT-237", "description": "Tail Cap O-Ring (Buna-N, 22mm)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.10, "supplier_name": "Parker Hannifin",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 2},
        # Electronics components
        {"part_id": "MCU-241", "description": "Microcontroller (ATtiny1616)", "category": PartCategory.COMPONENT,
         "unit_cost": 1.85, "supplier_name": "Wurth Elektronik",
         "criticality": CriticalityLevel.CRITICAL, "lead_time_sensitivity": 0.95, "substitute_pool_size": 1},
        {"part_id": "FET-242", "description": "N-Channel MOSFET (30V)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.55, "supplier_name": "Wurth Elektronik",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 2},
        {"part_id": "CAP-243", "description": "Ceramic Decoupling Capacitors (kit)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.30, "supplier_name": "Wurth Elektronik",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 3},
        {"part_id": "DRV-245", "description": "Gate Driver IC", "category": PartCategory.COMPONENT,
         "unit_cost": 0.95, "supplier_name": "Wurth Elektronik",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 2},
        # Packaging components
        {"part_id": "PKG-301", "description": "Retail Box (printed cardboard)", "category": PartCategory.COMPONENT,
         "unit_cost": 1.80, "supplier_name": "Uline",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "PKG-302", "description": "Die-Cut Foam Insert", "category": PartCategory.COMPONENT,
         "unit_cost": 0.95, "supplier_name": "Uline",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "PKG-303", "description": "User Manual + Warranty Card", "category": PartCategory.COMPONENT,
         "unit_cost": 0.40, "supplier_name": "Uline",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "LYD-304", "description": "Lanyard (550 Paracord)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.60, "supplier_name": "YKK / National Molding",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "HST-305", "description": "Nylon Belt Holster", "category": PartCategory.COMPONENT,
         "unit_cost": 3.50, "supplier_name": "YKK / National Molding",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 2},
        {"part_id": "SLP-306", "description": "Spare O-Ring Set (2x)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.15, "supplier_name": "SLP-306 Vendor",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        # Headlamp-specific components
        {"part_id": "HBD-261", "description": "Elastic Headband (adjustable)", "category": PartCategory.COMPONENT,
         "unit_cost": 1.40, "supplier_name": "YKK / National Molding",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.4, "substitute_pool_size": 2},
        {"part_id": "BKL-262", "description": "Quick-Release Buckle (plastic)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.35, "supplier_name": "YKK / National Molding",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 3},
        {"part_id": "SWV-263", "description": "Swivel Mount Bracket (aluminum)", "category": PartCategory.COMPONENT,
         "unit_cost": 2.80, "supplier_name": "Apex CNC Works",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 1},
        {"part_id": "PAD-264", "description": "Silicone Comfort Pad", "category": PartCategory.COMPONENT,
         "unit_cost": 0.90, "supplier_name": "YKK / National Molding",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 3},
        {"part_id": "REF-265", "description": "Rear Reflective Safety Strip", "category": PartCategory.COMPONENT,
         "unit_cost": 0.25, "supplier_name": "REF-Tech",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "HSG-271", "description": "Die-Cast Housing Shell (magnesium)", "category": PartCategory.COMPONENT,
         "unit_cost": 6.20, "supplier_name": "Precision Die Cast",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 1},
        {"part_id": "GKT-272", "description": "Housing Gasket (silicone, rectangular)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.18, "supplier_name": "Parker Hannifin",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 2},
        {"part_id": "SCR-273", "description": "M2 Stainless Screws (set of 6)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.30, "supplier_name": "McMaster-Carr",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "LBL-275", "description": "Product Label (laser-etched)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.45, "supplier_name": "LaserMark Inc.",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 2},
        {"part_id": "SEN-246", "description": "Motion Sensor (accelerometer)", "category": PartCategory.COMPONENT,
         "unit_cost": 1.50, "supplier_name": "STMicroelectronics",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.6, "substitute_pool_size": 1},
        # Headlamp packaging
        {"part_id": "PKG-311", "description": "Headlamp Retail Box", "category": PartCategory.COMPONENT,
         "unit_cost": 2.10, "supplier_name": "Uline",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "PKG-312", "description": "Molded Tray Insert", "category": PartCategory.COMPONENT,
         "unit_cost": 1.20, "supplier_name": "Uline",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        # Weapon light components
        {"part_id": "BAT-217", "description": "CR123A Lithium Cell", "category": PartCategory.COMPONENT,
         "unit_cost": 3.80, "supplier_name": "Energizer Industrial",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 2},
        {"part_id": "RIL-281", "description": "Picatinny Rail Clamp (7075 Aluminum)", "category": PartCategory.COMPONENT,
         "unit_cost": 5.60, "supplier_name": "Apex CNC Works",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.8, "substitute_pool_size": 1},
        {"part_id": "LVR-282", "description": "Quick-Detach Lever", "category": PartCategory.COMPONENT,
         "unit_cost": 2.40, "supplier_name": "Apex CNC Works",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 1},
        {"part_id": "PIN-283", "description": "Cross-Lock Pin (hardened steel)", "category": PartCategory.COMPONENT,
         "unit_cost": 1.10, "supplier_name": "McMaster-Carr",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.4, "substitute_pool_size": 2},
        {"part_id": "TRQ-284", "description": "Torque Limiting Screw", "category": PartCategory.COMPONENT,
         "unit_cost": 0.85, "supplier_name": "McMaster-Carr",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 3},
        {"part_id": "PAD-285", "description": "Anti-Slip Interface Pad (rubber)", "category": PartCategory.COMPONENT,
         "unit_cost": 0.30, "supplier_name": "YKK / National Molding",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "TSW-291", "description": "Dual-Function Tail Switch", "category": PartCategory.COMPONENT,
         "unit_cost": 4.50, "supplier_name": "Dongguan SwitchTech",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 1},
        {"part_id": "REM-292", "description": "Remote Pressure Pad (with cable)", "category": PartCategory.COMPONENT,
         "unit_cost": 6.80, "supplier_name": "Shenzhen CableWorks",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 0},
        {"part_id": "CBL-293", "description": "Coiled Activation Cable (1m)", "category": PartCategory.COMPONENT,
         "unit_cost": 2.20, "supplier_name": "Shenzhen CableWorks",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.4, "substitute_pool_size": 1},
        {"part_id": "VLC-294", "description": "Velcro Cable Management Strips", "category": PartCategory.COMPONENT,
         "unit_cost": 0.40, "supplier_name": "YKK / National Molding",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "CH-236", "description": "Weapon Light Body Tube (7075-T6)", "category": PartCategory.COMPONENT,
         "unit_cost": 12.50, "supplier_name": "Apex CNC Works",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.8, "substitute_pool_size": 1},
        {"part_id": "STB-247", "description": "Strobe Circuit Module", "category": PartCategory.COMPONENT,
         "unit_cost": 2.30, "supplier_name": "STMicroelectronics",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 1},
        # Weapon light packaging
        {"part_id": "PKG-321", "description": "Weapon Light Hard Case", "category": PartCategory.COMPONENT,
         "unit_cost": 8.50, "supplier_name": "Pelican Products",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 1},
        {"part_id": "PKG-322", "description": "Custom Foam Insert", "category": PartCategory.COMPONENT,
         "unit_cost": 2.40, "supplier_name": "Uline",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.1, "substitute_pool_size": 3},
        {"part_id": "PKG-323", "description": "Rail Adapter Kit (2 sizes)", "category": PartCategory.COMPONENT,
         "unit_cost": 3.20, "supplier_name": "Pelican Products",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.2, "substitute_pool_size": 1},

        # --- Services (4) ---
        {"part_id": "ANO-234", "description": "Type III Hard Anodize (service)", "category": PartCategory.SERVICE,
         "unit_cost": 2.50, "supplier_name": "MIL-SPEC Coatings",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.5, "substitute_pool_size": 1},
        {"part_id": "KNL-235", "description": "Knurling Treatment (service)", "category": PartCategory.SERVICE,
         "unit_cost": 1.20, "supplier_name": "MIL-SPEC Coatings",
         "criticality": CriticalityLevel.LOW, "lead_time_sensitivity": 0.3, "substitute_pool_size": 1},
        {"part_id": "FW-244", "description": "Firmware Flash (service)", "category": PartCategory.SERVICE,
         "unit_cost": 0.50, "supplier_name": "FlashTech Solutions",
         "criticality": CriticalityLevel.HIGH, "lead_time_sensitivity": 0.7, "substitute_pool_size": 0},
        {"part_id": "RFL-224", "description": "Anti-Reflective Coating (service)", "category": PartCategory.SERVICE,
         "unit_cost": 0.85, "supplier_name": "OptiCoat Ltd",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.4, "substitute_pool_size": 1},
        {"part_id": "ANO-274", "description": "Anodize Finish (headlamp, service)", "category": PartCategory.SERVICE,
         "unit_cost": 1.80, "supplier_name": "MIL-SPEC Coatings",
         "criticality": CriticalityLevel.MEDIUM, "lead_time_sensitivity": 0.4, "substitute_pool_size": 1},
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
    # 3. BILL OF MATERIALS (~120 entries, 3-level: FG → SA → Component)
    # ---------------------------------------------------------------
    bom_data = [
        # ===== FL-001-T (Tactical Flashlight) =====
        # Level 1: FG → Sub-Assemblies
        {"parent": "FL-001-T", "component": "SA-LED-100", "qty": 1},
        {"parent": "FL-001-T", "component": "SA-PWR-110", "qty": 1},
        {"parent": "FL-001-T", "component": "SA-OPT-120", "qty": 1},
        {"parent": "FL-001-T", "component": "SA-BDY-130", "qty": 1},
        {"parent": "FL-001-T", "component": "SA-ELC-140", "qty": 1},
        {"parent": "FL-001-T", "component": "SA-PKG-150", "qty": 1},

        # ===== FL-001-S (Standard Flashlight) — same as T minus holster/lanyard =====
        {"parent": "FL-001-S", "component": "SA-LED-100", "qty": 1},
        {"parent": "FL-001-S", "component": "SA-PWR-110", "qty": 1},
        {"parent": "FL-001-S", "component": "SA-OPT-120", "qty": 1},
        {"parent": "FL-001-S", "component": "SA-BDY-130", "qty": 1},
        {"parent": "FL-001-S", "component": "SA-ELC-140", "qty": 1},
        {"parent": "FL-001-S", "component": "SA-PKG-150", "qty": 1},

        # ===== HL-002-P (Pro Headlamp) =====
        {"parent": "HL-002-P", "component": "SA-LED-100", "qty": 1},
        {"parent": "HL-002-P", "component": "SA-PWR-110", "qty": 1},
        {"parent": "HL-002-P", "component": "SA-OPT-120", "qty": 1},
        {"parent": "HL-002-P", "component": "SA-HBD-160", "qty": 1},
        {"parent": "HL-002-P", "component": "SA-HSG-170", "qty": 1},
        {"parent": "HL-002-P", "component": "SA-ELC-140", "qty": 1},
        {"parent": "HL-002-P", "component": "SA-PKG-155", "qty": 1},

        # ===== HL-002-B (Basic Headlamp) — same as P minus SEN-246, REF-265 =====
        {"parent": "HL-002-B", "component": "SA-LED-100", "qty": 1},
        {"parent": "HL-002-B", "component": "SA-PWR-110", "qty": 1},
        {"parent": "HL-002-B", "component": "SA-OPT-120", "qty": 1},
        {"parent": "HL-002-B", "component": "SA-HBD-160", "qty": 1},
        {"parent": "HL-002-B", "component": "SA-HSG-170", "qty": 1},
        {"parent": "HL-002-B", "component": "SA-ELC-140", "qty": 1},
        {"parent": "HL-002-B", "component": "SA-PKG-155", "qty": 1},

        # ===== WL-003-R (Weapon Light - Rifle) =====
        {"parent": "WL-003-R", "component": "SA-LED-100", "qty": 1},
        {"parent": "WL-003-R", "component": "SA-PWR-115", "qty": 1},
        {"parent": "WL-003-R", "component": "SA-OPT-120", "qty": 1},
        {"parent": "WL-003-R", "component": "SA-MNT-180", "qty": 1},
        {"parent": "WL-003-R", "component": "SA-ACT-190", "qty": 1},
        {"parent": "WL-003-R", "component": "SA-BDY-135", "qty": 1},
        {"parent": "WL-003-R", "component": "SA-ELC-145", "qty": 1},
        {"parent": "WL-003-R", "component": "SA-PKG-158", "qty": 1},

        # ===== WL-003-C (Weapon Light - Compact) — same minus REM-292, CBL-293, VLC-294; 1x BAT-217 =====
        {"parent": "WL-003-C", "component": "SA-LED-100", "qty": 1},
        {"parent": "WL-003-C", "component": "SA-PWR-115", "qty": 1},
        {"parent": "WL-003-C", "component": "SA-OPT-120", "qty": 1},
        {"parent": "WL-003-C", "component": "SA-MNT-180", "qty": 1},
        {"parent": "WL-003-C", "component": "SA-ACT-190", "qty": 1},
        {"parent": "WL-003-C", "component": "SA-BDY-135", "qty": 1},
        {"parent": "WL-003-C", "component": "SA-ELC-145", "qty": 1},
        {"parent": "WL-003-C", "component": "SA-PKG-158", "qty": 1},

        # ===== Level 2: Sub-Assembly → Components =====

        # SA-LED-100 (LED Module — shared by all 6 products)
        {"parent": "SA-LED-100", "component": "LED-201", "qty": 1},
        {"parent": "SA-LED-100", "component": "PCB-202", "qty": 1},
        {"parent": "SA-LED-100", "component": "HS-203", "qty": 1},
        {"parent": "SA-LED-100", "component": "TCP-204", "qty": 1},
        {"parent": "SA-LED-100", "component": "MCR-205", "qty": 1},
        {"parent": "SA-LED-100", "component": "RST-206", "qty": 1},

        # SA-PWR-110 (Power Module — FL-001-T/S, HL-002-P/B)
        {"parent": "SA-PWR-110", "component": "BAT-211", "qty": 1},
        {"parent": "SA-PWR-110", "component": "PCB-212", "qty": 1},
        {"parent": "SA-PWR-110", "component": "SPR-213", "qty": 1},
        {"parent": "SA-PWR-110", "component": "USB-214", "qty": 1},
        {"parent": "SA-PWR-110", "component": "IND-215", "qty": 1},
        {"parent": "SA-PWR-110", "component": "WRH-216", "qty": 1},

        # SA-PWR-115 (Power Module CR123A — WL-003-R/C)
        {"parent": "SA-PWR-115", "component": "BAT-217", "qty": 2},  # WL-003-R uses 2x CR123A
        {"parent": "SA-PWR-115", "component": "SPR-213", "qty": 1},
        {"parent": "SA-PWR-115", "component": "WRH-216", "qty": 1},

        # SA-OPT-120 (Optics Assembly — shared)
        {"parent": "SA-OPT-120", "component": "LNS-221", "qty": 1},
        {"parent": "SA-OPT-120", "component": "BZL-222", "qty": 1},
        {"parent": "SA-OPT-120", "component": "GKT-223", "qty": 1},
        {"parent": "SA-OPT-120", "component": "RFL-224", "qty": 1},
        {"parent": "SA-OPT-120", "component": "RET-225", "qty": 1},

        # SA-BDY-130 (Body Assembly — FL-001-T/S)
        {"parent": "SA-BDY-130", "component": "CH-231", "qty": 1},
        {"parent": "SA-BDY-130", "component": "SW-232", "qty": 1},
        {"parent": "SA-BDY-130", "component": "CLP-233", "qty": 1},
        {"parent": "SA-BDY-130", "component": "ANO-234", "qty": 1},
        {"parent": "SA-BDY-130", "component": "KNL-235", "qty": 1},
        {"parent": "SA-BDY-130", "component": "THD-236", "qty": 1},
        {"parent": "SA-BDY-130", "component": "GKT-237", "qty": 1},

        # SA-ELC-140 (Electronics — FL-001-T/S, HL-002-P/B base)
        {"parent": "SA-ELC-140", "component": "MCU-241", "qty": 1},
        {"parent": "SA-ELC-140", "component": "FET-242", "qty": 1},
        {"parent": "SA-ELC-140", "component": "CAP-243", "qty": 1},
        {"parent": "SA-ELC-140", "component": "FW-244", "qty": 1},
        {"parent": "SA-ELC-140", "component": "DRV-245", "qty": 1},

        # SA-PKG-150 (Flashlight Packaging — FL-001-T includes holster/lanyard)
        {"parent": "SA-PKG-150", "component": "PKG-301", "qty": 1},
        {"parent": "SA-PKG-150", "component": "PKG-302", "qty": 1},
        {"parent": "SA-PKG-150", "component": "PKG-303", "qty": 1},
        {"parent": "SA-PKG-150", "component": "LYD-304", "qty": 1},
        {"parent": "SA-PKG-150", "component": "HST-305", "qty": 1},
        {"parent": "SA-PKG-150", "component": "SLP-306", "qty": 1},

        # SA-HBD-160 (Headband — HL-002-P/B)
        {"parent": "SA-HBD-160", "component": "HBD-261", "qty": 1},
        {"parent": "SA-HBD-160", "component": "BKL-262", "qty": 1},
        {"parent": "SA-HBD-160", "component": "SWV-263", "qty": 1},
        {"parent": "SA-HBD-160", "component": "PAD-264", "qty": 1},
        {"parent": "SA-HBD-160", "component": "REF-265", "qty": 1},

        # SA-HSG-170 (Lamp Housing — HL-002-P/B)
        {"parent": "SA-HSG-170", "component": "HSG-271", "qty": 1},
        {"parent": "SA-HSG-170", "component": "GKT-272", "qty": 1},
        {"parent": "SA-HSG-170", "component": "SCR-273", "qty": 1},
        {"parent": "SA-HSG-170", "component": "ANO-274", "qty": 1},
        {"parent": "SA-HSG-170", "component": "LBL-275", "qty": 1},

        # SA-MNT-180 (Picatinny Mount — WL-003-R/C)
        {"parent": "SA-MNT-180", "component": "RIL-281", "qty": 1},
        {"parent": "SA-MNT-180", "component": "LVR-282", "qty": 1},
        {"parent": "SA-MNT-180", "component": "PIN-283", "qty": 1},
        {"parent": "SA-MNT-180", "component": "TRQ-284", "qty": 1},
        {"parent": "SA-MNT-180", "component": "PAD-285", "qty": 1},

        # SA-ACT-190 (Activation — WL-003-R gets full kit, WL-003-C gets TSW only)
        {"parent": "SA-ACT-190", "component": "TSW-291", "qty": 1},
        {"parent": "SA-ACT-190", "component": "REM-292", "qty": 1},
        {"parent": "SA-ACT-190", "component": "CBL-293", "qty": 1},
        {"parent": "SA-ACT-190", "component": "VLC-294", "qty": 1},

        # SA-BDY-135 (Weapon Light Body — WL-003-R/C)
        {"parent": "SA-BDY-135", "component": "CH-236", "qty": 1},
        {"parent": "SA-BDY-135", "component": "ANO-234", "qty": 1},
        {"parent": "SA-BDY-135", "component": "GKT-237", "qty": 1},
        {"parent": "SA-BDY-135", "component": "KNL-235", "qty": 1},

        # SA-ELC-145 (Weapon Light Electronics — WL-003-R/C)
        {"parent": "SA-ELC-145", "component": "MCU-241", "qty": 1},
        {"parent": "SA-ELC-145", "component": "FET-242", "qty": 1},
        {"parent": "SA-ELC-145", "component": "CAP-243", "qty": 1},
        {"parent": "SA-ELC-145", "component": "FW-244", "qty": 1},
        {"parent": "SA-ELC-145", "component": "DRV-245", "qty": 1},
        {"parent": "SA-ELC-145", "component": "STB-247", "qty": 1},

        # SA-PKG-155 (Headlamp Packaging)
        {"parent": "SA-PKG-155", "component": "PKG-311", "qty": 1},
        {"parent": "SA-PKG-155", "component": "PKG-312", "qty": 1},
        {"parent": "SA-PKG-155", "component": "PKG-303", "qty": 1},
        {"parent": "SA-PKG-155", "component": "SLP-306", "qty": 1},

        # SA-PKG-158 (Weapon Light Packaging)
        {"parent": "SA-PKG-158", "component": "PKG-321", "qty": 1},
        {"parent": "SA-PKG-158", "component": "PKG-322", "qty": 1},
        {"parent": "SA-PKG-158", "component": "PKG-303", "qty": 1},
        {"parent": "SA-PKG-158", "component": "PKG-323", "qty": 1},
    ]

    for b in bom_data:
        entry = BOMEntry(
            parent_id=parts[b["parent"]].id,
            component_id=parts[b["component"]].id,
            quantity_per=b["qty"],
        )
        db.add(entry)

    # ---------------------------------------------------------------
    # 4. INVENTORY (Starting levels with built-in tension)
    # ---------------------------------------------------------------
    # Daily burn rates based on 750 units/month total production
    # FL-001-T:200, FL-001-S:250, HL-002-P:120, HL-002-B:80, WL-003-R:60, WL-003-C:40
    inventory_data = [
        # Finished Goods
        {"part_id": "FL-001-T", "on_hand": 120, "safety_stock": 50, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "FL-001-S", "on_hand": 300, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 11.0},
        {"part_id": "HL-002-P", "on_hand": 80, "safety_stock": 30, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "HL-002-B", "on_hand": 60, "safety_stock": 20, "reserved": 0, "daily_burn_rate": 4.0},
        {"part_id": "WL-003-R", "on_hand": 45, "safety_stock": 15, "reserved": 0, "daily_burn_rate": 3.0},
        {"part_id": "WL-003-C", "on_hand": 30, "safety_stock": 10, "reserved": 0, "daily_burn_rate": 2.0},
        # Key components with tension
        {"part_id": "LED-201", "on_hand": 1450, "safety_stock": 625, "reserved": 100, "daily_burn_rate": 34.0},
        {"part_id": "PCB-202", "on_hand": 900, "safety_stock": 375, "reserved": 50, "daily_burn_rate": 34.0},
        {"part_id": "MCU-241", "on_hand": 380, "safety_stock": 500, "reserved": 0, "daily_burn_rate": 34.0},  # BELOW SAFETY
        {"part_id": "BAT-211", "on_hand": 1100, "safety_stock": 540, "reserved": 50, "daily_burn_rate": 29.0},
        {"part_id": "BAT-217", "on_hand": 600, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 8.0},
        {"part_id": "CH-231", "on_hand": 280, "safety_stock": 225, "reserved": 30, "daily_burn_rate": 20.0},  # Just above
        {"part_id": "CH-236", "on_hand": 150, "safety_stock": 50, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "GKT-223", "on_hand": 2800, "safety_stock": 750, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "LNS-221", "on_hand": 420, "safety_stock": 500, "reserved": 0, "daily_burn_rate": 34.0},  # BELOW SAFETY
        {"part_id": "USB-214", "on_hand": 180, "safety_stock": 150, "reserved": 20, "daily_burn_rate": 29.0},
        {"part_id": "HSG-271", "on_hand": 350, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "RIL-281", "on_hand": 85, "safety_stock": 50, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "SW-232", "on_hand": 500, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 20.0},
        {"part_id": "TSW-291", "on_hand": 120, "safety_stock": 50, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "HBD-261", "on_hand": 350, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "REM-292", "on_hand": 90, "safety_stock": 30, "reserved": 0, "daily_burn_rate": 3.0},
        # Remaining components (comfortable stock)
        {"part_id": "HS-203", "on_hand": 800, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "TCP-204", "on_hand": 5000, "safety_stock": 500, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "MCR-205", "on_hand": 1200, "safety_stock": 300, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "RST-206", "on_hand": 8000, "safety_stock": 1000, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "PCB-212", "on_hand": 600, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 29.0},
        {"part_id": "SPR-213", "on_hand": 3000, "safety_stock": 500, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "IND-215", "on_hand": 4000, "safety_stock": 500, "reserved": 0, "daily_burn_rate": 29.0},
        {"part_id": "WRH-216", "on_hand": 2000, "safety_stock": 400, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "BZL-222", "on_hand": 700, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "RET-225", "on_hand": 1500, "safety_stock": 300, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "CLP-233", "on_hand": 1000, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 20.0},
        {"part_id": "THD-236", "on_hand": 2000, "safety_stock": 300, "reserved": 0, "daily_burn_rate": 20.0},
        {"part_id": "GKT-237", "on_hand": 3000, "safety_stock": 500, "reserved": 0, "daily_burn_rate": 25.0},
        {"part_id": "FET-242", "on_hand": 2500, "safety_stock": 400, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "CAP-243", "on_hand": 6000, "safety_stock": 800, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "DRV-245", "on_hand": 1800, "safety_stock": 400, "reserved": 0, "daily_burn_rate": 34.0},
        # Packaging
        {"part_id": "PKG-301", "on_hand": 2000, "safety_stock": 500, "reserved": 0, "daily_burn_rate": 20.0},
        {"part_id": "PKG-302", "on_hand": 2000, "safety_stock": 500, "reserved": 0, "daily_burn_rate": 20.0},
        {"part_id": "PKG-303", "on_hand": 5000, "safety_stock": 1000, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "LYD-304", "on_hand": 1500, "safety_stock": 300, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "HST-305", "on_hand": 800, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "SLP-306", "on_hand": 4000, "safety_stock": 600, "reserved": 0, "daily_burn_rate": 29.0},
        # Headlamp components
        {"part_id": "BKL-262", "on_hand": 600, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "SWV-263", "on_hand": 400, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "PAD-264", "on_hand": 500, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "REF-265", "on_hand": 400, "safety_stock": 60, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "GKT-272", "on_hand": 1500, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "SCR-273", "on_hand": 3000, "safety_stock": 300, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "LBL-275", "on_hand": 800, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "SEN-246", "on_hand": 250, "safety_stock": 60, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "PKG-311", "on_hand": 1000, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 9.0},
        {"part_id": "PKG-312", "on_hand": 1000, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 9.0},
        # Weapon light components
        {"part_id": "LVR-282", "on_hand": 200, "safety_stock": 50, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "PIN-283", "on_hand": 500, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "TRQ-284", "on_hand": 600, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "PAD-285", "on_hand": 800, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "CBL-293", "on_hand": 150, "safety_stock": 30, "reserved": 0, "daily_burn_rate": 3.0},
        {"part_id": "VLC-294", "on_hand": 400, "safety_stock": 50, "reserved": 0, "daily_burn_rate": 3.0},
        {"part_id": "STB-247", "on_hand": 200, "safety_stock": 50, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "PKG-321", "on_hand": 150, "safety_stock": 30, "reserved": 0, "daily_burn_rate": 3.0},
        {"part_id": "PKG-322", "on_hand": 300, "safety_stock": 50, "reserved": 0, "daily_burn_rate": 5.0},
        {"part_id": "PKG-323", "on_hand": 200, "safety_stock": 30, "reserved": 0, "daily_burn_rate": 3.0},
        # Services (virtual inventory — tracks capacity slots)
        {"part_id": "ANO-234", "on_hand": 500, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 25.0},
        {"part_id": "KNL-235", "on_hand": 500, "safety_stock": 100, "reserved": 0, "daily_burn_rate": 25.0},
        {"part_id": "FW-244", "on_hand": 1000, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "RFL-224", "on_hand": 800, "safety_stock": 200, "reserved": 0, "daily_burn_rate": 34.0},
        {"part_id": "ANO-274", "on_hand": 300, "safety_stock": 50, "reserved": 0, "daily_burn_rate": 9.0},
    ]

    for inv in inventory_data:
        record = Inventory(
            part_id=parts[inv["part_id"]].id,
            on_hand=inv["on_hand"],
            safety_stock=inv["safety_stock"],
            reserved=inv.get("reserved", 0),
            ring_fenced_qty=0,
            daily_burn_rate=inv["daily_burn_rate"],
        )
        db.add(record)

    # ---------------------------------------------------------------
    # 5. DEMAND FORECASTS (7 periods × 5 products = 35 records)
    # ---------------------------------------------------------------
    forecast_data = [
        # Historical actuals (2025)
        {"part_id": "FL-001-T", "period": "2025-Q1", "forecast_qty": 500, "actual_qty": 480,
         "source": "HISTORICAL_AVG", "confidence_level": "HIGH", "forecast_accuracy_pct": 0.92, "notes": "Post-holiday slowdown"},
        {"part_id": "FL-001-T", "period": "2025-Q2", "forecast_qty": 570, "actual_qty": 550,
         "source": "HISTORICAL_AVG", "confidence_level": "HIGH", "forecast_accuracy_pct": 0.87, "notes": "Spring outdoor season"},
        {"part_id": "FL-001-T", "period": "2025-Q3", "forecast_qty": 700, "actual_qty": 680,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.78, "notes": "Peak camping"},
        {"part_id": "FL-001-T", "period": "2025-Q4", "forecast_qty": 720, "actual_qty": 750,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.85, "notes": "Holiday + military Q4"},
        {"part_id": "FL-001-T", "period": "2026-Q1", "forecast_qty": 540, "actual_qty": 520,
         "source": "HISTORICAL_AVG", "confidence_level": "HIGH", "forecast_accuracy_pct": 0.92, "notes": "Post-holiday dip"},
        {"part_id": "FL-001-T", "period": "2026-Q2", "forecast_qty": 600, "actual_qty": 0,
         "source": "SALES_PIPELINE", "confidence_level": "MEDIUM", "notes": "Expected spring uptick"},
        {"part_id": "FL-001-T", "period": "2026-Q3", "forecast_qty": 720, "actual_qty": 0,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "LOW", "notes": "Peak season forecast"},

        {"part_id": "FL-001-S", "period": "2025-Q1", "forecast_qty": 640, "actual_qty": 620,
         "source": "HISTORICAL_AVG", "confidence_level": "HIGH", "forecast_accuracy_pct": 0.94, "notes": ""},
        {"part_id": "FL-001-S", "period": "2025-Q2", "forecast_qty": 720, "actual_qty": 700,
         "source": "HISTORICAL_AVG", "confidence_level": "HIGH", "forecast_accuracy_pct": 0.91, "notes": ""},
        {"part_id": "FL-001-S", "period": "2025-Q3", "forecast_qty": 870, "actual_qty": 850,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.82, "notes": ""},
        {"part_id": "FL-001-S", "period": "2025-Q4", "forecast_qty": 920, "actual_qty": 950,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.88, "notes": ""},
        {"part_id": "FL-001-S", "period": "2026-Q1", "forecast_qty": 700, "actual_qty": 680,
         "source": "HISTORICAL_AVG", "confidence_level": "HIGH", "forecast_accuracy_pct": 0.94, "notes": ""},
        {"part_id": "FL-001-S", "period": "2026-Q2", "forecast_qty": 750, "actual_qty": 0,
         "source": "SALES_PIPELINE", "confidence_level": "MEDIUM", "notes": ""},
        {"part_id": "FL-001-S", "period": "2026-Q3", "forecast_qty": 900, "actual_qty": 0,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "LOW", "notes": ""},

        {"part_id": "HL-002-P", "period": "2025-Q1", "forecast_qty": 300, "actual_qty": 280,
         "source": "HISTORICAL_AVG", "confidence_level": "HIGH", "forecast_accuracy_pct": 0.88, "notes": ""},
        {"part_id": "HL-002-P", "period": "2025-Q2", "forecast_qty": 360, "actual_qty": 350,
         "source": "HISTORICAL_AVG", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.83, "notes": ""},
        {"part_id": "HL-002-P", "period": "2025-Q3", "forecast_qty": 440, "actual_qty": 420,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.72, "notes": ""},
        {"part_id": "HL-002-P", "period": "2025-Q4", "forecast_qty": 400, "actual_qty": 380,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.80, "notes": ""},
        {"part_id": "HL-002-P", "period": "2026-Q1", "forecast_qty": 310, "actual_qty": 300,
         "source": "HISTORICAL_AVG", "confidence_level": "HIGH", "forecast_accuracy_pct": 0.88, "notes": ""},
        {"part_id": "HL-002-P", "period": "2026-Q2", "forecast_qty": 380, "actual_qty": 0,
         "source": "SALES_PIPELINE", "confidence_level": "MEDIUM", "notes": ""},
        {"part_id": "HL-002-P", "period": "2026-Q3", "forecast_qty": 450, "actual_qty": 0,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "LOW", "notes": ""},

        {"part_id": "WL-003-R", "period": "2025-Q1", "forecast_qty": 160, "actual_qty": 140,
         "source": "HISTORICAL_AVG", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.76, "notes": ""},
        {"part_id": "WL-003-R", "period": "2025-Q2", "forecast_qty": 190, "actual_qty": 180,
         "source": "HISTORICAL_AVG", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.71, "notes": ""},
        {"part_id": "WL-003-R", "period": "2025-Q3", "forecast_qty": 270, "actual_qty": 250,
         "source": "SALES_PIPELINE", "confidence_level": "LOW", "forecast_accuracy_pct": 0.65, "notes": "Lumpy military"},
        {"part_id": "WL-003-R", "period": "2025-Q4", "forecast_qty": 280, "actual_qty": 300,
         "source": "SALES_PIPELINE", "confidence_level": "LOW", "forecast_accuracy_pct": 0.82, "notes": "Military Q4 spend"},
        {"part_id": "WL-003-R", "period": "2026-Q1", "forecast_qty": 170, "actual_qty": 160,
         "source": "HISTORICAL_AVG", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.76, "notes": ""},
        {"part_id": "WL-003-R", "period": "2026-Q2", "forecast_qty": 200, "actual_qty": 0,
         "source": "SALES_PIPELINE", "confidence_level": "LOW", "notes": ""},
        {"part_id": "WL-003-R", "period": "2026-Q3", "forecast_qty": 260, "actual_qty": 0,
         "source": "SALES_PIPELINE", "confidence_level": "LOW", "notes": ""},

        # HL-002-B shares trend with HL-002-P at lower volume
        {"part_id": "HL-002-B", "period": "2025-Q3", "forecast_qty": 200, "actual_qty": 190,
         "source": "HISTORICAL_AVG", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.80, "notes": ""},
        {"part_id": "HL-002-B", "period": "2025-Q4", "forecast_qty": 180, "actual_qty": 170,
         "source": "HISTORICAL_AVG", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.82, "notes": ""},
        {"part_id": "HL-002-B", "period": "2026-Q1", "forecast_qty": 160, "actual_qty": 150,
         "source": "HISTORICAL_AVG", "confidence_level": "HIGH", "forecast_accuracy_pct": 0.85, "notes": ""},
        {"part_id": "HL-002-B", "period": "2026-Q2", "forecast_qty": 200, "actual_qty": 0,
         "source": "SALES_PIPELINE", "confidence_level": "MEDIUM", "notes": ""},
        {"part_id": "HL-002-B", "period": "2026-Q3", "forecast_qty": 240, "actual_qty": 0,
         "source": "SEASONAL_ADJUSTMENT", "confidence_level": "LOW", "notes": ""},

        # WL-003-C
        {"part_id": "WL-003-C", "period": "2026-Q1", "forecast_qty": 80, "actual_qty": 75,
         "source": "HISTORICAL_AVG", "confidence_level": "MEDIUM", "forecast_accuracy_pct": 0.78, "notes": ""},
        {"part_id": "WL-003-C", "period": "2026-Q2", "forecast_qty": 100, "actual_qty": 0,
         "source": "SALES_PIPELINE", "confidence_level": "LOW", "notes": ""},
    ]

    for f in forecast_data:
        forecast = DemandForecast(
            part_id=parts[f["part_id"]].id,
            forecast_qty=f["forecast_qty"],
            actual_qty=f["actual_qty"],
            period=f["period"],
            source=f.get("source", "HISTORICAL_AVG"),
            confidence_level=f.get("confidence_level", "MEDIUM"),
            forecast_accuracy_pct=f.get("forecast_accuracy_pct"),
            notes=f.get("notes", ""),
        )
        db.add(forecast)

    # ---------------------------------------------------------------
    # 6. SALES ORDERS (6 realistic orders)
    # ---------------------------------------------------------------
    sales_order_data = [
        {"order_number": "SO-MIL-001", "part_id": "WL-003-R", "quantity": 200, "priority": "VIP"},
        {"order_number": "SO-AMZ-002", "part_id": "FL-001-S", "quantity": 500, "priority": "NORMAL"},
        {"order_number": "SO-REI-003", "part_id": "HL-002-P", "quantity": 150, "priority": "NORMAL"},
        {"order_number": "SO-LEO-004", "part_id": "FL-001-T", "quantity": 300, "priority": "EXPEDITED"},
        {"order_number": "SO-DLR-005", "part_id": "FL-001-T", "quantity": 50, "priority": "NORMAL"},
        {"order_number": "SO-OEM-006", "part_id": "SA-LED-100", "quantity": 100, "priority": "NORMAL"},
    ]

    for so in sales_order_data:
        order = SalesOrder(
            order_number=so["order_number"],
            part_id=parts[so["part_id"]].id,
            quantity=so["quantity"],
            priority=so["priority"],
            status=SalesOrderStatus.OPEN,
        )
        db.add(order)

    # ---------------------------------------------------------------
    # 7. SUPPLIER CONTRACTS (6 contracts)
    # ---------------------------------------------------------------
    contracts_data = [
        {"contract_number": "BPA-CREE-2026", "supplier_name": "CREE Inc.",
         "contract_type": ContractType.BLANKET_PO,
         "start_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
         "end_date": datetime(2026, 12, 31, tzinfo=timezone.utc),
         "total_committed_value": 180000.0, "total_committed_qty": 15000,
         "released_value": 120000.0, "released_qty": 10000,
         "price_schedule": json.dumps([{"part_id": "LED-201", "unit_price": 11.50, "spot_price": 12.80}]),
         "payment_terms": "Net 30", "status": ContractStatus.ACTIVE},
        {"contract_number": "BPA-SSDI-2026", "supplier_name": "Samsung SDI",
         "contract_type": ContractType.BLANKET_PO,
         "start_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
         "end_date": datetime(2026, 12, 31, tzinfo=timezone.utc),
         "total_committed_value": 95000.0, "total_committed_qty": 20000,
         "released_value": 60000.0, "released_qty": 12600,
         "price_schedule": json.dumps([{"part_id": "BAT-211", "unit_price": 4.75, "spot_price": 5.40}]),
         "payment_terms": "Net 30", "status": ContractStatus.ACTIVE},
        {"contract_number": "FW-WURTH-2026", "supplier_name": "Wurth Elektronik",
         "contract_type": ContractType.FRAMEWORK,
         "start_date": datetime(2025, 7, 1, tzinfo=timezone.utc),
         "end_date": datetime(2027, 6, 30, tzinfo=timezone.utc),
         "total_committed_value": 120000.0, "total_committed_qty": None,
         "released_value": 45000.0, "released_qty": 0,
         "price_schedule": json.dumps([
             {"part_id": "MCU-241", "unit_price": 1.85},
             {"part_id": "FET-242", "unit_price": 0.55},
             {"part_id": "CAP-243", "unit_price": 0.30},
             {"part_id": "DRV-245", "unit_price": 0.95},
             {"part_id": "RST-206", "unit_price": 0.08},
         ]),
         "payment_terms": "2/10 Net 30", "status": ContractStatus.ACTIVE},
        {"contract_number": "SPT-APEX", "supplier_name": "Apex CNC Works",
         "contract_type": ContractType.SPOT_BUY,
         "start_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
         "end_date": datetime(2026, 12, 31, tzinfo=timezone.utc),
         "total_committed_value": None, "total_committed_qty": None,
         "released_value": 32000.0, "released_qty": 0,
         "price_schedule": json.dumps([]),
         "payment_terms": "Net 30", "status": ContractStatus.ACTIVE},
        {"contract_number": "CSG-MCMASTER", "supplier_name": "McMaster-Carr",
         "contract_type": ContractType.CONSIGNMENT,
         "start_date": datetime(2025, 1, 1, tzinfo=timezone.utc),
         "end_date": datetime(2027, 12, 31, tzinfo=timezone.utc),
         "total_committed_value": None, "total_committed_qty": None,
         "released_value": 0.0, "released_qty": 0,
         "price_schedule": json.dumps([]),
         "payment_terms": "Pay on pull", "status": ContractStatus.ACTIVE},
        {"contract_number": "BPA-ENG-2026", "supplier_name": "Energizer Industrial",
         "contract_type": ContractType.BLANKET_PO,
         "start_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
         "end_date": datetime(2026, 12, 31, tzinfo=timezone.utc),
         "total_committed_value": 38000.0, "total_committed_qty": 10000,
         "released_value": 14400.0, "released_qty": 4000,
         "price_schedule": json.dumps([{"part_id": "BAT-217", "unit_price": 3.60, "spot_price": 3.80}]),
         "payment_terms": "Net 30", "status": ContractStatus.ACTIVE},
    ]

    for c in contracts_data:
        supplier_name = c.pop("supplier_name")
        contract = SupplierContract(
            **c,
            supplier_id=suppliers[supplier_name].id,
        )
        db.add(contract)

    # ---------------------------------------------------------------
    # 8. ALTERNATE SUPPLIER MAPPINGS (8 pairs)
    # ---------------------------------------------------------------
    alternate_data = [
        {"part_id": "LED-201", "primary": "CREE Inc.", "alternate": "Luminus Devices",
         "cost_premium_pct": 22.0, "lead_time_delta_days": 14, "notes": "Lower lumen output"},
        {"part_id": "BAT-211", "primary": "Samsung SDI", "alternate": "LG Energy Solution",
         "cost_premium_pct": 8.0, "lead_time_delta_days": 7, "notes": "Same spec"},
        {"part_id": "PCB-202", "primary": "ShenZhen FastPCB", "alternate": "PCBWay",
         "cost_premium_pct": 5.0, "lead_time_delta_days": 0, "notes": "Same region risk"},
        {"part_id": "PCB-202", "primary": "ShenZhen FastPCB", "alternate": "Advanced Circuits",
         "cost_premium_pct": 45.0, "lead_time_delta_days": -8, "notes": "Eliminates tariff risk"},
        {"part_id": "CH-231", "primary": "Apex CNC Works", "alternate": "Proto Labs",
         "cost_premium_pct": 60.0, "lead_time_delta_days": -7, "notes": "Rapid prototyping rates"},
        {"part_id": "GKT-223", "primary": "Parker Hannifin", "alternate": "Marco Rubber",
         "cost_premium_pct": 15.0, "lead_time_delta_days": 2, "notes": "Custom tooling needed"},
        {"part_id": "MCU-241", "primary": "Wurth Elektronik", "alternate": "Digi-Key",
         "cost_premium_pct": 35.0, "lead_time_delta_days": -14, "notes": "No allocation guarantee"},
        {"part_id": "SW-232", "primary": "Dongguan SwitchTech", "alternate": "C&K Switches",
         "cost_premium_pct": 40.0, "lead_time_delta_days": -5, "notes": "Higher quality"},
    ]

    for a in alternate_data:
        alt = AlternateSupplier(
            part_id=parts[a["part_id"]].id,
            primary_supplier_id=suppliers[a["primary"]].id,
            alternate_supplier_id=suppliers[a["alternate"]].id,
            cost_premium_pct=a["cost_premium_pct"],
            lead_time_delta_days=a["lead_time_delta_days"],
            notes=a["notes"],
        )
        db.add(alt)

    db.commit()
    db.close()

    print("=" * 60)
    print("Core-Guard Tactical Lighting Division — Seed Complete")
    print("=" * 60)
    print(f"  Suppliers:          {len(suppliers_data)}")
    print(f"  Parts:              {len(parts_data)}")
    print(f"  BOM entries:        {len(bom_data)}")
    print(f"  Inventory records:  {len(inventory_data)}")
    print(f"  Demand forecasts:   {len(forecast_data)}")
    print(f"  Sales orders:       {len(sales_order_data)}")
    print(f"  Contracts:          {len(contracts_data)}")
    print(f"  Alternate suppliers:{len(alternate_data)}")
    print("=" * 60)


if __name__ == "__main__":
    seed()
