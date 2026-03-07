import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { DigitalDock } from "../DigitalDock";
import { api } from "@/lib/api";
import { toast } from "sonner";

// Hoist mock data so vi.mock factories can reference it
const { mockOrders, mockInspections } = vi.hoisted(() => {
  const mockOrders = [
    {
      po_number: "PO-001",
      part_id: "LED-201",
      supplier: "CREE Inc.",
      quantity: 500,
      unit_cost: 11.5,
      total_cost: 5750,
      status: "PENDING_APPROVAL",
      created_at: "2026-02-28T10:00:00Z",
      triggered_by: "Buyer",
    },
    {
      po_number: "PO-002",
      part_id: "CH-231",
      supplier: "Apex CNC Works",
      quantity: 100,
      unit_cost: 8.0,
      total_cost: 800,
      status: "APPROVED",
      created_at: "2026-02-28T09:00:00Z",
      triggered_by: "Buyer",
    },
  ];

  const mockInspections = [
    {
      id: 1,
      part: "LED-201",
      batch_size: 100,
      result: "PASS",
      notes: null,
      inspected_at: "2026-02-28T10:00:00Z",
    },
    {
      id: 2,
      part: "CH-231",
      batch_size: 50,
      result: "FAIL",
      notes: "Tolerance exceeded",
      inspected_at: "2026-02-28T10:01:00Z",
    },
  ];

  return { mockOrders, mockInspections };
});

vi.mock("@/lib/api", () => ({
  api: {
    getQualityInspections: vi.fn(),
    getOrders: vi.fn(),
    updateOrderStatus: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { id: 1, email: "admin@test.com", name: "Admin", role: "admin", picture: null, is_active: true },
    token: "fake-token",
    loading: false,
    logout: vi.fn(),
  }),
  hasRole: (user: { role: string } | null, ...roles: string[]) =>
    user !== null && roles.includes(user.role),
}));

const mockedGetQualityInspections = vi.mocked(api.getQualityInspections);
const mockedGetOrders = vi.mocked(api.getOrders);
const mockedUpdateOrderStatus = vi.mocked(api.updateOrderStatus);
const mockedToastSuccess = vi.mocked(toast.success);

describe("DigitalDock", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetQualityInspections.mockResolvedValue(mockInspections);
    mockedGetOrders.mockResolvedValue(mockOrders);
    mockedUpdateOrderStatus.mockResolvedValue({
      ...mockOrders[0],
      status: "APPROVED",
    });
    // Mock window.prompt for rejection reason dialog
    vi.stubGlobal("prompt", vi.fn().mockReturnValue("test reason"));
  });

  it("renders quality inspections with PASS/FAIL badges after loading", async () => {
    render(<DigitalDock />);

    // Wait for the data to load and inspections to appear
    expect(await screen.findByText("PASS")).toBeInTheDocument();
    expect(screen.getByText("FAIL")).toBeInTheDocument();

    // Verify part IDs are rendered
    expect(screen.getByText("LED-201")).toBeInTheDocument();
    expect(screen.getByText("CH-231")).toBeInTheDocument();

    // Verify the FAIL notes are visible
    expect(screen.getByText("Tolerance exceeded")).toBeInTheDocument();
  });

  it("switches to Purchase Orders tab and shows order list", async () => {
    const user = userEvent.setup();
    render(<DigitalDock />);

    // Wait for loading to finish
    await screen.findByText("PASS");

    // Click the Purchase Orders tab
    await user.click(screen.getByRole("tab", { name: /Purchase Orders/i }));

    // Both PO numbers should be visible
    expect(await screen.findByText("PO-001")).toBeInTheDocument();
    expect(screen.getByText("PO-002")).toBeInTheDocument();

    // Status badges should be visible
    expect(screen.getByText("PENDING_APPROVAL")).toBeInTheDocument();
    expect(screen.getByText("APPROVED")).toBeInTheDocument();
  });

  it("shows Approve/Reject buttons when a PENDING_APPROVAL PO is expanded", async () => {
    const user = userEvent.setup();
    render(<DigitalDock />);

    // Wait for loading to finish
    await screen.findByText("PASS");

    // Switch to Purchase Orders tab
    await user.click(screen.getByRole("tab", { name: /Purchase Orders/i }));
    await screen.findByText("PO-001");

    // Click on PO-001 row to expand it (it is PENDING_APPROVAL)
    await user.click(screen.getByText("PO-001"));

    // Approve and Reject buttons should now be visible inside the expanded section.
    // Use exact name match to avoid matching the PO-002 row button whose
    // accessible name contains "APPROVED".
    expect(
      await screen.findByRole("button", { name: /^Approve$/ })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Reject$/ })
    ).toBeInTheDocument();

    // Financial constitution warning should be visible
    expect(
      screen.getByText("Financial Constitution Triggered")
    ).toBeInTheDocument();
  });

  it("calls updateOrderStatus with APPROVED when Approve button is clicked", async () => {
    const user = userEvent.setup();
    render(<DigitalDock />);

    // Wait for loading
    await screen.findByText("PASS");

    // Switch to Purchase Orders tab
    await user.click(screen.getByRole("tab", { name: /Purchase Orders/i }));
    await screen.findByText("PO-001");

    // Expand PO-001
    await user.click(screen.getByText("PO-001"));
    const approveButton = await screen.findByRole("button", {
      name: /^Approve$/,
    });

    // Click Approve
    await user.click(approveButton);

    await waitFor(() => {
      expect(mockedUpdateOrderStatus).toHaveBeenCalledWith(
        "PO-001",
        "APPROVED",
        undefined
      );
    });

    // Verify toast was called
    await waitFor(() => {
      expect(mockedToastSuccess).toHaveBeenCalledWith("PO PO-001 approved");
    });
  });

  it("calls updateOrderStatus with CANCELLED when Reject button is clicked", async () => {
    const user = userEvent.setup();
    render(<DigitalDock />);

    // Wait for loading
    await screen.findByText("PASS");

    // Switch to Purchase Orders tab
    await user.click(screen.getByRole("tab", { name: /Purchase Orders/i }));
    await screen.findByText("PO-001");

    // Expand PO-001
    await user.click(screen.getByText("PO-001"));
    const rejectButton = await screen.findByRole("button", {
      name: /^Reject$/,
    });

    // Click Reject — window.prompt is mocked to return "test reason"
    await user.click(rejectButton);

    await waitFor(() => {
      expect(mockedUpdateOrderStatus).toHaveBeenCalledWith(
        "PO-001",
        "CANCELLED",
        "test reason"
      );
    });

    // Verify toast was called
    await waitFor(() => {
      expect(mockedToastSuccess).toHaveBeenCalledWith("PO PO-001 rejected");
    });
  });

  it("displays correct summary stats for approved and pending counts", async () => {
    const user = userEvent.setup();
    render(<DigitalDock />);

    // Wait for loading to finish on inspections tab
    await screen.findByText("PASS");

    // Switch to Purchase Orders tab to see PO summary stats
    await user.click(screen.getByRole("tab", { name: /Purchase Orders/i }));
    await screen.findByText("PO-001");

    // Approved count: 1 (PO-002 is APPROVED)
    const approvedLabel = screen.getByText("Approved:");
    expect(approvedLabel.nextElementSibling).toHaveTextContent("1");

    // Pending count: 1 (PO-001 is PENDING_APPROVAL)
    const pendingLabel = screen.getByText("Pending:");
    expect(pendingLabel.nextElementSibling).toHaveTextContent("1");
  });
});
