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
            className={`bg-gray-900 border-gray-800 ${isLow ? "border-red-800" : ""}`}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold text-gray-100">
                  {item.part_id}
                </CardTitle>
                <Badge variant={isLow ? "destructive" : "secondary"} className="text-xs">
                  {item.category}
                </Badge>
              </div>
              <p className="text-xs text-gray-400">{item.description}</p>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex items-center gap-1.5">
                  <Package className="h-3.5 w-3.5 text-gray-500" />
                  <span className="text-gray-400">On Hand:</span>
                  <span className="text-white font-mono">{item.on_hand}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <AlertTriangle className={`h-3.5 w-3.5 ${isLow ? "text-red-400" : "text-gray-500"}`} />
                  <span className="text-gray-400">Available:</span>
                  <span className={`font-mono ${isLow ? "text-red-400" : "text-green-400"}`}>
                    {item.available}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400 text-xs">Safety Stock: </span>
                  <span className="text-gray-300 font-mono text-xs">{item.safety_stock}</span>
                </div>
                <div>
                  <span className="text-gray-400 text-xs">Reserved: </span>
                  <span className="text-gray-300 font-mono text-xs">{item.reserved}</span>
                </div>
              </div>
              {item.supplier && (
                <p className="text-xs text-gray-500 mt-2">
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
