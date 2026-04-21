import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  databaseBackupTree: vi.fn(),
  databaseBackupNode: vi.fn(),
  databaseBackupZipUrl: vi.fn(),
}));

vi.mock("../../shared/api/client", () => ({
  api: {
    databaseBackupTree: apiMock.databaseBackupTree,
    databaseBackupNode: apiMock.databaseBackupNode,
    databaseBackupZipUrl: apiMock.databaseBackupZipUrl,
  },
}));

import { DatabaseBackupsPage } from "./DatabaseBackupsPage";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DatabaseBackupsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DatabaseBackupsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "getComputedStyle").mockImplementation(
      () =>
        ({
          getPropertyValue: () => "",
        }) as unknown as CSSStyleDeclaration,
    );

    apiMock.databaseBackupTree.mockResolvedValue({
      main_root_id: "root-1",
      items: [
        {
          id: "root-1",
          name: "prod-main",
          database_name: "prod_main",
          odoo_version: "18.0",
          parent_id: null,
          source_type: "root",
          is_main_root: true,
          created_at: "2026-04-21T09:30:00Z",
          children: [
            {
              id: "branch-1",
              name: "prod-main-uat",
              database_name: "prod_main_uat",
              odoo_version: "18.0",
              parent_id: "root-1",
              source_type: "branch",
              is_main_root: false,
              created_at: "2026-04-21T10:00:00Z",
              children: [],
            },
          ],
        },
      ],
    });
    apiMock.databaseBackupNode.mockResolvedValue({
      id: "root-1",
      name: "prod-main",
      database_name: "prod_main",
      odoo_version: "18.0",
      parent_id: null,
      source_type: "root",
      is_main_root: true,
      note: "生产主线数据库备份。",
      created_at: "2026-04-21T09:30:00Z",
      updated_at: "2026-04-21T09:30:00Z",
      zip: {
        file_id: "file-1",
        filename: "prod-main-20260421.zip",
        size: 2048,
        mime_type: "application/zip",
        sha256: "abc123def456",
        download_url: "/api/database-backups/nodes/root-1/zip",
      },
    });
    apiMock.databaseBackupZipUrl.mockReturnValue("/api/database-backups/nodes/root-1/zip");
  });

  it("显示页面标题", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "数据库备份库" })).toBeInTheDocument();
  });

  it("显示树节点名称", async () => {
    renderPage();

    expect(await screen.findByText("prod-main")).toBeInTheDocument();
  });

  it("默认选中节点后显示详情备注", async () => {
    renderPage();

    expect(await screen.findByText("生产主线数据库备份。")).toBeInTheDocument();
  });

  it("切换到命名与升级规范标签后显示数据库命名规范", async () => {
    renderPage();

    fireEvent.click(await screen.findByRole("tab", { name: "命名与升级规范" }));

    expect(await screen.findByText("数据库命名规范")).toBeInTheDocument();
  });
});
