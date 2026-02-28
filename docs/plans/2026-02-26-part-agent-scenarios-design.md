# Part Agent Scenarios Design

## Goal

Showcase the Part Agent's autonomous monitoring capabilities through 3 new standalone scenarios and integrate it into the 4 existing scenarios that currently skip it.

## New Standalone Scenarios

### Scenario G: Slow Bleed (Silent Stockout)

Part Agent detects a gradual, invisible crisis. No Aura spike, no supplier failure — just a creeping burn rate increase.

- **Mechanic:** Incrementally increase `daily_burn_rate` for CH-101 (40 -> 55 -> 70 -> 85) across 4 simulated "days"
- **Agent chain:** Part Agent (solo) -> Handshake -> Core-Guard -> Ghost-Writer
- **Key moment:** Part Agent is the ONLY agent that fires. Aura stays silent (no spike). Part Agent proves its independent value.
- **Glass Box logs:** Show runway shrinking each "day" (12.5d -> 9.1d -> 7.1d -> 5.9d), then handshake fires

### Scenario H: Inventory Decay (Ghost + Stale Detection)

Part Agent discovers inventory numbers are lying. On paper there's enough stock, but physical reality differs.

- **Mechanic:** Set `last_consumption_date` to 30 days ago while `daily_burn_rate > 0` (ghost). Set another part to 6+ months stale (suspect). Run Part Agent monitoring.
- **Agent chain:** Part Agent (baseline) -> Data Integrity Agent (ghost/suspect scan) -> Part Agent recalculates with corrected numbers -> Handshake -> Core-Guard -> Ghost-Writer
- **Key moment:** Part Agent initially reports "all clear" -> Data Integrity reveals ghost inventory -> Part Agent re-evaluates and triggers crisis. The "plot twist."

### Scenario I: Multi-SKU Contention

Both flashlight variants need the same chassis simultaneously. Part Agent detects shared component runway is halved.

- **Mechanic:** Inject demand for FL-001-T (200 units) AND FL-001-S (300 units) simultaneously. CH-101 is shared (2x per Tactical, 1x per Standard = 700 chassis needed).
- **Agent chain:** Part Agent monitors CH-101 for both SKUs -> detects combined burn rate exceeds supply -> Handshake with contention flag -> Core-Guard prioritizes by criticality (Tactical HIGH > Standard MEDIUM) -> Ghost-Writer
- **Key moment:** Part Agent surfaces the contention — not just "low stock" but "two products fighting over the same component."

## Integration Into Existing Scenarios

### Scenario B (Supply Shock)

After supplier goes offline, run Part Agent on affected parts. It recalculates runway with the alternate supplier's longer lead time, shifting the handshake threshold.

### Scenario C (Quality Fail)

After Eagle-Eye quarantines a batch, Part Agent recalculates runway with reduced `on_hand` (minus quarantined units). Shows how a quality event impacts days-to-stockout.

### Scenario D (Cascade Failure)

Add Part Agent between Aura and Dispatcher (same position as Scenario A). Monitors components under both crises simultaneously.

### Scenario F (Full Blackout)

Run Part Agent after all suppliers go offline. With no active supplier, the handshake threshold becomes unreachable. Part Agent logs "CRITICAL: No supplier path exists, runway is finite but unrecoverable."

## UI Layout

### God Mode Panel Changes

Below the existing 6 scenario buttons, add a new section:

- **Section divider** labeled "Part Agent Spotlight" with subtitle: "Scenarios where the Part Agent's autonomous monitoring drives the response"
- **3 buttons** in a row, styled consistently with existing God Mode buttons using the Part Agent's color theme
- Each button: icon + scenario name + one-line description
  - "Slow Bleed" — Gradual burn rate increase, no external trigger
  - "Inventory Decay" — Ghost and stale stock hiding behind good numbers
  - "Multi-SKU Contention" — Two products compete for the same component

### No Breaking Changes

- Existing 6 buttons unchanged in appearance and behavior
- Part Agent integration into B/C/D/F is backend-only — existing buttons just produce richer logs

## Backend Endpoints

- `POST /api/simulate/slow-bleed`
- `POST /api/simulate/inventory-decay`
- `POST /api/simulate/multi-sku-contention`

## Frontend API Additions

Add 3 new methods to `api.ts`:
- `simulateSlowBleed()`
- `simulateInventoryDecay()`
- `simulateMultiSkuContention()`

## Response Schemas

Add 3 new Pydantic response models to `schemas.py`:
- `SlowBleedResponse`
- `InventoryDecayResponse`
- `MultiSkuContentionResponse`
