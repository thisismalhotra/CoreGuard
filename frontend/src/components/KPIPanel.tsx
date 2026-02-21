"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Activity, Box, Cpu, Zap } from "lucide-react";
import type { KPIs } from "@/lib/api";

const KPI_CARDS = [
  {
    key: "inventory_health" as const,
    label: "Inventory Health",
    icon: Box,
    format: (v: number) => `${v}x`,
    color: "text-green-400",
  },
  {
    key: "active_threads" as const,
    label: "Active Agents",
    icon: Cpu,
    format: (v: number) => `${v}`,
    color: "text-blue-400",
  },
  {
    key: "automation_rate" as const,
    label: "Automation Rate",
    icon: Zap,
    format: (v: number) => `${v}%`,
    color: "text-purple-400",
  },
  {
    key: "total_orders" as const,
    label: "Total POs",
    icon: Activity,
    format: (v: number) => `${v}`,
    color: "text-orange-400",
  },
];

export function KPIPanel({ kpis }: { kpis: KPIs | null }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {KPI_CARDS.map(({ key, label, icon: Icon, format, color }) => (
        <Card key={key} className="bg-gray-900 border-gray-800">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-3">
              <Icon className={`h-8 w-8 ${color}`} />
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-wider">{label}</p>
                <p className={`text-2xl font-bold font-mono ${color}`}>
                  {kpis ? format(kpis[key]) : "—"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
