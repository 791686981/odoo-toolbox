import { Card, Empty, Table, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";

import { api } from "../../shared/api/client";

export function FilesPage() {
  const filesQuery = useQuery({
    queryKey: ["files"],
    queryFn: api.files,
  });
  const files = filesQuery.data ?? [];
  const uploadCount = files.filter((file) => file.kind === "upload").length;
  const generatedCount = files.filter((file) => file.kind === "generated").length;

  return (
    <div className="page-stack">
      <section className="workspace-hero compact">
        <div className="workspace-copy-group">
          <Typography.Title level={2} className="workspace-title">
            文件中心
          </Typography.Title>
        </div>
        <div className="metric-grid compact">
          <div className="metric-tile compact">
            <span className="metric-label">上传</span>
            <strong>{uploadCount}</strong>
            <span className="metric-note">源文件</span>
          </div>
          <div className="metric-tile compact">
            <span className="metric-label">产物</span>
            <strong>{generatedCount}</strong>
            <span className="metric-note">导出与报告</span>
          </div>
          <div className="metric-tile compact">
            <span className="metric-label">总文件数</span>
            <strong>{files.length}</strong>
            <span className="metric-note">平台统一管理</span>
          </div>
        </div>
      </section>

      <Card className="panel-card">
        <Typography.Text className="section-kicker">Catalog</Typography.Text>
        <Typography.Title level={3} className="panel-title">
          文件清单
        </Typography.Title>
        {files.length ? (
          <Table
            rowKey="id"
            className="result-table"
            loading={filesQuery.isLoading}
            pagination={false}
            dataSource={files}
            columns={[
              {
                title: "文件名",
                dataIndex: "original_name",
              },
              {
                title: "类型",
                dataIndex: "kind",
                width: 120,
                render: (value: string) => (
                  <Tag color={value === "generated" ? "gold" : "blue"}>
                    {value === "generated" ? "产物" : "上传"}
                  </Tag>
                ),
              },
              {
                title: "来源",
                width: 220,
                render: (_, record) =>
                  record.tool_id ? `${record.tool_id}${record.artifact_label ? ` · ${record.artifact_label}` : ""}` : "-",
              },
              {
                title: "MIME",
                dataIndex: "mime_type",
                width: 180,
              },
              {
                title: "大小",
                dataIndex: "size",
                width: 120,
                render: (value: number) => `${Math.max(1, Math.round(value / 1024))} KB`,
              },
              {
                title: "创建时间",
                dataIndex: "created_at",
                width: 220,
                render: (value: string) => new Date(value).toLocaleString("zh-CN"),
              },
            ]}
          />
        ) : (
          <Empty description="当前还没有文件记录。" />
        )}
      </Card>
    </div>
  );
}
