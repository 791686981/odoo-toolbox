import {
  InboxOutlined,
  ReloadOutlined,
  RobotOutlined,
  UploadOutlined,
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
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { UploadRequestOption } from "rc-upload/lib/interface";

import { api } from "../../shared/api/client";
import type {
  ProofreadSuggestion,
  TranslationJob,
  TranslationRow,
  UploadedFileRecord,
} from "../../shared/api/types";

type TranslationFormValues = {
  source_language: string;
  target_language: string;
  chunk_size: number;
  concurrency: number;
  overwrite_existing: boolean;
};

export function CsvTranslationPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [form] = Form.useForm<TranslationFormValues>();
  const [uploadedFile, setUploadedFile] = useState<UploadedFileRecord | null>(null);
  const [background, setBackground] = useState("");
  const [jobId, setJobId] = useState<string>(searchParams.get("jobId") ?? "");
  const [page, setPage] = useState(1);
  const [proofreadOpen, setProofreadOpen] = useState(false);
  const [proofreadModel, setProofreadModel] = useState("");
  const [proofreadSuggestions, setProofreadSuggestions] = useState<ProofreadSuggestion[]>([]);
  const [applyingSuggestionId, setApplyingSuggestionId] = useState("");
  const [applyingAllSuggestions, setApplyingAllSuggestions] = useState(false);
  const pageSize = 20;

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
  });
  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = (query.state.data as TranslationJob | undefined)?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    },
  });
  const rowsQuery = useQuery({
    queryKey: ["job-rows", jobId, page],
    queryFn: () => api.rows(jobId, page, pageSize),
    enabled: Boolean(jobId),
    refetchInterval: jobQuery.data?.status === "queued" || jobQuery.data?.status === "running" ? 2000 : false,
  });

  useEffect(() => {
    if (settingsQuery.data) {
      form.setFieldsValue({
        source_language: settingsQuery.data.default_source_language,
        target_language: settingsQuery.data.default_target_language,
        chunk_size: settingsQuery.data.default_chunk_size,
        concurrency: settingsQuery.data.default_concurrency,
        overwrite_existing: settingsQuery.data.default_overwrite_existing,
      });
    }
  }, [form, settingsQuery.data]);

  useEffect(() => {
    if (jobId) {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("jobId", jobId);
      setSearchParams(nextParams, { replace: true });
    }
  }, [jobId, searchParams, setSearchParams]);

  const contextDraftMutation = useMutation({
    mutationFn: api.createContextDraft,
    onSuccess: (data) => setBackground(data.background),
    onError: (error: Error) => message.error(error.message),
  });

  const createJobMutation = useMutation({
    mutationFn: api.createJob,
    onSuccess: async (data) => {
      setJobId(data.id);
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["job", data.id] });
      message.success("翻译任务已启动");
    },
    onError: (error: Error) => message.error(error.message),
  });

  const updateRowMutation = useMutation({
    mutationFn: ({ rowId, value }: { rowId: string; value: string }) => api.updateRow(jobId, rowId, value),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["job-rows", jobId, page] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  const exportMutation = useMutation({
    mutationFn: () => api.exportJob(jobId),
    onSuccess: async (data) => {
      window.open(`/api/files/${data.file_id}/download`, "_blank");
      await queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      message.success("导出文件已生成");
    },
    onError: (error: Error) => message.error(error.message),
  });

  const proofreadMutation = useMutation({
    mutationFn: () => api.proofreadJob(jobId),
    onSuccess: (data) => {
      setProofreadModel(data.model);
      setProofreadSuggestions(data.items);
      setProofreadOpen(true);
    },
    onError: (error: Error) => message.error(error.message),
  });

  const uploadProps = {
    accept: ".csv,text/csv",
    maxCount: 1,
    customRequest: async (options: UploadRequestOption) => {
      try {
        const file = options.file as File;
        const record = await api.upload(file);
        setUploadedFile(record);

        const values = form.getFieldsValue();
        contextDraftMutation.mutate({
          uploaded_file_id: record.id,
          source_language: values.source_language,
          target_language: values.target_language,
        });

        options.onSuccess?.(record);
      } catch (error) {
        options.onError?.(error as Error);
      }
    },
  };

  const handleGenerateDraft = () => {
    if (!uploadedFile) {
      message.warning("请先上传 CSV 文件");
      return;
    }
    const values = form.getFieldsValue();
    contextDraftMutation.mutate({
      uploaded_file_id: uploadedFile.id,
      source_language: values.source_language,
      target_language: values.target_language,
    });
  };

  const handleCreateJob = (values: TranslationFormValues) => {
    if (!uploadedFile) {
      message.warning("请先上传 CSV 文件");
      return;
    }
    if (!background.trim()) {
      message.warning("请先确认背景说明");
      return;
    }
    createJobMutation.mutate({
      uploaded_file_id: uploadedFile.id,
      background_context: background,
      source_language: values.source_language,
      target_language: values.target_language,
      chunk_size: values.chunk_size,
      concurrency: values.concurrency,
      overwrite_existing: values.overwrite_existing,
    });
  };

  const jobStatusColor =
    jobQuery.data?.status === "completed"
      ? "success"
      : jobQuery.data?.status === "failed"
        ? "error"
        : "processing";

  const applySuggestion = async (suggestion: ProofreadSuggestion) => {
    setApplyingSuggestionId(suggestion.row_id);
    try {
      await api.updateRow(jobId, suggestion.row_id, suggestion.suggested_value);
      setProofreadSuggestions((current) => current.filter((item) => item.row_id !== suggestion.row_id));
      await queryClient.invalidateQueries({ queryKey: ["job-rows", jobId, page] });
      message.success(`已采用第 ${suggestion.row_number} 行建议`);
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
          api.updateRow(jobId, suggestion.row_id, suggestion.suggested_value),
        ),
      );
      setProofreadSuggestions([]);
      await queryClient.invalidateQueries({ queryKey: ["job-rows", jobId, page] });
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
            <div className="step-uploader-shell">
              <Upload.Dragger {...uploadProps} showUploadList={false} className="tool-uploader">
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">拖拽或点击上传 Odoo CSV</p>
                <p className="ant-upload-hint">首版只支持标准 Odoo i18n CSV</p>
              </Upload.Dragger>
            </div>
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
                  <Form.Item label="每块行数" name="chunk_size" rules={[{ required: true }]}>
                    <InputNumber min={1} max={200} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="并发数" name="concurrency" rules={[{ required: true }]}>
                    <InputNumber min={1} max={10} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="覆盖已有 value" name="overwrite_existing" valuePropName="checked">
                <Switch />
              </Form.Item>

              <Space className="action-row" wrap>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleGenerateDraft}
                  loading={contextDraftMutation.isPending}
                >
                  重新生成背景
                </Button>
                <Button type="primary" htmlType="submit" loading={createJobMutation.isPending}>
                  开始翻译
                </Button>
              </Space>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card className="panel-card step-card">
            <Typography.Text className="section-kicker">Step 02</Typography.Text>
            <Typography.Title level={3} className="panel-title">
              背景说明
            </Typography.Title>
            <div className="context-editor-shell">
              <Input.TextArea
                className="context-editor"
                value={background}
                rows={12}
                onChange={(event) => setBackground(event.target.value)}
                placeholder="上传文件后，可在这里确认或修改背景说明。"
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Card className="panel-card">
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <div className="job-header">
            <div>
              <Typography.Text className="section-kicker">Step 03</Typography.Text>
              <Typography.Title level={3} className="panel-title">
                翻译结果工作台
              </Typography.Title>
            </div>
            <Space className="result-toolbar" wrap>
              {jobQuery.data ? <Tag color={jobStatusColor}>{jobQuery.data.status}</Tag> : null}
              <Button
                icon={<RobotOutlined />}
                disabled={!jobQuery.data || jobQuery.data.status !== "completed"}
                loading={proofreadMutation.isPending}
                onClick={() => proofreadMutation.mutate()}
              >
                AI 校对
              </Button>
              <Button
                type="primary"
                icon={<UploadOutlined />}
                disabled={!jobQuery.data || jobQuery.data.status !== "completed"}
                loading={exportMutation.isPending}
                onClick={() => exportMutation.mutate()}
              >
                导出 CSV
              </Button>
            </Space>
          </div>

          {jobQuery.isLoading ? <Spin /> : null}
          {jobQuery.data ? (
            <>
              <div className="metric-grid compact">
                <div className="metric-tile compact">
                  <span className="metric-label">已处理</span>
                  <strong>{jobQuery.data.processed_rows}</strong>
                  <span className="metric-note">总计 {jobQuery.data.total_rows} 行</span>
                </div>
                <div className="metric-tile compact">
                  <span className="metric-label">语言对</span>
                  <strong>
                    {jobQuery.data.source_language} → {jobQuery.data.target_language}
                  </strong>
                  <span className="metric-note">上下文已锁定到任务</span>
                </div>
                <div className="metric-tile compact">
                  <span className="metric-label">并发设置</span>
                  <strong>{jobQuery.data.concurrency}</strong>
                  <span className="metric-note">每块 {jobQuery.data.chunk_size} 行</span>
                </div>
              </div>
              <Progress percent={jobQuery.data.progress} status={jobQuery.data.status === "failed" ? "exception" : "active"} />
              {jobQuery.data.error_message ? (
                <Typography.Text type="danger">{jobQuery.data.error_message}</Typography.Text>
              ) : null}
            </>
          ) : (
            <Empty description="创建任务后，这里会出现实时进度和翻译结果。" />
          )}

          <div className="table-shell">
            <Table
              rowKey="id"
              className="result-table"
              loading={rowsQuery.isLoading}
              dataSource={rowsQuery.data?.items ?? []}
              pagination={{
                current: page,
                pageSize,
                total: rowsQuery.data?.total ?? 0,
                onChange: (nextPage) => setPage(nextPage),
              }}
              columns={[
                {
                  title: "#",
                  dataIndex: "row_number",
                  width: 72,
                },
                {
                  title: "模块",
                  dataIndex: "module",
                  width: 120,
                },
                {
                  title: "源文",
                  dataIndex: "source_text",
                  render: (value: string) => <Typography.Text>{value}</Typography.Text>,
                },
                {
                  title: "模型译文",
                  dataIndex: "translated_value",
                  render: (value: string) => <Typography.Text>{value || "-"}</Typography.Text>,
                },
                {
                  title: "人工修订",
                  render: (_, record: TranslationRow) => (
                    <Input.TextArea
                      defaultValue={record.edited_value}
                      autoSize={{ minRows: 1, maxRows: 4 }}
                      onBlur={(event) => {
                        const nextValue = event.target.value;
                        if (nextValue !== record.edited_value) {
                          updateRowMutation.mutate({ rowId: record.id, value: nextValue });
                        }
                      }}
                    />
                  ),
                },
              ]}
            />
          </div>
        </Space>
      </Card>

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
            onClick={applyAllSuggestions}
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
            rowKey="row_id"
            size="small"
            className="proofread-table"
            pagination={false}
            scroll={{ x: 1080, y: 460 }}
            dataSource={proofreadSuggestions}
            columns={[
              {
                title: "#",
                dataIndex: "row_number",
                width: 72,
              },
              {
                title: "源文",
                dataIndex: "source_text",
                width: 240,
              },
              {
                title: "当前结果",
                dataIndex: "current_value",
                width: 280,
              },
              {
                title: "AI 建议",
                dataIndex: "suggested_value",
                width: 280,
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
                render: (_, suggestion: ProofreadSuggestion) => (
                  <Button
                    type="link"
                    loading={applyingSuggestionId === suggestion.row_id}
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
