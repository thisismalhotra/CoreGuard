# Core-Guard

Autonomous Supply Chain Operating System — Glass Box MVP

Core-Guard replaces manual procurement workflows with a network of 8 autonomous AI agents that detect supply chain crises and execute solutions in real-time. Users trigger chaos scenarios ("God Mode") and watch agents negotiate, triage, and generate Purchase Orders without human intervention.

**Product:** FL-001 Modular Flashlight Assembly
**Architecture:** Event-driven agent chain with full Glass Box transparency
**Status:** MVP (local simulation)

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm

### Backend

```bash
cd backend
pip install -r requirements.txt
python seed.py                                          # Seed FL-001 dataset
uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000  # Start API server
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # Start Next.js dev server at http://localhost:3000
```

### Running Tests

```bash
# Backend
cd backend && pytest tests/ -v --tb=short

# Frontend
cd frontend && npx vitest run
```

### Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

```bash
# Required for Google OAuth login
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
JWT_SECRET=change-me-to-a-random-32-char-string
FRONTEND_URL=http://localhost:3000

# Optional (LLM and vector DB — not yet integrated)
OPENAI_API_KEY=sk-your-key-here
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENVIRONMENT=us-east-1
```

**Google OAuth setup:** Create a project in [Google Cloud Console](https://console.cloud.google.com), enable the OAuth consent screen, create OAuth 2.0 credentials, and add `http://localhost:8000/api/auth/callback` as an authorized redirect URI.

## Tech Stack

| Layer    | Technology                                      |
|----------|------------------------------------------------|
| Frontend | Next.js 16, React 19, Tailwind CSS v4, Shadcn UI |
| Realtime | Socket.io (bidirectional log streaming)        |
| Backend  | Python FastAPI, python-socketio, slowapi       |
| Database | SQLite (WAL mode) via SQLAlchemy 2.0 ORM       |
| PDF Gen  | fpdf2 (Purchase Order documents)               |
| Charts   | Recharts                                       |
| Icons    | Lucide React                                   |
| Theming  | next-themes (dark/light mode)                  |
| Toasts   | sonner                                         |
| Auth     | Google OAuth + JWT (authlib, python-jose)      |
| CI       | GitHub Actions (Ruff, pytest, ESLint, Vitest, Next.js build) |

## Authentication

Google OAuth login with 4-role RBAC. First user is auto-assigned Admin; subsequent users default to Viewer.

| Role     | Dashboard | Simulations | Create POs | Approve POs | Reset | Manage Users |
|----------|-----------|-------------|------------|-------------|-------|--------------|
| Viewer   | Y         | -           | -          | -           | -     | -            |
| Operator | Y         | Y           | Y          | -           | -     | -            |
| Approver | Y         | Y           | Y          | Y           | -     | -            |
| Admin    | Y         | Y           | Y          | Y           | Y     | Y            |

## The 8 Agents

```
Scout → Router → Solver → Buyer
                              ↑
               Inspector ─────┘ (on quality failure)

Auditor   — monitors inventory integrity in background
Lookout   — classifies demand horizon zones
Pulse     — digital twin per SKU, triggers handshakes
```

All agents are stateless functions. They never call `db.commit()` — the calling router owns the transaction.

| Agent        | File                      | Role                                              |
|--------------|---------------------------|----------------------------------------------------|
| Scout        | `agents/aura.py`          | Demand sensing — fires when actual > forecast × 1.2 |
| Router       | `agents/dispatcher.py`    | Triage & prioritization — scores by criticality + lead time + gap |
| Solver       | `agents/core_guard.py`    | MRP engine — recursive BOM explosion, net requirements, reallocation |
| Buyer        | `agents/ghost_writer.py`  | PO generation — validates spend vs $5k constitution, generates PDF |
| Inspector    | `agents/eagle_eye.py`     | Quality inspection — sensor scans against CAD specs, quarantine on failure |
| Auditor      | `agents/data_integrity.py`| Ghost/suspect inventory detection (PRD §11) |
| Lookout      | `agents/demand_horizon.py`| Demand horizon zone classification (Zone 1/2/3, PRD §10) |
| Pulse        | `agents/part_agent.py`    | Digital twin per SKU — dynamic safety stock, runway, handshake trigger |

See [AGENTS.md](docs/AGENTS.md) for detailed documentation on each agent.

## Dashboard Pages

| Page           | Route        | Description                                           |
|----------------|--------------|-------------------------------------------------------|
| Command Center | `/`          | Main dashboard with Network Status, Live Logs, Digital Dock, Analytics, and God Mode tabs |
| Agent Registry | `/agents`    | Expandable cards showing each agent's role, rules, constitution, and data flow |
| DB Viewer      | `/db`        | Raw table browser for all 13 SQLite tables with pagination |
| Onboarding     | `/onboarding`| First-run walkthrough                                 |

## God Mode Scenarios

The simulation engine supports 17 chaos scenarios plus a reset. All are `POST /api/simulate/*` with rate limit 5/min:

| Scenario               | What Happens                                            | Tests                                    |
|------------------------|---------------------------------------------------------|------------------------------------------|
| 300% Demand Spike      | Scout detects surge, full agent chain executes           | Normal MRP + PO flow                     |
| Supplier Fire          | CREE Inc. goes offline, emergency reorder from alternates | Supplier failover                       |
| Quality Fail           | CH-231 batch fails inspection, quarantine + reorder      | Inspector inspection pipeline            |
| Cascade Failure        | 500% spike + CREE Inc. offline simultaneously            | Multi-crisis coordination                |
| Constitution Breach    | 800% spike forces POs over $5k limit                     | Financial guardrail enforcement          |
| Full Blackout          | All 22 suppliers offline + demand spike                  | System halt + human escalation           |
| Slow Bleed             | Gradual inventory drain over time                        | Slow-moving shortage detection           |
| Inventory Decay        | Ghost/suspect inventory appears                          | Auditor integrity checks                 |
| Multi-SKU Contention   | Multiple SKUs compete for same component                 | Resource contention resolution           |
| Contract Exhaustion    | Blanket PO runs out of remaining quantity                | Contract lifecycle management            |
| Tariff Shock           | Cost spike on a region's suppliers                       | Cost-driven re-sourcing                  |
| MOQ Trap               | Minimum order quantity exceeds actual need                | MOQ constraint handling                  |
| Military Surge         | VIP military order with priority allocation              | Ring-fencing and priority logic          |
| Semiconductor Allocation | Capacity reduction at key supplier                    | Allocation-based procurement             |
| Seasonal Ramp          | Seasonal demand forecast deviation                       | Forecast-driven planning                 |
| Demand Horizon         | Zone 1/2/3 classification of demand                      | Lookout zone classification              |
| Reset                  | Drop all tables, re-seed FL-001 data (rate limit 2/min)  | Fresh state for demo                     |

## Ground Truth Data (FL-001)

Seeded by `seed.py`: ~55 parts across 6 finished goods, 22 suppliers, 120+ BOM entries (3-level: FG → Sub-Assembly → Component).

| Part ID  | Description                        | Category      | Criticality | Supplier            |
|----------|------------------------------------|---------------|-------------|---------------------|
| FL-001-T | Tactical Flashlight                | Finished Good | CRITICAL    | N/A                 |
| FL-001-S | Standard Flashlight                | Finished Good | HIGH        | N/A                 |
| CH-231   | Body Tube (6061-T6 Aluminum)       | Component     | HIGH        | Apex CNC Works      |
| SW-232   | Reverse-Click Tail Switch Assembly | Component     | MEDIUM      | Dongguan SwitchTech |
| LNS-221  | TIR Optic Lens (Polycarbonate)     | Component     | HIGH        | Jiangsu OptiMold    |
| LED-201  | CREE XHP70.3 HI                    | Component     | CRITICAL    | CREE Inc.           |

### Database Tables (13)

`suppliers`, `supplier_contracts`, `scheduled_releases`, `alternate_suppliers`, `parts`, `inventory`, `bom`, `purchase_orders`, `demand_forecast`, `quality_inspections`, `sales_orders`, `ring_fence_audit`, `inventory_health`, `agent_logs`

## Architectural Rules

1. **Rule A — Glass Box:** Every agent action emits a structured log `{timestamp, agent, message, type}` persisted to `agent_logs` and streamed to the frontend via Socket.io.

2. **Rule B — Logic vs LLM:** All arithmetic (MRP calculations, spike detection) is pure Python. LLMs are reserved for unstructured data interpretation only (not yet integrated).

3. **Rule C — Financial Constitution:** Hard-coded in `ghost_writer.py`: if `total_cost > $5,000`, status = `PENDING_APPROVAL`. No agent or LLM can override this.

## Project Structure

```
CoreGuard/
├── backend/
│   ├── main.py                 # FastAPI + Socket.io ASGI wrapper
│   ├── seed.py                 # FL-001 dataset seeder
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── rate_limit.py           # slowapi rate limiter setup
│   ├── agents/
│   │   ├── aura.py             # Scout — Demand sensing
│   │   ├── dispatcher.py       # Router — Triage & prioritization
│   │   ├── core_guard.py       # Solver — MRP logic
│   │   ├── ghost_writer.py     # Buyer — PO generation + constitution
│   │   ├── eagle_eye.py        # Inspector — Quality inspection
│   │   ├── data_integrity.py   # Auditor — Ghost inventory detection
│   │   ├── demand_horizon.py   # Lookout — Demand horizon zones
│   │   ├── part_agent.py       # Pulse — Digital twin per SKU
│   │   └── utils.py            # create_agent_log() helper
│   ├── routers/
│   │   ├── inventory.py        # GET /api/inventory, /api/suppliers
│   │   ├── orders.py           # GET/POST /api/orders, PATCH approve/reject
│   │   ├── kpis.py             # GET /api/kpis, /api/logs, /api/settings/*
│   │   ├── agents_meta.py      # GET /api/agents, /api/db/* (table viewer)
│   │   ├── simulations.py      # POST /api/simulate/* (17 scenarios + reset)
│   │   └── data_integrity.py   # GET /api/data-integrity/warnings
│   ├── database/
│   │   ├── models.py           # SQLAlchemy ORM (13 tables)
│   │   └── connection.py       # DB engine, session, init_db()
│   ├── tests/
│   │   ├── conftest.py         # In-memory SQLite fixture
│   │   ├── test_agents.py      # Agent logic unit tests
│   │   ├── test_models_extended.py
│   │   ├── test_new_simulations.py
│   │   └── test_recursive_bom.py
│   ├── vectors/                # Empty stub (Pinecone planned)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router pages (/, /agents, /db, /onboarding)
│   │   ├── components/
│   │   │   ├── CommandCenter.tsx    # Main shell — tabs, Socket.io, data fetching
│   │   │   ├── KPIPanel.tsx         # KPI metric cards
│   │   │   ├── LiveLogs.tsx         # Real-time Glass Box terminal
│   │   │   ├── InventoryCards.tsx   # Inventory level cards
│   │   │   ├── InventoryCharts.tsx  # Recharts inventory visualizations
│   │   │   ├── AnalyticsCharts.tsx  # Recharts analytics dashboards
│   │   │   ├── GodMode.tsx          # Chaos scenario trigger buttons
│   │   │   ├── DigitalDock.tsx      # Quality inspection UI
│   │   │   ├── DBViewer.tsx         # Raw DB table viewer with pagination
│   │   │   ├── AgentsPage.tsx       # Agent cards with metadata
│   │   │   ├── OnboardingModal.tsx  # First-run walkthrough modal
│   │   │   ├── ThemeProvider.tsx    # Dark/light theme provider
│   │   │   ├── ThemeToggle.tsx      # Theme switch button
│   │   │   ├── ui/                  # Shadcn primitives (badge, button, card, sonner, tabs)
│   │   │   └── __tests__/           # Vitest component tests
│   │   └── lib/
│   │       ├── api.ts          # Backend API client functions
│   │       ├── socket.ts       # Socket.io singleton client
│   │       └── utils.ts        # cn() and utility helpers
│   ├── vitest.config.ts
│   └── package.json
├── .github/workflows/ci.yml   # GitHub Actions (Ruff, pytest, ESLint, Vitest, build)
├── CLAUDE.md                   # Development instructions
├── PRD.md                      # Product requirements
├── ARCHITECTURE.md             # System architecture (stub)
└── docs/
    ├── AGENTS.md               # Agent documentation
    ├── API.md                  # API reference
    └── plans/                  # Design and planning docs
```

## Further Documentation

- [API Reference](docs/API.md) — All REST and Socket.io endpoints
- [Agent Documentation](docs/AGENTS.md) — Detailed agent behavior, rules, and data flows
- [PRD](PRD.md) — Product Requirements Document
