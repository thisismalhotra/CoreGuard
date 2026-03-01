# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role & Persona

You are the Lead Systems Architect and Senior Full-Stack Engineer for Core-Guard. Your goal is to build a robust "Glass Box" MVP for an Autonomous Supply Chain Operating System. You value: Deterministic Logic, Type Safety, Visual Feedback, and System Stability.

## Project Context

Core-Guard is an AI-driven supply chain management system.

- **The Product:** FL-001 Flashlight (Modular Assembly)
- **The Problem:** Manual supply chains are too slow
- **The Solution:** A network of 8 autonomous agents (Scout, Router, Solver, Buyer, Inspector, Auditor, Lookout, Pulse) that detect shortages and execute solutions instantly
- **The MVP:** A local simulation where a user triggers a "Demand Spike" and watches the agents negotiate and execute a Purchase Order (PO) in real-time

See `PRD.md` for full product requirements. Note: `ARCHITECTURE.md` exists but is a stub — the source of truth is this file and the codebase itself.

## Tech Stack

**Frontend**
- Next.js 16 (App Router)
- Tailwind CSS v4 + Shadcn UI (Lucide React Icons)
- Socket.io Client (real-time agent logs)
- Recharts (inventory charts, analytics dashboards)
- next-themes (dark/light mode), sonner (toast notifications)

**Backend**
- Python 3.10+, FastAPI
- SQLite (MVP) via SQLAlchemy 2.0 ORM (WAL mode, aiosqlite)
- python-socketio (async, wrapped as ASGI app)
- fpdf2 (PO PDF generation)
- slowapi (rate limiting)

**Not yet integrated** (installed in requirements.txt but unused):
- LangChain / langchain-openai — planned for LLM-based decisions
- Pinecone — planned for vector search (CAD specs, etc.)
- OpenAI — planned for agent reasoning

## Commands

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000  # Start API + Socket server
python seed.py                     # Seed FL-001 dataset into DB
pytest tests/ -v --tb=short        # Run backend tests
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                        # Start Next.js dev server
npm run build && npm run start     # Production build
npm run lint                       # Run ESLint
npx vitest run                     # Run frontend tests
```

**CI** (GitHub Actions — `.github/workflows/ci.yml`)
- Backend job: Python 3.12, Ruff lint, pytest
- Frontend job: Node 20, ESLint, Vitest, Next.js build

## Project Structure

```
backend/
├── main.py                  # FastAPI app + Socket.io ASGI wrapper
├── seed.py                  # FL-001 dataset seeder
├── schemas.py               # Pydantic request/response schemas
├── rate_limit.py            # slowapi rate limiter setup
├── database/
│   ├── connection.py        # SQLite engine, session, init_db()
│   └── models.py            # 14 SQLAlchemy tables (incl. users)
├── agents/                  # 8 stateless agent modules
│   ├── aura.py              # Scout — demand sensing
│   ├── dispatcher.py        # Router — triage & prioritization
│   ├── core_guard.py        # Solver — MRP engine, BOM explosion
│   ├── ghost_writer.py      # Buyer — PO creation, $5k guardrail, PDF
│   ├── eagle_eye.py         # Inspector — quality / Digital Dock
│   ├── data_integrity.py    # Auditor — ghost inventory detection
│   ├── demand_horizon.py    # Lookout — demand horizon zones
│   ├── part_agent.py        # Pulse — digital twin per SKU
│   └── utils.py             # create_agent_log() helper
├── auth.py                  # JWT helpers, get_current_user, require_role
├── routers/                 # FastAPI route modules
│   ├── auth.py              # Google OAuth login/callback, /me
│   ├── admin.py             # User management (admin only)
│   ├── inventory.py         # GET /api/inventory, /api/suppliers
│   ├── orders.py            # GET/POST /api/orders, PATCH approve/reject
│   ├── kpis.py              # GET /api/kpis, /api/logs, /api/settings/*
│   ├── agents_meta.py       # GET /api/agents, /api/db/* (table viewer)
│   ├── simulations.py       # POST /api/simulate/* (17 scenarios + reset)
│   └── data_integrity.py    # GET /api/data-integrity/warnings
├── tests/
│   ├── conftest.py          # In-memory SQLite fixture
│   ├── test_agents.py       # Agent logic unit tests
│   ├── test_models_extended.py
│   ├── test_new_simulations.py
│   └── test_recursive_bom.py
└── vectors/                 # Empty stub (Pinecone planned)

