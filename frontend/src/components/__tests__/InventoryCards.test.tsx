import { render, screen } from "@testing-library/react";
import { InventoryCards } from "../InventoryCards";
import type { InventoryItem } from "@/lib/api";

function makeItem(overrides: Partial<InventoryItem> & Pick<InventoryItem, "part_id">): InventoryItem {
  return {
    description: "Test Part",
    category: "COMMON_CORE",
    on_hand: 500,
    safety_stock: 200,
    reserved: 0,
    ring_fenced: 0,
    available: 500,
    daily_burn_rate: 10,
    supplier: null,
    ...overrides,
  };
}

describe("InventoryCards", () => {
  it("renders items grouped by category", () => {
    const items: InventoryItem[] = [
      makeItem({ part_id: "CH-101", category: "COMMON_CORE" }),
      makeItem({ part_id: "FL-001-T", category: "FINISHED_GOOD" }),
    ];
    render(<InventoryCards items={items} />);
    expect(screen.getByText("Common Core")).toBeInTheDocument();
    expect(screen.getByText("Finished Goods")).toBeInTheDocument();
  });

  it("shows CRITICAL badge when available < 50% of safety stock", () => {
    const items: InventoryItem[] = [
      makeItem({
        part_id: "CH-101",
        safety_stock: 200,
        available: 80, // 80 < 200 * 0.5 = 100 -> CRITICAL
      }),
    ];
    render(<InventoryCards items={items} />);
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
  });

  it("shows LOW badge when available < safety stock but >= 50%", () => {
    const items: InventoryItem[] = [
      makeItem({
        part_id: "SW-303",
        safety_stock: 200,
        available: 150, // 150 >= 100 (50%) but < 200 -> LOW
      }),
    ];
    render(<InventoryCards items={items} />);
    expect(screen.getByText("LOW")).toBeInTheDocument();
  });

  it("shows no severity badge when available >= safety stock", () => {
    const items: InventoryItem[] = [
      makeItem({
        part_id: "LNS-505",
        safety_stock: 200,
        available: 300, // 300 >= 200 -> normal
      }),
    ];
    render(<InventoryCards items={items} />);
    expect(screen.queryByText("CRITICAL")).not.toBeInTheDocument();
    expect(screen.queryByText("LOW")).not.toBeInTheDocument();
  });

  it("handles empty items array without crashing", () => {
    const { container } = render(<InventoryCards items={[]} />);
    // Should render the wrapper div but no category groups
    expect(container.querySelector(".space-y-2")).toBeInTheDocument();
  });
});
