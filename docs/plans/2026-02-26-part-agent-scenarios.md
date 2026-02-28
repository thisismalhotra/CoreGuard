# Part Agent Scenarios Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 3 new Part Agent-centric God Mode scenarios and integrate Part Agent into the 4 existing scenarios that currently skip it.

**Architecture:** New backend simulation endpoints + Pydantic schemas + frontend API methods + GodMode UI section. Each new scenario follows the existing pattern: endpoint in `simulations.py`, response schema in `schemas.py`, API method in `api.ts`, button in `GodMode.tsx`.

**Tech Stack:** Python/FastAPI (backend), Pydantic (schemas), React/Next.js/Tailwind/Shadcn (frontend), pytest (tests)

---

### Task 1: Add Pydantic Response Schemas for 3 New Scenarios

**Files:**
- Modify: `backend/schemas.py:218` (after `FullBlackoutResponse`)

**Step 1: Add the 3 response schemas**

Add after the `FullBlackoutResponse` class (line ~218):

```python
class SlowBleedResponse(BaseModel):
    status: str
    scenario: str = "SLOW_BLEED"
    part_id: str
    days_simulated: int
    runway_progression: list[dict[str, Any]]
    handshake_triggered: bool
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class InventoryDecayResponse(BaseModel):
    status: str
    scenario: str = "INVENTORY_DECAY"
    ghost_parts: list[dict[str, Any]]
    suspect_parts: list[dict[str, Any]]
    corrected_runway: dict[str, Any]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]


class MultiSkuContentionResponse(BaseModel):
    status: str
    scenario: str = "MULTI_SKU_CONTENTION"
    contending_skus: list[str]
    shared_component: str
    combined_demand: int
    prioritization: list[dict[str, Any]]
    procurement: list[PurchaseOrderSummary]
    logs: list[GlassBoxLog]
```

**Step 2: Run lint to verify**

Run: `cd backend && python3 -c "from schemas import SlowBleedResponse, InventoryDecayResponse, MultiSkuContentionResponse; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/schemas.py
git commit -m "feat: add Pydantic response schemas for Part Agent scenarios"
```

---

### Task 2: Implement Scenario G — Slow Bleed Endpoint

**Files:**
- Modify: `backend/routers/simulations.py` (add new endpoint after full-blackout, before reset)

**Step 1: Write the failing test**

Add to `backend/tests/test_agents.py` at the end of the file:

```python
class TestSlowBleedScenario:
    """Test Scenario G: Slow Bleed — gradual burn rate increase detected by Part Agent."""

    def test_slow_bleed_detects_runway_decline(self, db):
        """Part Agent should detect runway declining across simulated days."""
        from agents.part_agent import monitor_part, calculate_runway

        # Simulate increasing burn rate over 4 "days"
        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        burn_rates = [40.0, 55.0, 70.0, 85.0]
        runways = []

        for rate in burn_rates:
            inv.daily_burn_rate = rate
            db.flush()
            result = monitor_part(db, "CH-101")
            runways.append(result["runway_days"])

        # Runway should decline monotonically
        for i in range(1, len(runways)):
            assert runways[i] < runways[i - 1], f"Runway should decline: {runways}"

    def test_slow_bleed_triggers_handshake(self, db):
        """At high enough burn rate, Part Agent handshake should fire."""
        from agents.part_agent import monitor_part

        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        inv.daily_burn_rate = 85.0  # High burn rate
        db.flush()

        result = monitor_part(db, "CH-101")
        # With on_hand=500 and burn=85/day, runway=5.9d
        # Threshold = lead_time(5) + safety_stock_days(200/85=2.35) = 7.35d
        # 5.9 < 7.35 → handshake should fire
        assert result["handshake_triggered"] is True
        assert result["crisis_signal"] is not None
```

**Step 2: Run test to verify it passes** (these test agent logic, not the endpoint)

Run: `cd backend && python3 -m pytest tests/test_agents.py::TestSlowBleedScenario -v`
Expected: PASS (tests use existing Part Agent functions)

