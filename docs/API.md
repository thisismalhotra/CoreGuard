# API Reference

Base URL: `http://localhost:8000`

The backend runs as a combined FastAPI + Socket.io ASGI server. Start with:

```bash
uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
```

## REST Endpoints

### Inventory & Orders

#### `GET /api/inventory`

Returns current inventory levels for all parts.

**Response:**
```json
[
  {
    "part_id": "CH-231",
    "description": "Body Tube (6061-T6 Aluminum)",
    "category": "Component",
    "on_hand": 280,
    "safety_stock": 225,
    "reserved": 30,
    "available": 250,
    "supplier": "Apex CNC Works"
  }
]
```

#### `GET /api/orders`

Returns all purchase orders, newest first.

**Response:**
```json
[
  {
    "po_number": "PO-A1B2C3D4",
    "part_id": "CH-231",
    "supplier": "Apex CNC Works",
    "quantity": 150,
    "unit_cost": 12.50,
    "total_cost": 1875.00,
    "status": "APPROVED",
    "created_at": "2026-02-21T12:00:00+00:00",
    "triggered_by": "Core-Guard"
  }
]
```

**Status values:** `DRAFT`, `APPROVED`, `PENDING_APPROVAL`, `SENT`, `CANCELLED`

#### `GET /api/suppliers`

Returns all suppliers with their status.

**Response:**
```json
[
  {
    "id": 1,
    "name": "CREE Inc.",
    "lead_time_days": 42,
    "reliability_score": 0.94,
    "is_active": true
  }
]
```

#### `GET /api/logs?limit=50`

Returns recent Glass Box agent logs (persisted entries). Oldest first for display.

| Parameter | Type | Default | Description               |
|-----------|------|---------|---------------------------|
| `limit`   | int  | 50      | Max number of logs to return |

**Response:**
```json
[
  {
    "timestamp": "2026-02-21T12:00:00+00:00",
    "agent": "Aura",
    "message": "Scanning demand signal for FL-001-T...",
    "type": "info"
  }
]
```

**Log types:** `info`, `warning`, `success`, `error`

#### `GET /api/kpis`

Returns dashboard KPIs for the Network Status tab.

**Response:**
```json
{
  "inventory_health": 2.15,
  "total_on_hand": 2070,
  "total_safety_stock": 800,
  "active_threads": 4,
  "automation_rate": 100.0,
  "total_orders": 0
}
```

- `inventory_health`: ratio of total on-hand to total safety stock
- `automation_rate`: percentage of orders auto-approved (vs. PENDING_APPROVAL)

### Settings

#### `GET /api/settings/log-delay`

Returns the current log delay setting (seconds between each log line during simulations).

**Response:**
```json
{ "delay": 2.0 }
```

#### `POST /api/settings/log-delay?delay=1.0`

Updates the delay between log lines. Clamped to 0.5–5.0 seconds.

| Parameter | Type  | Default | Description          |
|-----------|-------|---------|----------------------|
| `delay`   | float | 2.0     | Seconds between logs |

### Agent Metadata

#### `GET /api/agents`

Returns metadata for all 5 agents: name, role, description, trigger, inputs, outputs, rules, constitution, downstream chain, color, icon, and source file.

**Response:**
```json
[
  {
    "name": "Aura",
    "role": "Demand Sensing Agent",
    "description": "Monitors real-time sales data...",
    "trigger": "Incoming demand data exceeds forecast by 20%+",
    "inputs": ["SKU identifier", "New actual demand quantity", "Demand forecast table"],
    "outputs": ["DEMAND_SPIKE event", "Spike multiplier", "Glass Box logs"],
    "downstream": "Dispatcher",
    "constitution": null,
    "rules": ["Stateless — reads DB state, never caches", "..."],
    "color": "purple",
    "icon": "Radio",
    "source_file": "agents/aura.py"
  }
]
```

### DB Viewer (Raw Tables)

All DB viewer endpoints return raw table dumps for the DB Viewer page.

| Endpoint                        | Table               | Notes                           |
|---------------------------------|---------------------|---------------------------------|
| `GET /api/db/suppliers`         | suppliers           | All columns                     |
| `GET /api/db/parts`             | parts               | Includes criticality fields     |
| `GET /api/db/inventory`         | inventory           | Includes computed `available`   |
| `GET /api/db/bom`               | bom                 | Parent → Component mappings     |
| `GET /api/db/orders`            | purchase_orders     | All POs with status             |
| `GET /api/db/demand_forecast`   | demand_forecast     | Forecast vs actual              |
| `GET /api/db/quality_inspections` | quality_inspections | Inspection results             |
| `GET /api/db/agent_logs`        | agent_logs          | Last 200 logs, newest first     |

---

## Simulation Endpoints (God Mode)

All simulation endpoints trigger the full agent chain and stream logs via Socket.io in real-time.

### `POST /api/simulate/spike`

**Scenario A: Demand Spike**

Triggers: Aura → Dispatcher → Core-Guard → Ghost-Writer

