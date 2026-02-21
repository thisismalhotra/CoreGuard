"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Flame, TrendingUp, XCircle } from "lucide-react";
import { api } from "@/lib/api";

type Scenario = {
  id: string;
  label: string;
  description: string;
  icon: typeof TrendingUp;
  color: string;
  action: () => Promise<unknown>;
};

export function GodMode({ onSimulationComplete }: { onSimulationComplete: () => void }) {
  const [running, setRunning] = useState<string | null>(null);

  const scenarios: Scenario[] = [
    {
      id: "spike",
      label: "300% Demand Spike",
      description: "Simulate 300% increase in FL-001-T demand. Triggers Aura → Core-Guard → Ghost-Writer chain.",
      icon: TrendingUp,
      color: "bg-yellow-600 hover:bg-yellow-500",
      action: () => api.simulateSpike("FL-001-T", 3.0),
    },
    {
      id: "shock",
      label: "Supplier Fire (AluForge)",
      description: "Simulate AluForge going offline. Disables CH-101 supply chain.",
      icon: Flame,
      color: "bg-red-600 hover:bg-red-500",
      action: () => api.simulateSupplyShock("AluForge"),
    },
    {
      id: "quality",
      label: "Quality Fail (CH-101)",
      description: "Simulate a batch of Chassis failing inspection at the dock.",
      icon: XCircle,
      color: "bg-orange-600 hover:bg-orange-500",
      action: async () => ({ status: "not_implemented", message: "Eagle-Eye agent coming soon" }),
    },
  ];

  const handleRun = async (scenario: Scenario) => {
    setRunning(scenario.id);
    try {
      await scenario.action();
      onSimulationComplete();
    } catch (err) {
      console.error("Simulation failed:", err);
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {scenarios.map((scenario) => {
        const Icon = scenario.icon;
        const isRunning = running === scenario.id;
        return (
          <Card key={scenario.id} className="bg-gray-900 border-gray-800">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base text-gray-100">
                <Icon className="h-5 w-5" />
                {scenario.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-gray-400 mb-4">{scenario.description}</p>
              <Button
                className={`w-full ${scenario.color} text-white`}
                onClick={() => handleRun(scenario)}
                disabled={running !== null}
              >
                {isRunning ? "Running..." : "Inject Chaos"}
              </Button>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