**Step 3: Add the Slow Bleed endpoint**

Add to `backend/routers/simulations.py` after the `full-blackout` endpoint (before `reset`):

```python
# ---------------------------------------------------------------------------
# Scenario G: Slow Bleed (Silent Stockout)
# ---------------------------------------------------------------------------

@router.post("/slow-bleed", response_model=SlowBleedResponse)
async def simulate_slow_bleed(
    part_id: str = "CH-101",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario G: Simulate a gradual burn rate increase over 4 "days".
    Part Agent is the ONLY agent that detects this — Aura stays silent.
    """
    all_logs: list[dict[str, str]] = []

    part = db.query(Part).filter(Part.part_id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail=f"Part '{part_id}' not found")

    inv = part.inventory
    if not inv:
        raise HTTPException(status_code=404, detail=f"No inventory for '{part_id}'")

    log = _sys_log(db, f"SLOW BLEED INITIATED: Simulating gradual burn rate increase on {part_id}. No external trigger — Part Agent must detect the drift.", "warning")
    all_logs.append(log)
    await emit_logs([log])

    original_burn_rate = inv.daily_burn_rate
    burn_rates = [
        original_burn_rate,
        original_burn_rate * 1.375,
        original_burn_rate * 1.75,
        original_burn_rate * 2.125,
    ]
    runway_progression = []
    handshake_triggered = False

    for day, rate in enumerate(burn_rates, 1):
        inv.daily_burn_rate = round(rate, 1)
        db.flush()

        log = _sys_log(db, f"--- Day {day}: Burn rate drifts to {inv.daily_burn_rate}/day (was {original_burn_rate}/day) ---", "info")
        all_logs.append(log)
        await emit_logs([log])

        result = monitor_part(db, part_id)
        all_logs.extend(result["logs"])
        await emit_logs(result["logs"])

        runway_progression.append({
            "day": day,
            "burn_rate": inv.daily_burn_rate,
            "runway_days": result["runway_days"],
            "handshake_triggered": result["handshake_triggered"],
        })

        if result["handshake_triggered"]:
            handshake_triggered = True

    # If handshake fired, run Core-Guard + Ghost-Writer
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if handshake_triggered:
        log = _sys_log(db, "Part Agent handshake triggered. Escalating to Core-Guard...", "warning")
        all_logs.append(log)
        await emit_logs([log])

        # Estimate demand from elevated burn rate (30-day projection)
        projected_demand = int(inv.daily_burn_rate * 30)
        # Find which finished good uses this part
        bom_entry = db.query(BOMEntry).filter(BOMEntry.component_id == part.id).first()
        if bom_entry:
            parent = db.query(Part).filter(Part.id == bom_entry.parent_id).first()
            if parent:
                mrp_result = calculate_net_requirements(db, parent.part_id, projected_demand)
                all_logs.extend(mrp_result["logs"])
                await emit_logs(mrp_result["logs"])

                buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
                if buy_orders:
                    ghost_result = process_buy_orders(db, buy_orders)
                    all_logs.extend(ghost_result["logs"])
                    await emit_logs(ghost_result["logs"])

    # Restore original burn rate
    inv.daily_burn_rate = original_burn_rate

    summary_type = "warning" if handshake_triggered else "success"
    summary_msg = (
        f"Slow bleed simulation complete: burn rate drifted {original_burn_rate} → {burn_rates[-1]:.1f}/day over 4 days. "
        f"{'Part Agent detected the crisis and triggered procurement.' if handshake_triggered else 'Part Agent monitored but runway remained safe.'}"
    )
    log = _sys_log(db, summary_msg, summary_type)
    all_logs.append(log)
    await emit_logs([log])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "SLOW_BLEED",
        "part_id": part_id,
        "days_simulated": len(burn_rates),
        "runway_progression": runway_progression,
        "handshake_triggered": handshake_triggered,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }
```