frontend/src/
├── app/
│   ├── page.tsx             # Main dashboard (CommandCenter)
│   ├── login/page.tsx       # Google OAuth login page
│   ├── agents/page.tsx      # Agent metadata cards
│   ├── db/page.tsx          # Raw DB table viewer
│   └── onboarding/page.tsx  # First-run walkthrough
├── components/
│   ├── CommandCenter.tsx     # Main shell — tabs, Socket.io, data fetching
│   ├── KPIPanel.tsx          # KPI metric cards
│   ├── LiveLogs.tsx          # Real-time Glass Box terminal
│   ├── InventoryCards.tsx    # Inventory level cards
│   ├── InventoryCharts.tsx   # Recharts inventory visualizations
│   ├── AnalyticsCharts.tsx   # Recharts analytics dashboards
│   ├── GodMode.tsx           # Chaos scenario trigger buttons
│   ├── DigitalDock.tsx       # Quality inspection UI
│   ├── DBViewer.tsx          # Raw DB table viewer with pagination
│   ├── AgentsPage.tsx        # Agent cards with metadata
│   ├── OnboardingModal.tsx   # First-run modal
│   └── ui/                   # Shadcn primitives (badge, button, card, etc.)
├── middleware.ts             # Route protection (auth check)
└── lib/
    ├── auth.tsx             # AuthProvider, useAuth, hasRole
    ├── api.ts               # Backend API client (auto-injects JWT)
    ├── socket.ts            # Socket.io singleton client (JWT auth)
    └── utils.ts             # cn() and utility helpers
