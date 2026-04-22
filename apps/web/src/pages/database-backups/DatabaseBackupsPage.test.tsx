import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  databaseBackupTree: vi.fn(),
  databaseBackupNode: vi.fn(),
  createDatabaseBackupNode: vi.fn(),
  updateDatabaseBackupNode: vi.fn(),
  deleteDatabaseBackupNode: vi.fn(),
  markDatabaseBackupMainRoot: vi.fn(),
  databaseBackupZipUrl: vi.fn(),
}));

vi.mock("../../shared/api/client", () => ({
  api: {
    databaseBackupTree: apiMock.databaseBackupTree,
    databaseBackupNode: apiMock.databaseBackupNode,
    createDatabaseBackupNode: apiMock.createDatabaseBackupNode,
    updateDatabaseBackupNode: apiMock.updateDatabaseBackupNode,
    deleteDatabaseBackupNode: apiMock.deleteDatabaseBackupNode,
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
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

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
              children: [
                {
                  id: "leaf-1",
                  name: "prod-main-uat-check",
                  database_name: "prod_main_uat_check",
                  odoo_version: "18.0",
                  parent_id: "branch-1",
                  source_type: "branch",
                  is_main_root: false,
                  created_at: "2026-04-21T11:00:00Z",
                  children: [],
                },
              ],
            },
          ],
        },
      ],
    });
    apiMock.databaseBackupNode.mockImplementation((nodeId: string) => {
      if (nodeId === "branch-1") {
        return Promise.resolve(
          buildDetail({
            id: "branch-1",
            name: "prod-main-uat",
            parent_id: "root-1",
            source_type: "branch",
            is_main_root: false,
            note: "UAT 分支备份。",
          }),
        );
      }
      if (nodeId === "leaf-1") {
        return Promise.resolve(
          buildDetail({
            id: "leaf-1",
            name: "prod-main-uat-check",
            parent_id: "branch-1",
            source_type: "branch",
            is_main_root: false,
            note: "末端验证备份。",
          }),
        );
      }
      return Promise.resolve(buildDetail());
    });
    apiMock.createDatabaseBackupNode.mockResolvedValue(buildDetail({ id: "new-root" }));
    apiMock.updateDatabaseBackupNode.mockResolvedValue(
      buildDetail({
        name: "prod-main-renamed",
        note: "updated",
        updated_at: "2026-04-21T10:00:00Z",
      }),
    );
    apiMock.deleteDatabaseBackupNode.mockResolvedValue(undefined);
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

  it("根节点显示在独立入口，分支树不重复显示根节点", async () => {
    renderPage();

    expect(await screen.findByRole("button", { name: /prod-main/ })).toBeInTheDocument();
    const branchTreePanel = document.querySelector(".database-backup-branch-tree-panel");
    expect(branchTreePanel).toBeInTheDocument();
    expect(within(branchTreePanel as HTMLElement).queryByText("prod-main")).not.toBeInTheDocument();
    expect(within(branchTreePanel as HTMLElement).getByText("prod-main-uat")).toBeInTheDocument();
  });

  it("分支树支持折叠节点", async () => {
    renderPage();

    expect(await screen.findByText("prod-main-uat-check")).toBeInTheDocument();
    const switcher = document.querySelector<HTMLElement>(".database-backup-tree .ant-tree-switcher");
    expect(switcher).toBeInTheDocument();
    fireEvent.click(switcher!);

    await waitFor(() => expect(screen.queryByText("prod-main-uat-check")).not.toBeInTheDocument());
  });

  it("新增分支按钮会根据当前节点切换文案", async () => {
    renderPage();

    expect(await screen.findAllByRole("button", { name: "新增一级分支" })).not.toHaveLength(0);

    fireEvent.click(await screen.findByText("prod-main-uat"));

    expect(await screen.findAllByRole("button", { name: "新增子分支" })).not.toHaveLength(0);
  });

  it("可以从分支树节点快捷新增子分支", async () => {
    renderPage();
    const file = new File(["zip-bytes"], "branch.zip", { type: "application/zip" });

    fireEvent.click(await screen.findByRole("button", { name: "给 prod-main-uat 新增子分支" }));
    fireEvent.change(screen.getByLabelText("节点名"), { target: { value: "prod-main-uat-next" } });

    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).toBeInTheDocument();
    fireEvent.change(fileInput!, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /确\s*认/ }));

    await waitFor(() => expect(apiMock.createDatabaseBackupNode).toHaveBeenCalled());
    const [payload] = apiMock.createDatabaseBackupNode.mock.calls[0];
    expect(payload).toEqual(
      expect.objectContaining({
        name: "prod-main-uat-next",
        parent_id: "branch-1",
        source_type: "branch",
        file,
      }),
    );
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
    fireEvent.click(screen.getByRole("button", { name: /确\s*认/ }));

    expect(await screen.findByText("请上传 zip 备份文件")).toBeInTheDocument();
  });

  it("创建节点表单只要求节点名和 zip 文件", async () => {
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "新建根节点" }));

    expect(screen.getByLabelText("节点名")).toBeInTheDocument();
    expect(screen.getByText("zip 备份文件")).toBeInTheDocument();
    expect(screen.queryByLabelText("数据库名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Odoo 版本")).not.toBeInTheDocument();
  });

  it("选择 zip 后创建节点会提交节点名和文件", async () => {
    renderPage();
    const file = new File(["zip-bytes"], "prod-main.zip", { type: "application/zip" });

    fireEvent.click(await screen.findByRole("button", { name: "新建根节点" }));
    fireEvent.change(screen.getByLabelText("节点名"), { target: { value: "prod-main-20260422" } });

    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).toBeInTheDocument();
    fireEvent.change(fileInput!, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /确\s*认/ }));

    await waitFor(() => expect(apiMock.createDatabaseBackupNode).toHaveBeenCalled());
    const [payload] = apiMock.createDatabaseBackupNode.mock.calls[0];
    expect(payload).toEqual(
      expect.objectContaining({
        name: "prod-main-20260422",
        file,
      }),
    );
    expect(payload).not.toHaveProperty("database_name");
    expect(payload).not.toHaveProperty("odoo_version");
  });

  it("点击选择 zip 文件按钮时会触发文件选择框", async () => {
    const inputClickSpy = vi.spyOn(HTMLInputElement.prototype, "click");

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "新建根节点" }));
    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');

    expect(fileInput).toBeInTheDocument();
    expect(fileInput?.getAttribute("style")).toContain("display: none");

    fireEvent.click(screen.getByRole("button", { name: "选择 zip 文件" }));

    expect(inputClickSpy).toHaveBeenCalled();
  });

  it("编辑节点时只提交可编辑字段", async () => {
    renderPage();

    await screen.findByText("生产主线数据库备份。");
    fireEvent.change(screen.getByLabelText("节点名"), { target: { value: "prod-main-renamed" } });
    fireEvent.change(screen.getByLabelText("备注"), { target: { value: "updated" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() =>
      expect(apiMock.updateDatabaseBackupNode).toHaveBeenCalledWith("root-1", {
        name: "prod-main-renamed",
        note: "updated",
      }),
    );
  });

  it("可以复制当前节点 ID", async () => {
    renderPage();

    await screen.findByText("生产主线数据库备份。");
    fireEvent.click(screen.getByRole("button", { name: "复制节点 ID" }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("root-1");
    });
  });

  it("详情里保留节点 ID，但不再直接展示 zip 校验值", async () => {
    renderPage();

    expect(await screen.findByText("root-1")).toBeInTheDocument();
    expect(screen.queryByText("abc123def456")).not.toBeInTheDocument();
  });

  it("叶子节点可以从详情面板删除", async () => {
    renderPage();

    fireEvent.click(await screen.findByText("prod-main-uat-check"));
    expect(await screen.findByText("末端验证备份。")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "删除节点" }));

    await waitFor(() => expect(apiMock.deleteDatabaseBackupNode).toHaveBeenCalledWith("leaf-1"));
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