Also add the import for `SlowBleedResponse` at the top of the file with the other schema imports, and add `BOMEntry` to the models import and `monitor_part` to the part_agent import:

```python
from agents.part_agent import monitor_all_components, monitor_part
from database.models import (
    Part, Supplier, DemandForecast, AgentLog, Base, BOMEntry,
)
from schemas import (
    SpikeResponse, SupplyShockResponse, QualityFailResponse,
    CascadeFailureResponse, ConstitutionBreachResponse,
    FullBlackoutResponse, ResetResponse,
    SlowBleedResponse,
)
```

**Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_agents.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/routers/simulations.py backend/tests/test_agents.py
git commit -m "feat: add Slow Bleed scenario (G) — Part Agent detects gradual burn rate drift"
```

---

### Task 3: Implement Scenario H — Inventory Decay Endpoint

**Files:**
- Modify: `backend/routers/simulations.py` (add endpoint after slow-bleed)

**Step 1: Write the failing test**

Add to `backend/tests/test_agents.py`:

```python
class TestInventoryDecayScenario:
    """Test Scenario H: Inventory Decay — Part Agent + Data Integrity find ghost/stale stock."""

    def test_ghost_inventory_changes_runway(self, db):
        """After ghost detection, recalculated runway should reflect corrected inventory."""
        from datetime import datetime, timezone, timedelta
        from agents.part_agent import monitor_part

        # Set CH-101 as ghost: has burn rate but no consumption for 30 days
        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
        inv.last_consumption_date = datetime.now(timezone.utc) - timedelta(days=30)
        db.flush()

        # Initial monitoring should show healthy runway (on_hand=500, burn=40)
        result_before = monitor_part(db, "CH-101")
        assert result_before["runway_days"] is not None
        assert result_before["runway_days"] > 0

        # After zeroing ghost inventory, runway collapses
        inv.on_hand = 0
        db.flush()
        result_after = monitor_part(db, "CH-101")
        # With on_hand=0, runway should be 0
        assert result_after["runway_days"] == 0.0
        assert result_after["handshake_triggered"] is True
```

**Step 2: Run test**

Run: `cd backend && python3 -m pytest tests/test_agents.py::TestInventoryDecayScenario -v`
Expected: PASS

**Step 3: Add the Inventory Decay endpoint**

Add to `backend/routers/simulations.py` after the slow-bleed endpoint:

```python
# ---------------------------------------------------------------------------
# Scenario H: Inventory Decay (Ghost + Stale Detection)
# ---------------------------------------------------------------------------