```

## The 8 Agents

All agents are **stateless functions** that operate on DB state. They never call `db.commit()` — the calling router owns the transaction. Each agent emits structured logs via `create_agent_log()`.

| Persona      | File                    | Role                                                    |
|--------------|-------------------------|---------------------------------------------------------|
| **Scout**    | `agents/aura.py`        | Demand sensing — detects spike when actual > forecast × 1.2 |
| **Router**   | `agents/dispatcher.py`  | Triage & prioritization — scores BOM components by criticality |
| **Solver**   | `agents/core_guard.py`  | MRP engine — recursive BOM explosion, net requirements, reallocation |
| **Buyer**    | `agents/ghost_writer.py`| PO creation, $5,000 Constitution enforcement, PDF via fpdf2 |
| **Inspector**| `agents/eagle_eye.py`   | Quality inspection at Digital Dock, CAD spec tolerance checks |
| **Auditor**  | `agents/data_integrity.py` | Ghost/suspect inventory detection (PRD §11) |
| **Lookout**  | `agents/demand_horizon.py` | Demand horizon zone classification (Zone 1/2/3, PRD §10) |
| **Pulse**    | `agents/part_agent.py`  | Digital twin per SKU — dynamic safety stock, runway, handshake trigger |

## Critical Architectural Rules

### Rule A: The "Glass Box" Pattern
Every backend function (MRP calculation, PO generation) must emit a structured log to the frontend via Socket.io.

```python
# Required log format for all agent emissions
{ "timestamp": str, "agent": str, "message": str, "type": "info" | "warning" | "success" | "error" }
```

Logs are persisted to the `agent_logs` table via `create_agent_log()` in `agents/utils.py`, then emitted via `sio.emit("agent_log", log_dict)` in routers. A configurable `log_delay_seconds` (default 2.0s) paces emissions for the Glass Box effect.

### Rule B: Logic vs. LLM Separation
- **Math:** Never ask the LLM to calculate arithmetic (e.g., `Forecast - Inventory`). Use Python.
- **Decision:** Use the LLM only to interpret unstructured data (PDFs, emails) or determine intent.
- **Execution:** Use Python to update the SQL database. Comment in code where "AI Handover" occurs.

Currently, all agent logic is pure deterministic Python — no LLM calls are made yet.

### Rule C: The "Constitution" (Guardrails)
Hard-code in `ghost_writer.py`: if `total_cost > 5000`, status **must** be `PENDING_APPROVAL`. The LLM cannot override this.

## Authentication & RBAC

Google OAuth login via `authlib`. Backend issues JWT (signed with `python-jose`). Frontend stores in localStorage, sends as `Authorization: Bearer` header.

**4 roles:** Admin, Operator, Approver, Viewer. First user auto-assigned Admin; subsequent users default to Viewer.

| Action | Viewer | Operator | Approver | Admin |
|--------|--------|----------|----------|-------|
| View dashboard, inventory, logs | Y | Y | Y | Y |
| Trigger simulations (God Mode) | - | Y | Y | Y |
| Create manual POs | - | Y | Y | Y |
| Approve/reject POs | - | - | Y | Y |
| Reset database | - | - | - | Y |
| Manage users | - | - | - | Y |

**Auth dependencies** (`backend/auth.py`):
- `get_current_user` — validates JWT, returns User. Use on all protected endpoints.
- `require_role("operator", "admin")` — wraps `get_current_user` + role check.

**Required env vars:**
```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
JWT_SECRET=...
FRONTEND_URL=http://localhost:3000
```

## The Data Model (Ground Truth)

Do not hallucinate new parts. Use only the FL-001 dataset seeded by `seed.py`: ~55 parts across 6 finished goods, 22 suppliers, 120+ BOM entries (3-level: FG → Sub-Assembly → Component), across 14 database tables.

Representative examples:

| Part ID  | Description                        | Category      | Supplier            |
|----------|------------------------------------|---------------|---------------------|
| FL-001-T | Tactical Flashlight                | Finished Good | N/A                 |
| FL-001-S | Standard Flashlight                | Finished Good | N/A                 |
| CH-231   | Body Tube (6061-T6 Aluminum)       | Component     | Apex CNC Works      |
| SW-232   | Reverse-Click Tail Switch Assembly | Component     | Dongguan SwitchTech |
| LNS-221  | TIR Optic Lens (Polycarbonate)     | Component     | Jiangsu OptiMold    |
| LED-201  | CREE XHP70.3 HI                    | Component     | CREE Inc.           |

Foreign keys must link Parts to Suppliers in the DB schema.

### Database Tables (14 total)
`suppliers`, `supplier_contracts`, `scheduled_releases`, `alternate_suppliers`, `parts`, `inventory`, `bom`, `purchase_orders`, `demand_forecast`, `quality_inspections`, `sales_orders`, `ring_fence_audit`, `inventory_health`, `agent_logs`, `users`

## Simulation Scenarios

All simulation endpoints are `POST /api/simulate/*` with rate limit 5/min:

`/spike`, `/supply-shock`, `/quality-fail`, `/cascade-failure`, `/constitution-breach`, `/full-blackout`, `/slow-bleed`, `/inventory-decay`, `/multi-sku-contention`, `/contract-exhaustion`, `/tariff-shock`, `/moq-trap`, `/military-surge`, `/semiconductor-allocation`, `/seasonal-ramp`, `/demand-horizon`, `/reset`

## Coding Style

**Python:** Use type hints (`def calculate(qty: int) -> dict:`). Handle exceptions gracefully. Agents are stateless functions that act on DB state. Agents call `db.flush()` (not `db.commit()`) — the router owns the transaction.

**React:** Functional components and hooks only. Keep state logic simple.

**Comments:** Explain the *why*, not just the *how*. Always mark where "AI Handover" occurs in agent code.

## Agent Prompt Template

When writing LangChain prompts (for future LLM integration), use this structure:

```
SYSTEM: You are Solver, the MRP Logic Agent.
CONTEXT:
  - SKU: CH-231
  - On Hand: 150
  - Safety Stock: 225
  - Incoming Demand: 400
  - BOM Substitute: FL-001-S has 300 units reserved.

TASK: Calculate the Net Requirement. Decide if we should (A) Buy New or (B) Reallocate from Substitute.
OUTPUT: Return JSON only.
{ "action": "REALLOCATE", "source": "FL-001-S", "qty": 200 }
```
