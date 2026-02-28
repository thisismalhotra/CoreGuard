# Realistic Seed Data & Multi-Product BOM Design

**Date:** 2026-02-27
**Status:** Approved
**Goal:** Transform CoreGuard from a 5-part demo into a credible multi-product supply chain simulation that passes the "smell test" for supply chain professionals evaluating the platform.

---

## 1. Product Family: Tactical Lighting Division

Three product lines, one manufacturer. All portable lighting products sharing common components.

| Product ID | Name | Category | Variants |
|---|---|---|---|
| FL-001 | Tactical Flashlight | Handheld | FL-001-T (Tactical), FL-001-S (Standard) |
| HL-002 | Tactical Headlamp | Head-Mounted | HL-002-P (Pro), HL-002-B (Basic) |
| WL-003 | Weapon-Mounted Light | Rail-Mount | WL-003-R (Rifle), WL-003-C (Compact) |

---

## 2. Bill of Materials (3 Levels, ~55 Unique Parts)

### FL-001-T (Tactical Flashlight) — Full BOM

```
FL-001-T  Tactical Flashlight
├── SA-LED-100  LED Module Assembly
│   ├── LED-201   CREE XHP70.3 HI LED Emitter          ($11.50)
│   ├── PCB-202   LED Driver PCB (Constant Current)     ($3.20)
│   ├── HS-203    Machined Aluminum Heat Sink            ($2.80)
│   ├── TCP-204   Thermal Compound Paste (0.5g)          ($0.35)
│   ├── MCR-205   MCPCB Star Board (20mm)                ($1.10)
│   └── RST-206   Current Sense Resistor (SMD)           ($0.08)
│
├── SA-PWR-110  Power Module
│   ├── BAT-211   18650 Li-Ion Cell (3500mAh)            ($4.75)
│   ├── PCB-212   Battery Protection Circuit (BMS)       ($1.85)
│   ├── SPR-213   Gold-Plated Contact Springs (pair)     ($0.45)
│   ├── USB-214   USB-C Charging Port Assembly           ($2.10)
│   ├── IND-215   Power Indicator LED (RGB)              ($0.22)
│   └── WRH-216   Internal Wiring Harness (22AWG)        ($0.90)
│
├── SA-OPT-120  Optics Assembly
│   ├── LNS-221   TIR Optic Lens (Polycarbonate)        ($1.60)
│   ├── BZL-222   Stainless Steel Bezel Ring             ($3.40)
│   ├── GKT-223   Lens O-Ring (Buna-N, 28mm)            ($0.12)
│   ├── RFL-224   Anti-Reflective Coating (service)      ($0.85)
│   └── RET-225   Centering Retainer Ring                ($0.40)
│
├── SA-BDY-130  Body Assembly
│   ├── CH-231    Body Tube (6061-T6 Aluminum)           ($8.50)
│   ├── SW-232    Reverse-Click Tail Switch Assembly     ($3.20)
│   ├── CLP-233   Deep Carry Pocket Clip (Spring Steel)  ($1.15)
│   ├── ANO-234   Type III Hard Anodize (service)        ($2.50)
│   ├── KNL-235   Knurling Treatment (service)           ($1.20)
│   ├── THD-236   Lubricated Thread Insert (Brass)       ($0.65)
│   └── GKT-237   Tail Cap O-Ring (Buna-N, 22mm)        ($0.10)
│
├── SA-ELC-140  Electronics/Control Module
│   ├── MCU-241   Microcontroller (ATtiny1616)           ($1.85)
│   ├── FET-242   N-Channel MOSFET (30V)                 ($0.55)
│   ├── CAP-243   Ceramic Decoupling Capacitors (kit)    ($0.30)
│   ├── FW-244    Firmware Flash (service)               ($0.50)
│   └── DRV-245   Gate Driver IC                         ($0.95)
│
├── SA-PKG-150  Packaging & Accessories
│   ├── PKG-301   Retail Box (printed cardboard)         ($1.80)
│   ├── PKG-302   Die-Cut Foam Insert                    ($0.95)
│   ├── PKG-303   User Manual + Warranty Card            ($0.40)
│   ├── LYD-304   Lanyard (550 Paracord)                 ($0.60)
│   ├── HST-305   Nylon Belt Holster                     ($3.50)
│   └── SLP-306   Spare O-Ring Set (2x)                  ($0.15)
```

### HL-002-P (Pro Headlamp) — Full BOM

