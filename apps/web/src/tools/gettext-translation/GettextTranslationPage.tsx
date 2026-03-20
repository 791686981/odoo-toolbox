import {
  ExportOutlined,
  InboxOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { UploadRequestOption } from "rc-upload/lib/interface";

import { api } from "../../shared/api/client";
import type {
  GettextProofreadSuggestion,
  GettextTranslationEntry,
  GettextTranslationMode,
  UploadedFileRecord,
} from "../../shared/api/types";

type GettextFormValues = {
  source_language: string;
  target_language: string;
  chunk_size: number;
  concurrency: number;
  translation_mode: GettextTranslationMode;
};

function summarizeTranslation(entry: GettextTranslationEntry, field: "msgstr" | "translated" | "edited") {
  if (!entry.is_plural) {
    if (field === "msgstr") {
      return entry.msgstr || "-";
    }
    if (field === "translated") {
      return entry.translated_value || "-";
    }
    return entry.edited_value || "-";
  }

  const valueMap =
    field === "msgstr"
      ? entry.msgstr_plural
      : field === "translated"
        ? entry.translated_plural_values
        : entry.edited_plural_values;
  const parts = Object.entries(valueMap).map(([key, value]) => `[${key}] ${value}`);
  return parts.length ? parts.join(" / ") : "-";
}

function summarizePluralValues(values: Record<number, string>) {
  const parts = Object.entries(values).map(([key, value]) => `[${key}] ${value}`);
  return parts.length ? parts.join(" / ") : "-";
}

function summarizeProofreadValue(
  suggestion: GettextProofreadSuggestion,
  field: "current" | "suggested",
) {
  if (!suggestion.is_plural) {
    return field === "current" ? suggestion.current_value || "-" : suggestion.suggested_value || "-";
  }

  const values =
    field === "current" ? suggestion.current_plural_values : suggestion.suggested_plural_values;
  return summarizePluralValues(values);
}

function buildPluralDraft(entry: GettextTranslationEntry) {
  const keys = new Set([
    ...Object.keys(entry.msgstr_plural),
    ...Object.keys(entry.translated_plural_values),
    ...Object.keys(entry.edited_plural_values),
  ]);
  if (!keys.size) {
    keys.add("0");
    keys.add("1");
  }

  const draft: Record<string, string> = {};
  for (const key of keys) {
    draft[key] =
      entry.edited_plural_values[Number(key)] ??
      entry.translated_plural_values[Number(key)] ??
      entry.msgstr_plural[Number(key)] ??
      "";
  }
  return draft;
}

export function GettextTranslationPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [form] = Form.useForm<GettextFormValues>();
  const [uploadedFile, setUploadedFile] = useState<UploadedFileRecord | null>(null);
  const [uploadedFileType, setUploadedFileType] = useState<"po" | "pot" | null>(null);
  const [contextText, setContextText] = useState("");
  const [generatedContextSignature, setGeneratedContextSignature] = useState("");
  const [runId, setRunId] = useState(searchParams.get("runId") ?? "");
  const [page, setPage] = useState(1);
  const [pluralEditorEntry, setPluralEditorEntry] = useState<GettextTranslationEntry | null>(null);
  const [pluralDraft, setPluralDraft] = useState<Record<string, string>>({});
  const [proofreadOpen, setProofreadOpen] = useState(false);
  const [proofreadModel, setProofreadModel] = useState("");
  const [proofreadSuggestions, setProofreadSuggestions] = useState<GettextProofreadSuggestion[]>([]);
  const [applyingSuggestionId, setApplyingSuggestionId] = useState("");
  const [applyingAllSuggestions, setApplyingAllSuggestions] = useState(false);
  const pageSize = 20;
  const sourceLanguage = Form.useWatch("source_language", form) ?? "";
  const targetLanguage = Form.useWatch("target_language", form) ?? "";
  const currentContextSignature = uploadedFile ? `${uploadedFile.id}:${sourceLanguage}:${targetLanguage}` : "";
  const canGenerateContext = Boolean(uploadedFile && sourceLanguage.trim() && targetLanguage.trim());
  const canCreateJob = Boolean(
    uploadedFile &&
      contextText.trim() &&
      generatedContextSignature &&
      generatedContextSignature === currentContextSignature,
  );

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
    retry: false,
  });
  const runQuery = useQuery({
    queryKey: ["gettext-run", runId],
    queryFn: () => api.gettextRun(runId),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    },
  });
  const entriesQuery = useQuery({
    queryKey: ["gettext-entries", runId, page],
    queryFn: () => api.gettextEntries(runId, page, pageSize),
    enabled: Boolean(runId),
    refetchInterval:
      runQuery.data?.status === "queued" || runQuery.data?.status === "running" ? 2000 : false,
  });

  useEffect(() => {
    if (settingsQuery.data) {
      form.setFieldsValue({
        source_language: settingsQuery.data.default_source_language,
        target_language: settingsQuery.data.default_target_language,
        chunk_size: settingsQuery.data.default_chunk_size,
        concurrency: settingsQuery.data.default_concurrency,
        translation_mode: "blank",
      });
    }
  }, [form, settingsQuery.data]);

  useEffect(() => {
    if (runId) {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("runId", runId);
      setSearchParams(nextParams, { replace: true });
    }
  }, [runId, searchParams, setSearchParams]);

  useEffect(() => {
    if (runQuery.data) {
      setUploadedFileType(runQuery.data.input_file_type === "po" ? "po" : "pot");
      setContextText(runQuery.data.context_text);
      setGeneratedContextSignature(
        runQuery.data.context_text.trim()
          ? `${runQuery.data.uploaded_file_id}:${runQuery.data.source_language}:${runQuery.data.target_language}`
          : "",
      );
      form.setFieldsValue({
        source_language: runQuery.data.source_language,
        target_language: runQuery.data.target_language,
        chunk_size: runQuery.data.chunk_size,
        concurrency: runQuery.data.concurrency,
        translation_mode: runQuery.data.translation_mode,
      });
    }
  }, [form, runQuery.data]);

  const contextDraftMutation = useMutation({
    mutationFn: api.createGettextContextDraft,
    onSuccess: (data, variables) => {
      setContextText(data.background);
      setGeneratedContextSignature(
        `${variables.uploaded_file_id}:${variables.source_language}:${variables.target_language}`,
      );
      message.success("术语与上下文说明已生成");
    },
    onError: (error: Error) => message.error(error.message),
  });

  const createJobMutation = useMutation({
    mutationFn: api.createGettextJob,
    onSuccess: async (data) => {
      setRunId(data.id);
      await queryClient.invalidateQueries({ queryKey: ["runs"] });
      await queryClient.invalidateQueries({ queryKey: ["gettext-run", data.id] });
      message.success("Gettext 翻译任务已启动");
    },
    onError: (error: Error) => message.error(error.message),
  });

  const updateEntryMutation = useMutation({
    mutationFn: ({
      entryId,
      editedValue,
      editedPluralValues,
    }: {
      entryId: string;
      editedValue: string;
      editedPluralValues: Record<number, string>;
    }) => api.updateGettextEntry(runId, entryId, { edited_value: editedValue, edited_plural_values: editedPluralValues }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["gettext-entries", runId, page] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const exportMutation = useMutation({
    mutationFn: () => api.exportGettextRun(runId),
    onSuccess: async (data) => {
      window.open(`/api/files/${data.file_id}/download`, "_blank");
      await queryClient.invalidateQueries({ queryKey: ["gettext-run", runId] });
      await queryClient.invalidateQueries({ queryKey: ["files"] });
      message.success("Gettext 导出文件已生成");
    },
    onError: (error: Error) => message.error(error.message),
  });

  const proofreadMutation = useMutation({
    mutationFn: () => api.proofreadGettextRun(runId),
    onSuccess: (data) => {
      setProofreadModel(data.model);
      setProofreadSuggestions(data.items);
      setProofreadOpen(true);
    },
    onError: (error: Error) => message.error(error.message),
  });

  const uploadProps = useMemo(
    () => ({
      accept: ".po,.pot,text/plain",
      maxCount: 1,
      beforeUpload: (file: File) => {
        const extension = file.name.toLowerCase().split(".").pop();
        setUploadedFileType(extension === "po" ? "po" : extension === "pot" ? "pot" : null);
        return true;
      },
      customRequest: async (options: UploadRequestOption) => {
        try {
          const file = options.file as File;
          const record = await api.upload(file);
          setUploadedFile(record);
          setRunId("");
          setPage(1);
          setContextText("");
          setGeneratedContextSignature("");
          options.onSuccess?.(record);
        } catch (error) {
          options.onError?.(error as Error);
        }
      },
    }),
    [],
  );

  const handleGenerateContext = () => {
    if (!uploadedFile) {
      message.warning("请先上传 .po 或 .pot 文件");
      return;
    }
    if (!sourceLanguage.trim() || !targetLanguage.trim()) {
      message.warning("请先填写源语言和目标语言");
      return;
    }

    contextDraftMutation.mutate({
      uploaded_file_id: uploadedFile.id,
      source_language: sourceLanguage,
      target_language: targetLanguage,
    });
  };

  const handleCreateJob = (values: GettextFormValues) => {
    if (!uploadedFile) {
      message.warning("请先上传 .po 或 .pot 文件");
      return;
    }
    if (!contextText.trim()) {
      message.warning("请先生成术语与上下文说明");
      return;
    }
    if (generatedContextSignature !== currentContextSignature) {
      message.warning("源语言、目标语言或文件已变化，请重新生成术语与上下文说明");
      return;
    }

    createJobMutation.mutate({
      uploaded_file_id: uploadedFile.id,
      source_language: values.source_language,
      target_language: values.target_language,
      context_text: contextText,
      translation_mode: uploadedFileType === "po" ? values.translation_mode : "blank",
      chunk_size: values.chunk_size,
      concurrency: values.concurrency,
    });
  };

  const savePluralDraft = () => {
    if (!pluralEditorEntry) {
      return;
    }

    const payload = Object.fromEntries(
      Object.entries(pluralDraft).map(([key, value]) => [Number(key), value]),
    ) as Record<number, string>;

    updateEntryMutation.mutate({
      entryId: pluralEditorEntry.id,
      editedValue: pluralEditorEntry.edited_value,
      editedPluralValues: payload,
    });
    setPluralEditorEntry(null);
  };

  const statusColor =
    runQuery.data?.status === "completed"
      ? "success"
      : runQuery.data?.status === "failed"
        ? "error"
        : "processing";

  const applySuggestion = async (suggestion: GettextProofreadSuggestion) => {
    setApplyingSuggestionId(suggestion.entry_id);
    try {
      await api.updateGettextEntry(runId, suggestion.entry_id, {
        edited_value: suggestion.is_plural ? "" : suggestion.suggested_value,
        edited_plural_values: suggestion.is_plural ? suggestion.suggested_plural_values : {},
      });
      setProofreadSuggestions((current) => current.filter((item) => item.entry_id !== suggestion.entry_id));
      await queryClient.invalidateQueries({ queryKey: ["gettext-entries", runId, page] });
      message.success(`已采用第 ${suggestion.entry_index} 条建议`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "采用建议失败");
    } finally {
      setApplyingSuggestionId("");
    }
  };

  const applyAllSuggestions = async () => {
    if (!proofreadSuggestions.length) {
      return;
    }
    setApplyingAllSuggestions(true);
    try {
      await Promise.all(
        proofreadSuggestions.map((suggestion) =>
          api.updateGettextEntry(runId, suggestion.entry_id, {
            edited_value: suggestion.is_plural ? "" : suggestion.suggested_value,
            edited_plural_values: suggestion.is_plural ? suggestion.suggested_plural_values : {},
          }),
        ),
      );
      setProofreadSuggestions([]);
      await queryClient.invalidateQueries({ queryKey: ["gettext-entries", runId, page] });
      message.success("已采用全部 AI 校对建议");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "批量采用失败");
    } finally {
      setApplyingAllSuggestions(false);
    }
  };

  return (
    <div className="page-stack">
      <Row gutter={[20, 20]} className="step-grid">
        <Col xs={24} lg={10}>
          <Card className="panel-card step-card">
            <Typography.Text className="section-kicker">Step 01</Typography.Text>
            <Typography.Title level={3} className="panel-title">
              上传与任务设置
            </Typography.Title>

            <Upload.Dragger {...uploadProps} showUploadList={false} className="tool-uploader">
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">拖拽或点击上传 .po / .pot</p>
              <p className="ant-upload-hint">首版支持 Gettext 模板和已有翻译文件</p>
            </Upload.Dragger>

            {uploadedFile ? (
              <div className="upload-summary">
                <Tag color="blue">{uploadedFile.original_name}</Tag>
                <Typography.Text type="secondary">{Math.round(uploadedFile.size / 1024)} KB</Typography.Text>
              </div>
            ) : null}

            <Form form={form} layout="vertical" onFinish={handleCreateJob} className="stack-form">
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item label="源语言" name="source_language" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="目标语言" name="target_language" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="每块条目数" name="chunk_size" rules={[{ required: true }]}>
                    <InputNumber min={1} max={200} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="并发数" name="concurrency" rules={[{ required: true }]}>
                    <InputNumber min={1} max={10} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>

              {uploadedFileType === "po" ? (
                <Form.Item label="处理模式" name="translation_mode">
                  <Select
                    options={[
                      { value: "blank", label: "只翻空白项" },
                      { value: "blank_and_fuzzy", label: "翻空白项和 fuzzy" },
                      { value: "overwrite_all", label: "全部重翻" },
                    ]}
                  />
                </Form.Item>
              ) : null}
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card className="panel-card step-card">
            <Typography.Text className="section-kicker">Step 02</Typography.Text>
            <Typography.Title level={3} className="panel-title">
              术语与上下文说明
            </Typography.Title>
            <Input.TextArea
              rows={12}
              value={contextText}
              onChange={(event) => setContextText(event.target.value)}
              placeholder="在这里输入术语偏好、上下文说明和风格要求。"
            />
            <Space className="action-row" wrap style={{ marginTop: 16 }}>
              <Button
                onClick={handleGenerateContext}
                loading={contextDraftMutation.isPending}
                disabled={!canGenerateContext}
              >
                生成术语与上下文说明
              </Button>
              <Button
                type="primary"
                onClick={() => form.submit()}
                loading={createJobMutation.isPending}
                disabled={!canCreateJob}
              >
                翻译内容
              </Button>
            </Space>
            <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              重新上传文件，或修改源语言、目标语言后，需要重新生成一次说明。
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>

      <Card className="panel-card">
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <div className="job-header">
            <div>
              <Typography.Text className="section-kicker">Step 03</Typography.Text>
              <Typography.Title level={3} className="panel-title">
                结果工作台
              </Typography.Title>
            </div>
            <Space className="result-toolbar" wrap>
              {runQuery.data ? <Tag color={statusColor}>{runQuery.data.status}</Tag> : null}
              <Button
                icon={<RobotOutlined />}
                disabled={!runQuery.data || runQuery.data.status !== "completed"}
                loading={proofreadMutation.isPending}
                onClick={() => proofreadMutation.mutate()}
              >
                AI 校对
              </Button>
              <Button
                type="primary"
                icon={<ExportOutlined />}
                disabled={!runQuery.data || runQuery.data.status !== "completed"}
                loading={exportMutation.isPending}
                onClick={() => exportMutation.mutate()}
              >
                导出 PO
              </Button>
            </Space>
          </div>

          {runQuery.isLoading ? <Spin /> : null}
          {runQuery.data ? (
            <>
              <div className="metric-grid compact">
                <div className="metric-tile compact">
                  <span className="metric-label">已处理</span>
                  <strong>{runQuery.data.processed_entries}</strong>
                  <span className="metric-note">总计 {runQuery.data.total_entries} 条</span>
                </div>
                <div className="metric-tile compact">
                  <span className="metric-label">文件类型</span>
                  <strong>{runQuery.data.input_file_type.toUpperCase()}</strong>
                  <span className="metric-note">{runQuery.data.source_language} → {runQuery.data.target_language}</span>
                </div>
                <div className="metric-tile compact">
                  <span className="metric-label">处理模式</span>
                  <strong>{runQuery.data.translation_mode}</strong>
                  <span className="metric-note">每块 {runQuery.data.chunk_size} 条</span>
                </div>
              </div>
              <Progress percent={runQuery.data.progress} status={runQuery.data.status === "failed" ? "exception" : "active"} />
              {runQuery.data.error_message ? (
                <Typography.Text type="danger">{runQuery.data.error_message}</Typography.Text>
              ) : null}
            </>
          ) : (
            <Empty description="创建任务后，这里会展示 Gettext 条目、AI 译文和人工修订入口。" />
          )}

          <Table
            rowKey="id"
            className="result-table"
            loading={entriesQuery.isLoading}
            dataSource={entriesQuery.data?.items ?? []}
            pagination={{
              current: page,
              pageSize,
              total: entriesQuery.data?.total ?? 0,
              onChange: (nextPage) => setPage(nextPage),
            }}
            columns={[
              {
                title: "#",
                dataIndex: "entry_index",
                width: 72,
              },
              {
                title: "上下文",
                dataIndex: "msgctxt",
                width: 180,
                render: (value: string) => value || "-",
              },
              {
                title: "源文",
                render: (_, entry: GettextTranslationEntry) => (
                  <div>
                    <Typography.Text>{entry.msgid}</Typography.Text>
                    {entry.msgid_plural ? (
                      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                        plural: {entry.msgid_plural}
                      </Typography.Paragraph>
                    ) : null}
                  </div>
                ),
              },
              {
                title: "当前译文",
                render: (_, entry: GettextTranslationEntry) => summarizeTranslation(entry, "msgstr"),
              },
              {
                title: "AI 译文",
                render: (_, entry: GettextTranslationEntry) => summarizeTranslation(entry, "translated"),
              },
              {
                title: "人工修订",
                width: 260,
                render: (_, entry: GettextTranslationEntry) =>
                  entry.is_plural ? (
                    <Button
                      onClick={() => {
                        setPluralEditorEntry(entry);
                        setPluralDraft(buildPluralDraft(entry));
                      }}
                    >
                      编辑 plural
                    </Button>
                  ) : (
                    <Input.TextArea
                      defaultValue={entry.edited_value || entry.translated_value || entry.msgstr}
                      autoSize={{ minRows: 1, maxRows: 4 }}
                      onBlur={(event) => {
                        if (event.target.value !== entry.edited_value) {
                          updateEntryMutation.mutate({
                            entryId: entry.id,
                            editedValue: event.target.value,
                            editedPluralValues: entry.edited_plural_values,
                          });
                        }
                      }}
                    />
                  ),
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 110,
                render: (value: string) => (
                  <Tag color={value === "edited" ? "gold" : value === "translated" ? "success" : "default"}>
                    {value}
                  </Tag>
                ),
              },
            ]}
          />
        </Space>
      </Card>

      <Modal
        open={Boolean(pluralEditorEntry)}
        title="Plural 条目编辑"
        onCancel={() => setPluralEditorEntry(null)}
        onOk={savePluralDraft}
        confirmLoading={updateEntryMutation.isPending}
      >
        {pluralEditorEntry ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Typography.Paragraph>
              <strong>{pluralEditorEntry.msgid}</strong>
              {pluralEditorEntry.msgid_plural ? ` / ${pluralEditorEntry.msgid_plural}` : ""}
            </Typography.Paragraph>
            {Object.keys(pluralDraft)
              .sort((left, right) => Number(left) - Number(right))
              .map((key) => (
                <div key={key}>
                  <Typography.Text>[{key}]</Typography.Text>
                  <Input
                    value={pluralDraft[key]}
                    onChange={(event) =>
                      setPluralDraft((current) => ({
                        ...current,
                        [key]: event.target.value,
                      }))
                    }
                  />
                </div>
              ))}
          </Space>
        ) : null}
      </Modal>

      <Modal
        open={proofreadOpen}
        title="AI 校对建议"
        width={1180}
        onCancel={() => setProofreadOpen(false)}
        footer={[
          <Button key="close" onClick={() => setProofreadOpen(false)}>
            关闭
          </Button>,
          <Button
            key="apply-all"
            type="primary"
            disabled={!proofreadSuggestions.length}
            loading={applyingAllSuggestions}
            onClick={() => void applyAllSuggestions()}
          >
            全部采用
          </Button>,
        ]}
      >
        <Typography.Paragraph className="proofread-copy">
          当前使用模型：{proofreadModel || "-"}。AI 只返回建议修改项，最终是否采用由你决定。
        </Typography.Paragraph>
        {proofreadSuggestions.length ? (
          <Table
            rowKey="entry_id"
            size="small"
            className="proofread-table"
            pagination={false}
            scroll={{ x: 1080, y: 460 }}
            dataSource={proofreadSuggestions}
            columns={[
              {
                title: "#",
                dataIndex: "entry_index",
                width: 72,
              },
              {
                title: "源文",
                width: 260,
                render: (_, suggestion: GettextProofreadSuggestion) => (
                  <div>
                    <Typography.Text>{suggestion.msgid}</Typography.Text>
                    {suggestion.msgid_plural ? (
                      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                        plural: {suggestion.msgid_plural}
                      </Typography.Paragraph>
                    ) : null}
                  </div>
                ),
              },
              {
                title: "当前结果",
                width: 280,
                render: (_, suggestion: GettextProofreadSuggestion) =>
                  summarizeProofreadValue(suggestion, "current"),
              },
              {
                title: "AI 建议",
                width: 280,
                render: (_, suggestion: GettextProofreadSuggestion) =>
                  summarizeProofreadValue(suggestion, "suggested"),
              },
              {
                title: "原因",
                dataIndex: "reason",
                width: 280,
              },
              {
                title: "操作",
                width: 108,
                fixed: "right",
                render: (_, suggestion: GettextProofreadSuggestion) => (
                  <Button
                    type="link"
                    loading={applyingSuggestionId === suggestion.entry_id}
                    onClick={() => void applySuggestion(suggestion)}
                  >
                    采用
                  </Button>
                ),
              },
            ]}
          />
        ) : (
          <Empty description="AI 校对未提出需要修改的建议。" />
        )}
      </Modal>
    </div>
  );
}