@router.post("/inventory-decay", response_model=InventoryDecayResponse)
async def simulate_inventory_decay(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario H: Part Agent discovers inventory numbers are lying.
    Data Integrity Agent reveals ghost/suspect stock, then Part Agent re-evaluates.
    """
    all_logs: list[dict[str, str]] = []

    log = _sys_log(db, "INVENTORY DECAY INITIATED: Simulating ghost and suspect inventory conditions. Part Agent will monitor, then Data Integrity will reveal the truth.", "warning")
    all_logs.append(log)
    await emit_logs([log])

    # Act 1: Part Agent runs baseline check — everything looks fine
    log = _sys_log(db, "Act 1: Part Agent baseline monitoring — checking runway on all components...", "info")
    all_logs.append(log)
    await emit_logs([log])

    baseline_result = monitor_all_components(db, "FL-001-T", 100)
    all_logs.extend(baseline_result["logs"])
    await emit_logs(baseline_result["logs"])

    log = _sys_log(db, "Part Agent reports: All runways appear healthy. But are the numbers real?", "info")
    all_logs.append(log)
    await emit_logs([log])

    # Act 2: Inject decay conditions
    now = datetime.now(timezone.utc)

    # CH-101: Ghost — burn rate says 40/day but no consumption recorded for 30 days
    ch101_inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
    original_ch101_consumption = ch101_inv.last_consumption_date
    ch101_inv.last_consumption_date = now - timedelta(days=30)

    # LNS-505: Suspect — no movement for 200 days
    lns505_inv = db.query(Inventory).join(Part).filter(Part.part_id == "LNS-505").first()
    original_lns505_updated = lns505_inv.last_updated
    lns505_inv.last_updated = now - timedelta(days=200)

    db.flush()

    log = _sys_log(db, "Act 2: Data Integrity Agent scanning for anomalies...", "warning")
    all_logs.append(log)
    await emit_logs([log])

    # Run Data Integrity scan
    integrity_result = run_full_integrity_check(db, reference_date=now)
    all_logs.extend(integrity_result["logs"])
    await emit_logs(integrity_result["logs"])

    # Act 3: Part Agent re-evaluates with corrected inventory
    # Ghost inventory means on-hand is unreliable — simulate zeroing ghost parts
    ghost_part_ids = [g["part_id"] for g in integrity_result["ghost"]["ghost_parts"]]
    original_on_hands = {}

    if ghost_part_ids:
        log = _sys_log(db, f"Act 3: {len(ghost_part_ids)} ghost part(s) detected! Part Agent re-evaluating with corrected inventory...", "error")
        all_logs.append(log)
        await emit_logs([log])

        for gp_id in ghost_part_ids:
            inv = db.query(Inventory).join(Part).filter(Part.part_id == gp_id).first()
            if inv:
                original_on_hands[gp_id] = inv.on_hand
                # Reduce on-hand by 50% (ghost means we can't trust the count)
                inv.on_hand = inv.on_hand // 2
                log = _sys_log(db, f"Correcting {gp_id}: on_hand {original_on_hands[gp_id]} → {inv.on_hand} (50% ghost discount applied pending physical count).", "warning", agent="Part-Agent")
                all_logs.append(log)
                await emit_logs([log])
        db.flush()

    # Re-run Part Agent monitoring with corrected numbers
    corrected_result = monitor_all_components(db, "FL-001-T", 100)
    all_logs.extend(corrected_result["logs"])
    await emit_logs(corrected_result["logs"])

    # Process any crisis signals through Core-Guard + Ghost-Writer
    ghost_writer_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    if corrected_result["crisis_signals"]:
        mrp_result = calculate_net_requirements(db, "FL-001-T", 100)
        all_logs.extend(mrp_result["logs"])
        await emit_logs(mrp_result["logs"])

        buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
        if buy_orders:
            ghost_writer_result = process_buy_orders(db, buy_orders)
            all_logs.extend(ghost_writer_result["logs"])
            await emit_logs(ghost_writer_result["logs"])

    # Restore original values
    ch101_inv.last_consumption_date = original_ch101_consumption
    lns505_inv.last_updated = original_lns505_updated
    for gp_id, orig_oh in original_on_hands.items():
        inv = db.query(Inventory).join(Part).filter(Part.part_id == gp_id).first()
        if inv:
            inv.on_hand = orig_oh

    summary = _sys_log(
        db,
        f"Inventory decay simulation complete: {integrity_result['total_issues']} integrity issue(s) found. "
        f"Part Agent re-evaluated and {'triggered crisis response' if corrected_result['crisis_signals'] else 'confirmed safe runway with corrected data'}.",
        "warning" if integrity_result["total_issues"] > 0 else "success",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "INVENTORY_DECAY",
        "ghost_parts": integrity_result["ghost"]["ghost_parts"],
        "suspect_parts": integrity_result["suspect"]["suspect_parts"],
        "corrected_runway": {
            "crisis_signals": corrected_result["crisis_signals"],
            "component_count": len(corrected_result["component_reports"]),
        },
        "procurement": ghost_writer_result["purchase_orders"],
        "logs": all_logs,
    }
```

Also add the import for `InventoryDecayResponse` to the schemas import, `run_full_integrity_check` is already imported, and add `datetime`, `timezone`, `timedelta` imports:

```python
from datetime import datetime, timezone, timedelta
from schemas import (
    ...,
    InventoryDecayResponse,
)
```

**Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_agents.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/routers/simulations.py backend/tests/test_agents.py
git commit -m "feat: add Inventory Decay scenario (H) — ghost/stale detection with Part Agent re-evaluation"
```

---

### Task 4: Implement Scenario I — Multi-SKU Contention Endpoint

**Files:**
- Modify: `backend/routers/simulations.py` (add endpoint after inventory-decay)

**Step 1: Write the failing test**

Add to `backend/tests/test_agents.py`:

```python
class TestMultiSkuContentionScenario:
    """Test Scenario I: Multi-SKU Contention — two products compete for shared components."""

    def test_combined_burn_rate_exceeds_individual(self, db):
        """When two SKUs share a component, combined burn rate should exceed either individual."""
        from agents.part_agent import monitor_part

        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()

        # Monitor with normal burn rate
        result_solo = monitor_part(db, "CH-101")
        solo_runway = result_solo["runway_days"]

        # Simulate combined demand (double the burn rate)
        inv.daily_burn_rate = inv.daily_burn_rate * 2
        db.flush()
        result_combined = monitor_part(db, "CH-101")
        combined_runway = result_combined["runway_days"]

        # Combined runway should be roughly half of solo
        assert combined_runway < solo_runway

    def test_contention_triggers_handshake_when_solo_is_safe(self, db):
        """A component safe for one SKU may trigger handshake under multi-SKU contention."""
        from agents.part_agent import monitor_part

        inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()

        # Solo: safe
        result_solo = monitor_part(db, "CH-101")

        # Under contention: triple the burn rate
        inv.daily_burn_rate = inv.daily_burn_rate * 3
        db.flush()
        result_contention = monitor_part(db, "CH-101")
        assert result_contention["handshake_triggered"] is True
```

**Step 2: Run test**

Run: `cd backend && python3 -m pytest tests/test_agents.py::TestMultiSkuContentionScenario -v`
Expected: PASS

**Step 3: Add the Multi-SKU Contention endpoint**

Add to `backend/routers/simulations.py` after the inventory-decay endpoint:

```python
# ---------------------------------------------------------------------------
# Scenario I: Multi-SKU Contention
# ---------------------------------------------------------------------------

@router.post("/multi-sku-contention", response_model=MultiSkuContentionResponse)
async def simulate_multi_sku_contention(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Scenario I: FL-001-T and FL-001-S compete for shared CH-101 chassis.
    Part Agent detects combined demand halves the runway.
    """
    all_logs: list[dict[str, str]] = []

    sku_a = "FL-001-T"
    sku_b = "FL-001-S"
    demand_a = 200
    demand_b = 300

    log = _sys_log(db, f"MULTI-SKU CONTENTION INITIATED: {sku_a} ({demand_a} units) and {sku_b} ({demand_b} units) both need CH-101 chassis simultaneously.", "warning")
    all_logs.append(log)
    await emit_logs([log])

    # Act 1: Part Agent monitors CH-101 for SKU A
    log = _sys_log(db, f"Act 1: Part Agent monitoring CH-101 demand from {sku_a} ({demand_a} units, 2x chassis each = {demand_a * 2} chassis)...", "info")
    all_logs.append(log)
    await emit_logs([log])

    result_a = monitor_all_components(db, sku_a, demand_a)
    all_logs.extend(result_a["logs"])
    await emit_logs(result_a["logs"])

    # Act 2: Part Agent monitors CH-101 for SKU B
    log = _sys_log(db, f"Act 2: Part Agent monitoring CH-101 demand from {sku_b} ({demand_b} units, 1x chassis each = {demand_b} chassis)...", "info")
    all_logs.append(log)
    await emit_logs([log])

    result_b = monitor_all_components(db, sku_b, demand_b)
    all_logs.extend(result_b["logs"])
    await emit_logs(result_b["logs"])

    # Act 3: Part Agent detects contention — combined burn rate
    ch101_inv = db.query(Inventory).join(Part).filter(Part.part_id == "CH-101").first()
    original_burn_rate = ch101_inv.daily_burn_rate

    # BOM: FL-001-T needs 2x CH-101, FL-001-S needs 1x CH-101
    # Total chassis demand = (200 × 2) + (300 × 1) = 700
    combined_daily = (demand_a * 2 + demand_b * 1) / 30.0  # Spread over 30 days
    ch101_inv.daily_burn_rate = original_burn_rate + combined_daily
    db.flush()

    log = _sys_log(
        db,
        f"Act 3: CONTENTION DETECTED on CH-101! Combined demand: {demand_a * 2 + demand_b} chassis. "
        f"Burn rate surges {original_burn_rate:.1f} → {ch101_inv.daily_burn_rate:.1f}/day.",
        "error",
        agent="Part-Agent",
    )
    all_logs.append(log)
    await emit_logs([log])

    contention_result = monitor_part(db, "CH-101")
    all_logs.extend(contention_result["logs"])
    await emit_logs(contention_result["logs"])

    # Restore burn rate before MRP
    ch101_inv.daily_burn_rate = original_burn_rate
    db.flush()

    # Act 4: Core-Guard prioritizes by criticality
    log = _sys_log(db, "Act 4: Core-Guard applying criticality-based prioritization...", "info")
    all_logs.append(log)
    await emit_logs([log])

    # FL-001-T is HIGH criticality, FL-001-S is MEDIUM → Tactical gets priority
    prioritization = []

    part_a = db.query(Part).filter(Part.part_id == sku_a).first()
    part_b = db.query(Part).filter(Part.part_id == sku_b).first()

    prioritization.append({
        "sku": sku_a,
        "criticality": part_a.criticality.value if part_a else "UNKNOWN",
        "demand": demand_a,
        "chassis_needed": demand_a * 2,
        "priority": 1,
    })
    prioritization.append({
        "sku": sku_b,
        "criticality": part_b.criticality.value if part_b else "UNKNOWN",
        "demand": demand_b,
        "chassis_needed": demand_b * 1,
        "priority": 2,
    })

    log = _sys_log(
        db,
        f"Prioritization: {sku_a} ({part_a.criticality.value if part_a else 'N/A'}) gets priority over {sku_b} ({part_b.criticality.value if part_b else 'N/A'}). "
        f"Allocating CH-101 to {sku_a} first.",
        "info",
        agent="Core-Guard",
    )
    all_logs.append(log)
    await emit_logs([log])

    # Run MRP for the combined demand
    total_demand = demand_a + demand_b
    mrp_result = calculate_net_requirements(db, sku_a, total_demand)
    all_logs.extend(mrp_result["logs"])
    await emit_logs(mrp_result["logs"])

    # Ghost-Writer processes any buy orders
    ghost_result: dict[str, Any] = {"purchase_orders": [], "logs": []}
    buy_orders = [a for a in mrp_result["actions"] if a["type"] == "BUY_ORDER"]
    if buy_orders:
        ghost_result = process_buy_orders(db, buy_orders)
        all_logs.extend(ghost_result["logs"])
        await emit_logs(ghost_result["logs"])

    summary = _sys_log(
        db,
        f"Multi-SKU contention resolved: {demand_a * 2 + demand_b} chassis needed across 2 SKUs. "
        f"Core-Guard prioritized {sku_a} (criticality: {part_a.criticality.value if part_a else 'N/A'}). "
        f"{len(ghost_result['purchase_orders'])} PO(s) issued.",
        "success",
    )
    all_logs.append(summary)
    await emit_logs([summary])

    db.commit()

    return {
        "status": "simulation_complete",
        "scenario": "MULTI_SKU_CONTENTION",
        "contending_skus": [sku_a, sku_b],
        "shared_component": "CH-101",
        "combined_demand": demand_a * 2 + demand_b,
        "prioritization": prioritization,
        "procurement": ghost_result["purchase_orders"],
        "logs": all_logs,
    }
```

Add `MultiSkuContentionResponse` to the schemas import.

**Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/test_agents.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/routers/simulations.py backend/tests/test_agents.py
git commit -m "feat: add Multi-SKU Contention scenario (I) — shared component prioritization"
```

---

### Task 5: Integrate Part Agent into Existing Scenarios B, C, D, F

**Files:**
- Modify: `backend/routers/simulations.py`

**Step 1: Integrate into Scenario B (Supply Shock)**

After the supplier is disabled and affected parts are identified (around line 208), add Part Agent monitoring before the emergency orders loop:

```python
    # Part Agent: Recalculate runway with alternate supplier's lead time
    for part in affected_parts:
        pa_result = monitor_part(db, part.part_id)
        all_logs.extend(pa_result["logs"])
        await emit_logs(pa_result["logs"])
```

**Step 2: Integrate into Scenario C (Quality Fail)**

After Eagle-Eye inspection (around line 315), add Part Agent check:

```python
    # Part Agent: Recalculate runway after quarantine reduces effective on-hand
    pa_result = monitor_part(db, part_id)
    all_logs.extend(pa_result["logs"])
    await emit_logs(pa_result["logs"])
```

**Step 3: Integrate into Scenario D (Cascade Failure)**

After Aura detection (around line 374), add Part Agent monitoring before Dispatcher:

```python
    # Part Agent: Baseline monitoring under dual crisis
    part_agent_result = monitor_all_components(db, "FL-001-T", spiked_qty)
    all_logs.extend(part_agent_result["logs"])
    await emit_logs(part_agent_result["logs"])
```

**Step 4: Integrate into Scenario F (Full Blackout)**

After all suppliers disabled (around line 548), add Part Agent assessment:

```python
    # Part Agent: Assess runway with no supplier path
    part_agent_result = monitor_all_components(db, "FL-001-T", spiked_qty)
    all_logs.extend(part_agent_result["logs"])
    await emit_logs(part_agent_result["logs"])
```

**Step 5: Run tests**

Run: `cd backend && python3 -m pytest tests/test_agents.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/routers/simulations.py
git commit -m "feat: integrate Part Agent monitoring into Supply Shock, Quality Fail, Cascade, and Blackout scenarios"
```

---

### Task 6: Add Frontend API Methods

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add the 3 new API methods**

Add after `simulateFullBlackout` (around line 96):

```typescript
  simulateSlowBleed: (partId = "CH-101") =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/slow-bleed?part_id=${partId}`,
      { method: "POST" }
    ),
  simulateInventoryDecay: () =>
    fetchJSON<Record<string, unknown>>("/api/simulate/inventory-decay", { method: "POST" }),
  simulateMultiSkuContention: () =>
    fetchJSON<Record<string, unknown>>("/api/simulate/multi-sku-contention", { method: "POST" }),
