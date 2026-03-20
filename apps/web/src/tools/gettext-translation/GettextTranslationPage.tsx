import {
  ExportOutlined,
  InboxOutlined,
  SaveOutlined,
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
  const [runId, setRunId] = useState(searchParams.get("runId") ?? "");
  const [page, setPage] = useState(1);
  const [pluralEditorEntry, setPluralEditorEntry] = useState<GettextTranslationEntry | null>(null);
  const [pluralDraft, setPluralDraft] = useState<Record<string, string>>({});
  const pageSize = 20;

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
      form.setFieldsValue({
        source_language: runQuery.data.source_language,
        target_language: runQuery.data.target_language,
        chunk_size: runQuery.data.chunk_size,
        concurrency: runQuery.data.concurrency,
        translation_mode: runQuery.data.translation_mode,
      });
    }
  }, [form, runQuery.data]);

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
          options.onSuccess?.(record);
        } catch (error) {
          options.onError?.(error as Error);
        }
      },
    }),
    [],
  );

  const handleCreateJob = (values: GettextFormValues) => {
    if (!uploadedFile) {
      message.warning("请先上传 .po 或 .pot 文件");
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

              <Button type="primary" htmlType="submit" loading={createJobMutation.isPending} icon={<SaveOutlined />}>
                开始翻译
              </Button>
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
    </div>
  );
}
