import { Button, Card, Table, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../../shared/api/client";
import { getToolRunDetailPath } from "../../tools/registry";

export function RunsPage() {
  const navigate = useNavigate();
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: api.runs,
  });
  const runs = runsQuery.data ?? [];
  const completedCount = runs.filter((run) => run.status === "completed").length;
  const activeCount = runs.filter((run) => run.status === "running" || run.status === "queued").length;
  const failedCount = runs.filter((run) => run.status === "failed").length;

  return (
    <div className="page-stack">
      <section className="workspace-hero compact">
        <div className="workspace-copy-group">
          <Typography.Title level={2} className="workspace-title">
            运行记录
          </Typography.Title>
        </div>
        <div className="hero-metrics">
          <div className="metric-tile compact">
            <span className="metric-label">总运行数</span>
            <strong>{runs.length}</strong>
            <span className="metric-note">全部工具</span>
          </div>
          <div className="metric-tile compact">
            <span className="metric-label">处理中</span>
            <strong>{activeCount}</strong>
            <span className="metric-note">排队或执行中</span>
          </div>
          <div className="metric-tile compact">
            <span className="metric-label">已完成</span>
            <strong>{completedCount}</strong>
            <span className="metric-note">失败 {failedCount} 个</span>
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
          loading={runsQuery.isLoading}
          dataSource={runs}
          pagination={false}
          columns={[
            {
              title: "运行 ID",
              dataIndex: "id",
              render: (value: string) => <Typography.Text code>{value.slice(0, 8)}</Typography.Text>,
            },
            {
              title: "工具",
              dataIndex: "tool_id",
              render: (value: string) => <Tag color="blue">{value}</Tag>,
            },
            {
              title: "摘要",
              dataIndex: "summary",
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
              title: "最近更新时间",
              dataIndex: "updated_at",
              width: 220,
              render: (value: string) => new Date(value).toLocaleString("zh-CN"),
            },
            {
              title: "操作",
              render: (_, record) => {
                const detailPath = getToolRunDetailPath(record.tool_id, record.id);

                return (
                  <Button disabled={!detailPath} onClick={() => detailPath && navigate(detailPath)}>
                    查看详情
                  </Button>
                );
              },
            },
          ]}
        />
      </Card>
    </div>
  );
}
