# Core-Guard Code Review — Outstanding Issues

> **Last updated:** 2026-02-21
> **Reviewed by:** Lead Systems Architect
> **Scope:** Full-stack audit of backend (Python/FastAPI) and frontend (Next.js/React)

This document tracks all identified issues, bugs, and improvement opportunities in the Core-Guard codebase. Items are organized by severity and include affected files, descriptions, and suggested fixes.

**Previously resolved (not listed here):**
- ~~Fix reallocation logic bug in core_guard.py~~ *(commit c75a851)*
- ~~Fix reset endpoint race condition in main.py~~ *(commit c75a851)*
- ~~Split main.py monolith into FastAPI routers~~ *(commit c75a851)*
- ~~Build Digital Dock UI & PO viewer~~ *(commit c75a851)*
- ~~Add Pydantic request/response models~~ *(commit c75a851)*

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| Critical | 3 | Data integrity, security, persistence bugs |
| High | 10 | Logic bugs, API design, performance, code quality |
| Medium | 14 | Inconsistencies, missing validation, UX gaps |
| Low | 16 | Style, documentation, minor UX, testing |
| **Total** | **43** | |

---

## Critical (3)

### 1. Multiple Agents Commit on the Same DB Session

- **Category:** Bug / Data Integrity
- **Files:** `agents/aura.py`, `agents/core_guard.py`, `agents/ghost_writer.py`, `agents/dispatcher.py`, `agents/eagle_eye.py`, `routers/simulations.py`
- **Description:** Every agent function (`detect_demand_spike`, `calculate_net_requirements`, `triage_demand_spike`, `process_buy_orders`, `inspect_batch`) calls `db.commit()` at the end. The simulation endpoints call multiple agents sequentially on the same DB session. This means a single simulation runs 3-4 commits instead of one atomic transaction. If an error occurs mid-chain (e.g., Buyer fails after Solver committed), the database is left in a partially mutated state with no way to roll back.
- **Fix:** Remove `db.commit()` from all agent functions. Each agent should only `db.flush()` (which it already does for log IDs). Let the simulation endpoint perform a single `db.commit()` at the end, wrapping the entire chain in one transaction. On failure, the session rolls back automatically.

### 2. CORS Wildcard with Credentials Enabled

- **Category:** Security
- **File:** `main.py` (lines 37-43)
- **Description:** `allow_origins=["*"]` combined with `allow_credentials=True` is technically invalid per the CORS spec (browsers should reject it) and signals a misconfiguration. It exposes the API to cross-origin credential-forwarding attacks if any auth were added later. The Socket.io server also uses `cors_allowed_origins="*"`.
- **Fix:** Set `allow_credentials=False` (no cookies are used), or replace `"*"` with the specific frontend origin (e.g., `["http://localhost:3000"]`). Apply the same to Socket.io `cors_allowed_origins`.

### 3. `simulate_demand_spike` Lacks `db.commit()`

