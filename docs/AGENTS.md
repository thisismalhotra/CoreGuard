# Agent Documentation

Core-Guard uses 5 autonomous agents arranged in an event-driven chain. Each agent is stateless, operates on database state, and emits structured Glass Box logs for full transparency.

## Agent Chain

```
                          ┌─────────────────────────────────────────────┐
                          │                                             │
  Demand Data ──► Aura ──► Dispatcher ──► Core-Guard ──► Ghost-Writer  │
                                                                       │
  Shipment ──► Eagle-Eye ──────────────────────────────────────────────┘
                                (on failure, triggers Ghost-Writer)
```

All agents share this common pattern:

```python
def _log(db, message, log_type="info") -> dict:
    """Persist log to agent_logs table and return dict for Socket.io emission."""

def agent_function(db, ...) -> dict:
    logs = []
    # ... deterministic logic ...
    db.commit()
    return {"result": ..., "logs": logs}
```

---

## 1. Aura — Demand Sensing Agent

**Source:** `backend/agents/aura.py`
**Role:** First responder. Monitors demand signals and detects anomalies.

### Trigger
Incoming demand data (injected by simulation endpoints).

### Logic
```
multiplier = actual_qty / forecast_qty
spike_detected = actual_qty > forecast_qty * 1.2
```

All math is pure Python (Rule B). The threshold is `SPIKE_THRESHOLD = 1.2` (20% above forecast).

### Function

```python
detect_demand_spike(db: Session, sku: str, new_actual_qty: int) -> dict
```

**Steps:**
1. Look up the part by SKU
2. Query its `DemandForecast` record
3. Update `actual_qty` with the new demand reading
4. Calculate the spike multiplier
5. If `actual > forecast * 1.2`: fire DEMAND_SPIKE

**Returns:**
| Field          | Type  | Description                              |
|----------------|-------|------------------------------------------|
| spike_detected | bool  | Whether the threshold was breached        |
| sku            | str   | The SKU that was checked                  |
| forecast_qty   | int   | Baseline forecast quantity                |
| actual_qty     | int   | Injected actual demand                    |
| multiplier     | float | Ratio of actual to forecast               |
| logs           | list  | Glass Box log entries                     |

### Downstream
Hands off to **Dispatcher** when a spike is detected.

---

## 2. Dispatcher — Triage & Prioritisation Agent

**Source:** `backend/agents/dispatcher.py`
**Role:** Analyzes all BOM components for a spiked SKU and ranks them by urgency so Core-Guard processes the most critical shortages first.

### Trigger
DEMAND_SPIKE event from Aura.

### Logic

For each BOM component, the Dispatcher calculates a priority score:

```
priority_score = criticality_weight + (lead_time_sensitivity * 30) + (gap_severity * 20)
```

Where:
- `criticality_weight`: CRITICAL=100, HIGH=75, MEDIUM=50, LOW=25
- `lead_time_sensitivity`: 0.0 (tolerant) to 1.0 (urgent), multiplied by 30
- `gap_severity`: `max(0, gap) / max(required, 1)`, multiplied by 20 (0.0 = no gap, 1.0 = total shortfall)

Components are sorted by priority score **descending** (highest first).

### Function

```python
triage_demand_spike(db: Session, sku: str, demand_qty: int) -> dict
```

**Steps:**
1. Locate the finished good by SKU
2. Explode its BOM to get all components
3. For each component: calculate required qty, check inventory, compute gap severity
4. Score and rank all components
5. Flag CRITICAL components and at-risk items

**Returns:**
| Field          | Type  | Description                              |
|----------------|-------|------------------------------------------|
| sku            | str   | The finished good SKU                     |
| demand_qty     | int   | Demand quantity being triaged             |
| priority_queue | list  | Components sorted by priority score       |
| assessment     | dict  | `{total_components, at_risk, critical_count}` |
| logs           | list  | Glass Box log entries                     |

