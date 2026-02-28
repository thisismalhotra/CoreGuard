# UI Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Comprehensive 3-phase UI improvement — fix functional gaps, polish visuals, add new capabilities.

**Architecture:** Frontend-only changes across existing Next.js components. One new backend endpoint for data integrity alerts. No new dependencies needed — uses existing Shadcn UI, Recharts, Lucide, and Socket.io.

**Tech Stack:** Next.js 16 (App Router), React 19, Tailwind CSS 4, Shadcn UI, Recharts, Socket.io-client, Lucide React

**Note:** PO Approve/Reject buttons (originally 1A) already exist at `DigitalDock.tsx:444-473`. Removed from plan.

---

## Phase 1: Functional Gaps

### Task 1: Log Filtering — Search Input

**Files:**
- Modify: `frontend/src/components/LiveLogs.tsx`

**Step 1: Add search state and filter logic**

Add a `searchQuery` state and a `filteredLogs` memo that filters logs by text match:

```tsx
// Add to imports
import { Search, X } from "lucide-react";

// Inside component, after existing state declarations (~line 44)
const [searchQuery, setSearchQuery] = useState("");
const [agentFilter, setAgentFilter] = useState<string[]>([]);
const [typeFilter, setTypeFilter] = useState<string[]>([]);

const filteredLogs = useMemo(() => {
  return logs.filter((log) => {
    if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !log.agent.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (agentFilter.length > 0 && !agentFilter.includes(log.agent)) {
      return false;
    }
    if (typeFilter.length > 0 && !typeFilter.includes(log.type)) {
      return false;
    }
    return true;
  });
}, [logs, searchQuery, agentFilter, typeFilter]);
```

Also add `useMemo` to the imports from React.

**Step 2: Add search input to toolbar**

Insert between the entry count and the delay selector in the toolbar (~line 85-89). Place search input on a new row above the existing toolbar:

```tsx
{/* Filter bar */}
<div className="flex items-center gap-2">
  <div className="relative flex-1">
    <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
    <input
      type="text"
      placeholder="Search logs..."
      value={searchQuery}
      onChange={(e) => setSearchQuery(e.target.value)}
      className="w-full bg-card border border-input text-foreground text-xs rounded pl-7 pr-7 py-1.5 h-7 focus:outline-none focus:border-blue-500 placeholder:text-muted-foreground/50"
    />
    {searchQuery && (
      <button
        onClick={() => setSearchQuery("")}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
      >
        <X className="h-3 w-3" />
      </button>
    )}
  </div>
</div>
```

**Step 3: Replace `logs` with `filteredLogs` in rendering**

Change `logs.map(...)` at line 143 to `filteredLogs.map(...)`. Update the entry count display to show `{filteredLogs.length} of {logs.length} entries` when filters are active.

**Step 4: Verify manually**

Run: `cd frontend && npm run dev`
- Type in the search box — logs should filter in real-time
- Clear the search — all logs should reappear

**Step 5: Commit**

```bash
git add frontend/src/components/LiveLogs.tsx
git commit -m "feat: add search filtering to Live Logs"
```

---

### Task 2: Log Filtering — Agent & Type Toggle Filters

**Files:**
- Modify: `frontend/src/components/LiveLogs.tsx`

**Step 1: Add agent filter toggle buttons**

Below the search bar, add a row of agent filter buttons. Use the existing `AGENT_COLORS` map for styling:

```tsx
{/* Agent filters */}
<div className="flex items-center gap-1 flex-wrap">
  <span className="text-[10px] text-muted-foreground mr-1">Agent:</span>
  {Object.keys(AGENT_COLORS).map((agent) => (
    <button
      key={agent}
      onClick={() =>
        setAgentFilter((prev) =>
          prev.includes(agent)
            ? prev.filter((a) => a !== agent)
            : [...prev, agent]
        )
      }
      className={`text-[10px] px-1.5 py-0.5 rounded border transition-colors ${
        agentFilter.includes(agent)
          ? `${AGENT_COLORS[agent]} text-white border-transparent`
          : "bg-card text-muted-foreground border-input hover:border-foreground/30"
      }`}
    >
      {agent}
    </button>
  ))}
</div>
```

