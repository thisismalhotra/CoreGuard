"use client";

import Link from "next/link";
import {
  ArrowLeft,
  Flame,
  TrendingUp,
  XCircle,
  Layers,
  DollarSign,
  WifiOff,
  Shield,
  BookOpen,
  Lightbulb,
  ChevronRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ThemeToggle } from "./ThemeToggle";

const AGENT_CHAIN = [
  {
    name: "Aura",
    role: "Demand Sensing",
    color: "bg-purple-600",
    description: "Monitors demand forecasts vs actual consumption. Fires when actual > forecast × 1.2.",
    rule: "Spike threshold: 20% above forecast",
  },
  {
    name: "Dispatcher",
    role: "Triage & Prioritization",
    color: "bg-cyan-600",
    description: "Receives shortage alerts from Aura. Scores each component by criticality, lead time sensitivity, and gap size. Sorts into a priority queue.",
    rule: "High-criticality parts always processed first",
  },
  {
    name: "Core-Guard",
    role: "MRP Logic",
    color: "bg-blue-600",
    description: "Performs BOM explosion and net requirement calculations in pure Python. Decides whether to REALLOCATE from substitutes or BUY new stock.",
    rule: "All arithmetic is Python — never delegated to an LLM",
  },
  {
    name: "Ghost-Writer",
    role: "Procurement & PO Generation",
    color: "bg-emerald-600",
    description: "Creates Purchase Orders in the database and generates PDF documents. Enforces the Financial Constitution before any PO is issued.",
    rule: "Hard block: total_cost > $5,000 → PENDING_APPROVAL",
  },
  {
    name: "Eagle-Eye",
    role: "Quality Inspection",
    color: "bg-orange-600",
    description: "Validates incoming shipment batches against CAD spec tolerances (hardness, dimensions). Quarantines failed batches and triggers emergency reorders.",
    rule: "FAIL result → stock quarantined + Core-Guard reorder triggered",
  },
];

const SCENARIOS = [
  {
    id: "spike",
    label: "300% Demand Spike",
    icon: TrendingUp,
    color: "text-yellow-400",
    description: "Aura detects 3× demand surge on FL-001-T.",
    observe: "Watch Core-Guard decide between reallocation and new PO. Check if Ghost-Writer splits the order to stay under the $5k constitution.",
  },
  {
    id: "shock",
    label: "Supplier Fire (AluForge)",
    icon: Flame,
    color: "text-red-400",
    description: "AluForge goes offline — primary CH-101 supplier is unavailable.",
    observe: "Watch Core-Guard select an alternate supplier. See Dispatcher re-score priorities with elevated lead time.",
  },
  {
    id: "quality",
    label: "Quality Fail (CH-101)",
    icon: XCircle,
    color: "text-orange-400",
    description: "Eagle-Eye detects spec violations in an incoming CH-101 batch.",
    observe: "Batch is quarantined in Digital Dock. Core-Guard fires an emergency reorder. Check the Quality Inspections tab.",
  },
  {
    id: "cascade",
    label: "Cascade Failure",
    icon: Layers,
    color: "text-purple-400",
    description: "500% demand spike hits while AluForge is simultaneously offline.",
    observe: "Highest-stress scenario — watch all 5 agents fire in sequence under compounding pressure.",
  },
  {
    id: "constitution",
    label: "Constitution Breach",
    icon: DollarSign,
    color: "text-pink-400",
    description: "800% spike forces a PO that exceeds the $5,000 guardrail.",
    observe: "Ghost-Writer sets status to PENDING_APPROVAL. Navigate to Digital Dock → Purchase Orders to approve or reject it.",
  },
  {
    id: "blackout",
    label: "Full Blackout",
    icon: WifiOff,
    color: "text-gray-400",
    description: "ALL suppliers go offline simultaneously.",
    observe: "Core-Guard exhausts every option. A CRITICAL escalation alert is emitted. No PO can be issued.",
  },
];

const LOG_TYPES = [
  { type: "info", color: "text-blue-400", example: "MRP calculation started for CH-101" },
  { type: "warning", color: "text-yellow-400", example: "Inventory below safety stock threshold" },
  { type: "success", color: "text-green-400", example: "PO-2024-001 issued to AluForge" },
  { type: "error", color: "text-red-400", example: "All suppliers offline — escalating to COO" },
];

const TIPS = [
  { icon: "↺", text: "Use Reset Simulation in God Mode to restore the database to its seed state between scenarios." },
  { icon: "🗄", text: "Open the DB Viewer to inspect raw table data — see PurchaseOrder status, inventory levels, and agent logs persisted in SQLite." },
  { icon: "🤖", text: "The Agents page shows each agent's role, rules, and data flow — useful context before running a scenario." },
  { icon: "📄", text: "Ghost-Writer generates real PDF purchase orders in backend/generated_pos/ after each simulation." },
];