```
HL-002-P  Pro Headlamp
├── SA-LED-100  LED Module Assembly (SHARED)
│   ├── LED-201, PCB-202, HS-203, TCP-204, MCR-205, RST-206
│
├── SA-PWR-110  Power Module (SHARED)
│   ├── BAT-211, PCB-212, SPR-213, USB-214, IND-215, WRH-216
│
├── SA-OPT-120  Optics Assembly (PARTIAL SHARED)
│   ├── LNS-221, GKT-223, RFL-224, RET-225
│
├── SA-HBD-160  Headband Assembly (UNIQUE)
│   ├── HBD-261   Elastic Headband (adjustable)          ($1.40)
│   ├── BKL-262   Quick-Release Buckle (plastic)         ($0.35)
│   ├── SWV-263   Swivel Mount Bracket (aluminum)        ($2.80)
│   ├── PAD-264   Silicone Comfort Pad                   ($0.90)
│   └── REF-265   Rear Reflective Safety Strip           ($0.25)
│
├── SA-HSG-170  Lamp Housing (UNIQUE)
│   ├── HSG-271   Die-Cast Housing Shell (magnesium)     ($6.20)
│   ├── GKT-272   Housing Gasket (silicone, rectangular) ($0.18)
│   ├── SCR-273   M2 Stainless Screws (set of 6)        ($0.30)
│   ├── ANO-274   Anodize Finish (service)               ($1.80)
│   └── LBL-275   Product Label (laser-etched)           ($0.45)
│
├── SA-ELC-140  Electronics/Control (SHARED + UNIQUE)
│   ├── MCU-241, FET-242, CAP-243, FW-244, DRV-245
│   └── SEN-246   Motion Sensor (accelerometer)          ($1.50)
│
├── SA-PKG-155  Packaging (UNIQUE)
│   ├── PKG-311   Headlamp Retail Box                    ($2.10)
│   ├── PKG-312   Molded Tray Insert                     ($1.20)
│   ├── PKG-303   User Manual (SHARED)                   ($0.40)
│   └── SLP-306   Spare O-Ring Set (SHARED)              ($0.15)
```

### WL-003-R (Weapon-Mounted Light) — Full BOM

```
WL-003-R  Weapon-Mounted Light
├── SA-LED-100  LED Module Assembly (SHARED)
│   ├── LED-201, PCB-202, HS-203, TCP-204, MCR-205, RST-206
│
├── SA-PWR-115  Power Module (DIFFERENT BATTERY)
│   ├── BAT-217   CR123A Lithium Cell (x2)               ($3.80)
│   ├── SPR-213   Contact Springs (SHARED)               ($0.45)
│   └── WRH-216   Wiring Harness (SHARED)                ($0.90)
│
├── SA-OPT-120  Optics Assembly (SHARED)
│   ├── LNS-221, BZL-222, GKT-223, RFL-224, RET-225
│
├── SA-MNT-180  Picatinny Mount Assembly (UNIQUE)
│   ├── RIL-281   Picatinny Rail Clamp (7075 Aluminum)   ($5.60)
│   ├── LVR-282   Quick-Detach Lever                     ($2.40)
│   ├── PIN-283   Cross-Lock Pin (hardened steel)        ($1.10)
│   ├── TRQ-284   Torque Limiting Screw                  ($0.85)
│   └── PAD-285   Anti-Slip Interface Pad (rubber)       ($0.30)
│
├── SA-ACT-190  Activation System (UNIQUE)
│   ├── TSW-291   Dual-Function Tail Switch              ($4.50)
│   ├── REM-292   Remote Pressure Pad (with cable)       ($6.80)
│   ├── CBL-293   Coiled Activation Cable (1m)           ($2.20)
│   └── VLC-294   Velcro Cable Management Strips         ($0.40)
│
├── SA-BDY-135  Weapon Light Body (UNIQUE)
│   ├── CH-236    Weapon Light Body Tube (7075-T6)       ($12.50)
│   ├── ANO-234   Type III Hard Anodize (SHARED)         ($2.50)
│   ├── GKT-237   Tail Cap O-Ring (SHARED)               ($0.10)
│   └── KNL-235   Knurling Treatment (SHARED)            ($1.20)
│
├── SA-ELC-145  Electronics (SHARED + UNIQUE)
│   ├── MCU-241, FET-242, CAP-243, FW-244, DRV-245
│   └── STB-247   Strobe Circuit Module                  ($2.30)
│
├── SA-PKG-158  Packaging (UNIQUE)
│   ├── PKG-321   Weapon Light Hard Case                 ($8.50)
│   ├── PKG-322   Custom Foam Insert                     ($2.40)
│   ├── PKG-303   User Manual (SHARED)                   ($0.40)
│   └── PKG-323   Rail Adapter Kit (2 sizes)             ($3.20)
```

