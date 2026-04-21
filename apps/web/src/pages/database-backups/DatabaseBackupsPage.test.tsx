import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  databaseBackupTree: vi.fn(),
  databaseBackupNode: vi.fn(),
  createDatabaseBackupNode: vi.fn(),
  updateDatabaseBackupNode: vi.fn(),
  markDatabaseBackupMainRoot: vi.fn(),
  databaseBackupZipUrl: vi.fn(),
}));

vi.mock("../../shared/api/client", () => ({
  api: {
    databaseBackupTree: apiMock.databaseBackupTree,
    databaseBackupNode: apiMock.databaseBackupNode,
    createDatabaseBackupNode: apiMock.createDatabaseBackupNode,
    updateDatabaseBackupNode: apiMock.updateDatabaseBackupNode,
    markDatabaseBackupMainRoot: apiMock.markDatabaseBackupMainRoot,
    databaseBackupZipUrl: apiMock.databaseBackupZipUrl,
  },
}));

import { DatabaseBackupsPage } from "./DatabaseBackupsPage";

function buildDetail(overrides: Record<string, unknown> = {}) {
  return {
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
    ...overrides,
  };
}

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
    apiMock.databaseBackupNode.mockResolvedValue(buildDetail());
    apiMock.createDatabaseBackupNode.mockResolvedValue(buildDetail({ id: "new-root" }));
    apiMock.updateDatabaseBackupNode.mockResolvedValue(
      buildDetail({
        name: "prod-main-renamed",
        note: "updated",
        updated_at: "2026-04-21T10:00:00Z",
      }),
    );
    apiMock.markDatabaseBackupMainRoot.mockResolvedValue(buildDetail({ is_main_root: true }));
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

  it("创建根节点时要求上传 zip 文件", async () => {
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "新建根节点" }));
    fireEvent.change(screen.getByLabelText("节点名"), { target: { value: "prod-main-20260422" } });
    fireEvent.change(screen.getByLabelText("数据库名"), { target: { value: "prod_main_20260422" } });
    fireEvent.change(screen.getByLabelText("Odoo 版本"), { target: { value: "18.0" } });
    fireEvent.click(screen.getByRole("button", { name: /确\s*认/ }));

    expect(await screen.findByText("请上传 zip 备份文件")).toBeInTheDocument();
  });

  it("编辑节点时只提交可编辑字段", async () => {
    renderPage();

    await screen.findByText("生产主线数据库备份。");
    fireEvent.click(await screen.findByRole("button", { name: "编辑节点" }));
    fireEvent.change(screen.getByLabelText("节点名"), { target: { value: "prod-main-renamed" } });
    fireEvent.change(screen.getByLabelText("备注"), { target: { value: "updated" } });
    fireEvent.click(screen.getByRole("button", { name: /确\s*认/ }));

    await waitFor(() =>
      expect(apiMock.updateDatabaseBackupNode).toHaveBeenCalledWith("root-1", {
        name: "prod-main-renamed",
        note: "updated",
      }),
    );
  });

  it("从详情面板触发设为主线操作", async () => {
    apiMock.databaseBackupNode.mockResolvedValueOnce(
      buildDetail({
        is_main_root: false,
      }),
    );
    apiMock.markDatabaseBackupMainRoot.mockResolvedValueOnce(
      buildDetail({
        is_main_root: true,
      }),
    );

    renderPage();

    await screen.findByText("生产主线数据库备份。");
    const markButton = await screen.findByRole("button", { name: "设为主线" });
    await waitFor(() => expect(markButton).toBeEnabled());
    fireEvent.click(markButton);

    await waitFor(() => expect(apiMock.markDatabaseBackupMainRoot).toHaveBeenCalledWith("root-1"));
  });
});