export function OnboardingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Dashboard
          </Link>
          <div className="h-4 w-px bg-border" />
          <div>
            <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-blue-400" />
              Core-Guard User Guide
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              How the Glass Box simulation works
            </p>
          </div>
        </div>
        <ThemeToggle />
      </div>

      <div className="space-y-10">
        {/* Section 1: Agent Chain */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <ChevronRight className="h-4 w-4 text-blue-400" />
            <h2 className="text-base font-semibold">The Agent Chain</h2>
          </div>
          <p className="text-sm text-muted-foreground mb-4">
            When a disruption occurs, agents fire in sequence. Each agent logs every decision to
            the <span className="text-foreground font-medium">Live Logs</span> terminal in real-time
            — nothing happens behind the scenes.
          </p>

          {/* Pipeline visual */}
          <div className="flex flex-col gap-3">
            {AGENT_CHAIN.map((agent, i) => (
              <div key={agent.name} className="flex gap-4">
                {/* Step indicator */}
                <div className="flex flex-col items-center">
                  <div className="flex items-center justify-center w-6 h-6 rounded-full bg-muted text-xs font-mono text-muted-foreground shrink-0">
                    {i + 1}
                  </div>
                  {i < AGENT_CHAIN.length - 1 && (
                    <div className="w-px flex-1 bg-border mt-1" />
                  )}
                </div>
                {/* Agent card */}
                <Card className="bg-card border-border flex-1 mb-1">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge className={`${agent.color} text-white text-xs`}>
                        {agent.name}
                      </Badge>
                      <span className="text-xs text-muted-foreground">{agent.role}</span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed mb-2">
                      {agent.description}
                    </p>
                    <p className="text-xs font-mono bg-muted/50 rounded px-2 py-1 text-foreground/60">
                      Rule: {agent.rule}
                    </p>
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>
        </section>

        {/* Section 2: Simulation Scenarios */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <ChevronRight className="h-4 w-4 text-yellow-400" />
            <h2 className="text-base font-semibold">God Mode Scenarios</h2>
          </div>
          <p className="text-sm text-muted-foreground mb-4">
            Six chaos scenarios to inject. Each triggers a different agent chain path. After clicking
            <span className="font-medium text-foreground"> Inject Chaos</span>, the view switches
            automatically to Live Logs.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {SCENARIOS.map((scenario) => {
              const Icon = scenario.icon;
              return (
                <Card key={scenario.id} className="bg-card border-border">
                  <CardHeader className="pb-2 pt-4">
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <Icon className={`h-4 w-4 shrink-0 ${scenario.color}`} />
                      {scenario.label}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pb-4 space-y-2">
                    <p className="text-xs text-muted-foreground">{scenario.description}</p>
                    <div className="bg-muted/40 rounded px-2.5 py-1.5">
                      <p className="text-xs text-muted-foreground">
                        <span className="font-medium text-foreground/70">Watch for: </span>
                        {scenario.observe}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>

        {/* Section 3: Financial Constitution */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <ChevronRight className="h-4 w-4 text-pink-400" />
            <h2 className="text-base font-semibold">The Financial Constitution</h2>
          </div>
          <div className="bg-card border border-border rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-pink-400 shrink-0" />
              <p className="text-sm font-medium">
                Any PO exceeding <span className="text-pink-400">$5,000</span> is hard-blocked.
              </p>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              This rule is hard-coded in <span className="font-mono text-xs bg-muted px-1 py-0.5 rounded">ghost_writer.py</span>.
              No LLM prompt or agent instruction can override it. When triggered, Ghost-Writer sets the
              PO status to <span className="font-mono text-xs bg-muted px-1 py-0.5 rounded">PENDING_APPROVAL</span> and
              emits a warning log.
            </p>
            <div className="border-t border-border pt-3 space-y-1.5">
              <p className="text-xs font-medium text-foreground/80">To review a blocked PO:</p>
              <ol className="list-decimal list-inside text-xs text-muted-foreground space-y-1">
                <li>Go to the <span className="text-foreground font-medium">Digital Dock</span> tab</li>
                <li>Click <span className="font-medium text-foreground/80">Purchase Orders</span></li>
                <li>Expand the PENDING_APPROVAL order</li>
                <li>Click <span className="text-green-400 font-medium">Approve</span> or <span className="text-red-400 font-medium">Reject</span></li>
              </ol>
            </div>
          </div>
        </section>

        {/* Section 4: Reading the Logs */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <ChevronRight className="h-4 w-4 text-green-400" />
            <h2 className="text-base font-semibold">Reading the Live Logs</h2>
          </div>
          <p className="text-sm text-muted-foreground mb-4">
            Every log entry has three parts: a timestamp, a colored agent badge, and a message.
            Message color indicates severity.
          </p>
          <div className="bg-background border border-border rounded-lg p-4 font-mono text-sm space-y-2 mb-4">
            {LOG_TYPES.map((lt) => (
              <div key={lt.type} className="flex items-start gap-3">
                <span className="text-muted-foreground/60 w-[72px] shrink-0 text-xs">12:34:56</span>
                <Badge className="bg-blue-600 text-white text-[10px] w-[90px] justify-center shrink-0">
                  Core-Guard
                </Badge>
                <span className={`text-xs ${lt.color}`}>{lt.example}</span>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-3">
            {LOG_TYPES.map((lt) => (
              <div key={lt.type} className="flex items-center gap-1.5">
                <div className={`w-2 h-2 rounded-full ${lt.color.replace("text-", "bg-")}`} />
                <span className={`text-xs font-medium ${lt.color}`}>{lt.type}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Section 5: Tips */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-base font-semibold">Tips</h2>
          </div>
          <div className="space-y-2">
            {TIPS.map((tip, i) => (
              <div
                key={i}
                className="flex items-start gap-3 bg-card border border-border rounded-lg px-4 py-3"
              >
                <Lightbulb className="h-3.5 w-3.5 text-yellow-400 shrink-0 mt-0.5" />
                <p className="text-xs text-muted-foreground leading-relaxed">{tip.text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Footer nav */}
        <div className="flex items-center justify-between pt-4 border-t border-border">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Dashboard
          </Link>
          <div className="flex items-center gap-3">
            <Link href="/agents" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
              Agent Registry →
            </Link>
            <Link href="/db" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
              DB Viewer →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
