# PRD: Core-Guard — Autonomous Supply Chain Operating System

**Version:** 2.0 — Comprehensive MVP Build Reference
**Date:** 2026-02-26
**Status:** Active — Engineering Build Reference
**Classification:** Internal

---

## 1. Product Overview

Core-Guard is an AI-powered **Autonomous Supply Chain Operating System** that deploys a coordinated swarm of specialized agents to transform reactive, spreadsheet-driven supply chain planning into a proactive, real-time, human-supervised execution system.

### The Copilot Philosophy (Non-Negotiable)
> The AI drafts. The human decides. Always.

- Agents do the math, monitoring, and paperwork
- Humans retain 100% financial authority
- Every recommendation is transparent and auditable (the "Glass Box" principle)
- The AI cannot spend money, send emails to suppliers, or execute any transaction without a human clicking **Approve**

---

## 2. The Problem

Manufacturing/distribution supply chains are run by a 6–8 person relay race of specialized planners passing spreadsheets to each other. This creates:

1. **Time Lag** — 2–4 weeks from demand signal to Purchase Order (PO)
2. **Human Error** — buyers hand-copy specs from engineering PDFs; a single typo destroys a $50,000 batch
3. **Reactive Management** — ERPs run nightly batch jobs; a 10 AM warehouse event isn't detected until 2 AM the next day (17 hours of lost reaction time)

---

## 3. Target Users

| Persona | Core Pain Today | What Core-Guard Gives Them |
|---|---|---|
| Demand Planner | 3 days in Excel building pivot tables | Aura surfaces Forecast Recommendation Cards to review and approve |
| Material / Inventory Planner | 5,000-line shortage spreadsheet every morning | Part Agents alert proactively; Core-Guard shows exact shortage with math |
| Buyer / Procurement Specialist | "Swivel-chair" data entry from engineering PDFs | Ghost-Writer drafts the PO automatically; buyer clicks Approve |
| S&OP Leader / Data Analyst | 2 days to answer one CEO question | Lumina answers in plain English in 3 seconds |
| VP of Supply Chain | Reactive weekly reports of what broke | Real-time dashboard with predicted shortages and blast radius |

---

## 4. The Agent Swarm

All agents operate under **Bounded Autonomy** — math is deterministic Python, LLMs only interpret unstructured data, and humans always turn the final key.

### Agent Roster

| Agent | Role | Execution Risk |
|---|---|---|
| **AURA** | Predictive Demand Sensing — monitors CRM, Shopify, logistics data; issues plain-English shortage forecasts | ZERO — read-only |
| **THE PART AGENT** | Digital Twin for every SKU — calculates dynamic safety stock, real-time burn rate, runway | ZERO — alerts only |
| **CORE-GUARD (MRP)** | Master Math Engine — BOM explosion, Net Requirements, digital ring-fencing of inventory | ZERO — drafts To-Buy list |
| **GHOST-WRITER** | Autonomous PO Drafter — takes Core-Guard's math and drafts a complete, formatted Purchase Order | ZERO — drafts only; human must Approve |
| **PRISM** | Engineering Decoder — reads CAD PDFs, extracts GD&T specs, materials, tolerances | ZERO — read-only |
| **EAGLE-EYE** | Quality Gate — compares supplier inspection reports against Prism-extracted blueprint specs | ZERO — quarantines; human decides |
| **LUMINA** | Conversational BI — translates plain-English questions into SQL; generates charts; sends Monday Briefs | ZERO — read-only analytics |
| **APEX** *(planned)* | Category strategy, blanket agreements, capacity reservations for long-range forecasts | Future |
| **MAESTRO** *(planned)* | Floor Orchestrator — machine and labor scheduling | Future |
| **PATHFINDER** *(planned)* | Logistics Router — freight optimization, rerouting | Future |

---

## 5. MVP Product Editions

### Edition 1 — Planner Edition (Build First)
**Agents:** Aura + Part Agent + Core-Guard MRP
**Value Prop:** Predictive Supply Chain Copilot — "We do the math; you make the decision"
**GTM Advantage:** Zero integration risk — reads data only, never writes to external systems

