"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Flame, TrendingUp, XCircle, CheckCircle, AlertCircle,
  Layers, DollarSign, WifiOff, RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";

type ScenarioResult = {
  status: "idle" | "running" | "success" | "error";
  message?: string;
};

type Scenario = {
  id: string;
  label: string;
  description: string;
  icon: typeof TrendingUp;
  color: string;
  buttonLabel?: string;
  action: () => Promise<unknown>;
};

export function GodMode({
  onSimulationComplete,
  onSwitchToLogs,
}: {
  onSimulationComplete: () => void;
  onSwitchToLogs?: () => void;
}) {
  const [results, setResults] = useState<Record<string, ScenarioResult>>({});

  const scenarios: Scenario[] = [
    {
      id: "spike",
      label: "300% Demand Spike",
      description: "Aura detects 3x demand surge on FL-001-T. Core-Guard runs MRP, reallocates from FL-001-S, Ghost-Writer issues POs.",
      icon: TrendingUp,
      color: "bg-yellow-600 hover:bg-yellow-500",
      action: () => api.simulateSpike("FL-001-T", 3.0),
    },
    {
      id: "shock",
      label: "Supplier Fire (AluForge)",
      description: "AluForge goes offline. Core-Guard identifies CH-101 impact, switches to alternate supplier, Ghost-Writer raises emergency PO.",
      icon: Flame,
      color: "bg-red-600 hover:bg-red-500",
      action: () => api.simulateSupplyShock("AluForge"),
    },
    {
      id: "quality",
      label: "Quality Fail (CH-101)",
      description: "Eagle-Eye detects hardness and dimension violations in incoming CH-101 batch. Quarantines stock, triggers reorder.",
      icon: XCircle,
      color: "bg-orange-600 hover:bg-orange-500",
      action: () => api.simulateQualityFail("CH-101", 150),
    },
    {
      id: "cascade",
      label: "Cascade Failure",
      description: "500% demand spike hits simultaneously as AluForge goes offline. Agents must coordinate reallocation AND alternate sourcing under compounding stress.",
      icon: Layers,
      color: "bg-purple-600 hover:bg-purple-500",
      action: () => api.simulateCascadeFailure(),
    },
    {
      id: "constitution",
      label: "Constitution Breach",
      description: "800% spike forces a PO exceeding the $5,000 financial guardrail. Ghost-Writer blocks it with PENDING_APPROVAL — the LLM cannot override.",
      icon: DollarSign,
      color: "bg-pink-600 hover:bg-pink-500",
      action: () => api.simulateConstitutionBreach(),
    },
    {
      id: "blackout",
      label: "Full Blackout",
      description: "ALL suppliers go offline simultaneously. Core-Guard exhausts every procurement option and escalates a CRITICAL alert to the COO.",
      icon: WifiOff,
      color: "bg-gray-600 hover:bg-gray-500",
      action: () => api.simulateFullBlackout(),
    },
  ];

  const isAnyRunning = Object.values(results).some((r) => r.status === "running");
  const [resetting, setResetting] = useState(false);

  const handleRun = async (scenario: Scenario) => {
    setResults((prev) => ({ ...prev, [scenario.id]: { status: "running" } }));

    // Switch to Live Logs immediately so the user sees logs stream in
    if (onSwitchToLogs) onSwitchToLogs();

    try {
      await scenario.action();
      setResults((prev) => ({ ...prev, [scenario.id]: { status: "success", message: "Complete" } }));
      onSimulationComplete();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setResults((prev) => ({ ...prev, [scenario.id]: { status: "error", message: msg } }));
      console.error("Simulation failed:", err);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      await api.resetSimulation();
      setResults({});
      onSimulationComplete();
    } catch (err) {
      console.error("Reset failed:", err);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {scenarios.map((scenario) => {
          const Icon = scenario.icon;
          const result = results[scenario.id];
          const isRunning = result?.status === "running";

          return (
            <Card key={scenario.id} className="bg-card border-border flex flex-col">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Icon className="h-4 w-4 shrink-0" />
                  {scenario.label}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col flex-1 justify-between">
                <p className="text-xs text-muted-foreground mb-4 leading-relaxed">{scenario.description}</p>

                {result?.status === "success" && (
                  <div className="flex items-center gap-1.5 mb-2">
                    <CheckCircle className="h-3.5 w-3.5 text-green-400 shrink-0" />
                    <span className="text-xs text-green-400">{result.message}</span>
                  </div>
                )}
                {result?.status === "error" && (
                  <div className="flex items-center gap-1.5 mb-2">
                    <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                    <span className="text-xs text-red-400">{result.message}</span>
                  </div>
                )}

                <Button
                  className={`w-full ${scenario.color} text-white text-xs`}
                  onClick={() => handleRun(scenario)}
                  disabled={isAnyRunning || resetting}
                >
                  {isRunning ? "Running..." : "Inject Chaos"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Reset Button */}
      <div className="flex justify-end pt-2 border-t border-border">
        <Button
          variant="outline"
          className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-2 text-xs"
          onClick={handleReset}
          disabled={isAnyRunning || resetting}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${resetting ? "animate-spin" : ""}`} />
          {resetting ? "Resetting..." : "Reset Simulation"}
        </Button>
      </div>
    </div>
  );
}