```

**Step 2: Run lint**

Run: `cd frontend && npm run lint`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add frontend API methods for Part Agent scenarios"
```

---

### Task 7: Add Part Agent Spotlight Section to GodMode UI

**Files:**
- Modify: `frontend/src/components/GodMode.tsx`

**Step 1: Add the Lucide icon import**

Add `Activity`, `Ghost`, `GitMerge` to the existing Lucide imports:

```typescript
import {
  Flame, TrendingUp, XCircle, CheckCircle, AlertCircle,
  Layers, DollarSign, WifiOff, RefreshCw, Zap,
  Activity, Ghost, GitMerge,
} from "lucide-react";
```

**Step 2: Add the Part Agent scenarios array**

After the existing `scenarios` array (around line 85), add:

```typescript
  const partAgentScenarios: Scenario[] = [
    {
      id: "slow-bleed",
      label: "Slow Bleed",
      description: "Gradual burn rate increase with no external trigger. Part Agent is the ONLY agent that detects the silent drift toward stockout.",
      icon: Activity,
      color: "bg-teal-600 hover:bg-teal-500",
      action: () => api.simulateSlowBleed(),
    },
    {
      id: "inventory-decay",
      label: "Inventory Decay",
      description: "Part Agent initially reports all-clear, then Data Integrity reveals ghost and suspect stock hiding behind healthy numbers.",
      icon: Ghost,
      color: "bg-amber-600 hover:bg-amber-500",
      action: () => api.simulateInventoryDecay(),
    },
    {
      id: "multi-sku-contention",
      label: "Multi-SKU Contention",
      description: "FL-001-T and FL-001-S compete for shared CH-101 chassis. Part Agent detects contention, Core-Guard applies criticality-based prioritization.",
      icon: GitMerge,
      color: "bg-indigo-600 hover:bg-indigo-500",
      action: () => api.simulateMultiSkuContention(),
    },
  ];
```