Each item in `priority_queue`:
```json
{
  "part_id": "CH-101",
  "criticality": "CRITICAL",
  "lead_time_sensitivity": 0.95,
  "required": 600,
  "available": 400,
  "gap": 200,
  "gap_severity": 0.33,
  "priority_score": 135.1,
  "at_risk": true,
  "substitute_pool_size": 4
}
```

### Downstream
Hands the prioritised queue to **Core-Guard**.

---

## 3. Core-Guard — MRP Logic Agent

**Source:** `backend/agents/core_guard.py`
**Role:** The brain of the supply chain. Performs BOM explosion, calculates net material requirements, and decides procurement strategy based on part criticality.

### Trigger
Prioritised queue from Dispatcher, or direct invocation from simulation endpoints.

### Criticality-Based Routing Rules

Each criticality level has distinct procurement behavior:

| Criticality | Buffer Multiplier | Reallocation | Expedite | Strategy                                |
|-------------|-------------------|--------------|----------|-----------------------------------------|
| CRITICAL    | 1.5x              | BLOCKED      | Yes      | Order 50% extra, no stock transfers     |
| HIGH        | 1.25x             | Allowed      | Yes      | Order 25% extra, careful reallocation    |
| MEDIUM      | 1.0x              | Allowed      | No       | Order exact gap, standard reallocation   |
| LOW         | 1.0x              | Free         | No       | Order exact gap, unrestricted transfers  |

### Function

```python
calculate_net_requirements(db: Session, sku: str, demand_qty: int) -> dict
```

**Steps:**
1. Locate the finished good by SKU
2. Query its BOM entries
3. For each component:
   - Calculate `required = demand_qty * quantity_per`
   - Check `available = on_hand - reserved`
   - Calculate `gap = required - available`
   - If gap > 0: apply safety stock multiplier from routing rules
   - If reallocation is allowed: check other finished goods for surplus
   - If reallocation fails or is blocked: issue BUY_ORDER with expedite flag

### Reallocation Logic

When a component has a shortage, Core-Guard checks if other finished goods using the same component have excess inventory:

```python
# Example: CH-101 is shared by FL-001-T and FL-001-S
# If FL-001-S has surplus, Core-Guard can reallocate to cover FL-001-T's gap
```

Reallocation is **blocked** for CRITICAL parts — too risky to transfer stock from other products.

### Actions

Core-Guard emits two types of actions:

**REALLOCATE:**
```json
{ "type": "REALLOCATE", "part_id": "CH-101", "source_sku": "FL-001-S", "quantity": 50 }
```

**BUY_ORDER:**
```json
{
  "type": "BUY_ORDER",
  "part_id": "CH-101",
  "quantity": 300,
  "unit_cost": 12.50,
  "total_cost": 3750.00,
  "supplier_id": 1,
  "supplier_name": "AluForge",
  "triggered_by": "Core-Guard",
  "expedite": true,
  "criticality": "CRITICAL"
}
```

**Returns:**
| Field     | Type  | Description                              |
|-----------|-------|------------------------------------------|
| sku       | str   | The finished good SKU                     |
| demand_qty| int   | Demand quantity processed                 |
| shortages | list  | Components with insufficient stock        |
| actions   | list  | REALLOCATE and BUY_ORDER actions          |
| logs      | list  | Glass Box log entries                     |

### Downstream
BUY_ORDER actions are forwarded to **Ghost-Writer**.

---

## 4. Ghost-Writer — Procurement & PO Generation Agent

**Source:** `backend/agents/ghost_writer.py`
**Role:** Terminal procurement agent. Validates spend, creates PurchaseOrder records, and generates PDF documents.

### Trigger
BUY_ORDER actions from Core-Guard or Eagle-Eye.

### Financial Constitution (Rule C)

This is a hard-coded guardrail that no agent or LLM can override:

```python
FINANCIAL_CONSTITUTION_MAX_SPEND = 5000.00

if total_cost > 5000:
    status = OrderStatus.PENDING_APPROVAL  # Human approval required
else:
    status = OrderStatus.APPROVED          # Auto-approved
```

