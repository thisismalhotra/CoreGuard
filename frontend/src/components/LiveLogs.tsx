"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Trash2, Clock } from "lucide-react";
import type { AgentLog } from "@/lib/socket";
import { api } from "@/lib/api";

const LOG_TYPE_STYLES: Record<string, string> = {
  info: "text-blue-400",
  warning: "text-yellow-400",
  success: "text-green-400",
  error: "text-red-400",
};

const AGENT_COLORS: Record<string, string> = {
  Aura: "bg-purple-600",
  Dispatcher: "bg-cyan-600",
  "Core-Guard": "bg-blue-600",
  "Ghost-Writer": "bg-emerald-600",
  "Eagle-Eye": "bg-orange-600",
  System: "bg-gray-600",
};

const DELAY_OPTIONS = [
  { value: 1, label: "1s" },
  { value: 2, label: "2s" },
  { value: 3, label: "3s" },
];

export function LiveLogs({
  logs,
  onClear,
}: {
  logs: AgentLog[];
  onClear: () => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [delay, setDelay] = useState(2);

  // Fetch current delay from backend on mount
  useEffect(() => {
    api.getLogDelay().then((res) => setDelay(res.delay)).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleDelayChange = async (newDelay: number) => {
    setDelay(newDelay);
    try {
      await api.setLogDelay(newDelay);
    } catch {
      // Revert on failure
      setDelay(delay);
    }
  };

  return (
    <div className="space-y-2">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {logs.length} {logs.length === 1 ? "entry" : "entries"}
        </span>
        <div className="flex items-center gap-3">
          {/* Log delay selector */}
          <div className="flex items-center gap-1.5">
            <Clock className="h-3 w-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Delay:</span>
            <select
              value={delay}
              onChange={(e) => handleDelayChange(Number(e.target.value))}
              className="bg-card border border-input text-foreground/80 text-xs rounded px-1.5 py-0.5 h-7 focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              {DELAY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5 text-xs h-7"
            onClick={onClear}
            disabled={logs.length === 0}
          >
            <Trash2 className="h-3 w-3" />
            Clear Logs
          </Button>
        </div>
      </div>

      {/* Log terminal */}
      <div className="bg-background rounded-lg border border-border font-mono text-sm h-[500px] overflow-y-auto p-4">
        {logs.length === 0 && (
          <p className="text-muted-foreground animate-pulse">
            Awaiting agent activity...
          </p>
        )}
        {logs.map((log, i) => {
          const time = log.timestamp
            ? new Date(log.timestamp).toLocaleTimeString()
            : "--:--:--";
          return (
            <div key={i} className="flex items-start gap-2 mb-1.5 leading-relaxed">
              <span className="text-muted-foreground/60 shrink-0 w-[72px]">{time}</span>
              <Badge
                variant="secondary"
                className={`${AGENT_COLORS[log.agent] || "bg-gray-600"} text-white text-[10px] shrink-0 w-[90px] justify-center`}
              >
                {log.agent}
              </Badge>
              <span className={LOG_TYPE_STYLES[log.type] || "text-foreground/80"}>
                {log.message}
              </span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