**Step 3: Add the Part Agent Spotlight section to the JSX**

After the existing scenario grid's closing `</div>` (around line 178) and before the Reset Button section, add:

```tsx
      {/* Part Agent Spotlight Section */}
      <div className="pt-4 border-t border-border">
        <div className="flex items-center gap-2 mb-1">
          <Activity className="h-4 w-4 text-teal-400" />
          <h3 className="text-sm font-semibold text-foreground">Part Agent Spotlight</h3>
        </div>
        <p className="text-xs text-muted-foreground mb-4">
          Scenarios where the Part Agent&apos;s autonomous monitoring drives the response
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {partAgentScenarios.map((scenario) => {
            const Icon = scenario.icon;
            const result = results[scenario.id];
            const isRunning = result?.status === "running";

            return (
              <Card key={scenario.id} className="bg-card border-border flex flex-col">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Icon className="h-4 w-4 shrink-0" />
                    {scenario.label}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col flex-1 justify-between">
                  <p className="text-xs text-muted-foreground mb-4 leading-relaxed">{scenario.description}</p>

                  {result?.status === "success" && (
                    <div className="flex items-center gap-1.5 mb-2">
                      <CheckCircle className="h-3.5 w-3.5 text-green-400 shrink-0" />
                      <span className="text-xs text-green-400">{result.message}</span>
                    </div>
                  )}
                  {result?.status === "error" && (
                    <div className="flex items-center gap-1.5 mb-2">
                      <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                      <span className="text-xs text-red-400">{result.message}</span>
                    </div>
                  )}

                  <Button
                    className={`w-full ${scenario.color} text-white text-xs`}
                    onClick={() => handleRun(scenario)}
                    disabled={isAnyRunning || resetting}
                  >
                    {isRunning ? "Running..." : "Inject Chaos"}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
```