**Capabilities:**
- Predictive Zero-Day Shortage Alerts ("Part CH-101 will hit zero on Oct 14th based on new demand velocity")
- Multi-BOM Blast Radius Analysis (which finished goods are impacted by one missing part, and what revenue is at risk)
- Dynamic Digital Ring-Fencing (allocated inventory is protected from cannibalization by other orders)
- One-Click Drafted Recommendations (math + reason + action on a single card for buyer review)

### Edition 2 — Execution Copilot (Upsell at ~6 months)
**Agents:** Aura + Part Agent + Core-Guard MRP + Ghost-Writer
**Value Prop:** Assisted Supply Chain Execution — "One-Click Purchasing"

**Additional Capabilities:**
- Zero-Click PO Drafting (complete formatted PO auto-generated from shortage data + supplier database)
- Print-to-PO Translator (reads customer engineering PDFs via vision AI, no data entry)
- The Financial Guardrail ("The Inbox") — Ghost-Writer cannot send anything; all drafts land in the Approval Inbox

---

## 6. Critical Architectural Rules

These rules are **non-negotiable**. Every line of code must respect them.

### Rule A — The Glass Box Pattern
Every backend function (MRP calculation, PO generation, agent decision) **must** emit a structured log to the frontend via Socket.io.

```python
# Required log format for ALL agent emissions
{
  "timestamp": str,       # ISO 8601
  "agent": str,           # "CORE_GUARD" | "PART_AGENT" | "GHOST_WRITER" | "AURA"
  "message": str,         # Plain-English description of what the agent just did
  "type": "info" | "warning" | "success" | "error"
}
```

### Rule B — Logic vs. LLM Separation
- **Math:** NEVER ask an LLM to calculate arithmetic (e.g., `Forecast - Inventory`). Use Python.
- **Decision:** Use LLMs only to interpret unstructured data (PDFs, emails) or determine intent.
- **Execution:** Use Python to update the SQL database.
- **Comment every AI Handover point** in the code with `# AI HANDOVER: [reason]`

### Rule C — The Constitution (Hard-Coded Guardrails)
Hard-code in `ghost_writer.py`:

```python
# CONSTITUTION — THIS RULE CANNOT BE OVERRIDDEN BY ANY LLM OUTPUT
if total_cost > 5000:
    po_status = "PENDING_APPROVAL"  # Never "APPROVED" or "SEND"
```

---

## 7. The Data Model (Ground Truth)

**Do not hallucinate new parts.** Use only the FL-001 dataset. Foreign keys must link Parts to Suppliers in the DB schema.

| Part ID | Description | Category | Supplier |
|---|---|---|---|
| `FL-001-T` | Tactical Flashlight | Finished Good | N/A |
| `FL-001-S` | Standard Flashlight | Finished Good | N/A |
| `CH-101` | Modular Chassis | Common Core | AluForge |
| `SW-303` | Switch Assembly | Common Core | MicroConnect |
| `LNS-505` | Optic Lens | Common Core | Precision Optic |

---

## 8. Core Math (Must Implement in Python)

### Net Requirements Formula
```
Net Requirement = (Gross Demand + Safety Stock) - (On-Hand + On-Order)
```

### Dynamic Safety Stock (Part Agent)
```
Safety Stock = (Max Daily Usage × Max Lead Time) - (Avg Daily Usage × Avg Lead Time)
```

### Real-Time Runway (Part Agent)
```
Days to Stockout = Current On-Hand / Trailing 3-Day Velocity
```
> **NOTE:** Do NOT use monthly forecast averages. Use the trailing 3-day physical burn rate.

### Handshake Trigger Condition (Part Agent → Core-Guard)
```python
if runway < (supplier_lead_time + safety_stock_days):
    initiate_handshake(agent_id, on_hand, burn_rate, safety_stock)
```

---

## 9. The 5-Step Execution Loop (Part Agent ↔ Core-Guard)

