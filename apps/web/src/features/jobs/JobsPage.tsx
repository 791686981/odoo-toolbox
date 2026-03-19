import { Button, Card, Table, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../../shared/api/client";

export function JobsPage() {
  const navigate = useNavigate();
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
  });
  const jobs = jobsQuery.data ?? [];
  const completedCount = jobs.filter((job) => job.status === "completed").length;
  const activeCount = jobs.filter((job) => job.status === "running" || job.status === "queued").length;
  const averageProgress = jobs.length
    ? Math.round(jobs.reduce((sum, job) => sum + job.progress, 0) / jobs.length)
    : 0;

  return (
    <div className="page-stack">
      <section className="workspace-hero compact">
        <div className="workspace-copy-group">
          <Typography.Text className="section-kicker">Jobs Ledger</Typography.Text>
          <Typography.Title level={2} className="workspace-title">
            运行记录
          </Typography.Title>
          <Typography.Paragraph className="workspace-copy">
            汇总查看当前平台里所有运行中的工作项。首版主要承载 CSV 翻译任务，后续会逐步纳入更多工具。
          </Typography.Paragraph>
        </div>
        <div className="hero-metrics">
          <div className="metric-tile compact">
            <span className="metric-label">总任务</span>
            <strong>{jobs.length}</strong>
            <span className="metric-note">所有工具的运行会逐步汇总到这里</span>
          </div>
          <div className="metric-tile compact">
            <span className="metric-label">处理中</span>
            <strong>{activeCount}</strong>
            <span className="metric-note">正在运行或排队</span>
          </div>
          <div className="metric-tile compact">
            <span className="metric-label">平均进度</span>
            <strong>{averageProgress}%</strong>
            <span className="metric-note">已完成 {completedCount} 个任务</span>
          </div>
        </div>
      </section>

      <Card className="panel-card">
        <Typography.Text className="section-kicker">Overview</Typography.Text>
        <Typography.Title level={3} className="panel-title">
          运行清单
        </Typography.Title>
        <Table
          className="result-table"
          rowKey="id"
          loading={jobsQuery.isLoading}
          dataSource={jobs}
          pagination={false}
          columns={[
            {
              title: "任务 ID",
              dataIndex: "id",
              render: (value: string) => <Typography.Text code>{value.slice(0, 8)}</Typography.Text>,
            },
            {
              title: "状态",
              dataIndex: "status",
              render: (value: string) => (
                <Tag color={value === "completed" ? "success" : value === "failed" ? "error" : "processing"}>
                  {value}
                </Tag>
              ),
            },
            {
              title: "语言",
              render: (_, record) => `${record.source_language} -> ${record.target_language}`,
            },
            {
              title: "进度",
              dataIndex: "progress",
              render: (value: number) => `${value}%`,
            },
            {
              title: "操作",
              render: (_, record) => (
                <Button onClick={() => navigate(`/tools/csv-translation?jobId=${record.id}`)}>查看详情</Button>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
