const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const method = options?.method?.toUpperCase() || "GET";
  const maxRetries = ["GET", "HEAD", "OPTIONS"].includes(method) ? 3 : 0;
  let lastError: Error | null = null;

  // Inject auth token
  const token = typeof window !== "undefined" ? localStorage.getItem("cg_token") : null;
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const mergedOptions: RequestInit = { ...options, headers };

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, mergedOptions);
      if (res.status === 401 && typeof window !== "undefined") {
        localStorage.removeItem("cg_token");
        window.location.href = "/login";
        throw new Error("Unauthorized");
      }
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json();
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (lastError.message.match(/API error: 4[0-2][0-9]|API error: 43[0-9]|API error: 44[0-9]/)) throw lastError;
      if (attempt < maxRetries) {
        await new Promise((resolve) => setTimeout(resolve, 500 * Math.pow(2, attempt)));
      }
    }
  }
  throw lastError!;
}

export type InventoryItem = {
  part_id: string;
  description: string;
  category: string;
  on_hand: number;
  safety_stock: number;
  reserved: number;
  ring_fenced: number;
  available: number;
  daily_burn_rate: number;
  supplier: string | null;
};

export type PurchaseOrder = {
  po_number: string;
  part_id: string;
  supplier: string;
  quantity: number;
  unit_cost: number;
  total_cost: number;
  status: string;
  created_at: string;
  triggered_by: string;
  approved_by_name: string | null;
  approved_by_email: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
};

export type KPIs = {
  inventory_health: number;
  total_on_hand: number;
  total_safety_stock: number;
  active_threads: number;
  automation_rate: number;
  total_orders: number;
};

export type Agent = {
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

export type QualityInspection = {
  id: number;
  part: string | null;
  batch_size: number;
  result: string;
  notes: string | null;
  inspected_at: string | null;
};

export type UserProfile = {
  id: number;
  email: string;
  name: string;
  picture: string | null;
  role: string;
  is_active: boolean;
};

async function downloadBlob(path: string, filename: string): Promise<void> {
  const token = typeof window !== "undefined" ? localStorage.getItem("cg_token") : null;
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (res.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("cg_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const api = {
  getInventory: () => fetchJSON<InventoryItem[]>("/api/inventory"),
  getOrders: () => fetchJSON<PurchaseOrder[]>("/api/orders"),
  getKPIs: () => fetchJSON<KPIs>("/api/kpis"),
  getQualityInspections: () => fetchJSON<QualityInspection[]>("/api/db/quality_inspections"),
  getLogs: (limit = 50) =>
    fetchJSON<{ timestamp: string; agent: string; message: string; type: string }[]>(
      `/api/logs?limit=${limit}`
    ),
  simulateSpike: (sku = "FL-001-T", multiplier = 3.0) =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/spike?sku=${sku}&multiplier=${multiplier}`,
      { method: "POST" }
    ),
  simulateSupplyShock: (supplier = "CREE Inc.") =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/supply-shock?supplier_name=${supplier}`,
      { method: "POST" }
    ),
  simulateQualityFail: (partId = "CH-231", batchSize = 150) =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/quality-fail?part_id=${partId}&batch_size=${batchSize}`,
      { method: "POST" }
    ),
  simulateCascadeFailure: () =>
    fetchJSON<Record<string, unknown>>("/api/simulate/cascade-failure", { method: "POST" }),
  simulateConstitutionBreach: () =>
    fetchJSON<Record<string, unknown>>("/api/simulate/constitution-breach", { method: "POST" }),
  simulateFullBlackout: () =>
    fetchJSON<Record<string, unknown>>("/api/simulate/full-blackout", { method: "POST" }),
  simulateSlowBleed: (partId = "CH-231") =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/slow-bleed?part_id=${partId}`,
      { method: "POST" }
    ),
  simulateInventoryDecay: () =>
    fetchJSON<Record<string, unknown>>("/api/simulate/inventory-decay", { method: "POST" }),
  simulateMultiSkuContention: () =>
    fetchJSON<Record<string, unknown>>("/api/simulate/multi-sku-contention", { method: "POST" }),
  simulateContractExhaustion: (contractNumber = "BPA-CREE-2026") =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/contract-exhaustion?contract_number=${contractNumber}`,
      { method: "POST" }
    ),
  simulateTariffShock: (region = "CHINA", increasePct = 25) =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/tariff-shock?region=${region}&increase_pct=${increasePct}`,
      { method: "POST" }
    ),
  simulateMoqTrap: (partId = "LED-201", neededQty = 80) =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/moq-trap?part_id=${partId}&needed_qty=${neededQty}`,
      { method: "POST" }
    ),
  simulateMilitarySurge: () =>
    fetchJSON<Record<string, unknown>>("/api/simulate/military-surge", { method: "POST" }),
  simulateSemiconductorAllocation: (partId = "MCU-241", reductionPct = 60) =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/semiconductor-allocation?part_id=${partId}&capacity_reduction_pct=${reductionPct}`,
      { method: "POST" }
    ),
  simulateSeasonalRamp: (deviationPct = 40) =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/seasonal-ramp?deviation_pct=${deviationPct}`,
      { method: "POST" }
    ),
  simulateDemandHorizon: (partId = "CH-231", demandQty = 500, daysUntilNeeded = 30) =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/demand-horizon?part_id=${partId}&demand_qty=${demandQty}&days_until_needed=${daysUntilNeeded}`,
      { method: "POST" }
    ),
  updateOrderStatus: (poNumber: string, status: "APPROVED" | "CANCELLED", rejectionReason?: string) =>
    fetchJSON<PurchaseOrder>(`/api/orders/${poNumber}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, ...(rejectionReason && { rejection_reason: rejectionReason }) }),
    }),
  downloadPOPdf: (poNumber: string) =>
    downloadBlob(`/api/orders/${poNumber}/pdf`, `${poNumber}.pdf`),
  resetSimulation: () =>
    fetchJSON<Record<string, unknown>>("/api/simulate/reset", { method: "POST" }),
  getAgents: () => fetchJSON<Agent[]>("/api/agents"),
  getDataIntegrityWarnings: () =>
    fetchJSON<Array<{
      part_id: string;
      description: string;
      severity: string;
      issue: string;
      detail: string;
      action: string;
    }>>("/api/data-integrity/warnings"),
  getDBTable: (endpoint: string) =>
    fetchJSON<Record<string, unknown>[]>(endpoint),
  getLogDelay: () =>
    fetchJSON<{ delay: number }>("/api/settings/log-delay"),
  setLogDelay: (delay: number) =>
    fetchJSON<{ delay: number }>(`/api/settings/log-delay?delay=${delay}`, { method: "POST" }),
  // Admin: user management
  getUsers: () => fetchJSON<UserProfile[]>("/api/admin/users"),
  updateUserRole: (userId: number, role: string) =>
    fetchJSON<UserProfile>(`/api/admin/users/${userId}/role`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    }),
  updateUserActive: (userId: number, is_active: boolean) =>
    fetchJSON<UserProfile>(`/api/admin/users/${userId}/active`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active }),
    }),
};
