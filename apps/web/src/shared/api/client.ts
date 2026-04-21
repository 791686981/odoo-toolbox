import type {
  CreateDatabaseBackupNodePayload,
  DatabaseBackupDetailRecord,
  DatabaseBackupTreeRecord,
  GettextContextDraft,
  GettextProofreadPreview,
  GettextTranslationEntriesPage,
  GettextTranslationMode,
  GettextTranslationRun,
  ProofreadPreview,
  RuntimeSettings,
  SidebarTool,
  StoredFileRecord,
  ToolManifest,
  ToolRunRecord,
  TranslationJob,
  TranslationRow,
  TranslationRowsPage,
  UpdateDatabaseBackupNodePayload,
  UploadedFileRecord,
  User,
} from "./types";

type RequestOptions = RequestInit & {
  skipJson?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { skipJson, headers, ...rest } = options;
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    ...rest,
  });

  if (!response.ok) {
    const fallback = "请求失败";
    try {
      const payload = await response.json();
      throw new Error(payload.detail ?? fallback);
    } catch {
      throw new Error(fallback);
    }
  }

  if (skipJson || response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  login: (payload: { username: string; password: string }) =>
    request<User>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: () =>
    request<{ ok: boolean }>("/api/auth/logout", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  me: () => request<User>("/api/auth/me"),
  tools: () => request<ToolManifest[]>("/api/tools"),
  files: () => request<StoredFileRecord[]>("/api/files"),
  runs: () => request<ToolRunRecord[]>("/api/runs"),
  jobs: () => request<TranslationJob[]>("/api/jobs"),
  job: (jobId: string) => request<TranslationJob>(`/api/jobs/${jobId}`),
  rows: (jobId: string, page: number, pageSize: number) =>
    request<TranslationRowsPage>(`/api/jobs/${jobId}/rows?page=${page}&page_size=${pageSize}`),
  updateRow: (jobId: string, rowId: string, editedValue: string) =>
    request<TranslationRow>(`/api/jobs/${jobId}/rows/${rowId}`, {
      method: "PATCH",
      body: JSON.stringify({ edited_value: editedValue }),
    }),
  upload: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/api/files/upload", {
      method: "POST",
      body: formData,
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error("上传失败");
    }
    return (await response.json()) as UploadedFileRecord;
  },
  databaseBackupTree: () => request<DatabaseBackupTreeRecord>("/api/database-backups/tree"),
  databaseBackupNode: (nodeId: string) =>
    request<DatabaseBackupDetailRecord>(`/api/database-backups/nodes/${nodeId}`),
  createDatabaseBackupNode: async (payload: CreateDatabaseBackupNodePayload) => {
    const formData = new FormData();
    formData.append("name", payload.name);
    formData.append("database_name", payload.database_name);
    formData.append("odoo_version", payload.odoo_version);
    formData.append("source_type", payload.source_type);
    if (payload.parent_id) {
      formData.append("parent_id", payload.parent_id);
    }
    formData.append("is_main_root", String(payload.is_main_root ?? false));
    formData.append("note", payload.note ?? "");
    formData.append("file", payload.file);

    const response = await fetch("/api/database-backups/nodes", {
      method: "POST",
      body: formData,
      credentials: "include",
    });

    if (!response.ok) {
      const fallback = "请求失败";
      try {
        const result = await response.json();
        throw new Error(result.detail ?? fallback);
      } catch {
        throw new Error(fallback);
      }
    }

    return (await response.json()) as DatabaseBackupDetailRecord;
  },
  updateDatabaseBackupNode: (nodeId: string, payload: UpdateDatabaseBackupNodePayload) =>
    request<DatabaseBackupDetailRecord>(`/api/database-backups/nodes/${nodeId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  markDatabaseBackupMainRoot: (nodeId: string) =>
    request<DatabaseBackupDetailRecord>(`/api/database-backups/nodes/${nodeId}/mark-main-root`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  databaseBackupZipUrl: (nodeId: string) => `/api/database-backups/nodes/${nodeId}/zip`,
  createContextDraft: (payload: {
    uploaded_file_id: string;
    source_language: string;
    target_language: string;
  }) =>
    request<{ background: string }>("/api/tools/csv-translation/context-draft", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createJob: (payload: {
    uploaded_file_id: string;
    source_language: string;
    target_language: string;
    background_context: string;
    chunk_size: number;
    concurrency: number;
    overwrite_existing: boolean;
  }) =>
    request<TranslationJob>("/api/tools/csv-translation/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  exportJob: (jobId: string) =>
    request<{ file_id: string; filename: string }>(`/api/jobs/${jobId}/export`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  gettextRun: (runId: string) =>
    request<GettextTranslationRun>(`/api/tools/gettext-translation/runs/${runId}`),
  gettextEntries: (runId: string, page: number, pageSize: number) =>
    request<GettextTranslationEntriesPage>(
      `/api/tools/gettext-translation/runs/${runId}/entries?page=${page}&page_size=${pageSize}`,
    ),
  createGettextContextDraft: (payload: {
    uploaded_file_id: string;
    source_language: string;
    target_language: string;
  }) =>
    request<GettextContextDraft>("/api/tools/gettext-translation/context-draft", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createGettextJob: (payload: {
    uploaded_file_id: string;
    source_language: string;
    target_language: string;
    context_text: string;
    translation_mode: GettextTranslationMode;
    chunk_size: number;
    concurrency: number;
  }) =>
    request<GettextTranslationRun>("/api/tools/gettext-translation/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateGettextEntry: (
    runId: string,
    entryId: string,
    payload: {
      edited_value: string;
      edited_plural_values: Record<number, string>;
    },
  ) =>
    request(`/api/tools/gettext-translation/runs/${runId}/entries/${entryId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  proofreadGettextRun: (runId: string) =>
    request<GettextProofreadPreview>(`/api/tools/gettext-translation/runs/${runId}/proofread-preview`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  exportGettextRun: (runId: string) =>
    request<{ file_id: string; filename: string }>(`/api/tools/gettext-translation/runs/${runId}/export`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  proofreadJob: (jobId: string) =>
    request<ProofreadPreview>(`/api/jobs/${jobId}/proofread-preview`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  settings: () => request<RuntimeSettings>("/api/settings"),
  updateSettings: (payload: {
    default_source_language: string;
    default_target_language: string;
    default_chunk_size: number;
    default_concurrency: number;
    default_overwrite_existing: boolean;
  }) =>
    request<RuntimeSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};
