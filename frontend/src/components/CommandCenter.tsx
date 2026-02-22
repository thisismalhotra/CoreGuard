"use client";

import { useEffect, useState, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Activity, Terminal, Shield, Zap, Database, Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { getSocket, type AgentLog } from "@/lib/socket";
import { api, type InventoryItem, type KPIs } from "@/lib/api";
import { KPIPanel } from "./KPIPanel";
import { LiveLogs } from "./LiveLogs";
import { InventoryCards } from "./InventoryCards";
import { GodMode } from "./GodMode";

export function CommandCenter() {
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [kpis, setKPIs] = useState<KPIs | null>(null);
  const [connected, setConnected] = useState(false);
  const [activeTab, setActiveTab] = useState("logs");

  const refreshData = useCallback(async () => {
    try {
      const [inv, kpiData, logData] = await Promise.all([
        api.getInventory(),
        api.getKPIs(),
        api.getLogs(),
      ]);
      setInventory(inv);
      setKPIs(kpiData);
      // Merge persisted logs with live ones (avoid duplicates via message check)
      setLogs((prev) => {
        const existingMessages = new Set(prev.map((l) => l.message));
        const newLogs = logData.filter(
          (l) => !existingMessages.has(l.message)
        ) as AgentLog[];
        return [...newLogs, ...prev];
      });
    } catch (err) {
      console.error("Failed to refresh data:", err);
    }
  }, []);

  useEffect(() => {
    refreshData();

    const socket = getSocket();
    socket.connect();

    socket.on("connect", () => setConnected(true));
    socket.on("disconnect", () => setConnected(false));

    socket.on("agent_log", (log: AgentLog) => {
      setLogs((prev) => [...prev, log]);
    });

    return () => {
      socket.off("agent_log");
      socket.off("connect");
      socket.off("disconnect");
      socket.disconnect();
    };
  }, [refreshData]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Core-Guard <span className="text-blue-400">Command Center</span>
          </h1>
          <p className="text-sm text-gray-500">
            Autonomous Supply Chain Operating System — FL-001
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/agents">
            <Button
              variant="outline"
              size="sm"
              className="border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 gap-1.5"
            >
              <Bot className="h-3.5 w-3.5" />
              Agents
            </Button>
          </Link>
          <Link href="/db">
            <Button
              variant="outline"
              size="sm"
              className="border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 gap-1.5"
            >
              <Database className="h-3.5 w-3.5" />
              DB Viewer
            </Button>
          </Link>
          <div className="flex items-center gap-2">
            <div
              className={`h-2.5 w-2.5 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-red-500"}`}
            />
            <span className="text-xs text-gray-400">
              {connected ? "Live" : "Disconnected"}
            </span>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="mb-6">
        <KPIPanel kpis={kpis} />
      </div>

      {/* Tabbed Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-900 border border-gray-800">
          <TabsTrigger value="status" className="data-[state=active]:bg-gray-800 gap-1.5">
            <Activity className="h-3.5 w-3.5" />
            Network Status
          </TabsTrigger>
          <TabsTrigger value="logs" className="data-[state=active]:bg-gray-800 gap-1.5">
            <Terminal className="h-3.5 w-3.5" />
            Live Logs
          </TabsTrigger>
          <TabsTrigger value="dock" className="data-[state=active]:bg-gray-800 gap-1.5">
            <Shield className="h-3.5 w-3.5" />
            Digital Dock
          </TabsTrigger>
          <TabsTrigger value="godmode" className="data-[state=active]:bg-gray-800 gap-1.5">
            <Zap className="h-3.5 w-3.5" />
            God Mode
          </TabsTrigger>
        </TabsList>

        <TabsContent value="status" className="mt-4">
          <InventoryCards items={inventory} />
        </TabsContent>

        <TabsContent value="logs" className="mt-4">
          <LiveLogs logs={logs} onClear={() => setLogs([])} />
        </TabsContent>

        <TabsContent value="dock" className="mt-4">
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-8 text-center">
            <Shield className="h-12 w-12 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-400">
              Eagle-Eye Quality Agent — coming in next iteration.
            </p>
          </div>
        </TabsContent>

        <TabsContent value="godmode" className="mt-4">
          <GodMode
            onSimulationComplete={refreshData}
            onSwitchToLogs={() => setActiveTab("logs")}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
