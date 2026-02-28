"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Flame, TrendingUp, XCircle, CheckCircle, AlertCircle,
  Layers, DollarSign, WifiOff, RefreshCw, Zap,
  Activity, Ghost, GitMerge,
  FileText, Globe, Box, Shield, Cpu, Sun, Clock,
  ChevronDown, ChevronUp, Loader2,
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
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggleSection = (key: string) =>
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

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
      label: "Supplier Fire (CREE)",
      description: "CREE Inc. goes offline. Core-Guard identifies LED-201 impact, switches to alternate supplier, Ghost-Writer raises emergency PO.",
      icon: Flame,
      color: "bg-red-600 hover:bg-red-500",
      action: () => api.simulateSupplyShock("CREE Inc."),
    },
    {
      id: "quality",
      label: "Quality Fail (CH-231)",
      description: "Eagle-Eye detects hardness and dimension violations in incoming CH-231 Body Tube batch. Quarantines stock, triggers reorder.",
      icon: XCircle,
      color: "bg-orange-600 hover:bg-orange-500",
      action: () => api.simulateQualityFail("CH-231", 150),
    },
    {
      id: "cascade",
      label: "Cascade Failure",
      description: "500% demand spike hits simultaneously as CREE Inc. goes offline. Agents must coordinate reallocation AND alternate sourcing under compounding stress.",
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

  const partAgentScenarios: Scenario[] = [
    {
      id: "slow-bleed",
      label: "Slow Bleed",
      description: "Gradual burn rate increase with no external trigger. Part Agent is the ONLY agent that detects the silent drift toward stockout.",
      icon: Activity,
      color: "bg-teal-600 hover:bg-teal-500",
      action: () => api.simulateSlowBleed(),
    },
    {
      id: "inventory-decay",
      label: "Inventory Decay",
      description: "Part Agent initially reports all-clear, then Data Integrity reveals ghost and suspect stock hiding behind healthy numbers.",
      icon: Ghost,
      color: "bg-amber-600 hover:bg-amber-500",
      action: () => api.simulateInventoryDecay(),
    },
    {
      id: "multi-sku-contention",
      label: "Multi-SKU Contention",
      description: "FL-001-T and FL-001-S compete for shared CH-231 Body Tube. Part Agent detects contention, Core-Guard applies criticality-based prioritization.",
      icon: GitMerge,
      color: "bg-indigo-600 hover:bg-indigo-500",
      action: () => api.simulateMultiSkuContention(),
    },
  ];

  const supplyChainScenarios: Scenario[] = [
    {
      id: "contract-exhaustion",
      label: "Contract Exhaustion",
      description: "Blanket PO with CREE is 90% consumed. Ghost-Writer evaluates: extend contract, spot buy at premium, or renegotiate terms.",
      icon: FileText,
      color: "bg-rose-600 hover:bg-rose-500",
      action: () => api.simulateContractExhaustion(),
    },
    {
      id: "tariff-shock",
      label: "Tariff Shock",
      description: "25% tariff hits Chinese suppliers overnight. Core-Guard recalculates costs and evaluates switching to US/EU alternates.",
      icon: Globe,
      color: "bg-sky-600 hover:bg-sky-500",
      action: () => api.simulateTariffShock("CHINA", 25),
    },
    {
      id: "moq-trap",
      label: "MOQ Trap",
      description: "Need 80 LEDs but MOQ is 500. Ghost-Writer compares: buy excess and eat carry cost, or pay 15% small-lot premium.",
      icon: Box,
      color: "bg-lime-600 hover:bg-lime-500",
      action: () => api.simulateMoqTrap(),
    },
    {
      id: "military-surge",
      label: "Military Surge",
      description: "VIP military order doubles to 400 units with 21-day deadline. Core-Guard ring-fences inventory, displacing lower-priority orders.",
      icon: Shield,
      color: "bg-emerald-600 hover:bg-emerald-500",
      action: () => api.simulateMilitarySurge(),
    },
    {
      id: "semiconductor-allocation",
      label: "Semiconductor Allocation",
      description: "MCU-241 supplier announces 60% capacity cut for 26 weeks. System evaluates product mix prioritization by criticality.",
      icon: Cpu,
      color: "bg-cyan-600 hover:bg-cyan-500",
      action: () => api.simulateSemiconductorAllocation(),
    },
    {
      id: "seasonal-ramp",
      label: "Seasonal Ramp",
      description: "Peak season demand arrives 40% above forecast across all product lines. AURA detects deviation, Core-Guard pre-positions inventory.",
      icon: Sun,
      color: "bg-orange-500 hover:bg-orange-400",
      action: () => api.simulateSeasonalRamp(),
    },
  ];

  const demandHorizonScenarios: Scenario[] = [
    {
      id: "demand-horizon-z1",
      label: "Zone 1: Fuzzy Forecast",
      description: "Demand for CH-231 is 200+ days out. Aura monitors only — no PO generated. Cash preserved for nearer-term needs.",
      icon: Clock,
      color: "bg-blue-600 hover:bg-blue-500",
      action: () => api.simulateDemandHorizon("CH-231", 500, 200),
    },
    {
      id: "demand-horizon-z2",
      label: "Zone 2: Lead Time Horizon",
      description: "Demand for CH-231 in 90 days. Core-Guard explodes BOM, Ghost-Writer drafts standard PO to primary supplier.",
      icon: Clock,
      color: "bg-violet-600 hover:bg-violet-500",
      action: () => api.simulateDemandHorizon("CH-231", 500, 90),
    },
    {
      id: "demand-horizon-z3",
      label: "Zone 3: Drop-In Crisis",
      description: "Demand for CH-231 in 10 days — inside supplier lead time! Part Agent defends stock, Ghost-Writer pivots to secondary supplier.",
      icon: Clock,
      color: "bg-red-600 hover:bg-red-500",
      action: () => api.simulateDemandHorizon("CH-231", 500, 10),
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
      {/* First-run intro banner — shown until any scenario has been triggered */}
      {Object.keys(results).length === 0 && (
        <div className="flex items-start gap-3 bg-card border border-border rounded-lg px-4 py-3">
          <Zap className="h-4 w-4 text-yellow-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground">Ready to simulate</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Pick a scenario below and click{" "}
              <span className="font-medium text-foreground/80">Inject Chaos</span>.
              Logs will stream live in the{" "}
              <span className="font-medium text-blue-400">Live Logs</span> tab.
            </p>
          </div>
        </div>
      )}
      {/* Core Disruptions Section */}
      <div>
        <div
          className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm cursor-pointer flex items-center justify-between py-2"
          onClick={() => toggleSection("core")}
        >
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Flame className="h-4 w-4 text-red-400" />
              <h3 className="text-sm font-semibold text-foreground">Core Disruptions</h3>
            </div>
            <p className="text-xs text-muted-foreground">
              Demand spikes, supplier failures, and cascading disruption scenarios
            </p>
          </div>
          {collapsed["core"] ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        {!collapsed["core"] && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-3">
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
                      {isRunning ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Running...
                        </>
                      ) : (
                        "Inject Chaos"
                      )}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Part Agent Spotlight Section */}
      <div className="pt-4 border-t border-border">
        <div
          className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm cursor-pointer flex items-center justify-between py-2"
          onClick={() => toggleSection("partAgent")}
        >
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Activity className="h-4 w-4 text-teal-400" />
              <h3 className="text-sm font-semibold text-foreground">Part Agent Spotlight</h3>
            </div>
            <p className="text-xs text-muted-foreground">
              Scenarios where the Part Agent&apos;s autonomous monitoring drives the response
            </p>
          </div>
          {collapsed["partAgent"] ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        {!collapsed["partAgent"] && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-3">
            {partAgentScenarios.map((scenario) => {
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
                      {isRunning ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Running...
                        </>
                      ) : (
                        "Inject Chaos"
                      )}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Supply Chain Scenarios Section */}
      <div className="pt-4 border-t border-border">
        <div
          className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm cursor-pointer flex items-center justify-between py-2"
          onClick={() => toggleSection("supplyChain")}
        >
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Globe className="h-4 w-4 text-sky-400" />
              <h3 className="text-sm font-semibold text-foreground">Supply Chain Scenarios</h3>
            </div>
            <p className="text-xs text-muted-foreground">
              Contract, procurement, and geopolitical disruption scenarios
            </p>
          </div>
          {collapsed["supplyChain"] ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        {!collapsed["supplyChain"] && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-3">
            {supplyChainScenarios.map((scenario) => {
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
                      {isRunning ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Running...
                        </>
                      ) : (
                        "Inject Chaos"
                      )}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Demand Horizon Zones Section */}
      <div className="pt-4 border-t border-border">
        <div
          className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm cursor-pointer flex items-center justify-between py-2"
          onClick={() => toggleSection("demandHorizon")}
        >
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Clock className="h-4 w-4 text-violet-400" />
              <h3 className="text-sm font-semibold text-foreground">Demand Horizon Zones</h3>
            </div>
            <p className="text-xs text-muted-foreground">
              PRD &sect;10 &mdash; classify demand by time horizon to determine agent response
            </p>
          </div>
          {collapsed["demandHorizon"] ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        {!collapsed["demandHorizon"] && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-3">
            {demandHorizonScenarios.map((scenario) => {
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
                      {isRunning ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Running...
                        </>
                      ) : (
                        "Inject Chaos"
                      )}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
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