- **Category:** Bug
- **File:** `routers/simulations.py` (lines 66-133)
- **Description:** Unlike other simulation endpoints (`supply-shock`, `cascade-failure`, `constitution-breach`, `full-blackout`) which all have explicit `db.commit()` calls, `simulate_demand_spike` has none. It relies entirely on the agents to commit. If agent-level commits are removed (per issue #1), no data gets persisted.
- **Fix:** Add an explicit `db.commit()` before the `return` statement at the end of `simulate_demand_spike`.

---

## High (10)

### 4. `LOG_DELAY_SECONDS` Global Not Thread-Safe

- **Category:** Bug / Thread Safety
- **File:** `routers/kpis.py` (lines 15-16, 68-74)
- **Description:** `LOG_DELAY_SECONDS` is a module-level global mutated via `global LOG_DELAY_SECONDS` in the POST handler. In async/multi-worker environments this has race conditions. With `uvicorn --workers > 1`, each worker has its own copy, leading to inconsistent behavior.
- **Fix:** Store the log delay in the database (a simple settings table) or use a thread-safe mechanism. For MVP single-worker, this is functional but fragile.

### 5. `_sio` / `_get_log_delay` Fragile Module-Level Globals

- **Category:** Code Quality / Thread Safety
- **File:** `routers/simulations.py` (lines 27-36)
- **Description:** `_sio` and `_get_log_delay` are set via `init_sio()` called from `main.py`. If anything imports `simulations` before `main.py` calls `init_sio`, the values are `None` and `emit_logs` silently no-ops. There is no error if Socket.io fails to initialize.
- **Fix:** Use FastAPI's dependency injection or `app.state` to inject the Socket.io reference rather than module-level globals.

### 6. Simulation Endpoints Return Errors as HTTP 200

- **Category:** Bug / API Design
- **File:** `routers/simulations.py` (lines 84-85, 152-153, 326-327, 411-412, 497-498)
- **Description:** When a forecast or supplier is not found, the endpoint returns `{"error": "..."}` with HTTP 200. The frontend `fetchJSON` only checks `res.ok`, so it treats these error responses as successes. The user sees "Complete" when the simulation actually failed.
- **Fix:** Raise `HTTPException(status_code=404, detail=...)` instead of returning a dict with an error key. Update the frontend to handle error responses accordingly.

### 7. `_sys_log` Agent Name Mismatch Between DB and Socket.io

- **Category:** Bug
- **File:** `routers/simulations.py` (lines 49-59, 172-173)
- **Description:** `_sys_log` creates an `AgentLog` DB record with `agent="System"` and returns a dict also with `agent: "System"`. But in several places the returned dict's `agent` key is overwritten to `"Solver"` *after* the DB record was already created. The DB record and the Socket.io emitted log disagree on which agent produced the message.
- **Fix:** Pass the correct agent name to `_sys_log` as a parameter, or create a separate helper that accepts and stores the agent name consistently.

### 8. Unbounded Log Array Growth in Frontend

- **Category:** Performance
- **File:** `frontend/src/components/CommandCenter.tsx` (lines 55-57)
- **Description:** Every `agent_log` Socket.io event appends to the `logs` state array with no cap. During prolonged sessions, this array grows unboundedly, causing increasing re-render cost and potential memory exhaustion.
- **Fix:** Cap the `logs` array to a maximum size (e.g., 1000 entries), dropping the oldest when exceeded: `setLogs((prev) => [...prev, log].slice(-1000))`.

### 9. Log Deduplication by Message Alone is Fragile

- **Category:** Bug
- **File:** `frontend/src/components/CommandCenter.tsx` (lines 34-39)
- **Description:** `refreshData()` merges persisted logs with live logs by checking `message` uniqueness. If two different events produce the same message string, one is incorrectly filtered out. Running the same scenario twice produces logs with identical messages that should be distinct entries.
- **Fix:** Use a composite key of `timestamp + agent + message` or assign unique IDs to logs and deduplicate on ID.

### 10. Partial Reallocation Doesn't Reduce Buy Order Quantity

- **Category:** Bug / Logic
- **File:** `agents/core_guard.py` (lines 258-274)
- **Description:** When `_attempt_reallocation` performs a partial reallocation (e.g., 50 of 100 needed), it increments `reserved` on the component inventory but returns `None`. The calling code then issues a BUY_ORDER for the full `order_qty`, not just the remaining gap. So the system orders 100 units externally even though 50 were already reallocated.
- **Fix:** When partial reallocation occurs, return both the reallocation action AND adjust the buy order quantity to cover only the remaining gap (`order_qty - reallocatable`).

### 11. Unused Imports Across Agent Files

- **Category:** Code Quality
- **Files:** All 5 agent files
- **Description:**
  - `core_guard.py`: `PartCategory`, `Optional`, `DemandForecast` imported but never used
  - `ghost_writer.py`: `Optional` imported but never used
  - `eagle_eye.py`: `Inventory` imported but never used
  - `dispatcher.py`: `DemandForecast`, `Inventory` imported but never used
- **Fix:** Remove all unused imports.

### 12. CLAUDE.md Startup Command Is Incorrect

- **Category:** Bug / Documentation
- **File:** `CLAUDE.md` (line 41)
- **Description:** Says `uvicorn main:app --reload` but the actual ASGI entry point is `main:socket_app`. Running `main:app` means Socket.io is never mounted; WebSocket connections fail completely and the frontend never receives live logs.
- **Fix:** Update to `uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000`.

### 13. No `POST /orders` Endpoint Despite CLAUDE.md Specification

- **Category:** Missing Feature
- **Files:** `routers/orders.py`, `CLAUDE.md`
- **Description:** CLAUDE.md specifies `POST /orders` as part of the API layer, but only `GET /orders` exists. There is no endpoint for manually creating a purchase order.
- **Fix:** Add a `POST /orders` endpoint with Pydantic request validation for manual PO creation.

---

## Medium (14)

### 14. Simulation Response Models Defined but Never Used

- **Category:** Code Quality
- **Files:** `schemas.py`, `routers/simulations.py`
- **Description:** `SpikeResponse`, `SupplyShockResponse`, `QualityFailResponse`, etc. are defined in schemas.py but no simulation endpoint uses `response_model=`. The API docs show untyped responses.
- **Fix:** Add `response_model=SpikeResponse` (etc.) to each simulation endpoint.

### 15. DB Viewer Endpoints Lack Response Models

- **Category:** Code Quality
- **File:** `routers/agents_meta.py` (lines 133-236)
- **Description:** The DB viewer endpoints return raw dicts with no `response_model`. Corresponding Pydantic models (`DBSupplierRow`, `DBPartRow`, etc.) exist in `schemas.py` but are never used.
- **Fix:** Add `response_model=list[DBSupplierRow]` etc. to each endpoint.

### 16. `AgentsPage` Uses Raw `fetch()` Instead of `api.ts`

- **Category:** Code Quality / Inconsistency
- **File:** `frontend/src/components/AgentsPage.tsx` (lines 22, 170)
- **Description:** Defines its own `API_BASE` constant and uses raw `fetch()` instead of the centralized `api.ts` module. Bypasses shared error handling and duplicates base URL logic.
- **Fix:** Add a `getAgents()` method to `api.ts` and use it from `AgentsPage`.

### 17. `DBViewer` Uses Raw `fetch()` Instead of `api.ts`

- **Category:** Code Quality / Inconsistency
- **File:** `frontend/src/components/DBViewer.tsx` (lines 11, 152)
- **Description:** Same as #16 — defines its own `API_BASE` and uses raw `fetch()`.
- **Fix:** Add DB viewer methods to `api.ts` and use them.

### 18. Supply Shock Orders `safety_stock` Quantity Instead of Actual Shortage

- **Category:** Bug / Logic
- **File:** `routers/simulations.py` (line 181)
- **Description:** Emergency order quantity is set to `inv.safety_stock` rather than the actual shortfall. If a part has 500 on-hand but safety stock of 200, the system orders 200 more regardless.
- **Fix:** Use a meaningful calculation like `max(inv.safety_stock - inv.available, inv.safety_stock)` or route through Solver's MRP logic.

### 19. Inspector Reorders from the Same Failing Supplier

- **Category:** Bug / Logic
- **File:** `agents/eagle_eye.py` (lines 164-173)
- **Description:** When a batch fails quality inspection, Inspector creates a BUY_ORDER using the same supplier that just sent defective parts.
- **Fix:** Query for an alternate supplier with better reliability before generating the buy order, or flag the reorder for alternate supplier evaluation.

### 20. `Inventory.available` Can Return Negative Values

- **Category:** Bug
- **File:** `database/models.py` (lines 103-106)
- **Description:** The `available` property is `on_hand - reserved`. If `reserved > on_hand` (which can happen when reallocation increments `reserved` without bounds checking), `available` goes negative, inflating downstream shortage calculations.
- **Fix:** Clamp the property: `return max(0, self.on_hand - self.reserved)`. Alternatively, add a constraint that `reserved` can never exceed `on_hand`.

### 21. POST Parameters Sent as Query Strings Instead of Request Body

- **Category:** API Design
- **Files:** `routers/simulations.py`, `frontend/src/lib/api.ts`
- **Description:** POST endpoints like `/simulate/spike?sku=FL-001-T&multiplier=3.0` take parameters as query strings instead of JSON body, violating REST conventions.
- **Fix:** Create Pydantic request body models and accept them as JSON body parameters. Update the frontend to send JSON bodies.

### 22. Array Index as React Key in `LiveLogs`

- **Category:** UX / Performance
- **File:** `frontend/src/components/LiveLogs.tsx` (line 110)
- **Description:** `key={i}` causes React to re-render all items when logs are prepended (during `refreshData` merge).
- **Fix:** Use a composite key like `${timestamp}-${agent}-${i}`.

### 23. No Error Banner When Backend Is Offline

- **Category:** UX
- **File:** `frontend/src/components/CommandCenter.tsx`
- **Description:** If the initial `refreshData()` call fails, there is only a `console.error`. The user sees empty KPIs and no indication that the backend is unreachable.
- **Fix:** Add an error state that displays a clear banner when the initial fetch fails.

### 24. `handleDelayChange` Revert Uses Stale Closure

- **Category:** Bug
- **File:** `frontend/src/components/LiveLogs.tsx` (lines 51-59)
- **Description:** In the catch block, `setDelay(delay)` uses the closure-captured value which may be stale after the optimistic `setDelay(newDelay)` on line 52.
- **Fix:** Capture the previous delay before the optimistic update: `const prevDelay = delay; setDelay(newDelay); ... catch { setDelay(prevDelay); }`.

### 25. `Supplier.is_active` Uses Integer Instead of Boolean

- **Category:** Code Quality
- **File:** `database/models.py` (line 53)
- **Description:** `Column(Integer, default=1)` instead of `Column(Boolean, default=True)`. Requires manual `bool()` casts throughout the codebase and assignments use `0`/`1` instead of `True`/`False`.
- **Fix:** Use `Column(Boolean, default=True)` and update all assignments.

### 26. Missing Recharts Integration

- **Category:** Missing Feature
- **File:** `CLAUDE.md` (line 26)
- **Description:** CLAUDE.md lists Recharts for "inventory levels, demand curves" but no charts exist in the frontend. All data is displayed as cards with raw numbers.
- **Fix:** Add Recharts-based inventory/demand visualizations, or update CLAUDE.md to reflect actual state.

### 27. Socket Singleton Leaks Across Hot Reloads

- **Category:** Bug
- **File:** `frontend/src/lib/socket.ts` (lines 5-15)
- **Description:** Module-level `socket` variable persists across Next.js HMR. Old socket instance stays connected while new components mount, causing duplicate event listeners.
- **Fix:** Use `globalThis` with an HMR-safe pattern, or add cleanup logic on module disposal.

---

## Low (16)

### 28. Schemas Use `List`/`Dict` from `typing` Instead of Built-in

- **Category:** Code Quality
- **File:** `schemas.py`
- **Description:** Uses `from typing import List, Dict` while other files use built-in `list`/`dict`. Inconsistent style.
- **Fix:** Replace with built-in generics if targeting Python 3.10+.

### 29. `_log()` Helper Duplicated Across All 5 Agent Files

- **Category:** Code Quality / DRY
- **Files:** All agent files
- **Description:** The `_log()` function is identically defined in all five agent files. Only `AGENT_NAME` differs.
- **Fix:** Extract a shared `create_agent_log(db, agent_name, message, log_type)` function into `agents/utils.py`.

### 30. No Input Validation on Simulation Parameters

- **Category:** Validation
- **File:** `routers/simulations.py`
- **Description:** `multiplier` accepts negative/zero/huge values. `batch_size` has no bounds. Negative multiplier reduces demand; huge values create astronomical POs.
- **Fix:** Add `Query(ge=1.0, le=100.0)` to `multiplier`, `Query(ge=1, le=10000)` to `batch_size`, etc.

### 31. No Pagination on DB Viewer Endpoints

- **Category:** Performance
- **File:** `routers/agents_meta.py`
- **Description:** All DB viewer endpoints return all records (except `agent_logs` capped at 200). Tables grow unbounded with usage.
- **Fix:** Add `limit` and `offset` query parameters with reasonable defaults.

### 32. `generated_pos/` Not in `.gitignore`

- **Category:** Code Quality
- **File:** `agents/ghost_writer.py` (line 25)
- **Description:** Buyer generates PDFs to `backend/generated_pos/`. If not in `.gitignore`, generated PDFs could be accidentally committed.
- **Fix:** Add `backend/generated_pos/` to `.gitignore`.

### 33. `DemandForecast.period` Defaults to `"2025-Q1"`

- **Category:** Code Quality
- **File:** `database/models.py` (line 157)
- **Description:** Hardcoded past quarter as default. May confuse users reviewing the data.
- **Fix:** Dynamically compute current quarter or use a generic default.

### 34. No Loading Skeleton on KPIPanel

- **Category:** UX
- **File:** `frontend/src/components/KPIPanel.tsx` (line 49)
- **Description:** When `kpis` is `null` (initial load), each card shows a static dash with no skeleton/shimmer animation.
- **Fix:** Add a loading/skeleton state to KPI cards.

### 35. `DigitalDock` Silently Swallows Fetch Errors

- **Category:** UX
- **File:** `frontend/src/components/DigitalDock.tsx` (lines 82-84)
- **Description:** Empty `catch {}` block. If backend is down, user sees empty lists with no error message.
- **Fix:** Set an error state and display a user-facing error message.

### 36. `AgentsPage` Silently Swallows Fetch Errors

- **Category:** UX
- **File:** `frontend/src/components/AgentsPage.tsx` (line 177)
- **Description:** `.catch(() => {})` hides backend failures. User sees loading state that resolves to empty content.
- **Fix:** Add error state handling and display an error message.

### 37. Pinecone & LangChain Listed in Tech Stack but Unused

- **Category:** Documentation
- **File:** `CLAUDE.md` (lines 31-32)
- **Description:** Listed as part of the tech stack but neither is used anywhere. Inspector mentions Pinecone as "AI Handover" for production only.
- **Fix:** Add a note that these are "planned for production" or remove from tech stack.

### 38. `Inventory.last_updated` Never Updated on Mutations

- **Category:** Bug
- **Files:** `database/models.py` (line 99), `agents/core_guard.py`, `agents/eagle_eye.py`
- **Description:** Timestamp set at creation only. Not updated when `on_hand` or `reserved` are modified by agents.
- **Fix:** Set `inv.last_updated = datetime.now(timezone.utc)` whenever inventory fields are mutated.

### 39. CLAUDE.md Says "Stateless Classes" but Agents Are Functions

- **Category:** Documentation
- **Files:** `CLAUDE.md` (line 97), all agent files
- **Description:** Documentation says "Agents must be stateless classes that act on DB state" but all agents are implemented as standalone functions. The implementation is functionally equivalent but contradicts the spec.
- **Fix:** Update documentation to say "stateless functions" or refactor agents to be classes with a `.run()` method.

### 40. No ARIA Attributes on Custom Interactive Controls

- **Category:** UX / Accessibility
- **Files:** `ThemeToggle.tsx`, `DigitalDock.tsx`, `AgentsPage.tsx`
- **Description:** Custom dropdown buttons lack `aria-expanded`, `aria-haspopup`, `role`, and `aria-label` attributes. Screen readers cannot properly navigate these controls.
- **Fix:** Add appropriate ARIA attributes to all custom interactive elements.

### 41. Zero Test Coverage

- **Category:** Missing Feature / Code Quality
- **Description:** The entire codebase has no test files. No unit tests for agent logic (MRP calculations, constitution checks), no integration tests for API endpoints, and no component tests. The MRP math and financial constitution are critical business logic.
- **Fix:** Add at minimum: (1) unit tests for `calculate_net_requirements`, (2) unit tests for `process_buy_orders` verifying the $5,000 constitution, (3) API integration tests for each simulation endpoint.

### 42. Auto-Scroll Forces Bottom on Every Log in `LiveLogs`

- **Category:** UX
- **File:** `frontend/src/components/LiveLogs.tsx` (lines 47-49)
- **Description:** `scrollIntoView` fires on every `logs` state change. During a running simulation, the user cannot read earlier entries because the view constantly jumps to bottom.
- **Fix:** Only auto-scroll if the user is already near the bottom. Track scroll position and conditionally call `scrollIntoView`.

### 43. `print()` Used Instead of `logging` Module

- **Category:** Code Quality
- **Files:** `main.py` (lines 63, 67), `seed.py` (lines 174-179)
- **Description:** Socket.io connect/disconnect events and seed output use `print()` instead of `logging`. No log levels, timestamps, or filtering.
- **Fix:** Replace `print()` calls with `logging.info()` or `logging.debug()`.

---

## Recommended Fix Order

**Phase 1 — Data Integrity & Security (Critical)**
1. Remove `db.commit()` from all agents; add single commit in each simulation endpoint (#1, #3)
2. Fix CORS configuration (#2)

**Phase 2 — Logic Bugs & API Quality (High)**
3. Fix `_sys_log` agent mismatch (#7)
4. Fix partial reallocation buy-order quantity (#10)
5. Return proper HTTP error codes from simulations (#6)
6. Cap frontend log array and fix deduplication (#8, #9)
7. Fix CLAUDE.md startup command (#12)
8. Clean up unused imports (#11)

**Phase 3 — UX & Consistency (Medium)**
9. Wire up Pydantic response models to endpoints (#14, #15)
10. Centralize API calls in AgentsPage and DBViewer (#16, #17)
11. Fix `Inventory.available` negative values (#20)
12. Fix Inspector reorder supplier logic (#19)
13. Add error banners for offline backend (#23)
14. Smart auto-scroll in LiveLogs (#42 — listed as Low but high UX impact)

**Phase 4 — Polish & Testing (Low)**
15. Extract shared `_log()` helper (#29)
16. Add input validation to simulation params (#30)
17. Add `.gitignore` entries (#32)
18. Add ARIA attributes (#40)
19. Add test coverage for critical business logic (#41)
20. Switch to proper `logging` module (#43)
