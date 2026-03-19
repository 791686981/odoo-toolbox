import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  me: vi.fn(),
  tools: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("../shared/api/client", () => ({
  api: {
    me: apiMock.me,
    tools: apiMock.tools,
    logout: apiMock.logout,
  },
}));

import { ShellLayout } from "./ShellLayout";

function renderShellLayout() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/tools/csv-translation"]}>
        <Routes>
          <Route path="/" element={<ShellLayout />}>
            <Route path="tools/csv-translation" element={<div>CSV 内容区</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ShellLayout", () => {
  beforeEach(() => {
    apiMock.me.mockResolvedValue({
      username: "admin",
    });
    apiMock.tools.mockResolvedValue([
      {
        id: "csv-translation",
        title: "CSV 翻译",
        description: "CSV 翻译工具",
        route: "/tools/csv-translation",
        icon: "translation",
        category: "translation",
        enabled: true,
        order: 10,
        capabilities: ["upload", "translation"],
      },
    ]);
    apiMock.logout.mockResolvedValue({ ok: true });
  });

  it("keeps the shell compact and lets the sidebar collapse", async () => {
    renderShellLayout();

    expect(await screen.findByRole("button", { name: "收起侧边栏" })).toBeInTheDocument();
    expect(screen.queryByText("Internal Command Deck")).not.toBeInTheDocument();
    expect(screen.queryByText("内部工具箱")).not.toBeInTheDocument();
    expect(
      screen.queryByText("面向 Odoo 翻译、分析、生成与检查场景的内部工具平台，统一承接工具入口、运行记录和文件资产。"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Odoo Toolbox")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "收起侧边栏" }));

    expect(await screen.findByRole("button", { name: "展开侧边栏" })).toBeInTheDocument();
    expect(screen.queryByText("Odoo Toolbox")).not.toBeInTheDocument();
  });
});