### Function

```python
process_buy_orders(db: Session, buy_orders: list[dict]) -> dict
```

**Steps:**
1. For each BUY_ORDER:
   - Check `total_cost` against $5,000 limit
   - If over: set status to `PENDING_APPROVAL`, log CONSTITUTION BLOCK
   - If under: set status to `APPROVED`, log auto-approved
   - Create `PurchaseOrder` record with unique PO number (`PO-XXXXXXXX`)
   - Generate PDF to `backend/generated_pos/{PO_NUMBER}.pdf`

### PDF Layout

Generated POs include:
- Header: "PURCHASE ORDER"
- PO number, date, status
- Supplier name
- Line items table: Part ID, Quantity, Unit Cost, Total
- Footer: "Generated by Ghost-Writer Agent | Core-Guard MVP"

**Returns:**
| Field           | Type  | Description                       |
|-----------------|-------|-----------------------------------|
| purchase_orders | list  | Created PO records                |
| logs            | list  | Glass Box log entries             |

### Downstream
Terminal agent — no downstream. POs are the final output.

---

## 5. Eagle-Eye — Quality Inspection Agent

**Source:** `backend/agents/eagle_eye.py`
**Role:** Quality gate at the Digital Dock. Inspects incoming shipments against CAD spec tolerances.

### Trigger
Shipment arrival (simulated via `/api/simulate/quality-fail`).

### CAD Spec Tolerances

Hard-coded specs (in production, would come from Pinecone vector DB):

| Part   | Check 1                          | Check 2                           |
|--------|----------------------------------|-----------------------------------|
| CH-101 | Hardness: 8.0–10.0              | Dimension tolerance: +/-0.05mm    |
| SW-303 | Resistance: 4.5–5.5 ohm         | Cycle life: min 10,000            |
| LNS-505| Clarity: min 95%                 | Focal tolerance: +/-0.1mm         |

### Function

```python
inspect_batch(db: Session, part_id: str, batch_size: int, force_fail: bool = True) -> dict
```

**Steps:**
1. Retrieve part and its CAD spec
2. Simulate sensor readings (random values, biased by `force_fail`)
3. Compare each reading against spec tolerances
4. If all checks pass:
   - Add batch to `inventory.on_hand`
   - Record PASS in quality_inspections table
5. If any check fails:
   - Quarantine batch (stock NOT added)
   - Record FAIL with notes
   - Emit emergency BUY_ORDER for replacement batch

### AI Handover

Marked in code: in production, sensor readings would be compared against Pinecone vector embeddings of actual CAD drawings rather than hard-coded tolerance ranges.

**Returns:**
| Field         | Type  | Description                              |
|---------------|-------|------------------------------------------|
| result        | str   | `PASS`, `FAIL`, or `ERROR`                |
| part_id       | str   | Inspected part                            |
| batch_size    | int   | Units in the shipment                     |
| readings      | dict  | Simulated sensor values                   |
| failed_checks | list  | Spec violations (empty if passed)         |
| actions       | list  | BUY_ORDER actions (on failure)            |
| logs          | list  | Glass Box log entries                     |

### Downstream
On failure, emits BUY_ORDER actions to **Ghost-Writer** for emergency reorder.

---

## Glass Box Log Format

Every agent emits logs in this standard format:

```json
{
  "timestamp": "2026-02-21T12:00:00+00:00",
  "agent": "Core-Guard",
  "message": "SHORTAGE: CH-101 short by 200 units.",
  "type": "warning"
}
```

| Type      | Color (Frontend) | Usage                              |
|-----------|------------------|------------------------------------|
| `info`    | Blue             | General state changes              |
| `warning` | Yellow           | Potential issues, inventory gaps   |
| `success` | Green            | Resolved situations, approvals     |
| `error`   | Red              | Critical failures, constitution blocks |

Logs are persisted to the `agent_logs` table and streamed to the frontend via Socket.io.
