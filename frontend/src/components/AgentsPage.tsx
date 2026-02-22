"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  Bot,
  Radio,
  Shield,
  FileText,
  Eye,
  GitBranch,
  ArrowRight,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const ICON_MAP: Record<string, React.ReactNode> = {
  Radio: <Radio className="h-6 w-6" />,
  GitBranch: <GitBranch className="h-6 w-6" />,
  Shield: <Shield className="h-6 w-6" />,
  FileText: <FileText className="h-6 w-6" />,
  Eye: <Eye className="h-6 w-6" />,
};

const COLOR_MAP: Record<string, { bg: string; border: string; badge: string; text: string }> = {
  purple: { bg: "bg-purple-950/30", border: "border-purple-800/50", badge: "bg-purple-600", text: "text-purple-400" },
  cyan: { bg: "bg-cyan-950/30", border: "border-cyan-800/50", badge: "bg-cyan-600", text: "text-cyan-400" },
  blue: { bg: "bg-blue-950/30", border: "border-blue-800/50", badge: "bg-blue-600", text: "text-blue-400" },
  emerald: { bg: "bg-emerald-950/30", border: "border-emerald-800/50", badge: "bg-emerald-600", text: "text-emerald-400" },
  orange: { bg: "bg-orange-950/30", border: "border-orange-800/50", badge: "bg-orange-600", text: "text-orange-400" },
};

type Agent = {
  name: string;
  role: string;
  description: string;
  trigger: string;
  inputs: string[];
  outputs: string[];
  downstream: string | null;
  constitution: string | null;
  rules: string[];
  color: string;
  icon: string;
  source_file: string;
};

function AgentCard({ agent, isExpanded, onToggle }: { agent: Agent; isExpanded: boolean; onToggle: () => void }) {
  const colors = COLOR_MAP[agent.color] || COLOR_MAP.blue;

  return (
    <div className={`rounded-lg border ${colors.border} ${colors.bg} overflow-hidden transition-all`}>
      {/* Header — always visible */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-5 text-left hover:bg-foreground/5 transition-colors"
      >
        <div className="flex items-center gap-4">
          <div className={`${colors.badge} p-3 rounded-lg text-white`}>
            {ICON_MAP[agent.icon] || <Bot className="h-6 w-6" />}
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              {agent.name}
              <Badge className={`${colors.badge} text-white text-[10px] font-normal`}>
                {agent.role}
              </Badge>
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">{agent.description}</p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-5 w-5 text-muted-foreground shrink-0" />
        ) : (
          <ChevronDown className="h-5 w-5 text-muted-foreground shrink-0" />
        )}
      </button>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-5 pb-5 space-y-4 border-t border-border/50 pt-4">
          {/* Constitution block */}
          {agent.constitution && (
            <div className="bg-yellow-950/40 border border-yellow-700/50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-4 w-4 text-yellow-500" />
                <span className="text-sm font-semibold text-yellow-400">Financial Constitution</span>
              </div>
              <p className="text-sm text-yellow-200/80">{agent.constitution}</p>
            </div>
          )}

          {/* Trigger */}
          <div>
            <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Trigger</h3>
            <p className="text-sm text-foreground/80">{agent.trigger}</p>
          </div>

          {/* Inputs & Outputs side by side */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Inputs</h3>
              <ul className="space-y-1">
                {agent.inputs.map((input, i) => (
                  <li key={i} className="text-sm text-foreground/80 flex items-center gap-1.5">
                    <span className="text-muted-foreground/60">&#8226;</span> {input}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Outputs</h3>
              <ul className="space-y-1">
                {agent.outputs.map((output, i) => (
                  <li key={i} className="text-sm text-foreground/80 flex items-center gap-1.5">
                    <span className="text-muted-foreground/60">&#8226;</span> {output}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Rules */}
          <div>
            <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Rules & Logic</h3>
            <ul className="space-y-1">
              {agent.rules.map((rule, i) => (
                <li key={i} className="text-sm text-foreground/80 flex items-start gap-2">
                  <span className={`${colors.text} shrink-0 mt-0.5`}>&#9656;</span>
                  {rule}
                </li>
              ))}
            </ul>
          </div>

          {/* Downstream + Source */}
          <div className="flex items-center justify-between pt-2 border-t border-border/50">
            {agent.downstream ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>Downstream:</span>
                <Badge variant="secondary" className="bg-muted text-foreground/80 gap-1">
                  {agent.downstream}
                  <ArrowRight className="h-3 w-3" />
                </Badge>
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">Terminal agent — no downstream</span>
            )}
            <span className="text-xs text-muted-foreground/60 font-mono">{agent.source_file}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch(`${API_BASE}/api/agents`)
      .then((res) => res.json())
      .then((data) => {
        setAgents(data);
        // Expand all by default
        setExpanded(new Set(data.map((a: Agent) => a.name)));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggleAgent = (name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const allExpanded = expanded.size === agents.length;
  const toggleAll = () => {
    if (allExpanded) {
      setExpanded(new Set());
    } else {
      setExpanded(new Set(agents.map((a) => a.name)));
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link href="/">
            <Button
              variant="outline"
              size="sm"
              className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Dashboard
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Bot className="h-6 w-6 text-blue-400" />
              Agent Registry
            </h1>
            <p className="text-sm text-muted-foreground">
              {agents.length} autonomous agents — roles, rules, and constitutions
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Button
            variant="outline"
            size="sm"
            className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 text-xs"
            onClick={toggleAll}
          >
            {allExpanded ? "Collapse All" : "Expand All"}
          </Button>
        </div>
      </div>

      {/* Agent chain flow */}
      <div className="flex items-center justify-center gap-2 mb-6 text-sm">
        {agents.map((a, i) => {
          const colors = COLOR_MAP[a.color] || COLOR_MAP.blue;
          return (
            <div key={a.name} className="flex items-center gap-2">
              <Badge className={`${colors.badge} text-white text-xs px-3 py-1`}>
                {a.name}
              </Badge>
              {i < agents.length - 1 && (
                <ArrowRight className="h-4 w-4 text-muted-foreground/60" />
              )}
            </div>
          );
        })}
      </div>

      {/* Agent cards */}
      {loading ? (
        <div className="text-center py-12 text-muted-foreground animate-pulse">Loading agents...</div>
      ) : (
        <div className="space-y-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.name}
              agent={agent}
              isExpanded={expanded.has(agent.name)}
              onToggle={() => toggleAgent(agent.name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
