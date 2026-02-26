"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  RadialBarChart,
  RadialBar,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3, PieChart } from "lucide-react";
import type { InventoryItem } from "@/lib/api";

type Props = {
  items: InventoryItem[];
};

const COLORS = {
  on_hand: "#3b82f6",      // blue
  available: "#22c55e",     // green
  reserved: "#f59e0b",      // amber
  ring_fenced: "#ef4444",   // red
  safety_stock: "#8b5cf6",  // purple
};

/**
 * Inventory health score per part: available / safety_stock (capped at 1.0).
 * Green = healthy (>1.0), Yellow = caution (0.5-1.0), Red = critical (<0.5).
 */
function healthScore(item: InventoryItem): number {
  if (item.safety_stock === 0) return 1;
  return Math.min(item.available / item.safety_stock, 1.5);
}

function healthColor(score: number): string {
  if (score >= 1.0) return "#22c55e";
  if (score >= 0.5) return "#f59e0b";
  return "#ef4444";
}

export function InventoryCharts({ items }: Props) {
  if (items.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-12">
        No inventory data available. Start the backend server.
      </div>
    );
  }

  // --- Bar chart data: stock levels per component ---
  const barData = items
    .filter((i) => i.category === "Common Core")
    .map((item) => ({
      name: item.part_id,
      "On Hand": item.on_hand,
      "Available": item.available,
      "Reserved": item.reserved,
      "Ring-Fenced": item.ring_fenced,
      "Safety Stock": item.safety_stock,
    }));

  // --- Radial chart: per-part health score ---
  const healthData = items
    .filter((i) => i.category === "Common Core")
    .map((item) => {
      const score = healthScore(item);
      return {
        name: item.part_id,
        health: Math.round(score * 100),
        fill: healthColor(score),
      };
    });

  // --- Burn rate data ---
  const burnData = items
    .filter((i) => i.daily_burn_rate > 0)
    .map((item) => {
      const runway =
        item.daily_burn_rate > 0
          ? Math.round(item.on_hand / item.daily_burn_rate)
          : 999;
      return {
        name: item.part_id,
        "Burn Rate": item.daily_burn_rate,
        "Runway (days)": runway,
      };
    });

  return (
    <div className="space-y-6">
      {/* Stock Levels Bar Chart */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-blue-400" />
            Component Stock Levels
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="name"
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              />
              <YAxis tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  color: "hsl(var(--foreground))",
                }}
              />
              <Legend />
              <Bar dataKey="On Hand" fill={COLORS.on_hand} radius={[4, 4, 0, 0]} />
              <Bar dataKey="Available" fill={COLORS.available} radius={[4, 4, 0, 0]} />
              <Bar dataKey="Safety Stock" fill={COLORS.safety_stock} radius={[4, 4, 0, 0]} />
              <Bar dataKey="Reserved" fill={COLORS.reserved} radius={[4, 4, 0, 0]} />
              <Bar dataKey="Ring-Fenced" fill={COLORS.ring_fenced} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Part Health Radial Chart */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <PieChart className="h-4 w-4 text-green-400" />
              Component Health Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <RadialBarChart
                cx="50%"
                cy="50%"
                innerRadius="30%"
                outerRadius="90%"
                data={healthData}
                startAngle={180}
                endAngle={0}
              >
                <RadialBar
                  dataKey="health"
                  cornerRadius={6}
                  label={{ position: "insideStart", fill: "#fff", fontSize: 11 }}
                >
                  {healthData.map((entry, index) => (
                    <Cell key={index} fill={entry.fill} />
                  ))}
                </RadialBar>
                <Legend
                  formatter={(_, entry) => {
                    const item = healthData.find((d) => d.fill === entry?.color);
                    return item ? `${item.name} (${item.health}%)` : "";
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                    color: "hsl(var(--foreground))",
                  }}
                />
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-4 text-xs text-muted-foreground mt-2">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-green-500" /> Healthy (&ge;100%)
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-amber-500" /> Caution (50-99%)
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-red-500" /> Critical (&lt;50%)
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Burn Rate & Runway Chart */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-amber-400" />
              Daily Burn Rate &amp; Runway
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={burnData} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="name"
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                    color: "hsl(var(--foreground))",
                  }}
                />
                <Legend />
                <Bar
                  yAxisId="left"
                  dataKey="Burn Rate"
                  fill="#f59e0b"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  yAxisId="right"
                  dataKey="Runway (days)"
                  fill="#06b6d4"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