### Variant BOMs (Simplified versions)

- **FL-001-S (Standard):** Same as FL-001-T minus HST-305 (holster), LYD-304 (lanyard). Uses cheaper PKG.
- **HL-002-B (Basic):** Same as HL-002-P minus SEN-246 (motion sensor), REF-265 (reflective strip).
- **WL-003-C (Compact):** Same as WL-003-R minus REM-292 (remote pad), CBL-293 (cable), VLC-294 (velcro). Uses single BAT-217.

### Shared Component Matrix

| Component | FL-001-T | FL-001-S | HL-002-P | HL-002-B | WL-003-R | WL-003-C |
|---|---|---|---|---|---|---|
| LED-201 | 1 | 1 | 1 | 1 | 1 | 1 |
| PCB-202 | 1 | 1 | 1 | 1 | 1 | 1 |
| MCU-241 | 1 | 1 | 1 | 1 | 1 | 1 |
| BAT-211 | 1 | 1 | 1 | 1 | - | - |
| BAT-217 | - | - | - | - | 2 | 1 |
| GKT-223 | 1 | 1 | 1 | 1 | 1 | 1 |
| LNS-221 | 1 | 1 | 1 | 1 | 1 | 1 |
| SPR-213 | 1 | 1 | 1 | 1 | 1 | 1 |
| ANO-234 | 1 | 1 | - | - | 1 | 1 |
| GKT-237 | 1 | 1 | - | - | 1 | 1 |
| PKG-303 | 1 | 1 | 1 | 1 | 1 | 1 |
| SLP-306 | 1 | 1 | 1 | 1 | - | - |

---

## 3. Supplier Model

### Supplier Table (Enhanced Schema)

```
Supplier
├── name
├── region (US | CHINA | TAIWAN | SOUTH_KOREA | GERMANY | MEXICO)
├── tier (1 | 2 | 3 | SERVICE)
├── lead_time_days (standard)
├── expedite_lead_time_days
├── reliability_score (0.0-1.0)
├── minimum_order_qty (MOQ)
├── capacity_per_month (units)
├── payment_terms ("Net 30", "2/10 Net 30", "50% upfront")
├── certifications (JSON array: ["ISO 9001", "ITAR", "RoHS"])
├── risk_factors (JSON array: ["single source", "geopolitical", "capacity constrained"])
├── is_active
├── contact_email
```

### Primary Suppliers

| Supplier | Region | Tier | Parts Supplied | Lead Time | Expedite | MOQ | Reliability | Risk |
|---|---|---|---|---|---|---|---|---|
| CREE Inc. | US | 1 | LED-201 | 42 days | 28 days | 500 | 0.94 | Single source |
| Samsung SDI | South Korea | 1 | BAT-211 | 35 days | 21 days | 1000 | 0.92 | Geopolitical |
| Wurth Elektronik | Germany | 1 | MCU-241, FET-242, CAP-243, DRV-245, RST-206 | 28 days | 18 days | 250 | 0.88 | Semiconductor allocation |
| Kingbright | Taiwan | 1 | IND-215, MCR-205 | 21 days | 14 days | 2000 | 0.91 | None |
| ShenZhen FastPCB | China | 2 | PCB-202, PCB-212 | 18 days | 10 days | 100 | 0.85 | Tariff risk |
| Jiangsu OptiMold | China | 2 | LNS-221, RET-225, BZL-222 | 25 days | 16 days | 500 | 0.83 | Tariff risk |
| Apex CNC Works | US | 2 | CH-231, CH-236, HS-203, RIL-281, SWV-263 | 14 days | 7 days | 50 | 0.90 | Capacity constrained |
| Precision Die Cast | Mexico | 2 | HSG-271 | 21 days | 14 days | 200 | 0.87 | None |
| Dongguan SwitchTech | China | 2 | SW-232, TSW-291 | 20 days | 12 days | 300 | 0.82 | Tariff risk |
| Parker Hannifin | US | 3 | GKT-223, GKT-237, GKT-272 | 7 days | 3 days | 1000 | 0.96 | None |
| McMaster-Carr | US | 3 | SPR-213, SCR-273, THD-236, PIN-283, TRQ-284 | 3 days | 1 day | 1 | 0.99 | None |
| Uline | US | 3 | PKG-301, PKG-302, PKG-311, PKG-312, PKG-322 | 5 days | 3 days | 500 | 0.97 | None |
| Shenzhen CableWorks | China | 3 | WRH-216, CBL-293, USB-214, REM-292 | 15 days | 8 days | 200 | 0.84 | Tariff risk |
| YKK / National Molding | US | 3 | BKL-262, VLC-294, PAD-264, HBD-261, CLP-233, LYD-304, HST-305 | 10 days | 5 days | 500 | 0.93 | None |
| MIL-SPEC Coatings | US | Service | ANO-234, ANO-274, KNL-235 | 10 days | 5 days | 100 | 0.91 | Batch scheduling |
| FlashTech Solutions | US | Service | FW-244 | 2 days | 1 day | 1 | 0.98 | In-house capability |
| OptiCoat Ltd | Taiwan | Service | RFL-224 | 15 days | 8 days | 300 | 0.89 | None |
| Pelican Products | US | 3 | PKG-321, PKG-323 | 12 days | 6 days | 50 | 0.95 | None |
| LaserMark Inc. | US | Service | LBL-275 | 5 days | 2 days | 100 | 0.94 | None |
| REF-Tech | US | 3 | REF-265 | 8 days | 4 days | 500 | 0.92 | None |
| SLP-306 vendor | US | 3 | SLP-306 | 5 days | 2 days | 1000 | 0.96 | None |
| Energizer Industrial | US | 1 | BAT-217 | 14 days | 7 days | 500 | 0.95 | None |
| STMicroelectronics | Germany | 1 | SEN-246, STB-247 | 30 days | 20 days | 100 | 0.87 | Semiconductor allocation |

