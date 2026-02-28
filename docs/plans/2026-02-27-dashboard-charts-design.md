# Dashboard Charts Design

## Context

The Analytics tab has 3 inventory charts (stock levels, health score, burn rate/runway) in `InventoryCharts.tsx`. The PRD mentions "Recharts (planned for production — inventory levels, demand curves)" but PO, quality, demand, and agent activity visualizations are missing. Recharts v3.7.0 is already installed.

## Design

Add a single new component `AnalyticsCharts.tsx` rendered below `InventoryCharts` in the Analytics tab. It fetches data from 4 existing API endpoints — no backend changes needed.

### Charts

**1. Procurement (from `/api/orders`)**
- PO Status Breakdown — PieChart: count of orders by status (APPROVED, PENDING_APPROVAL, CANCELLED, etc.)
- Spend by Supplier — Horizontal BarChart: sum of total_cost grouped by supplier name

**2. Quality (from `/api/db/quality_inspections`)**
- Pass/Fail Rate — PieChart: count of inspections by result (PASS, FAIL, PENDING)

**3. Demand (from `/api/db/demand_forecast`)**
- Forecast vs Actual — Grouped BarChart: forecast_qty vs actual_qty per part

**4. Agent Activity (from `/api/logs`)**
- Activity by Agent — Stacked BarChart: log count per agent, segments colored by log type (info/warning/success/error)

### Styling
- Match existing dark theme from `InventoryCharts.tsx`
- Use `ResponsiveContainer` for all charts
- Color palette: reuse existing blues/greens/ambers + extend for new data
- Custom tooltips matching the card background (`hsl(var(--card))`)

### Files
- New: `frontend/src/components/AnalyticsCharts.tsx`
- Edit: `frontend/src/components/CommandCenter.tsx` (render AnalyticsCharts in Analytics tab)

### Data Flow
All data fetched client-side via existing `api.*` methods. No new backend endpoints.
