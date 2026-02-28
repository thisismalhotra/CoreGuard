"use client";

import { useEffect, useState, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Activity, Terminal, Shield, Zap, Database, Bot, AlertTriangle, HelpCircle, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { getSocket, type AgentLog } from "@/lib/socket";
import { api, type InventoryItem, type KPIs } from "@/lib/api";
import { KPIPanel } from "./KPIPanel";
import { LiveLogs } from "./LiveLogs";
import { InventoryCards } from "./InventoryCards";
import { GodMode } from "./GodMode";
import { DigitalDock } from "./DigitalDock";
import { InventoryCharts } from "./InventoryCharts";
import { AnalyticsCharts } from "./AnalyticsCharts";
import { ThemeToggle } from "./ThemeToggle";
import { OnboardingModal } from "./OnboardingModal";

export function CommandCenter() {
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [kpis, setKPIs] = useState<KPIs | null>(null);
  const [connected, setConnected] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("logs");

  const refreshData = useCallback(async () => {
    try {
      const [inv, kpiData, logData] = await Promise.all([
        api.getInventory(),
        api.getKPIs(),
        api.getLogs(),
      ]);
      setBackendError(null);
      setInventory(inv);
      setKPIs(kpiData);
      // Merge persisted logs with live ones (deduplicate via timestamp+agent+message composite key)
      setLogs((prev) => {
        const existingKeys = new Set(
          prev.map((l) => `${l.timestamp}|${l.agent}|${l.message}`)
        );
        const newLogs = logData.filter(
          (l) => !existingKeys.has(`${l.timestamp}|${l.agent}|${l.message}`)
        ) as AgentLog[];
        // Cap at 1000 entries to prevent unbounded memory growth
        return [...newLogs, ...prev].slice(0, 1000);
      });
    } catch (err) {
      console.error("Failed to refresh data:", err);
      setBackendError("Backend unreachable. Is the server running on port 8000?");
    }
  }, []);

  useEffect(() => {
    // Initial data fetch on mount — calls setInventory/setKPIs/setLogs
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional init fetch
    refreshData();

    const socket = getSocket();
    socket.connect();

    socket.on("connect", () => setConnected(true));
    socket.on("disconnect", () => setConnected(false));

    socket.on("agent_log", (log: AgentLog) => {
      // Cap at 1000 entries to prevent unbounded memory growth
      setLogs((prev) => [...prev, log].slice(-1000));
    });

    return () => {
      socket.off("agent_log");
      socket.off("connect");
      socket.off("disconnect");
      socket.disconnect();
    };
  }, [refreshData]);

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <OnboardingModal />
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Core-Guard <span className="text-blue-400">Command Center</span>
          </h1>
          <p className="text-sm text-muted-foreground">
            Autonomous Supply Chain Operating System — FL-001
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/agents">
            <Button
              variant="outline"
              size="sm"
              className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5"
            >
              <Bot className="h-3.5 w-3.5" />
              Agents
            </Button>
          </Link>
          <Link href="/db">
            <Button
              variant="outline"
              size="sm"
              className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5"
            >
              <Database className="h-3.5 w-3.5" />
              DB Viewer
            </Button>
          </Link>
          <Link href="/onboarding">
            <Button
              variant="outline"
              size="sm"
              className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5"
            >
              <HelpCircle className="h-3.5 w-3.5" />
              Guide
            </Button>
          </Link>
          <ThemeToggle />
          <div className="flex items-center gap-2">
            <div
              className={`h-2.5 w-2.5 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-red-500"}`}
            />
            <span className="text-xs text-muted-foreground">
              {connected ? "Live" : "Disconnected"}
            </span>
          </div>
        </div>
      </div>

      {/* Error banner */}
      {backendError && (
        <div className="mb-4 flex items-center gap-3 bg-red-950/50 border border-red-700/50 rounded-lg px-4 py-3">
          <AlertTriangle className="h-5 w-5 text-red-400 shrink-0" />
          <span className="text-sm text-red-300">{backendError}</span>
          <Button
            variant="outline"
            size="sm"
            className="ml-auto border-red-700/50 text-red-300 hover:bg-red-950 text-xs"
            onClick={refreshData}
          >
            Retry
          </Button>
        </div>
      )}

      {/* KPIs */}
      <div className="mb-6">
        <KPIPanel kpis={kpis} />
      </div>

      {/* Tabbed Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-card border border-border">
          <TabsTrigger value="status" className="data-[state=active]:bg-muted gap-1.5">
            <Activity className="h-3.5 w-3.5" />
            Network Status
          </TabsTrigger>
          <TabsTrigger value="analytics" className="data-[state=active]:bg-muted gap-1.5">
            <BarChart3 className="h-3.5 w-3.5" />
            Analytics
          </TabsTrigger>
          <TabsTrigger value="logs" className="data-[state=active]:bg-muted gap-1.5">
            <Terminal className="h-3.5 w-3.5" />
            Live Logs
          </TabsTrigger>
          <TabsTrigger value="dock" className="data-[state=active]:bg-muted gap-1.5">
            <Shield className="h-3.5 w-3.5" />
            Digital Dock
          </TabsTrigger>
          <TabsTrigger value="godmode" className="data-[state=active]:bg-muted gap-1.5">
            <Zap className="h-3.5 w-3.5" />
            God Mode
          </TabsTrigger>
        </TabsList>

        <TabsContent value="status" className="mt-4">
          <InventoryCards items={inventory} />
        </TabsContent>

        <TabsContent value="analytics" className="mt-4">
          <InventoryCharts items={inventory} />
          <AnalyticsCharts />
        </TabsContent>

        <TabsContent value="logs" className="mt-4">
          <LiveLogs
            logs={logs}
            onClear={() => setLogs([])}
            onSwitchToGodMode={() => setActiveTab("godmode")}
          />
        </TabsContent>

        <TabsContent value="dock" className="mt-4">
          <DigitalDock />
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