1. **Baseline Monitoring** — Part Agent calculates its own runway and dynamic safety stock continuously
2. **Trigger Event** — A physical event occurs (demand drop-in, scrap, supplier delay) and touches the Part Agent's data in real-time
3. **Local Validation** — Part Agent re-runs its math gate: `IF runway < lead_time + safety_stock → HANDSHAKE`
4. **Core-Guard Handshake** — Part Agent sends a verified Crisis Signal (not raw data) with confirmed variables
5. **Execution Draft** — Core-Guard calculates Net Requirement → Ghost-Writer drafts PO → buyer receives Approval notification

---

## 10. The Three Demand Horizon Zones

| Zone | Timeframe | Active Agents | System Behavior |
|---|---|---|---|
| Zone 1 — Fuzzy Forecast | 6–12+ months | Aura | Advises on blanket agreements and capacity reservations. No POs generated. Cash preserved. |
| Zone 2 — Lead Time Horizon | 2–5 months | Core-Guard + Ghost-Writer | Forecast consumption begins. Core-Guard explodes BOM for firm orders. Ghost-Writer drafts standard POs to primary suppliers. |
| Zone 3 — Inside Lead Time (Drop-In Crisis) | < supplier lead time | Part Agent + Core-Guard | Part Agent defends ring-fenced inventory. Ghost-Writer pivots to fastest available secondary supplier and drafts expedited PO with cost-vs-risk trade-off card. |

---

## 11. Data Integrity Rules

### Ghost Inventory Detection
```python
# If scheduled consumption > 0 but system deductions == 0 for 14 consecutive days:
# 1. Block that On-Hand value from MRP calculations
# 2. Generate a Cycle Count Task for the warehouse manager with bin location
# 3. Emit a warning log
```

### Suspect Inventory Detection
```python
# If a part has not moved in 6 months but count is non-zero:
# 1. Flag as "Suspect Inventory"
# 2. Generate a physical count task
# 3. Emit a warning log
```

### Ring-Fencing Enforcement
```python
# When inventory is allocated to Order A:
# 1. Mark those units as RING_FENCED with order reference
# 2. Any attempt to pull them for Order B must:
#    a. Block the transaction
#    b. Alert the buyer: "[X] units are ring-fenced for [Order A]"
#    c. Log the attempted override in the audit trail
```

---

## 12. Build Sequence

Follow this exact order — later steps depend on earlier ones.

### Step 1: Database & Models (`backend/models.py` + `backend/seed.py`)
- SQLAlchemy ORM models: `Part`, `Supplier`, `InventoryItem`, `SalesOrder`, `PurchaseOrder`
- Foreign key: `InventoryItem.supplier_id → Supplier.id`
- `Part` has `part_id`, `description`, `category`, `bom_components` (JSON)
- `InventoryItem` has `on_hand`, `on_order`, `safety_stock`, `lead_time_days`, `daily_burn_rate`, `ring_fenced_qty`
- Seed script: loads all 5 FL-001 parts with realistic inventory levels and supplier lead times

### Step 2: API Layer (`backend/main.py`)
- FastAPI app with Socket.io integration via `python-socketio`
- `SocketManager` class handles all agent log emission
- Endpoints:
  - `GET /inventory` — returns all parts with on-hand, on-order, safety stock, runway
  - `POST /orders` — creates a new sales order; triggers Core-Guard evaluation
  - `POST /simulate/spike` — triggers full simulation pipeline (see Step 4)
- Every endpoint must emit at least one Glass Box log event

### Step 3: Agent Logic

#### `backend/agents/core_guard.py`
```python
def calculate_net_requirements(part_id: str, demand_qty: int) -> dict:
    # 1. Emit "info" log: starting calculation
    # 2. Fetch On-Hand, On-Order, Safety Stock from DB
    # 3. Net Requirement = (demand_qty + safety_stock) - (on_hand + on_order)
    # 4. Emit "success" or "warning" log with result
    # 5. Return { part_id, gross_demand, safety_stock, on_hand, on_order, net_requirement }

def ring_fence_inventory(part_id: str, order_id: str, qty: int) -> bool:
    # 1. Check available (on_hand - ring_fenced_qty) >= qty
    # 2. If yes: increment ring_fenced_qty, log success, return True
    # 3. If no: emit "error" log with conflict details, return False

def calculate_blast_radius(part_id: str) -> list[dict]:
    # Returns all finished goods that require this part, with revenue at risk
```

