"use client";

import { useEffect, useState, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Activity, Terminal, Shield, Zap, Database, Bot, AlertTriangle, HelpCircle, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { toast } from "sonner";
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
  const [reconnecting, setReconnecting] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("logs");
  const [integrityWarnings, setIntegrityWarnings] = useState<Array<{
    part_id: string; description: string; severity: string;
    issue: string; detail: string; action: string;
  }>>([]);

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
      api.getDataIntegrityWarnings().then(setIntegrityWarnings).catch(() => {});
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

    socket.on("connect", () => {
      setConnected((prev) => {
        // Only toast on reconnection (prev was true then disconnected, now reconnecting)
        if (prev === false) toast.success("Connected to server");
        return true;
      });
    });
    socket.on("disconnect", () => {
      setConnected(false);
      toast.error("Disconnected from server");
    });

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

    socket.on("agent_log", (log: AgentLog) => {
      // Cap at 1000 entries to prevent unbounded memory growth
      setLogs((prev) => [...prev, log].slice(-1000));
    });

    return () => {
      socket.off("agent_log");
      socket.off("connect");
      socket.off("disconnect");
      socket.io.off("reconnect_attempt");
      socket.io.off("reconnect");
      socket.io.off("reconnect_failed");
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
                  onClick={() => getSocket().connect()}
                >
                  Retry
                </Button>
              </>
            )}
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
        <div className="overflow-x-auto scrollbar-hide">
          <TabsList className="bg-card border border-border inline-flex w-max min-w-full">
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
        </div>

        <TabsContent value="status" className="mt-4">
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
          <InventoryCards items={inventory} />
        </TabsContent>

        <TabsContent value="analytics" className="mt-4">
          <InventoryCharts items={inventory} loading={!inventory.length && !backendError} />
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