**Step 4: Run lint and build**

Run: `cd frontend && npm run lint && npm run build`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/src/components/GodMode.tsx
git commit -m "feat: add Part Agent Spotlight section to God Mode UI with 3 scenario buttons"
```

---

### Task 8: Verify End-to-End

**Step 1: Reset the simulation**

Run: `curl -X POST http://localhost:8000/api/simulate/reset`
Expected: `{"status":"reset_complete",...}`

**Step 2: Test each new endpoint**

Run each:
```bash
curl -X POST http://localhost:8000/api/simulate/slow-bleed
curl -X POST http://localhost:8000/api/simulate/inventory-decay
curl -X POST http://localhost:8000/api/simulate/multi-sku-contention
```
Expected: Each returns `{"status":"simulation_complete","scenario":"..."}` with logs

**Step 3: Run all backend tests**

Run: `cd backend && python3 -m pytest tests/test_agents.py -v`
Expected: All tests PASS (including 6 new tests)

**Step 4: Verify frontend renders**

Open `http://localhost:3000`, go to God Mode tab. Verify:
- Existing 6 scenario buttons are unchanged
- "Part Agent Spotlight" section appears below with 3 buttons
- Each button triggers correctly and logs stream in Live Logs

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete Part Agent scenarios — 3 new God Mode scenarios + integration into existing 4"
```
