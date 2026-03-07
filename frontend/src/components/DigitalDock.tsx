"use client";

import { useEffect, useState, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Shield,
  FileText,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Package,
  DollarSign,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  UserCheck,
} from "lucide-react";
import { toast } from "sonner";
import { api, type PurchaseOrder, type QualityInspection } from "@/lib/api";
import { useAuth, hasRole } from "@/lib/auth";

// --- Status badge helpers ---

function poStatusColor(status: string): string {
  switch (status) {
    case "APPROVED":
      return "bg-green-600";
    case "PENDING_APPROVAL":
      return "bg-yellow-600";
    case "DRAFT":
      return "bg-muted";
    case "SENT":
      return "bg-blue-600";
    case "CANCELLED":
      return "bg-red-600";
    default:
      return "bg-muted";
  }
}

function inspectionIcon(result: string) {
  switch (result) {
    case "PASS":
      return <CheckCircle className="h-4 w-4 text-green-400" />;
    case "FAIL":
      return <XCircle className="h-4 w-4 text-red-400" />;
    default:
      return <Clock className="h-4 w-4 text-yellow-400" />;
  }
}

function inspectionBadgeColor(result: string): string {
  switch (result) {
    case "PASS":
      return "bg-green-600";
    case "FAIL":
      return "bg-red-600";
    case "PENDING":
      return "bg-yellow-600";
    default:
      return "bg-muted";
  }
}

// --- Sub-tab type ---
type DockTab = "inspections" | "orders";