### Alternate Suppliers (Failover)

| Primary | Alternate Supplier | Cost Premium | Lead Time Delta | Notes |
|---|---|---|---|---|
| CREE (LED-201) | Luminus Devices | +22% | +14 days | Lower lumen output |
| Samsung SDI (BAT-211) | LG Energy Solution | +8% | +7 days | Same spec |
| ShenZhen FastPCB (PCBs) | PCBWay | +5% | Same | Same region risk |
| ShenZhen FastPCB (PCBs) | Advanced Circuits (US) | +45% | -8 days | Eliminates tariff risk |
| Apex CNC (machining) | Proto Labs | +60% | -7 days | Rapid prototyping rates |
| Parker Hannifin (gaskets) | Marco Rubber | +15% | +2 days | Custom tooling needed |
| Wurth (MCU-241) | Digi-Key (broker) | +35% | -14 days | No allocation guarantee |
| Dongguan SwitchTech | C&K Switches (US) | +40% | -5 days | Higher quality |

### Contract/Agreement Model (New Table)

```
SupplierContract
├── contract_number (e.g., "BPA-CREE-2026-001")
├── supplier_id (FK)
├── contract_type (BLANKET_PO | SPOT_BUY | CONSIGNMENT | FRAMEWORK)
├── start_date, end_date
├── total_committed_value ($)
├── total_committed_qty
├── released_value / released_qty
├── remaining_value / remaining_qty
├── price_schedule (JSON: [{ part_id, unit_price, qty_min, qty_max }])
├── payment_terms
├── penalty_clause
├── status (ACTIVE | EXPIRING | EXPIRED | CANCELLED)
```

```
ScheduledRelease (call-offs against a blanket)
├── release_number ("REL-001")
├── contract_id (FK)
├── part_id (FK)
├── quantity
├── requested_delivery_date
├── actual_delivery_date (nullable)
├── status (SCHEDULED | IN_TRANSIT | DELIVERED | LATE)
```

### Sample Contracts

| Contract | Supplier | Type | Value | Term | Coverage |
|---|---|---|---|---|---|
| BPA-CREE-2026 | CREE Inc. | Blanket PO | $180K/yr | 12 months | LED-201: 15K units @ $11.50 (spot: $12.80) |
| BPA-SSDI-2026 | Samsung SDI | Blanket PO | $95K/yr | 12 months | BAT-211: 20K cells @ $4.75 (spot: $5.40) |
| FW-WURTH-2026 | Wurth Elektronik | Framework | $120K/yr | 24 months | All electronics: tiered pricing by quarterly volume |
| SPT-APEX | Apex CNC Works | Spot Buy | Per PO | Ongoing | Machined parts: no volume commitment |
| CSG-MCMASTER | McMaster-Carr | Consignment | N/A | Rolling | Fasteners/springs: vendor-managed, pay on pull |
| BPA-ENG-2026 | Energizer Industrial | Blanket PO | $38K/yr | 12 months | BAT-217: 10K cells @ $3.60 (spot: $3.80) |