**Step 2: Add type filter toggle buttons**

Same pattern for log types using `LOG_TYPE_STYLES`:

```tsx
{/* Type filters */}
<div className="flex items-center gap-1 flex-wrap">
  <span className="text-[10px] text-muted-foreground mr-1">Type:</span>
  {Object.keys(LOG_TYPE_STYLES).map((type) => (
    <button
      key={type}
      onClick={() =>
        setTypeFilter((prev) =>
          prev.includes(type)
            ? prev.filter((t) => t !== type)
            : [...prev, type]
        )
      }
      className={`text-[10px] px-1.5 py-0.5 rounded border capitalize transition-colors ${
        typeFilter.includes(type)
          ? "bg-foreground text-background border-transparent"
          : "bg-card text-muted-foreground border-input hover:border-foreground/30"
      }`}
    >
      {type}
    </button>
  ))}
</div>
```

**Step 3: Add a "Clear Filters" button**

Show only when any filter is active:

```tsx
{(searchQuery || agentFilter.length > 0 || typeFilter.length > 0) && (
  <Button
    variant="ghost"
    size="sm"
    className="text-xs h-6 px-2 text-muted-foreground"
    onClick={() => {
      setSearchQuery("");
      setAgentFilter([]);
      setTypeFilter([]);
    }}
  >
    <X className="h-3 w-3 mr-1" />
    Clear Filters
  </Button>
)}
```

**Step 4: Verify manually**

- Click agent buttons — only logs from selected agents should show
- Click type buttons — only matching log types should show
- Combine with search — all filters should AND together
- Clear filters — everything resets

**Step 5: Commit**

```bash
git add frontend/src/components/LiveLogs.tsx
git commit -m "feat: add agent and type filter toggles to Live Logs"
```

---

### Task 3: DB Viewer Pagination

**Files:**
- Modify: `frontend/src/components/DBViewer.tsx`

**Step 1: Add pagination state and logic**

Inside the `DataTable` sub-component (~line 89), add pagination state:

```tsx
const [currentPage, setCurrentPage] = useState(1);
const rowsPerPage = 25;
const totalPages = Math.ceil(rows.length / rowsPerPage);
const paginatedRows = rows.slice(
  (currentPage - 1) * rowsPerPage,
  currentPage * rowsPerPage
);
```

Reset page when data changes:

```tsx
useEffect(() => setCurrentPage(1), [rows]);
```

**Step 2: Replace `rows` with `paginatedRows` in table body**

Change the `.map()` call that renders table rows to use `paginatedRows` instead of `rows`.

**Step 3: Add pagination controls below the table**

```tsx
{totalPages > 1 && (
  <div className="flex items-center justify-between px-2 py-2 border-t border-border">
    <span className="text-xs text-muted-foreground">
      {rows.length} rows — Page {currentPage} of {totalPages}
    </span>
    <div className="flex items-center gap-1">
      <Button
        variant="outline"
        size="sm"
        className="h-7 text-xs"
        disabled={currentPage === 1}
        onClick={() => setCurrentPage((p) => p - 1)}
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-7 text-xs"
        disabled={currentPage === totalPages}
        onClick={() => setCurrentPage((p) => p + 1)}
      >
        Next
      </Button>
    </div>
  </div>
)}
```

**Step 4: Verify manually**

- Open DB Viewer tab, pick a table with >25 rows
- Verify pagination shows, Previous/Next work
- Switch tabs — verify page resets to 1

**Step 5: Commit**

```bash
git add frontend/src/components/DBViewer.tsx
git commit -m "feat: add client-side pagination to DB Viewer"
```

---

### Task 4: Quality Inspections Pagination

**Files:**
- Modify: `frontend/src/components/DigitalDock.tsx`

**Step 1: Add pagination state for inspections**

Inside the DigitalDock component, add pagination state near the existing state declarations:

```tsx
const [inspPage, setInspPage] = useState(1);
const inspPerPage = 25;
```

