"use client";

import { useEffect, useState, useCallback } from "react";
import { Bell, FileText, DollarSign } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api, type PendingApproval } from "@/lib/api";
import { getSocket } from "@/lib/socket";

export function NotificationBell({ onNavigateToOrders }: { onNavigateToOrders: () => void }) {
  const [notifications, setNotifications] = useState<PendingApproval[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(() => {
    if (typeof window === "undefined") return new Set();
    const stored = localStorage.getItem("cg_dismissed_notifications");
    return stored ? new Set(JSON.parse(stored)) : new Set();
  });
  const [open, setOpen] = useState(false);

  const fetchNotifications = useCallback(async () => {
    try {
      const data = await api.getPendingApprovals();
      setNotifications(data);
      // Clean dismissed set — remove POs that are no longer pending
      setDismissed((prev) => {
        const activeIds = new Set(data.map((n) => n.po_number));
        const cleaned = new Set([...prev].filter((id) => activeIds.has(id)));
        if (cleaned.size !== prev.size) {
          localStorage.setItem("cg_dismissed_notifications", JSON.stringify([...cleaned]));
        }
        return cleaned;
      });
    } catch {
      // Silently ignore — user may not have approver role
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial fetch on mount
    fetchNotifications();
    const socket = getSocket();
    const handlePending = () => fetchNotifications();
    const handleLog = (log: { message: string }) => {
      if (log.message.includes("APPROVED") || log.message.includes("REJECTED")) {
        fetchNotifications();
      }
    };
    socket.on("po_pending_approval", handlePending);
    socket.on("agent_log", handleLog);
    return () => {
      socket.off("po_pending_approval", handlePending);
      socket.off("agent_log", handleLog);
    };
  }, [fetchNotifications]);

  const dismiss = (poNumber: string) => {
    setDismissed((prev) => {
      const next = new Set(prev);
      next.add(poNumber);
      localStorage.setItem("cg_dismissed_notifications", JSON.stringify([...next]));
      return next;
    });
  };

  const unread = notifications.filter((n) => !dismissed.has(n.po_number));
  const unreadCount = unread.length;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="relative h-8 w-8 p-0"
          aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} pending)` : ""}`}
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 h-4 min-w-4 rounded-full bg-red-500 text-[10px] text-white flex items-center justify-center font-bold px-0.5">
              {unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <div className="px-3 py-2 border-b border-border">
          <h4 className="text-sm font-semibold">Pending Approvals</h4>
          <p className="text-xs text-muted-foreground">
            {notifications.length === 0
              ? "No POs awaiting approval"
              : `${unreadCount} new, ${notifications.length} total`}
          </p>
        </div>
        <div className="max-h-[300px] overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="p-4 text-center text-xs text-muted-foreground">
              All clear — no pending approvals.
            </div>
          ) : (
            notifications.map((n) => {
              const isNew = !dismissed.has(n.po_number);
              return (
                <div
                  key={n.po_number}
                  className={`flex items-start gap-3 px-3 py-2.5 border-b border-border/50 hover:bg-muted/30 transition-colors cursor-pointer ${
                    isNew ? "bg-yellow-950/20" : ""
                  }`}
                  onClick={() => {
                    dismiss(n.po_number);
                    onNavigateToOrders();
                    setOpen(false);
                  }}
                >
                  <FileText className={`h-4 w-4 mt-0.5 shrink-0 ${isNew ? "text-yellow-400" : "text-muted-foreground"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-semibold text-foreground">{n.po_number}</span>
                      {isNew && <span className="h-1.5 w-1.5 rounded-full bg-yellow-400" />}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">
                      {n.part_id} from {n.supplier}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 text-xs font-mono text-yellow-400 shrink-0">
                    <DollarSign className="h-3 w-3" />
                    {n.total_cost.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                  </div>
                </div>
              );
            })
          )}
        </div>
        {notifications.length > 0 && (
          <div className="px-3 py-2 border-t border-border">
            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs h-7"
              onClick={() => {
                onNavigateToOrders();
                setOpen(false);
              }}
            >
              View all in Digital Dock
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
