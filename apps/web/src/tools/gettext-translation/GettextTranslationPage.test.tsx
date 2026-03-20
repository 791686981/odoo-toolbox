import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  settings: vi.fn().mockResolvedValue({
    default_source_language: "en_US",
    default_target_language: "zh_CN",
    default_chunk_size: 20,
    default_concurrency: 2,
    default_overwrite_existing: false,
  }),
}));

vi.mock("../../shared/api/client", () => ({
  api: {
    settings: apiMock.settings,
  },
}));

import { GettextTranslationPage } from "./GettextTranslationPage";

describe("GettextTranslationPage", () => {
  it("renders the upload and settings section", () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <GettextTranslationPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText("上传与任务设置")).toBeInTheDocument();
    expect(screen.queryByLabelText("处理模式")).not.toBeInTheDocument();
  });

  it("shows translation mode after selecting a po file", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <GettextTranslationPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(input).not.toBeNull();

    fireEvent.change(input!, {
      target: {
        files: [new File(["msgid \"Save\""], "sample.po", { type: "text/plain" })],
      },
    });

    await waitFor(() => {
      expect(screen.getByLabelText("处理模式")).toBeInTheDocument();
    });
  });
});