**Step 2: Calculate paginated inspections**

```tsx
const totalInspPages = Math.ceil(inspections.length / inspPerPage);
const paginatedInspections = inspections.slice(
  (inspPage - 1) * inspPerPage,
  inspPage * inspPerPage
);
```

**Step 3: Replace inspections rendering with paginated version**

Find the `inspections.map(...)` call in the Quality Inspections tab and replace with `paginatedInspections.map(...)`.

**Step 4: Add pagination controls below the inspections table**

Same pattern as Task 3 — Previous/Next buttons with page indicator.

**Step 5: Verify and commit**

```bash
git add frontend/src/components/DigitalDock.tsx
git commit -m "feat: add pagination to Quality Inspections table"
```

---

### Task 5: Loading Skeletons for Analytics Charts

**Files:**
- Modify: `frontend/src/components/AnalyticsCharts.tsx`

**Step 1: Replace the loading state**

Replace line 82-84:
```tsx
if (loading) {
  return <div className="text-center text-muted-foreground py-8 animate-pulse">Loading analytics...</div>;
}
```

With skeleton cards that approximate chart layouts:

```tsx
if (loading) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {[...Array(4)].map((_, i) => (
        <Card key={i} className="bg-card border-border">
          <CardHeader className="pb-2">
            <div className="h-4 w-32 bg-muted animate-pulse rounded" />
          </CardHeader>
          <CardContent>
            <div className="h-[250px] bg-muted/50 animate-pulse rounded flex items-end gap-1 p-4">
              {[...Array(6)].map((_, j) => (
                <div
                  key={j}
                  className="flex-1 bg-muted animate-pulse rounded-t"
                  style={{ height: `${30 + Math.random() * 60}%` }}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

Ensure `Card`, `CardHeader`, `CardContent` are imported (they should already be from existing chart rendering).

**Step 2: Verify manually**

- Reload the Analytics tab — should see pulsing skeleton cards instead of "Loading analytics..."

**Step 3: Commit**

```bash
git add frontend/src/components/AnalyticsCharts.tsx
git commit -m "feat: replace loading text with skeleton cards in AnalyticsCharts"
```

---

### Task 6: Loading Skeletons for Inventory Charts

**Files:**
- Modify: `frontend/src/components/InventoryCharts.tsx`

**Step 1: Add loading prop**

The component currently receives `inventory` as a prop. Check if there's already a loading indicator. If the component renders empty state when `filteredData.length === 0` (line 48-53), add a `loading` prop:

```tsx
export function InventoryCharts({
  inventory,
  loading,
}: {
  inventory: InventoryItem[];
  loading?: boolean;
}) {
```

**Step 2: Add skeleton state before empty check**

```tsx
if (loading) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {[...Array(3)].map((_, i) => (
        <Card key={i} className="bg-card border-border">
          <CardHeader className="pb-2">
            <div className="h-4 w-28 bg-muted animate-pulse rounded" />
          </CardHeader>
          <CardContent>
            <div className="h-[300px] bg-muted/50 animate-pulse rounded" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

**Step 3: Pass loading prop from CommandCenter**

In `CommandCenter.tsx`, pass a loading state to `InventoryCharts`:

```tsx
<InventoryCharts inventory={inventory} loading={!inventory.length && !backendError} />
```

**Step 4: Verify and commit**

```bash
git add frontend/src/components/InventoryCharts.tsx frontend/src/components/CommandCenter.tsx
git commit -m "feat: add loading skeletons to InventoryCharts"
```

---

### Task 7: Data Integrity Alerts — Backend Endpoint

**Files:**
- Create: `backend/routers/data_integrity.py`
- Modify: `backend/main.py` (to register the router)

**Step 1: Create the endpoint**

```python
"""Data‐integrity warnings endpoint — surfaces ghost/suspect inventory."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Inventory, Part

router = APIRouter(prefix="/api", tags=["data-integrity"])


@router.get("/data-integrity/warnings")
def get_data_integrity_warnings(db: Session = Depends(get_db)) -> list[dict]:
    """Return inventory items that have integrity concerns."""
    warnings: list[dict] = []
    items = db.query(Inventory).all()

    for item in items:
        part = db.query(Part).filter(Part.part_id == item.part_id).first()
        part_desc = part.description if part else item.part_id

        # Ghost inventory: on_hand > 0 but daily_burn_rate is 0 and no recent demand
        if item.on_hand > 0 and (item.daily_burn_rate or 0) == 0 and (item.reserved or 0) == 0:
            warnings.append({
                "part_id": item.part_id,
                "description": part_desc,
                "severity": "warning",
                "issue": "Ghost inventory",
                "detail": f"{item.on_hand} units on hand with zero burn rate and no reservations. May be stale.",
                "action": "Verify physical count and demand forecast.",
            })

        # Critical: below safety stock
        if item.available is not None and item.safety_stock is not None:
            if item.available < item.safety_stock:
                severity = "critical" if item.available < item.safety_stock * 0.5 else "warning"
                warnings.append({
                    "part_id": item.part_id,
                    "description": part_desc,
                    "severity": severity,
                    "issue": "Below safety stock",
                    "detail": f"Available: {item.available}, Safety Stock: {item.safety_stock}.",
                    "action": "Trigger replenishment or review safety stock level.",
                })

    return warnings
```

**Step 2: Register router in main.py**

Add the import and include the router alongside the existing ones:

```python
from routers.data_integrity import router as data_integrity_router
app.include_router(data_integrity_router)
```

**Step 3: Verify**

Run: `cd backend && python -c "from routers.data_integrity import router; print('OK')"`

**Step 4: Commit**

```bash
git add backend/routers/data_integrity.py backend/main.py
git commit -m "feat: add data integrity warnings API endpoint"
```

---

### Task 8: Data Integrity Alerts — Frontend Display

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/CommandCenter.tsx`

**Step 1: Add API method**

In `api.ts`, add to the api object:

```tsx
getDataIntegrityWarnings: () =>
  fetchJSON<Array<{
    part_id: string;
    description: string;
    severity: string;
    issue: string;
    detail: string;
    action: string;
  }>>(`${API_BASE}/api/data-integrity/warnings`),
```

**Step 2: Add state and fetch in CommandCenter**

```tsx
const [integrityWarnings, setIntegrityWarnings] = useState<Array<{
  part_id: string; description: string; severity: string;
  issue: string; detail: string; action: string;
}>>([]);
```

Fetch in `refreshData`:
```tsx
api.getDataIntegrityWarnings().then(setIntegrityWarnings).catch(() => {});
```

**Step 3: Render alerts above InventoryCards in the "status" tab**

```tsx
{integrityWarnings.length > 0 && (
  <div className="space-y-2 mb-4">
    {integrityWarnings.map((w, i) => (
      <div
        key={`${w.part_id}-${w.issue}-${i}`}
        className={`flex items-start gap-3 p-3 rounded-lg border text-xs ${
          w.severity === "critical"
            ? "bg-red-950/30 border-red-700/50 text-red-300"
            : "bg-yellow-950/30 border-yellow-700/50 text-yellow-300"
        }`}
      >
        <AlertTriangle className={`h-4 w-4 shrink-0 mt-0.5 ${
          w.severity === "critical" ? "text-red-500" : "text-yellow-500"
        }`} />
        <div>
          <span className="font-semibold">{w.part_id}</span>
          <span className="text-muted-foreground ml-1">— {w.issue}</span>
          <p className="text-muted-foreground mt-0.5">{w.detail}</p>
          <p className="mt-1 italic">{w.action}</p>
        </div>
      </div>
    ))}
  </div>
)}
```

Import `AlertTriangle` from lucide-react in CommandCenter.tsx.

**Step 4: Verify and commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/CommandCenter.tsx
git commit -m "feat: display data integrity alerts on Network Status tab"
```

---

## Phase 2: Visual Polish & UX

### Task 9: Theme-Aware Chart Tooltips

**Files:**
- Modify: `frontend/src/components/AnalyticsCharts.tsx`
- Modify: `frontend/src/components/InventoryCharts.tsx`

**Step 1: Update TOOLTIP_STYLE in AnalyticsCharts**

Replace the `TOOLTIP_STYLE` constant at line 21-26:

```tsx
const TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: "hsl(var(--card))",
  borderColor: "hsl(var(--border))",
  color: "hsl(var(--card-foreground))",
  borderRadius: "0.5rem",
  fontSize: "0.75rem",
};
```

**Step 2: Update tooltip styles in InventoryCharts**

Find any inline `contentStyle` on `<Tooltip>` components and apply the same pattern.

**Step 3: Verify by switching themes**

Switch between Light, Dark, and WARCOM — tooltips should match each theme.

**Step 4: Commit**

```bash
git add frontend/src/components/AnalyticsCharts.tsx frontend/src/components/InventoryCharts.tsx
git commit -m "fix: make chart tooltips theme-aware using CSS variables"
```

---

### Task 10: God Mode Collapsible Sections + Running State

**Files:**
- Modify: `frontend/src/components/GodMode.tsx`

**Step 1: Wrap each section in a collapsible**

Import `ChevronDown`, `ChevronUp` from lucide-react. Add state for collapsed sections:

```tsx
const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

const toggleSection = (key: string) =>
  setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
```

Wrap each section header in a clickable div that toggles visibility. Show ChevronDown/Up icon.

**Step 2: Add spinner to running scenarios**

Replace the button text with `<Loader2 className="h-3.5 w-3.5 animate-spin" />` + "Running..." when a scenario is in progress.

**Step 3: Make section headers sticky**

Add `sticky top-0 z-10 bg-card/95 backdrop-blur-sm` to section header divs.

**Step 4: Verify and commit**

```bash
git add frontend/src/components/GodMode.tsx
git commit -m "feat: add collapsible sections and running spinner to God Mode"
```

---

### Task 11: Smooth Theme Transitions

**Files:**
- Modify: `frontend/src/app/globals.css`

**Step 1: Add transitions to base layer**

Add to the `@layer base` section (~line 153):

```css
*,
*::before,
*::after {
  transition-property: background-color, border-color, color;
  transition-duration: 200ms;
  transition-timing-function: ease;
}
```

**Step 2: Exclude elements that shouldn't transition**

Add to prevent animation glitches on charts/modals:

```css
canvas,
svg,
[data-radix-popper-content-wrapper] {
  transition: none !important;
}
```

**Step 3: Verify**

Switch themes — should see smooth color crossfade instead of instant swap.

**Step 4: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat: add smooth color transitions on theme switch"
```

---

### Task 12: Low-Stock Visual Emphasis

**Files:**
- Modify: `frontend/src/components/InventoryCards.tsx`

**Step 1: Read existing file to find the card rendering**

Read the file first, then identify where inventory status is displayed.

**Step 2: Add severity classification**

```tsx
const getStockSeverity = (item: InventoryItem) => {
  if (!item.safety_stock) return "normal";
  if (item.available < item.safety_stock * 0.5) return "critical";
  if (item.available < item.safety_stock) return "low";
  return "normal";
};
```

**Step 3: Add visual indicators to card**

For each inventory card, based on severity:
- **Critical:** red pulsing dot + "CRITICAL" badge + `bg-red-950/10` card tint
- **Low:** amber pulsing dot + "LOW" badge + `bg-yellow-950/10` card tint
- **Normal:** no extra indicator

The pulsing dot:
```tsx
<span className="relative flex h-2 w-2">
  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
  <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
</span>
```

**Step 4: Verify and commit**

```bash
git add frontend/src/components/InventoryCards.tsx
git commit -m "feat: add pulsing dot and severity badges for low-stock inventory"
```

---

### Task 13: Mobile Responsiveness — Tab Bar Scroll

**Files:**
- Modify: `frontend/src/components/CommandCenter.tsx`

**Step 1: Make tab list horizontally scrollable**

Wrap the `TabsList` in a container with `overflow-x-auto` and hide scrollbar:

```tsx
<div className="overflow-x-auto scrollbar-hide">
  <TabsList className="bg-card border border-border inline-flex w-max min-w-full">
    {/* existing TabsTrigger elements */}
  </TabsList>
</div>
```

Add to globals.css:
```css
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
```

**Step 2: Commit**

```bash
git add frontend/src/components/CommandCenter.tsx frontend/src/app/globals.css
git commit -m "feat: make tab bar horizontally scrollable on mobile"
```

---

### Task 14: Accessibility — Skip Link + Focus Trap

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/OnboardingModal.tsx`

**Step 1: Add skip-to-content link in layout.tsx**

As the first child inside `<body>`:

```tsx
<a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-card focus:text-foreground focus:p-3 focus:rounded focus:border focus:border-border"
>
  Skip to main content
</a>
```

Add `id="main-content"` to the main content wrapper in `page.tsx` or `CommandCenter.tsx`.

**Step 2: Add basic focus trap to OnboardingModal**

Add a `useEffect` that traps Tab key within the modal when open:

```tsx
useEffect(() => {
  if (!open) return;
  const modal = modalRef.current;
  if (!modal) return;

  const focusableElements = modal.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const first = focusableElements[0] as HTMLElement;
  const last = focusableElements[focusableElements.length - 1] as HTMLElement;

  const handleTab = (e: KeyboardEvent) => {
    if (e.key !== "Tab") return;
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last?.focus(); }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first?.focus(); }
    }
  };

  document.addEventListener("keydown", handleTab);
  first?.focus();
  return () => document.removeEventListener("keydown", handleTab);
}, [open]);
```

**Step 3: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/components/OnboardingModal.tsx
git commit -m "feat: add skip-to-content link and modal focus trap for accessibility"
```

---

## Phase 3: New Capabilities

### Task 15: Export Logs as JSON

**Files:**
- Modify: `frontend/src/components/LiveLogs.tsx`

**Step 1: Add export button and handler**

Import `Download` icon from lucide-react. Add to toolbar:

```tsx
<Button
  variant="outline"
  size="sm"
  className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5 text-xs h-7"
  onClick={() => {
    const blob = new Blob([JSON.stringify(filteredLogs, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agent-logs-${new Date().toISOString().slice(0, 19)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }}
  disabled={filteredLogs.length === 0}
>
  <Download className="h-3 w-3" />
  Export
</Button>
```

**Step 2: Commit**

```bash
git add frontend/src/components/LiveLogs.tsx
git commit -m "feat: add JSON export button to Live Logs"
```

---

### Task 16: Export DB Viewer as CSV

**Files:**
- Modify: `frontend/src/components/DBViewer.tsx`

**Step 1: Add CSV export function and button**

```tsx
const exportCSV = (rows: Record<string, unknown>[], tableName: string) => {
  if (rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(","),
    ...rows.map((row) =>
      headers.map((h) => {
        const val = String(row[h] ?? "");
        return val.includes(",") ? `"${val}"` : val;
      }).join(",")
    ),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${tableName}-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
};
```

Add a "Export CSV" button next to each table, passing the current table's data and name.

**Step 2: Commit**

```bash
git add frontend/src/components/DBViewer.tsx
git commit -m "feat: add CSV export to DB Viewer tables"
```

---

### Task 17: Toast Notification System

**Files:**
- Run: `cd frontend && npx shadcn@latest add sonner`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/CommandCenter.tsx`
- Modify: `frontend/src/components/DigitalDock.tsx`
- Modify: `frontend/src/components/GodMode.tsx`

**Step 1: Install Sonner via Shadcn**

```bash
cd frontend && npx shadcn@latest add sonner
```

**Step 2: Add Toaster to layout**

In `layout.tsx`, import `{ Toaster }` from `@/components/ui/sonner` and add `<Toaster />` inside the body alongside other providers.

**Step 3: Add toasts to key actions**

In relevant components, import `{ toast }` from `sonner`:

- **CommandCenter.tsx:** Toast on Socket.io disconnect/reconnect
- **DigitalDock.tsx:** Toast on PO approve/reject success
- **GodMode.tsx:** Toast on scenario completion (success/failure)

Example:
```tsx
toast.success("PO approved successfully");
toast.error("Scenario failed: " + error.message);
toast.info("Reconnected to server");
```

**Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/components/CommandCenter.tsx frontend/src/components/DigitalDock.tsx frontend/src/components/GodMode.tsx frontend/src/components/ui/sonner.tsx
git commit -m "feat: add toast notification system using Sonner"
```

---

### Task 18: Socket.io Reconnection UI

**Files:**
- Modify: `frontend/src/components/CommandCenter.tsx`

**Step 1: Add reconnection state**

```tsx
const [reconnecting, setReconnecting] = useState(false);
const [reconnectAttempt, setReconnectAttempt] = useState(0);
```

**Step 2: Listen to Socket.io reconnection events**

In the useEffect where socket listeners are set up:

```tsx
socket.io.on("reconnect_attempt", (attempt) => {
  setReconnecting(true);
  setReconnectAttempt(attempt);
});
socket.io.on("reconnect", () => {
  setReconnecting(false);
  setReconnectAttempt(0);
  toast.success("Reconnected to server");
});
socket.io.on("reconnect_failed", () => {
  setReconnecting(false);
  toast.error("Failed to reconnect to server");
});
```

**Step 3: Update the connection indicator**

Replace the current green/red dot with three states:
- **Connected:** green pulsing dot + "Live"
- **Reconnecting:** amber pulsing dot + `Reconnecting (${reconnectAttempt})...`
- **Disconnected:** red dot + "Disconnected" + Retry button

```tsx
{reconnecting ? (
  <>
    <span className="h-2 w-2 rounded-full bg-yellow-500 animate-pulse" />
    <span className="text-xs text-yellow-400">Reconnecting ({reconnectAttempt})...</span>
  </>
) : connected ? (
  <>
    <span className="relative flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
    </span>
    <span className="text-xs text-green-400">Live</span>
  </>
) : (
  <>
    <span className="h-2 w-2 rounded-full bg-red-500" />
    <span className="text-xs text-red-400">Disconnected</span>
    <Button
      variant="ghost"
      size="sm"
      className="h-6 text-xs text-red-400"
      onClick={() => socket.connect()}
    >
      Retry
    </Button>
  </>
)}
```

**Step 4: Commit**

```bash
git add frontend/src/components/CommandCenter.tsx
git commit -m "feat: add Socket.io reconnection indicator with retry button"
```

---

### Task 19: Copy-to-Clipboard in DB Viewer

**Files:**
- Modify: `frontend/src/components/DBViewer.tsx`

**Step 1: Add clipboard handler**

```tsx
const [copiedCell, setCopiedCell] = useState<string | null>(null);

const copyToClipboard = async (value: string, cellKey: string) => {
  await navigator.clipboard.writeText(value);
  setCopiedCell(cellKey);
  setTimeout(() => setCopiedCell(null), 1500);
};
```

**Step 2: Add copy button to table cells**

Wrap each `<td>` content in a group with a hover-visible copy icon:

```tsx
<td className="group relative ...existing classes...">
  {/* existing cell content */}
  <button
    onClick={() => copyToClipboard(String(value), `${rowIdx}-${col}`)}
    className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity"
    title="Copy"
  >
    {copiedCell === `${rowIdx}-${col}` ? (
      <Check className="h-3 w-3 text-green-500" />
    ) : (
      <Copy className="h-3 w-3 text-muted-foreground hover:text-foreground" />
    )}
  </button>
</td>
```

Import `Copy`, `Check` from lucide-react.

**Step 3: Commit**

```bash
git add frontend/src/components/DBViewer.tsx
git commit -m "feat: add copy-to-clipboard on DB Viewer cells"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | Tasks 1-8 | Functional gaps: log filters, pagination, skeletons, data integrity |
| 2 | Tasks 9-14 | Visual polish: tooltips, God Mode, theme transitions, accessibility |
| 3 | Tasks 15-19 | New capabilities: export, toasts, reconnection UI, clipboard |

**Total:** 19 tasks, each independently committable.
