import { render, screen } from "@testing-library/react";
import { KPIPanel } from "../KPIPanel";
import type { KPIs } from "@/lib/api";

const mockKPIs: KPIs = {
  inventory_health: 3,
  total_on_hand: 5000,
  total_safety_stock: 2000,
  active_threads: 4,
  automation_rate: 87,
  total_orders: 12,
};

describe("KPIPanel", () => {
  it("renders loading skeleton when kpis prop is null", () => {
    const { container } = render(<KPIPanel kpis={null} />);
    const pulsingElements = container.querySelectorAll(".animate-pulse");
    expect(pulsingElements.length).toBe(4);
  });

  it("renders all four formatted KPI values correctly", () => {
    render(<KPIPanel kpis={mockKPIs} />);
    // inventory_health formatted as "3x"
    expect(screen.getByText("3x")).toBeInTheDocument();
    // active_threads formatted as "4"
    expect(screen.getByText("4")).toBeInTheDocument();
    // automation_rate formatted as "87%"
    expect(screen.getByText("87%")).toBeInTheDocument();
    // total_orders formatted as "12"
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("renders correct labels", () => {
    render(<KPIPanel kpis={mockKPIs} />);
    expect(screen.getByText("Inventory Health")).toBeInTheDocument();
    expect(screen.getByText("Active Agents")).toBeInTheDocument();
    expect(screen.getByText("Automation Rate")).toBeInTheDocument();
    expect(screen.getByText("Total POs")).toBeInTheDocument();
  });
});
