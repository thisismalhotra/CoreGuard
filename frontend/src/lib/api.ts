const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export type InventoryItem = {
  part_id: string;
  description: string;
  category: string;
  on_hand: number;
  safety_stock: number;
  reserved: number;
  available: number;
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
};

export type KPIs = {
  inventory_health: number;
  total_on_hand: number;
  total_safety_stock: number;
  active_threads: number;
  automation_rate: number;
  total_orders: number;
};

export const api = {
  getInventory: () => fetchJSON<InventoryItem[]>("/api/inventory"),
  getOrders: () => fetchJSON<PurchaseOrder[]>("/api/orders"),
  getKPIs: () => fetchJSON<KPIs>("/api/kpis"),
  getLogs: (limit = 50) =>
    fetchJSON<{ timestamp: string; agent: string; message: string; type: string }[]>(
      `/api/logs?limit=${limit}`
    ),
  simulateSpike: (sku = "FL-001-T", multiplier = 3.0) =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/spike?sku=${sku}&multiplier=${multiplier}`,
      { method: "POST" }
    ),
  simulateSupplyShock: (supplier = "AluForge") =>
    fetchJSON<Record<string, unknown>>(
      `/api/simulate/supply-shock?supplier_name=${supplier}`,
      { method: "POST" }
    ),
};