#### `backend/agents/ghost_writer.py`
```python
def draft_purchase_order(part_id: str, qty: int, supplier_id: str) -> dict:
    # 1. Fetch supplier details, pricing, part specs from DB
    # 2. Calculate total_cost = qty * unit_price
    # 3. # CONSTITUTION — CANNOT BE OVERRIDDEN
    #    if total_cost > 5000:
    #        status = "PENDING_APPROVAL"
    #    else:
    #        status = "DRAFT"
    # 4. Generate PDF using fpdf
    # 5. Save PO to DB
    # 6. Emit "success" log with PO details
    # 7. Return PO record
```

### Step 4: Simulation Harness (`POST /simulate/spike`)
Full pipeline trigger — every step must emit a Glass Box log:

```
POST /simulate/spike { "sku": "FL-001-T", "spike_multiplier": 3.0 }
  → Aura detects demand spike           → emit { agent: "AURA", type: "warning", ... }
  → Part Agent checks runway             → emit { agent: "PART_AGENT", type: "warning", ... }
  → Core-Guard calculates Net Req.      → emit { agent: "CORE_GUARD", type: "info", ... }
  → Core-Guard ring-fences inventory    → emit { agent: "CORE_GUARD", type: "success", ... }
  → Ghost-Writer drafts PO              → emit { agent: "GHOST_WRITER", type: "success", ... }
  → Dashboard displays Approval card   → emit { agent: "GHOST_WRITER", type: "info", ... }
```

### Step 5: Frontend Dashboard (`frontend/components/CommandCenter.tsx`)

**Tabs / Panels:**
1. **Network Status** — KPI cards: Inventory Health %, Active Alerts, Automation Rate
2. **Live Logs Terminal** — real-time scrolling stream of all agent Socket.io emissions; color-coded by type
3. **Inventory Cards** — per-part: on-hand, safety stock, runway, ring-fenced units, shortage status
4. **Approval Inbox** — list of all PENDING_APPROVAL / DRAFT POs with Approve/Reject buttons
5. **God Mode (Simulation)** — trigger buttons:
   - "Simulate 300% Demand Spike" → `POST /simulate/spike`
   - "Simulate Supply Shock" → `POST /simulate/shock`
   - "Simulate Quality Fail" → `POST /simulate/quality_fail`

**WebSocket Connection:**
```typescript
// Connect to Socket.io on mount
// Listen for "agent_log" events
// Append to live log terminal with timestamp, agent badge, message, type color
```

---

## 13. Tech Stack

### Backend
```
Python 3.10+
FastAPI
python-socketio       # Socket.io server
SQLAlchemy ORM
SQLite                # MVP database (swap for PostgreSQL in production)
fpdf                  # PDF PO generation
```

### Frontend
```
Next.js 14+ (App Router)
Tailwind CSS
Shadcn UI + Lucide React Icons
Socket.io Client      # Real-time agent logs
Recharts              # Inventory charts
```

### Start Commands
```bash
# Backend
cd backend
pip install -r requirements.txt
python seed.py                                          # Seed FL-001 dataset
uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## 14. Simulation Scenarios

### Scenario A — Demand Spike
```
Trigger: POST /simulate/spike { sku: "FL-001-T", multiplier: 3.0 }
Expected Flow:
  Aura detects 300% sales spike on Shopify
  → Part Agent: CH-101 runway drops to 8 days (supplier lead time: 12 days)
  → Core-Guard: Net Requirement = (3000 + 200) - (500 + 0) = 2700 units SHORT
  → Core-Guard: Ring-fence existing 500 for existing VIP order
  → Ghost-Writer: Drafts PO to AluForge for 2700 units at $4.50/ea = $12,150
  → CONSTITUTION TRIGGERED: total_cost > $5,000 → status = PENDING_APPROVAL
  → Dashboard: Approval card appears in Inbox