export function DigitalDock() {
  const { user } = useAuth();
  const canApprove = hasRole(user, "approver", "admin");
  const [activeTab, setActiveTab] = useState<DockTab>("inspections");
  const [inspections, setInspections] = useState<QualityInspection[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedPO, setExpandedPO] = useState<Set<string>>(new Set());
  const [updatingPO, setUpdatingPO] = useState<string | null>(null);
  const [poError, setPOError] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [requestedInspPage, setInspPage] = useState(1);
  const inspPerPage = 25;

  const handleUpdateStatus = async (
    poNumber: string,
    status: "APPROVED" | "CANCELLED"
  ) => {
    let rejectionReason: string | undefined;
    if (status === "CANCELLED") {
      const reason = window.prompt("Reason for rejection (optional):");
      if (reason === null) return; // User cancelled the prompt
      rejectionReason = reason || undefined;
    }
    setUpdatingPO(poNumber);
    setPOError(null);
    try {
      await api.updateOrderStatus(poNumber, status, rejectionReason);
      await fetchData();
      toast.success(`PO ${poNumber} ${status === "APPROVED" ? "approved" : "rejected"}`);
    } catch (err) {
      setPOError(
        `Failed to ${status === "APPROVED" ? "approve" : "reject"} ${poNumber}: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    } finally {
      setUpdatingPO(null);
    }
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const [inspData, orderData] = await Promise.all([
        api.getQualityInspections(),
        api.getOrders(),
      ]);
      setInspections(inspData);
      setOrders(orderData);
    } catch (err) {
      setFetchError(
        `Failed to load data: ${err instanceof Error ? err.message : "Is the backend running?"}`
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const togglePO = (poNumber: string) => {
    setExpandedPO((prev) => {
      const next = new Set(prev);
      if (next.has(poNumber)) next.delete(poNumber);
      else next.add(poNumber);
      return next;
    });
  };

  // Inspection pagination — clamp page to valid range
  const totalInspPages = Math.ceil(inspections.length / inspPerPage);
  const inspPage = Math.min(requestedInspPage, Math.max(1, totalInspPages));
  const paginatedInspections = inspections.slice(
    (inspPage - 1) * inspPerPage,
    inspPage * inspPerPage
  );

  // Summary stats
  const passCount = inspections.filter((i) => i.result === "PASS").length;
  const failCount = inspections.filter((i) => i.result === "FAIL").length;
  const approvedCount = orders.filter((o) => o.status === "APPROVED").length;
  const pendingCount = orders.filter(
    (o) => o.status === "PENDING_APPROVAL"
  ).length;
  const totalSpend = orders.reduce((sum, o) => sum + o.total_cost, 0);

  return (
    <div className="space-y-4">
      {/* Sub-tab bar + refresh */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 bg-card border border-border rounded-lg p-1" role="tablist" aria-label="Digital Dock sections">
          <button
            role="tab"
            aria-selected={activeTab === "inspections"}
            aria-controls="dock-panel-inspections"
            onClick={() => setActiveTab("inspections")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              activeTab === "inspections"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Shield className="h-3.5 w-3.5" />
            Quality Inspections
            {inspections.length > 0 && (
              <Badge
                variant="secondary"
                className="bg-muted text-foreground/80 text-[10px] px-1.5"
              >
                {inspections.length}
              </Badge>
            )}
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "orders"}
            aria-controls="dock-panel-orders"
            onClick={() => setActiveTab("orders")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              activeTab === "orders"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            Purchase Orders
            {orders.length > 0 && (
              <Badge
                variant="secondary"
                className="bg-muted text-foreground/80 text-[10px] px-1.5"
              >
                {orders.length}
              </Badge>
            )}
          </button>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5 text-xs"
          onClick={fetchData}
          disabled={loading}
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {/* Error banner */}
      {fetchError && (
        <div className="flex items-center gap-3 bg-red-950/50 border border-red-700/50 rounded-lg px-4 py-3">
          <AlertTriangle className="h-5 w-5 text-red-400 shrink-0" />
          <span className="text-sm text-red-300">{fetchError}</span>
          <Button
            variant="outline"
            size="sm"
            className="ml-auto border-red-700/50 text-red-300 hover:bg-red-950 text-xs"
            onClick={fetchData}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="bg-card rounded-lg border border-border p-8 text-center text-muted-foreground animate-pulse">
          Loading...
        </div>
      ) : activeTab === "inspections" ? (
        /* ============================================================
           QUALITY INSPECTIONS
           ============================================================ */
        <div className="space-y-3">
          {/* Summary bar */}
          <div className="flex gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <CheckCircle className="h-3.5 w-3.5 text-green-400" />
              <span className="text-muted-foreground">Passed:</span>
              <span className="text-foreground font-mono font-semibold">
                {passCount}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <XCircle className="h-3.5 w-3.5 text-red-400" />
              <span className="text-muted-foreground">Failed:</span>
              <span className="text-foreground font-mono font-semibold">
                {failCount}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <Package className="h-3.5 w-3.5 text-muted-foreground/60" />
              <span className="text-muted-foreground">Total Batches:</span>
              <span className="text-foreground font-mono font-semibold">
                {inspections.length}
              </span>
            </div>
          </div>

          {inspections.length === 0 ? (
            <div className="bg-card rounded-lg border border-border p-8 text-center">
              <Shield className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-muted-foreground text-sm">
                No inspections yet. Run a{" "}
                <span className="text-orange-400 font-medium">
                  Quality Fail
                </span>{" "}
                scenario from God Mode to simulate incoming shipments.
              </p>
            </div>
          ) : (
            <div className="bg-card rounded-lg border border-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left px-4 py-2.5 text-muted-foreground font-medium text-xs uppercase tracking-wider">
                      Result
                    </th>
                    <th className="text-left px-4 py-2.5 text-muted-foreground font-medium text-xs uppercase tracking-wider">
                      Part
                    </th>
                    <th className="text-left px-4 py-2.5 text-muted-foreground font-medium text-xs uppercase tracking-wider">
                      Batch Size
                    </th>
                    <th className="text-left px-4 py-2.5 text-muted-foreground font-medium text-xs uppercase tracking-wider">
                      Notes
                    </th>
                    <th className="text-left px-4 py-2.5 text-muted-foreground font-medium text-xs uppercase tracking-wider">
                      Inspected
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedInspections.map((insp) => (
                    <tr
                      key={insp.id}
                      className="border-b border-border/50 hover:bg-muted/30 transition-colors"
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          {inspectionIcon(insp.result)}
                          <Badge
                            className={`${inspectionBadgeColor(insp.result)} text-white text-[10px]`}
                          >
                            {insp.result}
                          </Badge>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-foreground/80 font-mono">
                        {insp.part || "—"}
                      </td>
                      <td className="px-4 py-2.5 text-foreground/80 font-mono">
                        {insp.batch_size}
                      </td>
                      <td className="px-4 py-2.5 text-foreground/60 text-xs max-w-[300px] truncate">
                        {insp.notes || "—"}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground text-xs whitespace-nowrap">
                        {insp.inspected_at
                          ? new Date(insp.inspected_at).toLocaleString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {totalInspPages > 1 && (
                <div className="flex items-center justify-between px-2 py-2 border-t border-border mt-2">
                  <span className="text-xs text-muted-foreground">
                    {inspections.length} inspections — Page {inspPage} of {totalInspPages}
                  </span>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      disabled={inspPage === 1}
                      onClick={() => setInspPage((p) => p - 1)}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      disabled={inspPage === totalInspPages}
                      onClick={() => setInspPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* ============================================================
           PURCHASE ORDERS
           ============================================================ */
        <div className="space-y-3">
          {/* Summary bar */}
          <div className="flex gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <CheckCircle className="h-3.5 w-3.5 text-green-400" />
              <span className="text-muted-foreground">Approved:</span>
              <span className="text-foreground font-mono font-semibold">
                {approvedCount}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 text-yellow-400" />
              <span className="text-muted-foreground">Pending:</span>
              <span className="text-foreground font-mono font-semibold">
                {pendingCount}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <DollarSign className="h-3.5 w-3.5 text-muted-foreground/60" />
              <span className="text-muted-foreground">Total Spend:</span>
              <span className="text-foreground font-mono font-semibold">
                ${totalSpend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>

          {orders.length === 0 ? (
            <div className="bg-card rounded-lg border border-border p-8 text-center">
              <FileText className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-muted-foreground text-sm">
                No purchase orders yet. Run a simulation from{" "}
                <span className="text-purple-400 font-medium">God Mode</span>{" "}
                to generate POs.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {orders.map((po) => {
                const isExpanded = expandedPO.has(po.po_number);
                const isBlocked = po.status === "PENDING_APPROVAL";
                const isApproved = po.status === "APPROVED";

                return (
                  <div
                    key={po.po_number}
                    className={`bg-card rounded-lg border overflow-hidden transition-colors ${
                      isBlocked
                        ? "border-yellow-700/50"
                        : isApproved
                          ? "border-green-800/50"
                          : "border-border"
                    }`}
                  >
                    {/* Header row */}
                    <button
                      onClick={() => togglePO(po.po_number)}
                      className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <FileText
                          className={`h-4 w-4 shrink-0 ${
                            isBlocked
                              ? "text-yellow-400"
                              : isApproved
                                ? "text-green-400"
                                : "text-muted-foreground"
                          }`}
                        />
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono font-semibold text-foreground">
                            {po.po_number}
                          </span>
                          <Badge
                            className={`${poStatusColor(po.status)} text-white text-[10px]`}
                          >
                            {po.status}
                          </Badge>
                        </div>
                        <span className="text-xs text-muted-foreground hidden sm:inline">
                          {po.quantity}x {po.part_id} from {po.supplier}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span
                          className={`text-sm font-mono font-semibold ${
                            po.total_cost > 5000
                              ? "text-yellow-400"
                              : "text-foreground"
                          }`}
                        >
                          $
                          {po.total_cost.toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </span>
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        )}
                      </div>
                    </button>

                    {/* Expanded details */}
                    {isExpanded && (
                      <div className="px-4 pb-3 border-t border-border/50 pt-3">
                        {isBlocked && (
                          <div className="bg-yellow-950/40 border border-yellow-700/50 rounded-lg p-3 mb-3">
                            <div className="flex items-center gap-2">
                              <AlertTriangle className="h-4 w-4 text-yellow-500 shrink-0" />
                              <span className="text-xs text-yellow-400 font-semibold">
                                Financial Constitution Triggered
                              </span>
                            </div>
                            <p className="text-xs text-yellow-200/70 mt-1">
                              Total cost exceeds $5,000 limit. Human approval
                              required before funds can be committed.
                            </p>
                            {canApprove ? (
                              <div className="flex items-center gap-2 mt-3">
                                <Button
                                  size="sm"
                                  className="bg-green-700 hover:bg-green-600 text-white gap-1.5 text-xs h-7 px-3"
                                  disabled={updatingPO === po.po_number}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleUpdateStatus(po.po_number, "APPROVED");
                                  }}
                                >
                                  <CheckCircle className="h-3.5 w-3.5" />
                                  {updatingPO === po.po_number
                                    ? "Approving..."
                                    : "Approve"}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="border-red-700/50 text-red-400 hover:bg-red-950/50 hover:text-red-300 gap-1.5 text-xs h-7 px-3"
                                  disabled={updatingPO === po.po_number}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleUpdateStatus(po.po_number, "CANCELLED");
                                  }}
                                >
                                  <XCircle className="h-3.5 w-3.5" />
                                  {updatingPO === po.po_number
                                    ? "Rejecting..."
                                    : "Reject"}
                                </Button>
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground mt-3 italic">
                                Approver or Admin role required to approve/reject.
                              </p>
                            )}
                            {poError &&
                              poError.includes(po.po_number) && (
                                <p className="text-xs text-red-400 mt-2">
                                  {poError}
                                </p>
                              )}
                          </div>
                        )}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                          <div>
                            <span className="text-muted-foreground">Part</span>
                            <p className="text-foreground font-mono mt-0.5">
                              {po.part_id}
                            </p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">
                              Supplier
                            </span>
                            <p className="text-foreground mt-0.5">
                              {po.supplier}
                            </p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">
                              Quantity
                            </span>
                            <p className="text-foreground font-mono mt-0.5">
                              {po.quantity} units
                            </p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">
                              Unit Cost
                            </span>
                            <p className="text-foreground font-mono mt-0.5">
                              ${po.unit_cost.toFixed(2)}
                            </p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">
                              Total Cost
                            </span>
                            <p
                              className={`font-mono mt-0.5 font-semibold ${
                                po.total_cost > 5000
                                  ? "text-yellow-400"
                                  : "text-green-400"
                              }`}
                            >
                              $
                              {po.total_cost.toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}
                            </p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">
                              Triggered By
                            </span>
                            <p className="text-foreground mt-0.5">
                              {po.triggered_by}
                            </p>
                          </div>
                          <div className="col-span-2">
                            <span className="text-muted-foreground">
                              Created
                            </span>
                            <p className="text-foreground mt-0.5">
                              {new Date(po.created_at).toLocaleString()}
                            </p>
                          </div>
                        </div>
                        {/* Audit trail */}
                        {po.approved_by_name && (
                          <div className="mt-3 pt-3 border-t border-border/50">
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <UserCheck className="h-3.5 w-3.5" />
                              <span>
                                {po.status === "CANCELLED" ? "Rejected" : "Approved"} by{" "}
                                <span className="text-foreground font-medium">{po.approved_by_name}</span>
                                {po.approved_at && (
                                  <> on {new Date(po.approved_at).toLocaleString()}</>
                                )}
                              </span>
                            </div>
                            {po.rejection_reason && (
                              <p className="text-xs text-red-400 mt-1 ml-5">
                                Reason: {po.rejection_reason}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
