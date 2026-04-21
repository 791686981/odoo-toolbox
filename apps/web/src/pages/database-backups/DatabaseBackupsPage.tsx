import { Card, Empty, Typography } from "antd";

export function DatabaseBackupsPage() {
  return (
    <div className="page-stack">
      <section className="workspace-hero compact">
        <div className="workspace-copy-group">
          <Typography.Title level={2} className="workspace-title">
            数据库备份库
          </Typography.Title>
          <Typography.Text className="workspace-copy">
            维护数据库 zip 备份的主线节点、分支关系和使用规范。
          </Typography.Text>
        </div>
      </section>

      <Card className="panel-card">
        <Typography.Text className="section-kicker">Coming Soon</Typography.Text>
        <Typography.Title level={3} className="panel-title">
          版本树与规范页即将上线
        </Typography.Title>
        <Empty description="数据库备份库页面骨架会在下一步补齐。" />
      </Card>
    </div>
  );
}