---

## 4. Inventory & Demand Model

### Monthly Production Plan

| Product | Monthly Volume | Daily Rate (~22 days) |
|---|---|---|
| FL-001-T | 200 | ~9/day |
| FL-001-S | 250 | ~11/day |
| HL-002-P | 120 | ~5/day |
| HL-002-B | 80 | ~4/day |
| WL-003-R | 60 | ~3/day |
| WL-003-C | 40 | ~2/day |
| **Total** | **750/month** | **~34/day** |

### Starting Inventory (Seeded with Tension)

| Part | On-Hand | Safety Stock | Daily Burn | Status | Story |
|---|---|---|---|---|---|
| LED-201 | 1,450 | 625 | 34 | Tight | 5.5 weeks stock, 6-week lead time |
| PCB-202 | 900 | 375 | 34 | OK | 3.5 weeks buffer |
| MCU-241 | 380 | 500 | 34 | **BELOW SAFETY** | Semiconductor allocation |
| BAT-211 | 1,100 | 540 | 29 | Healthy | Recent delivery |
| BAT-217 | 600 | 200 | 8 | Comfortable | Low volume |
| CH-231 | 280 | 225 | 20 | **Just above safety** | Apex behind schedule |
| CH-236 | 150 | 50 | 5 | OK | Low volume |
| GKT-223 | 2,800 | 750 | 34 | Comfortable | Bulk buy |
| LNS-221 | 420 | 500 | 34 | **BELOW SAFETY** | Optics quality issue |
| USB-214 | 180 | 150 | 29 | Tight | USB-C bottleneck |
| HSG-271 | 350 | 100 | 9 | OK | |
| RIL-281 | 85 | 50 | 5 | Adequate | Low volume |
| SW-232 | 500 | 200 | 20 | OK | |
| TSW-291 | 120 | 50 | 5 | OK | |
| HBD-261 | 350 | 100 | 9 | OK | Easy to source |
| REM-292 | 90 | 30 | 3 | OK | WL-003-R only |

### Pre-Seeded Sales Orders

| Order | Product | Qty | Priority | Delivery | Story |
|---|---|---|---|---|---|
| SO-MIL-001 | WL-003-R | 200 | VIP | 30 days | Military contract, non-negotiable |
| SO-AMZ-002 | FL-001-S | 500 | NORMAL | 45 days | Amazon FBA replenishment |
| SO-REI-003 | HL-002-P | 150 | NORMAL | 60 days | REI seasonal order |
| SO-LEO-004 | FL-001-T | 300 | EXPEDITED | 21 days | Law enforcement bulk buy |
| SO-DLR-005 | FL-001-T | 50 | NORMAL | 90 days | Dealer network |
| SO-OEM-006 | SA-LED-100 | 100 | NORMAL | 45 days | OEM customer buying sub-assembly |

### Demand Forecast (Enhanced)

```
DemandForecast (enhanced schema)
├── part_id (FK)
├── period ("2026-Q1", "2026-Q2", etc.)
├── forecast_qty
├── actual_qty (for historical periods)
├── forecast_accuracy_pct (computed)
├── source (HISTORICAL_AVG | SALES_PIPELINE | SEASONAL_ADJUSTMENT | MANUAL_OVERRIDE)
├── confidence_level (HIGH | MEDIUM | LOW)
├── notes
```

### Seasonal Demand Pattern (12 months history + 6 months forecast)

| Period | FL-001-T | FL-001-S | HL-002-P | WL-003-R | Driver |
|---|---|---|---|---|---|
| 2025-Q1 (actual) | 480 | 620 | 280 | 140 | Post-holiday slowdown |
| 2025-Q2 (actual) | 550 | 700 | 350 | 180 | Spring outdoor season |
| 2025-Q3 (actual) | 680 | 850 | 420 | 250 | Peak camping/outdoor |
| 2025-Q4 (actual) | 750 | 950 | 380 | 300 | Holiday + military Q4 spend |
| 2026-Q1 (actual, partial) | 520 | 680 | 300 | 160 | Post-holiday dip |
| 2026-Q2 (forecast) | 600 | 750 | 380 | 200 | Expected spring uptick |
| 2026-Q3 (forecast) | 720 | 900 | 450 | 260 | Peak season |

### Forecast Accuracy History

