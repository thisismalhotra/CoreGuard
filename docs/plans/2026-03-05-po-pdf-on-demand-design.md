# On-Demand PO PDF Generation Design

**Date:** 2026-03-05
**Status:** Approved

## Problem

PO PDFs are written to `backend/generated_pos/` on the local filesystem. On Render (ephemeral storage), files are lost on every deploy. There is also no endpoint to serve them and no frontend UI to download them.

## Solution

Generate PDFs on-demand from the existing `PurchaseOrder` DB record. No file storage needed.

## Backend Changes

### New endpoint: `GET /api/orders/{po_number}/pdf`

- Located in `routers/orders.py`
- Looks up PurchaseOrder by `po_number`, joins Part and Supplier
- Calls a refactored `generate_po_pdf_bytes()` that returns `bytes` instead of writing to disk
- Returns `StreamingResponse` with `content-type: application/pdf`
- Protected by `get_current_user` (any authenticated role)
- Returns 404 if PO not found

### Refactor `ghost_writer.py`

- Remove `PO_OUTPUT_DIR` constant and filesystem writes
- `_generate_po_pdf()` returns `bytes` (via `pdf.output()` with no path)
- During simulations, Buyer agent logs "PDF available for download" but no file is created
- Expose a public `generate_po_pdf_bytes(po_dict)` function for the router to call

## Frontend Changes

### `api.ts`

- Add `downloadPOPdf(poNumber: string)` — fetches the endpoint with auth headers, returns a blob, triggers browser download

### `DBViewer.tsx`

- Pass `tableKey` prop to `DataTable`
- When `tableKey === "orders"`, render an extra "PDF" column with a download icon button (FileDown from lucide-react)
- On click, calls `api.downloadPOPdf(row.po_number)`

## What's NOT changing

- PurchaseOrder DB model — no new columns
- Simulation flow — Buyer agent still creates PO records, just skips file writes
- Other agents — unaffected
