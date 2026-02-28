"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Package, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import type { InventoryItem } from "@/lib/api";

type StockSeverity = "critical" | "low" | "normal";

const getStockSeverity = (item: InventoryItem): StockSeverity => {
  if (!item.safety_stock) return "normal";
  if (item.available < item.safety_stock * 0.5) return "critical";
  if (item.available < item.safety_stock) return "low";
  return "normal";
};

const CATEGORY_ORDER = ["FINISHED_GOOD", "COMMON_CORE", "SUB_ASSEMBLY", "COMPONENT", "SERVICE"];

const CATEGORY_LABELS: Record<string, string> = {
  FINISHED_GOOD: "Finished Goods",
  COMMON_CORE: "Common Core",
  SUB_ASSEMBLY: "Sub-Assemblies",
  COMPONENT: "Components",
  SERVICE: "Services",
};

function groupByCategory(items: InventoryItem[]): Record<string, InventoryItem[]> {
  const groups: Record<string, InventoryItem[]> = {};
  for (const item of items) {
    const cat = item.category || "OTHER";
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(item);
  }
  return groups;
}

function CategoryGroup({ category, items }: { category: string; items: InventoryItem[] }) {
  const [expanded, setExpanded] = useState(true);
  const lowCount = items.filter((i) => i.available < i.safety_stock).length;
  const label = CATEGORY_LABELS[category] || category;

  return (
    <div>
      <Button
        variant="ghost"
        className="w-full justify-between px-2 py-1.5 h-auto mb-2"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
          <span className="text-sm font-semibold text-foreground">{label}</span>
          <Badge variant="secondary" className="text-xs font-mono">
            {items.length}
          </Badge>
          {lowCount > 0 && (
            <Badge variant="destructive" className="text-xs">
              {lowCount} low
            </Badge>
          )}
        </div>
      </Button>
      {expanded && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {items.map((item) => {
            const severity = getStockSeverity(item);
            const isLow = severity !== "normal";
            const cardTint =
              severity === "critical"
                ? "bg-red-950/10 border-red-800"
                : severity === "low"
                  ? "bg-yellow-950/10 border-yellow-800"
                  : "";
            return (
              <Card
                key={item.part_id}
                className={`bg-card border-border ${cardTint}`}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {severity === "critical" && (
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
                        </span>
                      )}
                      {severity === "low" && (
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-500" />
                        </span>
                      )}
                      <CardTitle className="text-base font-semibold text-foreground">
                        {item.part_id}
                      </CardTitle>
                      {severity === "critical" && (
                        <Badge variant="destructive" className="text-xs">
                          CRITICAL
                        </Badge>
                      )}
                      {severity === "low" && (
                        <Badge className="text-xs bg-yellow-600 hover:bg-yellow-700 text-white">
                          LOW
                        </Badge>
                      )}
                    </div>
                    <Badge variant={isLow ? "destructive" : "secondary"} className="text-xs">
                      {item.category}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{item.description}</p>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="flex items-center gap-1.5">
                      <Package className="h-3.5 w-3.5 text-muted-foreground/60" />
                      <span className="text-muted-foreground">On Hand:</span>
                      <span className="text-foreground font-mono">{item.on_hand}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <AlertTriangle className={`h-3.5 w-3.5 ${isLow ? "text-red-400" : "text-muted-foreground/60"}`} />
                      <span className="text-muted-foreground">Available:</span>
                      <span className={`font-mono ${isLow ? "text-red-400" : "text-green-400"}`}>
                        {item.available}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground text-xs">Safety Stock: </span>
                      <span className="text-foreground/80 font-mono text-xs">{item.safety_stock}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground text-xs">Reserved: </span>
                      <span className="text-foreground/80 font-mono text-xs">{item.reserved}</span>
                    </div>
                  </div>
                  {item.supplier && (
                    <p className="text-xs text-muted-foreground mt-2">
                      Supplier: {item.supplier}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function InventoryCards({ items }: { items: InventoryItem[] }) {
  const groups = groupByCategory(items);
  const sortedCategories = CATEGORY_ORDER.filter((c) => groups[c]?.length);
  // Append any categories not in our predefined order
  const remaining = Object.keys(groups).filter((c) => !CATEGORY_ORDER.includes(c));

  return (
    <div className="space-y-2">
      {[...sortedCategories, ...remaining].map((category) => (
        <CategoryGroup key={category} category={category} items={groups[category]} />
      ))}
    </div>
  );
}
