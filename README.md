# Core-Guard

Autonomous Supply Chain Operating System — Glass Box MVP

Core-Guard replaces manual procurement workflows with a network of 5 autonomous AI agents that detect supply chain crises and execute solutions in real-time. Users trigger chaos scenarios ("God Mode") and watch agents negotiate, triage, and generate Purchase Orders without human intervention.

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

### Environment Variables (optional)

Copy `backend/.env.example` to `backend/.env` and fill in:

```
OPENAI_API_KEY=sk-your-key-here
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENVIRONMENT=us-east-1
```

The MVP runs fully without these — LLM and vector DB integrations are placeholder for production.

## Tech Stack

| Layer    | Technology                                      |
|----------|------------------------------------------------|
| Frontend | Next.js 16, React 19, Tailwind CSS, Shadcn UI |
| Realtime | Socket.io (bidirectional log streaming)        |
| Backend  | Python FastAPI, python-socketio                |
| Database | SQLite via SQLAlchemy ORM                      |
| PDF Gen  | fpdf2 (Purchase Order documents)               |
| Charts   | Recharts                                       |
| Icons    | Lucide React                                   |

## Agent Chain

```
Aura → Dispatcher → Core-Guard → Ghost-Writer
                                       ↑
                    Eagle-Eye ──────────┘ (on quality failure)
```

| Agent        | Role                        | Key Logic                                              |
|--------------|-----------------------------|---------------------------------------------------------|
| Aura         | Demand Sensing              | Fires DEMAND_SPIKE when actual > forecast x 1.2        |
| Dispatcher   | Triage & Prioritisation     | Scores components by criticality + lead time + gap      |
| Core-Guard   | MRP Logic                   | BOM explosion, net requirements, REALLOCATE vs BUY      |
| Ghost-Writer | Procurement & PO Generation | Validates spend vs $5k constitution, generates PDF POs  |
| Eagle-Eye    | Quality Inspection          | Sensor scans against CAD specs, quarantine on failure    |

See [AGENTS.md](docs/AGENTS.md) for detailed documentation on each agent.

## Dashboard Pages

| Page         | Route     | Description                                           |
|--------------|-----------|-------------------------------------------------------|
| Command Center | `/`    | Main dashboard with Network Status, Live Logs, Digital Dock, and God Mode tabs |
| Agent Registry | `/agents` | Expandable cards showing each agent's role, rules, constitution, and data flow |
| DB Viewer    | `/db`     | Raw table browser for all 8 SQLite tables              |

## God Mode Scenarios

The simulation engine supports 6 chaos scenarios plus a reset:

| Scenario             | What Happens                                          | Tests                                    |
|----------------------|-------------------------------------------------------|------------------------------------------|
| 300% Demand Spike    | Aura detects surge, full agent chain executes          | Normal MRP + PO flow                     |
| Supplier Fire        | AluForge goes offline, emergency reorder from alternates | Supplier failover                       |
| Quality Fail         | CH-101 batch fails inspection, quarantine + reorder    | Eagle-Eye inspection pipeline            |
| Cascade Failure      | 500% spike + AluForge offline simultaneously           | Multi-crisis coordination                |
| Constitution Breach  | 800% spike forces POs over $5k limit                   | Financial guardrail enforcement          |
| Full Blackout        | All 22 suppliers offline + demand spike                | System halt + human escalation           |
| Reset                | Drop all tables, re-seed FL-001 data                   | Fresh state for demo                     |

## Ground Truth Data (FL-001)

| Part ID  | Description         | Category      | Criticality | Supplier        |
|----------|---------------------|---------------|-------------|-----------------|
| FL-001-T | Tactical Flashlight | Finished Good | HIGH        | N/A             |
| FL-001-S | Standard Flashlight | Finished Good | MEDIUM      | N/A             |
| CH-101   | Modular Chassis     | Common Core   | CRITICAL    | AluForge        |
| SW-303   | Switch Assembly     | Common Core   | MEDIUM      | MicroConnect    |
| LNS-505  | Optic Lens          | Common Core   | HIGH        | Precision Optic |

22 suppliers seeded (3 primary + 19 alternates).

## Architectural Rules

1. **Rule A — Glass Box:** Every agent action emits a structured log `{timestamp, agent, message, type}` streamed to the frontend via Socket.io.

2. **Rule B — Logic vs LLM:** All arithmetic (MRP calculations, spike detection) is pure Python. LLMs are reserved for unstructured data interpretation only.

3. **Rule C — Financial Constitution:** Hard-coded in `ghost_writer.py`: if `total_cost > $5,000`, status = `PENDING_APPROVAL`. No agent or LLM can override this.

## Project Structure

```
CoreGuard/
├── backend/
│   ├── main.py                 # FastAPI + Socket.io server (all endpoints)
│   ├── seed.py                 # FL-001 dataset seeder
│   ├── agents/
│   │   ├── aura.py             # Demand sensing
│   │   ├── dispatcher.py       # Triage & prioritisation
│   │   ├── core_guard.py       # MRP logic
│   │   ├── ghost_writer.py     # PO generation + constitution
│   │   └── eagle_eye.py        # Quality inspection
│   ├── database/
│   │   ├── models.py           # SQLAlchemy ORM (8 tables)
│   │   └── connection.py       # DB session management
│   ├── generated_pos/          # PDF output directory
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router pages
│   │   ├── components/         # React components
│   │   │   ├── CommandCenter.tsx
│   │   │   ├── GodMode.tsx
│   │   │   ├── LiveLogs.tsx
│   │   │   ├── KPIPanel.tsx
│   │   │   ├── InventoryCards.tsx
│   │   │   ├── AgentsPage.tsx
│   │   │   └── DBViewer.tsx
│   │   └── lib/
│   │       ├── api.ts          # REST client
│   │       └── socket.ts       # Socket.io client
│   └── package.json
├── CLAUDE.md                   # Development instructions
├── PRD.md                      # Product requirements
├── ARCHITECTURE.md             # System architecture spec
└── docs/
    ├── AGENTS.md               # Agent documentation
    └── API.md                  # API reference
```

## Further Documentation

- [API Reference](docs/API.md) — All REST and Socket.io endpoints
- [Agent Documentation](docs/AGENTS.md) — Detailed agent behavior, rules, and data flows
- [PRD](PRD.md) — Product Requirements Document
- [Architecture](ARCHITECTURE.md) — System architecture specification
