import { CompassOutlined, FolderOpenOutlined, ToolOutlined } from "@ant-design/icons";
import { Button, Card, Col, Empty, Row, Space, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../../shared/api/client";
import { getToolRunDetailPath } from "../../tools/registry";

export function HomePage() {
  const navigate = useNavigate();
  const toolsQuery = useQuery({
    queryKey: ["tools"],
    queryFn: api.tools,
  });
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: api.runs,
  });

  const tools = (toolsQuery.data ?? []).filter((tool) => tool.enabled);
  const recentRuns = (runsQuery.data ?? []).slice(0, 5);
  const activeRuns = recentRuns.filter((run) => run.status === "running" || run.status === "queued").length;

  return (
    <div className="page-stack">
      <section className="workspace-hero compact">
        <div className="workspace-copy-group">
          <Typography.Title level={2} className="workspace-title">
            Odoo 开发工具箱
          </Typography.Title>
        </div>
        <div className="hero-metrics">
          <div className="metric-tile">
            <span className="metric-label">可用工具</span>
            <strong>{tools.length}</strong>
            <span className="metric-note">统一入口</span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">最近运行</span>
            <strong>{recentRuns.length}</strong>
            <span className="metric-note">其中 {activeRuns} 个处理中</span>
          </div>
        </div>
      </section>

      <Row gutter={[20, 20]}>
        <Col xs={24} xl={14}>
          <Card className="panel-card">
            <Typography.Text className="section-kicker">Tools</Typography.Text>
            <Typography.Title level={3} className="panel-title">
              工具入口
            </Typography.Title>
            <div className="tool-grid">
              {tools.map((tool) => (
                <button key={tool.id} className="tool-tile" type="button" onClick={() => navigate(tool.route)}>
                  <div className="tool-tile-icon">
                    <ToolOutlined />
                  </div>
                  <div className="tool-tile-body">
                    <strong>{tool.title}</strong>
                    <span>{tool.description}</span>
                  </div>
                </button>
              ))}
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card className="panel-card">
            <Typography.Text className="section-kicker">Quick Access</Typography.Text>
            <Typography.Title level={3} className="panel-title">
              平台入口
            </Typography.Title>
            <div className="quick-link-list">
              <button type="button" className="quick-link-card" onClick={() => navigate("/runs")}>
                <HistoryCardContent />
              </button>
              <button type="button" className="quick-link-card" onClick={() => navigate("/files")}>
                <FilesCardContent />
              </button>
            </div>
          </Card>
        </Col>
      </Row>

      <Card className="panel-card">
        <div className="job-header">
          <div>
            <Typography.Text className="section-kicker">Recent Runs</Typography.Text>
            <Typography.Title level={3} className="panel-title">
              最近运行
            </Typography.Title>
          </div>
          <Button onClick={() => navigate("/runs")}>查看全部</Button>
        </div>

        {recentRuns.length ? (
          <div className="run-list">
            {recentRuns.map((run) => {
              const detailPath = getToolRunDetailPath(run.tool_id, run.id);

              return (
                <button
                  key={run.id}
                  type="button"
                  className="run-row"
                  onClick={() => {
                    if (detailPath) {
                      navigate(detailPath);
                    }
                  }}
                >
                  <div className="run-row-main">
                    <strong>{run.summary}</strong>
                    <span>{run.tool_id}</span>
                  </div>
                  <Space>
                    <Tag color={run.status === "completed" ? "success" : run.status === "failed" ? "error" : "processing"}>
                      {run.status}
                    </Tag>
                    <Typography.Text>{new Date(run.updated_at).toLocaleDateString("zh-CN")}</Typography.Text>
                  </Space>
                </button>
              );
            })}
          </div>
        ) : (
          <Empty description="还没有运行记录，先进入一个工具开始工作。" />
        )}
      </Card>
    </div>
  );
}

function HistoryCardContent() {
  return (
    <>
      <div className="quick-link-icon">
        <CompassOutlined />
      </div>
      <div className="quick-link-body">
        <strong>运行记录</strong>
        <span>统一查看不同工具的运行状态与结果入口</span>
      </div>
    </>
  );
}

function FilesCardContent() {
  return (
    <>
      <div className="quick-link-icon">
        <FolderOpenOutlined />
      </div>
      <div className="quick-link-body">
        <strong>文件中心</strong>
        <span>集中管理上传文件、导出文件与后续工具产物</span>
      </div>
    </>
  );
}
