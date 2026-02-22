"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Package, AlertTriangle } from "lucide-react";
import type { InventoryItem } from "@/lib/api";

export function InventoryCards({ items }: { items: InventoryItem[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((item) => {
        const isLow = item.available < item.safety_stock;
        return (
          <Card
            key={item.part_id}
            className={`bg-card border-border ${isLow ? "border-red-800" : ""}`}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold text-foreground">
                  {item.part_id}
                </CardTitle>
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
  );
}
