"use client";

import { useEffect, useState, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Database, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";
import { api } from "@/lib/api";

const TABLES = [
  { key: "suppliers", label: "Suppliers", endpoint: "/api/db/suppliers" },
  { key: "parts", label: "Parts", endpoint: "/api/db/parts" },
  { key: "inventory", label: "Inventory", endpoint: "/api/db/inventory" },
  { key: "bom", label: "BOM", endpoint: "/api/db/bom" },
  { key: "orders", label: "Purchase Orders", endpoint: "/api/db/orders" },
  { key: "demand", label: "Demand Forecast", endpoint: "/api/db/demand_forecast" },
  { key: "quality", label: "Quality Inspections", endpoint: "/api/db/quality_inspections" },
  { key: "sales_orders", label: "Sales Orders", endpoint: "/api/db/sales_orders" },
  { key: "contracts", label: "Contracts", endpoint: "/api/db/supplier_contracts" },
  { key: "releases", label: "Releases", endpoint: "/api/db/scheduled_releases" },
  { key: "alt_suppliers", label: "Alt Suppliers", endpoint: "/api/db/alternate_suppliers" },
  { key: "ring_fence", label: "Ring Fence Audit", endpoint: "/api/db/ring_fence_audit" },
  { key: "inv_health", label: "Inventory Health", endpoint: "/api/db/inventory_health" },
  { key: "logs", label: "Agent Logs", endpoint: "/api/db/agent_logs" },
] as const;

type TableKey = (typeof TABLES)[number]["key"];

// Status badge colors for purchase orders
function statusColor(status: string): string {
  switch (status) {
    case "APPROVED": return "bg-green-600";
    case "PENDING_APPROVAL": return "bg-yellow-600";
    case "DRAFT": return "bg-gray-600";
    case "SENT": return "bg-blue-600";
    case "CANCELLED": return "bg-red-600";
    default: return "bg-gray-600";
  }
}

function inspectionColor(result: string): string {
  switch (result) {
    case "PASS": return "bg-green-600";
    case "FAIL": return "bg-red-600";
    case "PENDING": return "bg-yellow-600";
    default: return "bg-gray-600";
  }
}

function priorityColor(priority: string): string {
  switch (priority) {
    case "VIP": return "bg-red-600";
    case "EXPEDITED": return "bg-yellow-600";
    case "NORMAL": return "bg-gray-600";
    default: return "bg-gray-600";
  }
}

function flagColor(flag: string): string {
  switch (flag) {
    case "GHOST": return "bg-red-600";
    case "SUSPECT": return "bg-yellow-600";
    case "NORMAL": return "bg-green-600";
    default: return "bg-gray-600";
  }
}

function actionColor(action: string): string {
  switch (action) {
    case "BLOCKED": return "bg-red-600";
    case "APPROVED": return "bg-green-600";
    case "RING_FENCED": return "bg-blue-600";
    default: return "bg-gray-600";
  }
}

function contractTypeColor(type: string): string {
  switch (type) {
    case "BLANKET_PO": return "bg-blue-600";
    case "SPOT_BUY": return "bg-yellow-600";
    case "CONSIGNMENT": return "bg-purple-600";
    case "FRAMEWORK": return "bg-teal-600";
    default: return "bg-gray-600";
  }
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No records found.
      </div>
    );
  }

  const columns = Object.keys(rows[0]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={col}
                className="text-left px-3 py-2 text-muted-foreground font-medium text-xs uppercase tracking-wider whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="border-b border-border/50 hover:bg-muted/30 transition-colors"
            >
              {columns.map((col) => {
                const val = row[col];
                let content: React.ReactNode;

                // Render badges for status-like fields
                if (col === "status" && typeof val === "string") {
                  content = (
                    <Badge className={`${statusColor(val)} text-white text-[10px]`}>
                      {val}
                    </Badge>
                  );
                } else if (col === "result" && typeof val === "string") {
                  content = (
                    <Badge className={`${inspectionColor(val)} text-white text-[10px]`}>
                      {val}
                    </Badge>
                  );
                } else if (col === "priority" && typeof val === "string") {
                  content = (
                    <Badge className={`${priorityColor(val)} text-white text-[10px]`}>
                      {val}
                    </Badge>
                  );
                } else if (col === "flag" && typeof val === "string") {
                  content = (
                    <Badge className={`${flagColor(val)} text-white text-[10px]`}>
                      {val}
                    </Badge>
                  );
                } else if (col === "action" && typeof val === "string") {
                  content = (
                    <Badge className={`${actionColor(val)} text-white text-[10px]`}>
                      {val}
                    </Badge>
                  );
                } else if (col === "contract_type" && typeof val === "string") {
                  content = (
                    <Badge className={`${contractTypeColor(val)} text-white text-[10px]`}>
                      {val}
                    </Badge>
                  );
                } else if (col === "tier" && typeof val === "string") {
                  content = (
                    <Badge className="bg-indigo-600 text-white text-[10px]">
                      {val}
                    </Badge>
                  );
                } else if (col === "region" && typeof val === "string") {
                  content = (
                    <Badge className="bg-sky-600 text-white text-[10px]">
                      {val}
                    </Badge>
                  );
                } else if (col === "is_active") {
                  content = (
                    <span className={val ? "text-green-400" : "text-red-400"}>
                      {val ? "Active" : "Offline"}
                    </span>
                  );
                } else if (col === "reliability_score" && typeof val === "number") {
                  content = (
                    <span className={val >= 0.9 ? "text-green-400" : val >= 0.7 ? "text-yellow-400" : "text-red-400"}>
                      {(val * 100).toFixed(0)}%
                    </span>
                  );
                } else if (typeof val === "boolean") {
                  content = val ? "Yes" : "No";
                } else if (val === null || val === undefined) {
                  content = <span className="text-muted-foreground/60">—</span>;
                } else if (typeof val === "string" && val.includes("T") && val.includes(":")) {
                  // ISO timestamp — format nicely
                  try {
                    content = new Date(val).toLocaleString();
                  } catch {
                    content = String(val);
                  }
                } else {
                  content = String(val);
                }

                return (
                  <td key={col} className="px-3 py-2 text-foreground/80 whitespace-nowrap max-w-[400px] truncate">
                    {content}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DBViewer() {
  const [activeTable, setActiveTable] = useState<TableKey>("suppliers");
  const [data, setData] = useState<Record<TableKey, Record<string, unknown>[]>>(
    {} as Record<TableKey, Record<string, unknown>[]>
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTable = useCallback(async (key: TableKey) => {
    const table = TABLES.find((t) => t.key === key);
    if (!table) return;

    setLoading(true);
    setError(null);
    try {
      const rows = await api.getDBTable(table.endpoint);
      setData((prev) => ({ ...prev, [key]: rows }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch active table on mount and tab change
  useEffect(() => {
    fetchTable(activeTable);
  }, [activeTable, fetchTable]);

  const rows = data[activeTable] || [];

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link href="/">
            <Button
              variant="outline"
              size="sm"
              className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Dashboard
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Database className="h-6 w-6 text-blue-400" />
              DB Viewer
            </h1>
            <p className="text-sm text-muted-foreground">
              Raw SQLite tables — Core-Guard Supply Chain Dataset
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {rows.length} {rows.length === 1 ? "row" : "rows"}
          </span>
          <ThemeToggle />
          <Button
            variant="outline"
            size="sm"
            className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5"
            onClick={() => fetchTable(activeTable)}
            disabled={loading}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Table Tabs */}
      <Tabs value={activeTable} onValueChange={(v) => setActiveTable(v as TableKey)} className="w-full">
        <TabsList className="bg-card border border-border flex-wrap h-auto gap-1 p-1">
          {TABLES.map((t) => (
            <TabsTrigger
              key={t.key}
              value={t.key}
              className="data-[state=active]:bg-muted text-xs"
            >
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {TABLES.map((t) => (
          <TabsContent key={t.key} value={t.key} className="mt-4">
            <div className="bg-card rounded-lg border border-border overflow-hidden">
              {error ? (
                <div className="p-8 text-center text-red-400">
                  Error: {error}
                </div>
              ) : loading ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">
                  Loading {t.label}...
                </div>
              ) : (
                <DataTable rows={(data[t.key] || []) as Record<string, unknown>[]} />
              )}
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
