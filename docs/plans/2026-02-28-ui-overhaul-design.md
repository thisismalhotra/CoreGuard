# UI Overhaul Design — 3-Phase Dashboard Improvements

**Date:** 2026-02-28
**Status:** Approved
**Scope:** Frontend only (backend changes noted where needed)

---

## Context

The Core-Guard dashboard is ~85% complete. The core Glass Box pattern, real-time logs, 16 chaos scenarios, and Recharts visualizations are solid. This design addresses functional gaps, visual polish, and new capabilities in a phased rollout.

**Current stack:** Next.js 16 (App Router), React 19, Tailwind CSS 4, Shadcn UI, Recharts, Socket.io-client, Lucide React, next-themes.

---

## Phase 1: Functional Gaps

Ship first — highest impact. Fixes incomplete workflows that block real usage.

### 1A. Approve/Reject PO Buttons (Digital Dock)

**File:** `DigitalDock.tsx`

Add two action buttons inside expanded PO cards when `status === "PENDING_APPROVAL"`:
- **Approve:** green outline button, CheckCircle icon. Calls `PATCH /orders/{id}/status` with `{ status: "APPROVED" }`.
- **Reject:** red outline button, XCircle icon. Calls `PATCH /orders/{id}/status` with `{ status: "CANCELLED" }`.
- Disable both during API call, show Loader2 spinner.
- After action: badge updates, buttons disappear, PO list refreshes.
- Backend emits Socket.io log so Live Logs captures the approval/rejection.

### 1B. Log Filtering & Search (Live Logs)

**File:** `LiveLogs.tsx`

Add a filter bar above the log terminal:
- **Text search:** input field that filters log messages client-side in real-time.
- **Agent filter:** multi-select dropdown (Aura, Core-Guard, Ghost-Writer, Eagle-Eye, Dispatcher, System).
- **Type filter:** toggle buttons for info / warning / success / error.
- **Clear filters** button.
- Filters apply to existing and incoming logs. Filter state persists during tab switches, resets on page reload.

### 1C. Pagination (DB Viewer & Quality Inspections)

**Files:** `DBViewer.tsx`, `DigitalDock.tsx` (Quality Inspections table)

Client-side pagination, 25 rows per page:
- Previous / Next buttons + "Page X of Y" indicator.
- Optional: rows-per-page selector (25, 50, 100).
- No server-side pagination needed at MVP data sizes.

### 1D. Data Integrity Alerts

**File:** `CommandCenter.tsx` (Network Status tab)

Alert banner at top of Network Status tab when data integrity issues exist:
- Fetch from endpoint that returns integrity warnings (may need new backend endpoint).
- Shadcn Alert components with AlertTriangle icon.
- Color-coded: amber for suspect inventory, red for ghost inventory.
- Each alert: part ID, issue description, recommended action.
- Dismissible per-session.

### 1E. Loading Skeletons

**Files:** `AnalyticsCharts.tsx`, `InventoryCharts.tsx`, `KPIPanel.tsx`, `DigitalDock.tsx`

Replace "Loading..." plain text with Shadcn-style skeleton components (pulsing gray bars) that approximate the chart/card layout.

---

## Phase 2: Visual Polish & UX

Refine what exists. Ship after Phase 1.

### 2A. Theme-Aware Chart Tooltips

**Files:** `InventoryCharts.tsx`, `AnalyticsCharts.tsx`

Replace hardcoded hex colors in Recharts `<Tooltip>` `contentStyle` with CSS variable references:
- Background: `hsl(var(--card))`
- Text: `hsl(var(--card-foreground))`
- Border: `hsl(var(--border))`

### 2B. God Mode Layout Improvements

**File:** `GodMode.tsx`

- Wrap each section (Core Disruptions, Part Agent, Supply Chain, Demand Horizon) in Shadcn Collapsible/Accordion. All expanded by default.
- Running state: Loader2 spinning icon + "Running..." on button during simulation. Show result summary inline after completion.
- Sticky section headers so user knows which category they're in.

### 2C. Mobile Responsiveness Fixes

**Files:** `CommandCenter.tsx`, `InventoryCards.tsx`, `GodMode.tsx`

- Header: wrap buttons into dropdown menu below `md` breakpoint.
- Inventory Cards: `grid-cols-1 sm:grid-cols-2 xl:grid-cols-3`.
- God Mode: single column below `md`.
- Tab bar: horizontal scroll with fade indicators on mobile.

### 2D. Smooth Theme Transitions

**File:** `globals.css`

Add to root: `transition: background-color 200ms, color 200ms, border-color 200ms`.

### 2E. Accessibility Improvements

**Files:** `OnboardingModal.tsx`, `layout.tsx`, `InventoryCards.tsx`

- Focus trap in OnboardingModal.
- Skip-to-main-content link in layout.tsx.
- Text labels alongside color indicators (e.g., "LOW" badge next to red border).
- Ensure all interactive elements have `aria-label`.

### 2F. Low-Stock Visual Emphasis

**File:** `InventoryCards.tsx`

- Pulsing amber/red dot + "LOW STOCK" or "CRITICAL" text badge in card header.
- Critical items (below safety stock): subtle background tint (red-50 light / red-950/10 dark).

---

## Phase 3: New Capabilities

Net-new features. Ship after Phase 2.

### 3A. Export Logs & Data

**Files:** `LiveLogs.tsx`, `DBViewer.tsx`

- Live Logs: "Export" button downloads filtered logs as JSON.
- DB Viewer: "Export CSV" button per table tab.
- Client-side: construct Blob, create download link, trigger. No backend changes.

### 3B. Interactive Agent Chain Diagram

**Files:** `AgentsPage.tsx`, `OnboardingPage.tsx`

Replace static agent chain (badges + `→` arrows) with interactive flow diagram:
- CSS grid + animated connection lines (no heavy library).
- Each agent: clickable card node showing name, status, current action.
- Connections animate when logs flow through (pulse effect).
- Clicking a node scrolls to that agent's detail card.

### 3C. Notification/Toast System

**File:** New `components/Toaster.tsx` + integration in `layout.tsx`

Shadcn Sonner integration:
- Toasts for: scenario completion, PO approval/rejection, Socket.io events.
- Bottom-right position, auto-dismiss 5s, color-coded by type.

### 3D. Socket.io Reconnection Indicator

**File:** `CommandCenter.tsx`

Enhanced connection indicator:
- Connected: green dot + "Live"
- Reconnecting: amber pulsing dot + "Reconnecting..." + attempt count
- Disconnected: red dot + "Disconnected" + manual "Retry" button
- Surface Socket.io's built-in reconnection events.

### 3E. Copy-to-Clipboard (DB Viewer)

**File:** `DBViewer.tsx`

Clipboard icon on hover per cell. Click copies value via `navigator.clipboard.writeText`. Brief "Copied!" tooltip.

---

## Summary

| Phase | Items | Focus |
|-------|-------|-------|
| 1 | 5 items (1A-1E) | Fix broken/missing workflows |
| 2 | 6 items (2A-2F) | Polish existing screens |
| 3 | 5 items (3A-3E) | Add new value |

Each phase ships independently. No cross-phase dependencies.