| Parameter    | Type   | Default    | Description                |
|-------------|--------|------------|----------------------------|
| `sku`       | string | FL-001-T   | SKU to spike               |
| `multiplier` | float  | 3.0        | Demand multiplier (3.0 = 300%) |

**Response:**
```json
{
  "status": "simulation_complete",
  "scenario": "DEMAND_SPIKE",
  "sku": "FL-001-T",
  "multiplier": 3.0,
  "aura": { "spike_detected": true, "multiplier": 3.0 },
  "mrp": {
    "shortages": [{ "part_id": "CH-231", "required": 600, "available": 250, "gap": 350, "criticality": "HIGH" }],
    "actions": [{ "type": "BUY_ORDER", "part_id": "CH-231", "quantity": 350, "total_cost": 6475.00 }]
  },
  "procurement": {
    "purchase_orders": [{ "po_number": "PO-A1B2C3D4", "status": "APPROVED" }]
  },
  "logs": [...]
}
```

### `POST /api/simulate/supply-shock`

**Scenario B: Supplier Fire**

Disables a supplier and triggers emergency reorders from the best alternate.

| Parameter       | Type   | Default  | Description              |
|----------------|--------|----------|--------------------------|
| `supplier_name` | string | CREE Inc. | Supplier to take offline  |

**Agent chain:** System → Core-Guard (impact assessment) → Ghost-Writer (emergency POs)

### `POST /api/simulate/quality-fail`

**Scenario C: Quality Failure**

Eagle-Eye inspects an incoming batch, forces failure, quarantines, and triggers emergency reorder.

| Parameter    | Type   | Default | Description              |
|-------------|--------|---------|--------------------------|
| `part_id`   | string | CH-231  | Part to inspect           |
| `batch_size` | int    | 150     | Units in the shipment     |

**Agent chain:** Eagle-Eye → Ghost-Writer (emergency reorder)

### `POST /api/simulate/cascade-failure`

**Scenario D: Cascade Failure**

CREE Inc. goes offline at the same moment a 500% demand spike hits FL-001-T. Tests multi-agent coordination under compounding stress.

No parameters. Automatically reroutes orders to the best alternate supplier.

**Agent chain:** System → Aura → Dispatcher → Core-Guard → Ghost-Writer (with supplier rerouting)

### `POST /api/simulate/constitution-breach`

**Scenario E: Constitution Breach**

800% demand spike forces POs that exceed the $5,000 financial guardrail. Ghost-Writer blocks them with `PENDING_APPROVAL`.

No parameters.

**Agent chain:** System → Aura → Dispatcher → Core-Guard → Ghost-Writer (constitution enforcement)

### `POST /api/simulate/full-blackout`

**Scenario F: Full Blackout**

All 22 suppliers go offline, then a 400% demand spike hits. Core-Guard exhausts every procurement path and escalates a CRITICAL alert requiring human intervention.

No parameters.

**Agent chain:** System → Aura → Dispatcher → Core-Guard → System (escalation)

### `POST /api/simulate/reset`

Drops all database tables, recreates them, and re-seeds with the FL-001 dataset. Returns the system to a clean state.

**Response:**
```json
{ "status": "reset_complete", "message": "Database wiped and re-seeded with FL-001 data." }
```

---

## Socket.io Events

The backend uses Socket.io for real-time Glass Box log streaming.

**Connection:** Clients connect to the same host/port as the REST API (`http://localhost:8000`).

### Events

| Event        | Direction       | Payload                                              | Description                          |
|-------------|-----------------|------------------------------------------------------|--------------------------------------|
| `connect`    | Client → Server | —                                                    | Client connects                      |
| `disconnect` | Client → Server | —                                                    | Client disconnects                   |
| `agent_log`  | Server → Client | `{timestamp, agent, message, type}`                   | Single Glass Box log entry           |

Logs are emitted one at a time with a configurable delay (`LOG_DELAY_SECONDS`) to simulate real-world agent processing time. Adjust via `POST /api/settings/log-delay`.

---

## Database Schema

8 tables managed by SQLAlchemy ORM. See `backend/database/models.py`.

| Table                | Primary Key | Key Columns                                                      |
|----------------------|-------------|------------------------------------------------------------------|
| `suppliers`          | id          | name, lead_time_days, reliability_score, is_active               |
| `parts`              | id          | part_id, category, criticality, lead_time_sensitivity, supplier_id |
| `inventory`          | id          | part_id (FK), on_hand, safety_stock, reserved                    |
| `bom`                | id          | parent_id (FK), component_id (FK), quantity_per                  |
| `purchase_orders`    | id          | po_number, part_id (FK), supplier_id (FK), status, total_cost    |
| `demand_forecast`    | id          | part_id (FK), forecast_qty, actual_qty, period                   |
| `quality_inspections`| id          | part_id (FK), batch_size, result, notes                          |
| `agent_logs`         | id          | agent, message, log_type, timestamp                              |
