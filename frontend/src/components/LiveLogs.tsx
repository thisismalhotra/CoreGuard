"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Trash2, Clock, Terminal, Zap, Search, X } from "lucide-react";
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
  onSwitchToGodMode,
}: {
  logs: AgentLog[];
  onClear: () => void;
  onSwitchToGodMode?: () => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [delay, setDelay] = useState(2);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState<string[]>([]);
  const [typeFilter, setTypeFilter] = useState<string[]>([]);

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase()) &&
          !log.agent.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false;
      }
      if (agentFilter.length > 0 && !agentFilter.includes(log.agent)) {
        return false;
      }
      if (typeFilter.length > 0 && !typeFilter.includes(log.type)) {
        return false;
      }
      return true;
    });
  }, [logs, searchQuery, agentFilter, typeFilter]);

  // Fetch current delay from backend on mount
  useEffect(() => {
    api.getLogDelay().then((res) => setDelay(res.delay)).catch(() => {});
  }, []);

  // Track scroll position — only auto-scroll if user is near the bottom
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleScroll = () => {
      const threshold = 80; // px from bottom
      const nearBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
      setIsNearBottom(nearBottom);
    };
    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (isNearBottom) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [filteredLogs, isNearBottom]);

  const handleDelayChange = async (newDelay: number) => {
    const prevDelay = delay;
    setDelay(newDelay);
    try {
      await api.setLogDelay(newDelay);
    } catch {
      // Revert on failure using captured previous value (not stale closure)
      setDelay(prevDelay);
    }
  };

  return (
    <div className="space-y-2">
      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-card border border-input text-foreground text-xs rounded pl-7 pr-7 py-1.5 h-7 focus:outline-none focus:border-blue-500 placeholder:text-muted-foreground/50"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Agent filters */}
      <div className="flex items-center gap-1 flex-wrap">
        <span className="text-[10px] text-muted-foreground mr-1">Agent:</span>
        {Object.keys(AGENT_COLORS).map((agent) => (
          <button
            key={agent}
            onClick={() =>
              setAgentFilter((prev) =>
                prev.includes(agent)
                  ? prev.filter((a) => a !== agent)
                  : [...prev, agent]
              )
            }
            className={`text-[10px] px-1.5 py-0.5 rounded border transition-colors ${
              agentFilter.includes(agent)
                ? `${AGENT_COLORS[agent]} text-white border-transparent`
                : "bg-card text-muted-foreground border-input hover:border-foreground/30"
            }`}
          >
            {agent}
          </button>
        ))}
      </div>

      {/* Type filters */}
      <div className="flex items-center gap-1 flex-wrap">
        <span className="text-[10px] text-muted-foreground mr-1">Type:</span>
        {Object.keys(LOG_TYPE_STYLES).map((type) => (
          <button
            key={type}
            onClick={() =>
              setTypeFilter((prev) =>
                prev.includes(type)
                  ? prev.filter((t) => t !== type)
                  : [...prev, type]
              )
            }
            className={`text-[10px] px-1.5 py-0.5 rounded border capitalize transition-colors ${
              typeFilter.includes(type)
                ? "bg-foreground text-background border-transparent"
                : "bg-card text-muted-foreground border-input hover:border-foreground/30"
            }`}
          >
            {type}
          </button>
        ))}
        {(searchQuery || agentFilter.length > 0 || typeFilter.length > 0) && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs h-6 px-2 text-muted-foreground"
            onClick={() => {
              setSearchQuery("");
              setAgentFilter([]);
              setTypeFilter([]);
            }}
          >
            <X className="h-3 w-3 mr-1" />
            Clear Filters
          </Button>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {searchQuery || agentFilter.length > 0 || typeFilter.length > 0
            ? `${filteredLogs.length} of ${logs.length} entries`
            : `${logs.length} ${logs.length === 1 ? "entry" : "entries"}`}
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
      <div ref={containerRef} className="bg-background rounded-lg border border-border font-mono text-sm h-[500px] overflow-y-auto p-4">
        {logs.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center font-sans">
            <Terminal className="h-8 w-8 text-muted-foreground/30" />
            <p className="text-muted-foreground text-sm">No agent activity yet.</p>
            <p className="text-muted-foreground/60 text-xs max-w-xs leading-relaxed">
              Go to <span className="text-yellow-400 font-medium">God Mode</span> and click{" "}
              <span className="font-medium text-foreground/70">Inject Chaos</span> to watch
              agents work in real-time.
            </p>
            {onSwitchToGodMode && (
              <Button
                size="sm"
                variant="outline"
                onClick={onSwitchToGodMode}
                className="gap-1.5 mt-1 border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 text-xs"
              >
                <Zap className="h-3 w-3" />
                Go to God Mode
              </Button>
            )}
          </div>
        )}
        {logs.length > 0 && filteredLogs.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center font-sans">
            <Search className="h-6 w-6 text-muted-foreground/30" />
            <p className="text-muted-foreground text-sm">No logs match the current filters.</p>
          </div>
        )}
        {filteredLogs.map((log, i) => {
          const time = log.timestamp
            ? new Date(log.timestamp).toLocaleTimeString()
            : "--:--:--";
          return (
            <div key={`${log.timestamp}-${log.agent}-${i}`} className="flex items-start gap-2 mb-1.5 leading-relaxed">
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