```

### Scenario B — Supply Shock
```
Trigger: POST /simulate/shock { supplier_id: "AluForge", delay_days: 30 }
Expected Flow:
  Aura detects port disruption (simulated)
  → Part Agent: CH-101 new runway = 8 days (reduced by 30-day delay)
  → Core-Guard: Blast Radius = FL-001-T at risk ($450k revenue), FL-001-S at risk ($220k)
  → Ghost-Writer: Cannot use AluForge (lead time > runway)
  → Ghost-Writer: Pivots to secondary local supplier; drafts expedited PO
  → Dashboard: Cost-vs-risk trade-off card shown to buyer
```

### Scenario C — Quality Fail
```
Trigger: POST /simulate/quality_fail { part_id: "CH-101", defect_rate: 0.15 }
Expected Flow:
  Eagle-Eye: Compares incoming inspection report to blueprint specs
  → 15% of batch out of tolerance on hole diameter
  → Eagle-Eye: Quarantines 150 units; flags for human review
  → Dashboard: Quality alert shown with discrepancy details
  → Human clicks Override & Approve OR Reject Shipment
```

---

## 15. Agent Prompt Template (LangChain — Production Phase)

When writing LangChain prompts, always use this structure:

```
SYSTEM: You are [AGENT_NAME], the [role].

CONTEXT:
  - SKU: [part_id]
  - On Hand: [qty]
  - Safety Stock: [qty]
  - Incoming Demand: [qty]
  - [Any additional context]

TASK: [Single, specific task in plain English]

OUTPUT: Return JSON only.
{ "action": "...", "reason": "...", "qty": ... }
```

> **Note:** For MVP, LangChain is NOT required. Use deterministic Python logic. LangChain is planned for production — Aura (demand prediction) and Ghost-Writer (PDF parsing) are the first candidates.

---

## 16. Success Metrics

### Leading Indicators (Days 1–30)
| Metric | Target |
|---|---|
| Time from demand signal to drafted PO | < 5 minutes (vs. 2–4 week legacy baseline) |
| Buyer adoption rate (logins to Approval Inbox) | > 80% of eligible buyers within 14 days |
| PO approval rate on AI-drafted recommendations | > 85% within 30 days |
| Part Agent alert accuracy (true positive rate) | > 95% |
| Data-entry typos on Ghost-Writer drafted POs | Zero |

### Lagging Indicators (Days 30–180)
| Metric | Target |
|---|---|
| Reduction in expedited air-freight events | 50% vs. 6-month pre-deployment baseline |
| Safety stock value reduction | 15–20% |
| Line-down events from undetected shortage | Zero |
| Scrap from procurement specification error | Zero |

---

## 17. Open Questions for Engineering

1. **ERP Integration (BLOCKING):** Read-only CSV export or live API for v1.0? This determines deployment complexity and sprint planning.
2. **Phantom Assemblies:** How does Core-Guard handle intermediate sub-assemblies built in-house (not purchased)?
3. **Part Agent Scaling:** Event-driven sleeping sentinel architecture from day one, or polling for MVP?
4. **Aura Data Sources:** Which external feeds (port APIs, Shopify webhooks, freight delay data) are in scope for v1.0?

---

## 18. What NOT to Build in MVP

- ❌ Autonomous financial transactions (no spending money without human Approve)
- ❌ ERP write-back (no writing to SAP/Oracle/NetSuite)
- ❌ Capacity planning (Maestro agent — future)
- ❌ Logistics routing (Pathfinder agent — future)
- ❌ Full Eagle-Eye, Lumina, or Prism (future editions — post Planner Edition GA)

---

## 19. Document Version History

| Version | Date | Summary |
|---|---|---|
| 1.0 | 2026-02-21 | Initial MVP spec — Glass Box simulation focus |
| 2.0 | 2026-02-26 | Comprehensive rewrite synthesizing all product strategy documents (Copilot model, agent roster, demand horizons, math formulas, data integrity rules, full build sequence) |

---

*This PRD is the single source of truth for the Core-Guard MVP build. All agent implementations, database schemas, and API contracts must conform to the specifications above.*
