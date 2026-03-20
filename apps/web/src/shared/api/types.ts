export type User = {
  username: string;
};

export type ToolManifest = {
  id: string;
  title: string;
  description: string;
  route: string;
  icon: string;
  category: string;
  enabled: boolean;
  order: number;
  capabilities: string[];
};

export type UploadedFileRecord = {
  id: string;
  original_name: string;
  mime_type: string;
  size: number;
  created_at: string;
};

export type StoredFileRecord = UploadedFileRecord & {
  kind: string;
  run_id?: string | null;
  tool_id?: string | null;
  artifact_label?: string | null;
};

export type ToolRunRecord = {
  id: string;
  tool_id: string;
  status: string;
  summary: string;
  error_message: string;
  created_at: string;
  updated_at: string;
};

export type TranslationJob = {
  id: string;
  status: string;
  progress: number;
  source_language: string;
  target_language: string;
  context_text: string;
  overwrite_existing: boolean;
  chunk_size: number;
  concurrency: number;
  total_rows: number;
  processed_rows: number;
  error_message: string;
  uploaded_file_id: string;
  exported_file_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type TranslationRow = {
  id: string;
  row_number: number;
  module: string;
  record_type: string;
  name: string;
  res_id: string;
  source_text: string;
  original_value: string;
  translated_value: string;
  edited_value: string;
  comments: string;
  status: string;
};

export type TranslationRowsPage = {
  items: TranslationRow[];
  total: number;
  page: number;
  page_size: number;
};

export type GettextTranslationMode = "blank" | "blank_and_fuzzy" | "overwrite_all";

export type GettextTranslationRun = {
  id: string;
  tool_id: string;
  status: string;
  progress: number;
  input_file_type: string;
  translation_mode: GettextTranslationMode;
  source_language: string;
  target_language: string;
  context_text: string;
  chunk_size: number;
  concurrency: number;
  total_entries: number;
  processed_entries: number;
  error_message: string;
  uploaded_file_id: string;
  exported_file_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type GettextTranslationEntry = {
  id: string;
  entry_index: number;
  msgctxt: string;
  msgid: string;
  msgid_plural: string;
  msgstr: string;
  msgstr_plural: Record<number, string>;
  translated_value: string;
  translated_plural_values: Record<number, string>;
  edited_value: string;
  edited_plural_values: Record<number, string>;
  comment: string;
  tcomment: string;
  occurrences: string[][];
  flags: string[];
  status: string;
  is_plural: boolean;
  is_fuzzy: boolean;
};

export type GettextTranslationEntriesPage = {
  items: GettextTranslationEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type ProofreadSuggestion = {
  row_id: string;
  row_number: number;
  source_text: string;
  current_value: string;
  suggested_value: string;
  reason: string;
};

export type ProofreadPreview = {
  model: string;
  items: ProofreadSuggestion[];
};

export type RuntimeSettings = {
  openai_base_url: string;
  openai_translation_model: string;
  openai_review_model: string;
  default_source_language: string;
  default_target_language: string;
  default_chunk_size: number;
  default_concurrency: number;
  default_overwrite_existing: boolean;
};

export type SidebarTool = ToolManifest & {
  section: "tool" | "platform";
};