| Product | Q1 | Q2 | Q3 | Q4 | Average |
|---|---|---|---|---|---|
| FL-001-T | 92% | 87% | 78% | 85% | 86% |
| FL-001-S | 94% | 91% | 82% | 88% | 89% |
| HL-002-P | 88% | 83% | 72% | 80% | 81% |
| WL-003-R | 76% | 71% | 65% | 82% | 74% |

### Demand Variability

| Product | CV | Interpretation | Safety Stock Impact |
|---|---|---|---|
| FL-001-S | 0.15 | Low variability, steady consumer | Standard safety stock |
| FL-001-T | 0.22 | Moderate, some bulk spikes | Higher safety stock |
| HL-002-P | 0.28 | Seasonal swings | Seasonal adjustment |
| WL-003-R | 0.42 | High, lumpy military orders | Large buffer or MTO |

---

## 5. Enhanced Simulation Scenarios

### Existing Scenarios (Now Richer)

| # | Scenario | Enhancement |
|---|---|---|
| 1 | Demand Spike | Cascades across 3 product lines competing for LED-201 and MCU-241 |
| 2 | Supply Shock | CREE offline affects all 3 products; blanket PO vs. spot buy pricing |
| 3 | Quality Fail | LNS-221 batch reject affects all products using shared optics |
| 4 | Cascade Failure | Spike + CREE offline = cross-product prioritization by VIP vs NORMAL |
| 5 | Constitution Breach | Military order at spot prices triggers >$5K threshold |
| 6 | Full Blackout | 20+ suppliers — show which tiers recover first |
| 7 | Slow Bleed | MCU-241 already below safety stock, burn rate creeping |
| 8 | Inventory Decay | Ghost inventory in long-tail parts |
| 9 | Multi-SKU Contention | All 3 product lines fighting for LED-201 |

### New Scenarios

| # | Scenario | Description | Agent Story |
|---|---|---|---|
| 10 | Contract Exhaustion | BPA-CREE-2026 blanket 90% consumed, 4 months left | Ghost-Writer compares blanket remainder vs. forecast, recommends extension |
| 11 | Tariff Shock | China suppliers costs +25% overnight | Core-Guard recalculates; Ghost-Writer evaluates US alternates |
| 12 | MOQ Trap | Need 80 LED-201 but MOQ is 500 | Ghost-Writer shows cost-of-carry vs. premium for small lot |
| 13 | Military Surge | SO-MIL-001 doubles to 400 units, 21-day deadline | Dispatcher triages VIP; Core-Guard ring-fences across product lines |
| 14 | Semiconductor Allocation | MCU-241 on 26-week allocation, capacity -60% | Part Agent recalculates runway; system evaluates product mix |
| 15 | Seasonal Ramp | Q3 orders arrive 40% above forecast | AURA detects deviation; Core-Guard pre-positions using confidence levels |

---

## 6. Schema Changes Required

### New/Modified Models

1. **Supplier** — Add: `tier`, `region`, `expedite_lead_time_days`, `minimum_order_qty`, `capacity_per_month`, `payment_terms`, `certifications` (JSON), `risk_factors` (JSON)
2. **SupplierContract** — New table (contract_number, type, dates, committed value/qty, released/remaining, price schedule, status)
3. **ScheduledRelease** — New table (release against blanket, delivery tracking)
4. **AlternateSupplier** — New table (primary_supplier_id, alternate_supplier_id, part_id, cost_premium_pct, lead_time_delta_days)
5. **DemandForecast** — Add: `forecast_accuracy_pct`, `source`, `confidence_level`
6. **Part** — Add: `unit_cost` to components (currently only on some parts)
7. **BOMEntry** — Ensure all 3-level BOMs are represented (sub-assembly → component links)

### Data Volume

- Parts: 5 → ~55
- Suppliers: 22 → ~22 (but much richer data per supplier)
- BOM entries: 7 → ~120 (3 levels × 6 variants)
- Contracts: 0 → 6
- Sales orders: 3 → 6
- Demand forecasts: 2 → 35+ (7 periods × 5 products)
- Inventory records: 5 → ~55

---

## 7. Migration Strategy

1. Extend existing models (non-breaking additions)
2. Add new models (SupplierContract, ScheduledRelease, AlternateSupplier)
3. Rewrite `seed.py` with the full dataset
4. Update agent logic to work with deeper BOMs (recursive BOM explosion)
5. Update simulation endpoints for new scenarios
6. Update frontend to display new data (product family selector, supplier tier badges, contract status)
