import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { DBViewer } from "../DBViewer";
import { api } from "@/lib/api";

// Mock the api module
vi.mock("@/lib/api", () => ({
  api: {
    getDBTable: vi.fn(),
  },
}));

// Mock next/link since DBViewer uses it for the Dashboard back-link
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

// Mock URL.createObjectURL / revokeObjectURL for CSV export
if (typeof URL.createObjectURL === "undefined") {
  URL.createObjectURL = vi.fn(() => "blob:mock-url");
}
if (typeof URL.revokeObjectURL === "undefined") {
  URL.revokeObjectURL = vi.fn();
}

// Generate 30 supplier rows to test pagination (25 per page)
const mockSupplierRows = Array.from({ length: 30 }, (_, i) => ({
  id: i + 1,
  name: `Supplier ${i + 1}`,
  contact_email: `supplier${i + 1}@example.com`,
  lead_time_days: 7 + i,
}));

const mockPartRows = [
  { id: 1, part_id: "CH-101", description: "Modular Chassis", category: "Common Core" },
  { id: 2, part_id: "SW-303", description: "Switch Assembly", category: "Common Core" },
];

const mockEmptyRows: Record<string, unknown>[] = [];

describe("DBViewer", () => {
  const mockedGetDBTable = vi.mocked(api.getDBTable);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders tab list with table names", async () => {
    mockedGetDBTable.mockResolvedValue(mockSupplierRows);

    render(<DBViewer />);

    // The component should render tab triggers for each table in the TABLES constant
    expect(screen.getByRole("tab", { name: "Suppliers" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Parts" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Inventory" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "BOM" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Purchase Orders" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Demand Forecast" })).toBeInTheDocument();
  });

  it("fetches and renders table data on mount", async () => {
    mockedGetDBTable.mockResolvedValue(mockSupplierRows);

    render(<DBViewer />);

    // Should have called getDBTable with the first tab's endpoint (suppliers)
    expect(mockedGetDBTable).toHaveBeenCalledWith("/api/db/suppliers");

    // Wait for the async data to render — check column headers
    await screen.findByText("id");
    expect(screen.getByText("name")).toBeInTheDocument();
    expect(screen.getByText("contact_email")).toBeInTheDocument();
    expect(screen.getByText("lead_time_days")).toBeInTheDocument();

    // Verify first row values render
    expect(screen.getByText("Supplier 1")).toBeInTheDocument();
    expect(screen.getByText("supplier1@example.com")).toBeInTheDocument();
  });

  it("shows pagination when rows exceed 25", async () => {
    mockedGetDBTable.mockResolvedValue(mockSupplierRows);

    render(<DBViewer />);

    // Wait for data to load and pagination to appear
    // 30 rows / 25 per page = 2 pages
    await screen.findByText("Page 1 of 2", { exact: false });

    // Pagination buttons should exist
    expect(screen.getByRole("button", { name: "Previous" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();

    // Previous should be disabled on page 1
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    // Next should be enabled
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("Next button advances to page 2", async () => {
    mockedGetDBTable.mockResolvedValue(mockSupplierRows);
    const user = userEvent.setup();

    render(<DBViewer />);

    // Wait for page 1 to render
    await screen.findByText("Page 1 of 2", { exact: false });

    // Verify first-page data is visible (Supplier 1) and second-page data is not (Supplier 26)
    expect(screen.getByText("Supplier 1")).toBeInTheDocument();
    expect(screen.queryByText("Supplier 26")).not.toBeInTheDocument();

    // Click Next
    const nextButton = screen.getByRole("button", { name: "Next" });
    await user.click(nextButton);

    // Should now show page 2
    await waitFor(() => {
      expect(screen.getByText("Page 2 of 2", { exact: false })).toBeInTheDocument();
    });

    // Page 2 data should be visible (rows 26-30), page 1 data should not
    expect(screen.getByText("Supplier 26")).toBeInTheDocument();
    expect(screen.queryByText("Supplier 1")).not.toBeInTheDocument();

    // Next should now be disabled on last page, Previous should be enabled
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();
  });

  it("shows empty state when no records are returned", async () => {
    mockedGetDBTable.mockResolvedValue(mockEmptyRows);

    render(<DBViewer />);

    // Wait for the empty state message
    await screen.findByText("No records found.");

    // Pagination should not be present
    expect(screen.queryByText("Previous")).not.toBeInTheDocument();
    expect(screen.queryByText("Next")).not.toBeInTheDocument();
  });

  it("tab switch triggers a new fetch with the correct endpoint", async () => {
    // First call returns suppliers, second call returns parts
    mockedGetDBTable
      .mockResolvedValueOnce(mockSupplierRows)
      .mockResolvedValueOnce(mockPartRows);

    const user = userEvent.setup();

    render(<DBViewer />);

    // Wait for initial fetch to complete
    await screen.findByText("Supplier 1");

    // The first call should be for suppliers
    expect(mockedGetDBTable).toHaveBeenCalledWith("/api/db/suppliers");

    // Click the "Parts" tab
    const partsTab = screen.getByRole("tab", { name: "Parts" });
    await user.click(partsTab);

    // Should trigger a new fetch with the parts endpoint
    await waitFor(() => {
      expect(mockedGetDBTable).toHaveBeenCalledWith("/api/db/parts");
    });

    // Wait for the parts data to render
    await screen.findByText("CH-101");
    expect(screen.getByText("Modular Chassis")).toBeInTheDocument();
    expect(screen.getByText("Switch Assembly")).toBeInTheDocument();
  });
});
