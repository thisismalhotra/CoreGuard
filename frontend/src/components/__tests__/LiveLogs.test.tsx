import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { LiveLogs } from "../LiveLogs";
import type { AgentLog } from "@/lib/socket";

// Mock the api module since the component calls api.getLogDelay() on mount
vi.mock("@/lib/api", () => ({
  api: {
    getLogDelay: vi.fn().mockResolvedValue({ delay: 2 }),
    setLogDelay: vi.fn().mockResolvedValue({ delay: 2 }),
  },
}));

const mockLogs: AgentLog[] = [
  {
    timestamp: "2026-02-28T10:00:00Z",
    agent: "Solver",
    message: "MRP calculation started",
    type: "info",
  },
  {
    timestamp: "2026-02-28T10:00:01Z",
    agent: "Buyer",
    message: "PO generated for LED-201",
    type: "success",
  },
  {
    timestamp: "2026-02-28T10:00:02Z",
    agent: "Inspector",
    message: "Batch failed inspection",
    type: "error",
  },
];

describe("LiveLogs", () => {
  const onClear = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state "No agent activity yet" when logs is empty', () => {
    render(<LiveLogs logs={[]} onClear={onClear} />);
    expect(screen.getByText("No agent activity yet.")).toBeInTheDocument();
  });

  it("renders log entries — pass 3 logs, verify all messages are visible", () => {
    render(<LiveLogs logs={mockLogs} onClear={onClear} />);
    expect(screen.getByText("MRP calculation started")).toBeInTheDocument();
    expect(screen.getByText("PO generated for LED-201")).toBeInTheDocument();
    expect(screen.getByText("Batch failed inspection")).toBeInTheDocument();
  });

  it("search filter narrows visible logs", async () => {
    const user = userEvent.setup();
    render(<LiveLogs logs={mockLogs} onClear={onClear} />);

    const searchInput = screen.getByPlaceholderText("Search logs...");
    await user.type(searchInput, "MRP");

    expect(screen.getByText("MRP calculation started")).toBeInTheDocument();
    expect(screen.queryByText("PO generated for LED-201")).not.toBeInTheDocument();
    expect(screen.queryByText("Batch failed inspection")).not.toBeInTheDocument();
  });

  it("agent filter toggle works — click an agent filter button, verify filtering", async () => {
    const user = userEvent.setup();
    render(<LiveLogs logs={mockLogs} onClear={onClear} />);

    // Click the "Solver" agent filter button
    const agentButtons = screen.getAllByRole("button");
    const solverButton = agentButtons.find(
      (btn) => btn.textContent === "Solver" && btn.className.includes("text-[10px]")
    );
    expect(solverButton).toBeDefined();
    await user.click(solverButton!);

    // Only Solver logs should be visible
    expect(screen.getByText("MRP calculation started")).toBeInTheDocument();
    expect(screen.queryByText("PO generated for LED-201")).not.toBeInTheDocument();
    expect(screen.queryByText("Batch failed inspection")).not.toBeInTheDocument();
  });

  it("type filter toggle works — click a type filter button, verify filtering", async () => {
    const user = userEvent.setup();
    render(<LiveLogs logs={mockLogs} onClear={onClear} />);

    // Click the "error" type filter button
    const allButtons = screen.getAllByRole("button");
    const errorTypeButton = allButtons.find(
      (btn) => btn.textContent === "error" && btn.className.includes("capitalize")
    );
    expect(errorTypeButton).toBeDefined();
    await user.click(errorTypeButton!);

    // Only error-type logs should be visible
    expect(screen.getByText("Batch failed inspection")).toBeInTheDocument();
    expect(screen.queryByText("MRP calculation started")).not.toBeInTheDocument();
    expect(screen.queryByText("PO generated for LED-201")).not.toBeInTheDocument();
  });

  it("combined filters show intersection", async () => {
    const user = userEvent.setup();
    render(<LiveLogs logs={mockLogs} onClear={onClear} />);

    // Activate agent filter for Buyer
    const allButtons = screen.getAllByRole("button");
    const buyerButton = allButtons.find(
      (btn) => btn.textContent === "Buyer" && btn.className.includes("text-[10px]")
    );
    await user.click(buyerButton!);

    // Activate type filter for "error"
    const errorTypeButton = allButtons.find(
      (btn) => btn.textContent === "error" && btn.className.includes("capitalize")
    );
    await user.click(errorTypeButton!);

    // Buyer + error type = no logs match (Buyer log is "success", not "error")
    expect(screen.queryByText("MRP calculation started")).not.toBeInTheDocument();
    expect(screen.queryByText("PO generated for LED-201")).not.toBeInTheDocument();
    expect(screen.queryByText("Batch failed inspection")).not.toBeInTheDocument();
    expect(screen.getByText("No logs match the current filters.")).toBeInTheDocument();
  });

  it("Clear Filters button resets all filters", async () => {
    const user = userEvent.setup();
    render(<LiveLogs logs={mockLogs} onClear={onClear} />);

    // Apply a search filter first
    const searchInput = screen.getByPlaceholderText("Search logs...");
    await user.type(searchInput, "MRP");

    // Only one log visible
    expect(screen.queryByText("PO generated for LED-201")).not.toBeInTheDocument();

    // Click Clear Filters
    const clearFiltersButton = screen.getByRole("button", { name: /Clear Filters/i });
    await user.click(clearFiltersButton);

    // All logs should be visible again
    expect(screen.getByText("MRP calculation started")).toBeInTheDocument();
    expect(screen.getByText("PO generated for LED-201")).toBeInTheDocument();
    expect(screen.getByText("Batch failed inspection")).toBeInTheDocument();
  });

  it('entry count shows "X of Y entries" when filters are active', async () => {
    const user = userEvent.setup();
    render(<LiveLogs logs={mockLogs} onClear={onClear} />);

    // Without filters, should show total entry count
    expect(screen.getByText("3 entries")).toBeInTheDocument();

    // Apply search filter
    const searchInput = screen.getByPlaceholderText("Search logs...");
    await user.type(searchInput, "MRP");

    // Should show "1 of 3 entries"
    expect(screen.getByText("1 of 3 entries")).toBeInTheDocument();
  });
});
