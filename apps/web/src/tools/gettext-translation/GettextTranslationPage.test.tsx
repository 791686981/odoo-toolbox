import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  settings: vi.fn(),
  upload: vi.fn(),
  createGettextContextDraft: vi.fn(),
  createGettextJob: vi.fn(),
  gettextRun: vi.fn(),
  gettextEntries: vi.fn(),
  proofreadGettextRun: vi.fn(),
  updateGettextEntry: vi.fn(),
  exportGettextRun: vi.fn(),
}));

vi.mock("../../shared/api/client", () => ({
  api: {
    settings: apiMock.settings,
    upload: apiMock.upload,
    createGettextContextDraft: apiMock.createGettextContextDraft,
    createGettextJob: apiMock.createGettextJob,
    gettextRun: apiMock.gettextRun,
    gettextEntries: apiMock.gettextEntries,
    proofreadGettextRun: apiMock.proofreadGettextRun,
    updateGettextEntry: apiMock.updateGettextEntry,
    exportGettextRun: apiMock.exportGettextRun,
  },
}));

import { GettextTranslationPage } from "./GettextTranslationPage";

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
        <GettextTranslationPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GettextTranslationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "getComputedStyle").mockImplementation(
      () =>
        ({
          getPropertyValue: () => "",
        }) as unknown as CSSStyleDeclaration,
    );
    apiMock.settings.mockResolvedValue({
      default_source_language: "en_US",
      default_target_language: "zh_CN",
      default_chunk_size: 20,
      default_concurrency: 2,
      default_overwrite_existing: false,
    });
    apiMock.upload.mockResolvedValue({
      id: "file-1",
      original_name: "sample.pot",
      mime_type: "text/plain",
      size: 1024,
      created_at: "2026-03-20T00:00:00Z",
    });
    apiMock.createGettextContextDraft.mockResolvedValue({
      background: "统一使用 Odoo 后台常见术语。",
    });
    apiMock.createGettextJob.mockResolvedValue({
      id: "run-1",
    });
    apiMock.gettextRun.mockResolvedValue(undefined);
    apiMock.gettextEntries.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
    apiMock.proofreadGettextRun.mockResolvedValue({
      model: "gpt-4.1-mini",
      items: [],
    });
    apiMock.updateGettextEntry.mockResolvedValue({});
    apiMock.exportGettextRun.mockResolvedValue({
      file_id: "file-2",
      filename: "sample.zh_CN.po",
    });
  });

  it("renders the upload and settings section", () => {
    renderPage();

    expect(screen.getByText("上传与任务设置")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /生成术语与上下文说明/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /翻译内容/ })).toBeDisabled();
    expect(screen.queryByLabelText("处理模式")).not.toBeInTheDocument();
  });

  it("shows translation mode after selecting a po file", async () => {
    const { container } = renderPage();

    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(input).not.toBeNull();

    fireEvent.change(input!, {
      target: {
        files: [new File(["msgid \"Save\""], "sample.po", { type: "text/plain" })],
      },
    });

    await waitFor(() => {
      expect(apiMock.upload).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(screen.getByLabelText("处理模式")).toBeInTheDocument();
    });
  });

  it("enables translation only after generating context", async () => {
    const { container } = renderPage();

    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(input).not.toBeNull();

    fireEvent.change(input!, {
      target: {
        files: [new File(["msgid \"Save\""], "sample.pot", { type: "text/plain" })],
      },
    });

    await waitFor(() => {
      expect(apiMock.upload).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("en_US")).toBeInTheDocument();
      expect(screen.getByDisplayValue("zh_CN")).toBeInTheDocument();
    });

    const translateButton = screen.getByRole("button", { name: /翻译内容/ });
    expect(translateButton).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /生成术语与上下文说明/ }));

    await waitFor(() => {
      expect(apiMock.createGettextContextDraft).toHaveBeenCalled();
    });
    expect(apiMock.createGettextContextDraft.mock.calls[0][0]).toEqual({
      uploaded_file_id: "file-1",
      source_language: "en_US",
      target_language: "zh_CN",
    });

    expect(await screen.findByDisplayValue("统一使用 Odoo 后台常见术语。")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /翻译内容/ })).toBeEnabled();
    });
  });

  it("opens gettext proofread suggestions and applies plural suggestion", async () => {
    apiMock.gettextRun.mockResolvedValue({
      id: "run-1",
      tool_id: "gettext-translation",
      status: "completed",
      progress: 100,
      input_file_type: "pot",
      translation_mode: "blank",
      source_language: "en_US",
      target_language: "zh_CN",
      context_text: "统一使用文件模块术语。",
      chunk_size: 20,
      concurrency: 2,
      total_entries: 2,
      processed_entries: 2,
      error_message: "",
      uploaded_file_id: "file-1",
      exported_file_id: null,
      created_at: "2026-03-20T00:00:00Z",
      updated_at: "2026-03-20T00:00:00Z",
    });
    apiMock.gettextEntries.mockResolvedValue({
      items: [
        {
          id: "entry-1",
          entry_index: 1,
          msgctxt: "",
          msgid: "Save",
          msgid_plural: "",
          msgstr: "",
          msgstr_plural: {},
          translated_value: "保存",
          translated_plural_values: {},
          edited_value: "",
          edited_plural_values: {},
          comment: "",
          tcomment: "",
          occurrences: [],
          flags: [],
          status: "translated",
          is_plural: false,
          is_fuzzy: false,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });
    apiMock.proofreadGettextRun.mockResolvedValue({
      model: "gpt-4.1-mini",
      items: [
        {
          entry_id: "entry-2",
          entry_index: 2,
          msgid: "File",
          msgid_plural: "Files",
          current_value: "",
          current_plural_values: { 0: "文件", 1: "多个文件" },
          suggested_value: "",
          suggested_plural_values: { 0: "文件", 1: "文件列表" },
          reason: "复数术语更统一。",
          is_plural: true,
        },
      ],
    });

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/tools/gettext-translation?runId=run-1"]}>
          <GettextTranslationPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /AI 校对/ })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: /AI 校对/ }));

    expect(await screen.findByText("AI 校对建议")).toBeInTheDocument();
    expect(await screen.findByText("复数术语更统一。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "采用" }));

    await waitFor(() => {
      expect(apiMock.updateGettextEntry).toHaveBeenCalled();
    });
    expect(apiMock.updateGettextEntry.mock.calls[0][0]).toBe("run-1");
    expect(apiMock.updateGettextEntry.mock.calls[0][1]).toBe("entry-2");
    expect(apiMock.updateGettextEntry.mock.calls[0][2]).toEqual({
      edited_value: "",
      edited_plural_values: { 0: "文件", 1: "文件列表" },
    });
  });
});
