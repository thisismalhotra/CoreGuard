"use client";

import { useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import type { AgentLog } from "@/lib/socket";

const LOG_TYPE_STYLES: Record<string, string> = {
  info: "text-blue-400",
  warning: "text-yellow-400",
  success: "text-green-400",
  error: "text-red-400",
};

const AGENT_COLORS: Record<string, string> = {
  Aura: "bg-purple-600",
  "Core-Guard": "bg-blue-600",
  "Ghost-Writer": "bg-emerald-600",
  "Eagle-Eye": "bg-orange-600",
  System: "bg-gray-600",
};

export function LiveLogs({ logs }: { logs: AgentLog[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="bg-gray-950 rounded-lg border border-gray-800 font-mono text-sm h-[500px] overflow-y-auto p-4">
      {logs.length === 0 && (
        <p className="text-gray-500 animate-pulse">
          Awaiting agent activity...
        </p>
      )}
      {logs.map((log, i) => {
        const time = log.timestamp
          ? new Date(log.timestamp).toLocaleTimeString()
          : "--:--:--";
        return (
          <div key={i} className="flex items-start gap-2 mb-1.5 leading-relaxed">
            <span className="text-gray-600 shrink-0 w-[72px]">{time}</span>
            <Badge
              variant="secondary"
              className={`${AGENT_COLORS[log.agent] || "bg-gray-600"} text-white text-[10px] shrink-0 w-[90px] justify-center`}
            >
              {log.agent}
            </Badge>
            <span className={LOG_TYPE_STYLES[log.type] || "text-gray-300"}>
              {log.message}
            </span>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
