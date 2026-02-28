"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DollarSign, ShieldCheck, TrendingUp, Users } from "lucide-react";
import { api, type PurchaseOrder } from "@/lib/api";

const TOOLTIP_STYLE = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "8px",
  color: "hsl(var(--foreground))",
};

const STATUS_COLORS: Record<string, string> = {
  APPROVED: "#22c55e",
  PENDING_APPROVAL: "#f59e0b",
  CANCELLED: "#ef4444",
  DRAFT: "#6b7280",
  SENT: "#3b82f6",
};

const RESULT_COLORS: Record<string, string> = {
  PASS: "#22c55e",
  FAIL: "#ef4444",
  PENDING: "#f59e0b",
};

const LOG_TYPE_COLORS: Record<string, string> = {
  info: "#3b82f6",
  warning: "#f59e0b",
  success: "#22c55e",
  error: "#ef4444",
};

type InspectionRow = { id: number; part: string | null; batch_size: number; result: string; notes: string | null; inspected_at: string | null };
type DemandRow = { id: number; part: string | null; forecast_qty: number; actual_qty: number; period: string | null };
type LogEntry = { timestamp: string; agent: string; message: string; type: string };

export function AnalyticsCharts() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [inspections, setInspections] = useState<InspectionRow[]>([]);
  const [demand, setDemand] = useState<DemandRow[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAll() {
      try {
        const [ord, insp, dem, lg] = await Promise.all([
          api.getOrders(),
          api.getDBTable("/api/db/quality_inspections") as Promise<InspectionRow[]>,
          api.getDBTable("/api/db/demand_forecast") as Promise<DemandRow[]>,
          api.getLogs(500),
        ]);
        setOrders(ord);
        setInspections(insp);
        setDemand(dem);
        setLogs(lg);
      } catch (err) {
        console.error("Failed to fetch analytics data:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchAll();
  }, []);

  if (loading) {
    return <div className="text-center text-muted-foreground py-8 animate-pulse">Loading analytics...</div>;
  }

  // --- PO Status Breakdown ---
  const statusCounts: Record<string, number> = {};
  for (const po of orders) {
    statusCounts[po.status] = (statusCounts[po.status] || 0) + 1;
  }
  const statusData = Object.entries(statusCounts).map(([name, value]) => ({ name, value }));

  // --- Spend by Supplier ---
  const spendBySupplier: Record<string, number> = {};
  for (const po of orders) {
    spendBySupplier[po.supplier] = (spendBySupplier[po.supplier] || 0) + po.total_cost;
  }
  const spendData = Object.entries(spendBySupplier)
    .map(([name, spend]) => ({ name, Spend: Math.round(spend * 100) / 100 }))
    .sort((a, b) => b.Spend - a.Spend)
    .slice(0, 10);

  // --- Quality Pass/Fail ---
  const resultCounts: Record<string, number> = {};
  for (const insp of inspections) {
    resultCounts[insp.result] = (resultCounts[insp.result] || 0) + 1;
  }
  const qualityData = Object.entries(resultCounts).map(([name, value]) => ({ name, value }));

  // --- Demand: Forecast vs Actual ---
  const demandData = demand
    .filter((d) => d.part && (d.forecast_qty > 0 || d.actual_qty > 0))
    .map((d) => ({
      name: d.part!,
      Forecast: d.forecast_qty,
      Actual: d.actual_qty,
    }));

  // --- Agent Activity ---
  const agentLogCounts: Record<string, Record<string, number>> = {};
  for (const log of logs) {
    if (!agentLogCounts[log.agent]) agentLogCounts[log.agent] = {};
    agentLogCounts[log.agent][log.type] = (agentLogCounts[log.agent][log.type] || 0) + 1;
  }
  const agentData = Object.entries(agentLogCounts).map(([agent, types]) => ({
    name: agent,
    ...types,
  }));
  const logTypes = [...new Set(logs.map((l) => l.type))];

  const hasOrders = orders.length > 0;
  const hasInspections = inspections.length > 0;
  const hasDemand = demandData.length > 0;
  const hasLogs = logs.length > 0;

  return (
    <div className="space-y-6 mt-6">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <TrendingUp className="h-4 w-4 text-blue-400" />
        <h3 className="text-sm font-semibold text-foreground">Operational Analytics</h3>
      </div>

      {/* Row 1: PO Status + Spend by Supplier */}
      {hasOrders && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-green-400" />
                PO Status Breakdown
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    dataKey="value"
                    label={({ name, value }) => `${name} (${value})`}
                    labelLine={false}
                  >
                    {statusData.map((entry) => (
                      <Cell key={entry.name} fill={STATUS_COLORS[entry.name] || "#6b7280"} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-amber-400" />
                Spend by Supplier
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={spendData} layout="vertical" margin={{ top: 5, right: 30, left: 80, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis type="number" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                  <YAxis dataKey="name" type="category" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} width={75} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value: number) => `$${value.toLocaleString()}`} />
                  <Bar dataKey="Spend" fill="#f59e0b" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Row 2: Quality + Demand */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {hasInspections && (
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-cyan-400" />
                Quality Pass/Fail Rate
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={qualityData}
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    dataKey="value"
                    label={({ name, value }) => `${name} (${value})`}
                    labelLine={false}
                  >
                    {qualityData.map((entry) => (
                      <Cell key={entry.name} fill={RESULT_COLORS[entry.name] || "#6b7280"} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {hasDemand && (
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-purple-400" />
                Forecast vs Actual Demand
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={demandData} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="name" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} />
                  <YAxis tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend />
                  <Bar dataKey="Forecast" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Actual" fill="#22c55e" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Row 3: Agent Activity */}
      {hasLogs && (
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Users className="h-4 w-4 text-indigo-400" />
              Agent Activity Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={agentData} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="name" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} />
                <YAxis tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Legend />
                {logTypes.map((type) => (
                  <Bar key={type} dataKey={type} stackId="a" fill={LOG_TYPE_COLORS[type] || "#6b7280"} radius={[2, 2, 0, 0]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
