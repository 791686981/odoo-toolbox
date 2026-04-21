import { DownloadOutlined, FileZipOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Empty, Spin, Tabs, Tag, Tree, Typography, message } from "antd";
import type { DataNode } from "antd/es/tree";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../shared/api/client";
import type {
  DatabaseBackupDetailRecord,
  DatabaseBackupTreeNodeRecord,
} from "../../shared/api/types";
import {
  DatabaseBackupNodeForm,
  type DatabaseBackupNodeFormMode,
  type DatabaseBackupNodeFormValues,
} from "./DatabaseBackupNodeForm";
import { databaseBackupSpec } from "./databaseBackupSpec";

type ModalState =
  | { mode: "create-root" }
  | { mode: "create-child"; parentId: string }
  | { mode: "edit" };

function flattenTree(nodes: DatabaseBackupTreeNodeRecord[]): DatabaseBackupTreeNodeRecord[] {
  return nodes.flatMap((node) => [node, ...flattenTree(node.children)]);
}

function buildTreeData(nodes: DatabaseBackupTreeNodeRecord[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.id,
    title: (
      <div className="database-backup-tree-title">
        <span className="database-backup-tree-name">{node.name}</span>
        <span className="database-backup-tree-meta">
          {node.is_main_root ? "主线根节点" : formatSourceType(node)}
        </span>
      </div>
    ),
    children: buildTreeData(node.children),
  }));
}

function pickDefaultNodeId(
  nodes: DatabaseBackupTreeNodeRecord[],
  mainRootId: string | null,
): string | null {
  const flatNodes = flattenTree(nodes);
  if (!flatNodes.length) {
    return null;
  }

  if (mainRootId) {
    const mainRoot = flatNodes.find((node) => node.id === mainRootId);
    if (mainRoot) {
      return mainRoot.id;
    }
  }

  return flatNodes[0]?.id ?? null;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatSourceType(detail: Pick<DatabaseBackupDetailRecord, "source_type">) {
  return detail.source_type === "root" ? "主线基点" : "升级分支";
}

function formatFileSize(size: number) {
  if (size >= 1024 * 1024 * 1024) {
    return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(2)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${size} B`;
}

function DetailField(props: { label: string; value: string }) {
  const { label, value } = props;

  return (
    <div className="database-backup-detail-field">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PanelLoading(props: { message: string }) {
  const { message } = props;

  return (
    <div className="database-backup-panel-state">
      <div className="database-backup-loading">
        <Spin />
        <span>{message}</span>
      </div>
    </div>
  );
}

function DatabaseBackupDetailPanel(props: {
  detail: DatabaseBackupDetailRecord | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  const { detail, isLoading, isError } = props;

  if (isLoading) {
    return <PanelLoading message="正在加载节点详情..." />;
  }

  if (isError) {
    return (
      <div className="database-backup-panel-state">
        <Empty description="节点详情加载失败，请稍后刷新重试。" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="database-backup-panel-state">
        <Empty description="请选择一个备份节点查看详情。" />
      </div>
    );
  }

  return (
    <div className="database-backup-detail">
      <div className="database-backup-detail-header">
        <div className="database-backup-detail-title">
          <Typography.Title level={3} className="panel-title">
            {detail.name}
          </Typography.Title>
          <div className="database-backup-detail-tags">
            <Tag color={detail.is_main_root ? "gold" : "default"}>
              {detail.is_main_root ? "主线" : "分支"}
            </Tag>
            <Tag color={detail.source_type === "root" ? "blue" : "geekblue"}>
              {formatSourceType(detail)}
            </Tag>
          </div>
        </div>
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          href={api.databaseBackupZipUrl(detail.id)}
        >
          下载 Zip
        </Button>
      </div>

      <div className="database-backup-detail-grid">
        <DetailField label="来源类型" value={formatSourceType(detail)} />
        <DetailField label="创建时间" value={formatDateTime(detail.created_at)} />
      </div>

      <div className="database-backup-detail-note">
        <span>备注</span>
        <p>{detail.note || "当前没有备注说明。"}</p>
      </div>

      <div className="database-backup-detail-zip">
        <div className="database-backup-detail-zip-icon">
          <FileZipOutlined />
        </div>
        <div className="database-backup-detail-zip-body">
          <strong>{detail.zip.filename}</strong>
          <span>
            {detail.zip.mime_type} · {formatFileSize(detail.zip.size)}
          </span>
          <code>{detail.zip.sha256}</code>
        </div>
      </div>
    </div>
  );
}

function DatabaseBackupSpecPanel() {
  return (
    <div className="database-backup-spec">
      <Typography.Title level={3} className="panel-title">
        {databaseBackupSpec.title}
      </Typography.Title>
      <Typography.Paragraph className="panel-copy">{databaseBackupSpec.intro}</Typography.Paragraph>
      <div className="database-backup-spec-grid">
        {databaseBackupSpec.sections.map((section) => (
          <section key={section.title} className="database-backup-spec-section">
            <Typography.Title level={4}>{section.title}</Typography.Title>
            <ul>
              {section.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

export function DatabaseBackupsPage() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [modalState, setModalState] = useState<ModalState | null>(null);
  const queryClient = useQueryClient();

  const treeQuery = useQuery({
    queryKey: ["database-backups", "tree"],
    queryFn: api.databaseBackupTree,
  });

  const treeItems = treeQuery.data?.items ?? [];

  useEffect(() => {
    if (!treeQuery.data) {
      return;
    }

    const flatNodes = flattenTree(treeQuery.data.items);
    if (!flatNodes.length) {
      setSelectedNodeId(null);
      return;
    }

    const stillExists = selectedNodeId && flatNodes.some((node) => node.id === selectedNodeId);
    if (stillExists) {
      return;
    }

    setSelectedNodeId(pickDefaultNodeId(treeQuery.data.items, treeQuery.data.main_root_id));
  }, [selectedNodeId, treeQuery.data]);

  const detailQuery = useQuery({
    queryKey: ["database-backups", "node", selectedNodeId],
    queryFn: () => api.databaseBackupNode(selectedNodeId!),
    enabled: Boolean(selectedNodeId),
  });

  const createMutation = useMutation({
    mutationFn: api.createDatabaseBackupNode,
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["database-backups", "tree"] });
      await queryClient.invalidateQueries({ queryKey: ["database-backups", "node", payload.id] });
      setSelectedNodeId(payload.id);
      setModalState(null);
      message.success("数据库备份节点已创建");
    },
    onError: (error: Error) => {
      message.error(error.message);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ nodeId, payload }: { nodeId: string; payload: { name?: string; note?: string } }) =>
      api.updateDatabaseBackupNode(nodeId, payload),
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["database-backups", "tree"] });
      await queryClient.invalidateQueries({ queryKey: ["database-backups", "node", payload.id] });
      setModalState(null);
      message.success("节点信息已更新");
    },
    onError: (error: Error) => {
      message.error(error.message);
    },
  });

  const markMainRootMutation = useMutation({
    mutationFn: (nodeId: string) => api.markDatabaseBackupMainRoot(nodeId),
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["database-backups", "tree"] });
      await queryClient.invalidateQueries({ queryKey: ["database-backups", "node", payload.id] });
      message.success("已切换主线根节点");
    },
    onError: (error: Error) => {
      message.error(error.message);
    },
  });

  const expandedKeys = useMemo(() => flattenTree(treeItems).map((node) => node.id), [treeItems]);
  const treeData = useMemo(() => buildTreeData(treeItems), [treeItems]);

  const editInitialValues = detailQuery.data
    ? {
        name: detailQuery.data.name,
        note: detailQuery.data.note,
      }
    : undefined;

  async function handleSubmit(values: DatabaseBackupNodeFormValues) {
    if (!modalState) {
      return;
    }

    if (modalState.mode === "edit" && detailQuery.data) {
      await updateMutation.mutateAsync({
        nodeId: detailQuery.data.id,
        payload: {
          name: values.name,
          note: values.note,
        },
      });
      return;
    }

    await createMutation.mutateAsync({
      name: values.name,
      source_type: modalState.mode === "create-root" ? "root" : "branch",
      parent_id: modalState.mode === "create-child" ? modalState.parentId : null,
      is_main_root: modalState.mode === "create-root" && treeItems.length === 0,
      note: values.note,
      file: values.file!,
    });
  }

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

      <Card className="panel-card database-backup-card">
        <div className="database-backups-page-actions">
          <Button onClick={() => setModalState({ mode: "create-root" })}>新建根节点</Button>
          <Button
            disabled={!detailQuery.data}
            onClick={() => detailQuery.data && setModalState({ mode: "create-child", parentId: detailQuery.data.id })}
          >
            新增子节点
          </Button>
          <Button disabled={!detailQuery.data} onClick={() => setModalState({ mode: "edit" })}>
            编辑节点
          </Button>
          <Button
            disabled={!detailQuery.data || detailQuery.data.parent_id !== null || detailQuery.data.is_main_root}
            loading={markMainRootMutation.isPending}
            onClick={() => detailQuery.data && markMainRootMutation.mutate(detailQuery.data.id)}
          >
            设为主线
          </Button>
        </div>
        <Tabs
          defaultActiveKey="tree"
          items={[
            {
              key: "tree",
              label: "版本树",
              children: (
                <div className="database-backup-layout">
                  <section className="database-backup-panel database-backup-tree-panel">
                    <div className="database-backup-panel-head">
                      <Typography.Text className="section-kicker">Version Tree</Typography.Text>
                      <Typography.Title level={3} className="panel-title">
                        备份版本树
                      </Typography.Title>
                      <Typography.Paragraph className="panel-copy">
                        默认定位主线根节点，左侧浏览备份分支结构，右侧查看当前节点详情与 Zip 摘要。
                      </Typography.Paragraph>
                    </div>

                    {treeQuery.isLoading ? (
                      <PanelLoading message="正在加载版本树..." />
                    ) : treeItems.length ? (
                      <Tree
                        className="database-backup-tree"
                        showLine
                        selectedKeys={selectedNodeId ? [selectedNodeId] : []}
                        expandedKeys={expandedKeys}
                        treeData={treeData}
                        onSelect={(keys) => {
                          setSelectedNodeId((keys[0] as string | undefined) ?? null);
                        }}
                      />
                    ) : (
                      <div className="database-backup-panel-state">
                        <Empty description="当前还没有备份节点，后续任务中创建主线节点后会显示在这里。" />
                      </div>
                    )}
                  </section>

                  <section className="database-backup-panel database-backup-detail-panel">
                    <div className="database-backup-panel-head">
                      <Typography.Text className="section-kicker">Node Detail</Typography.Text>
                      <Typography.Title level={3} className="panel-title">
                        节点详情
                      </Typography.Title>
                    </div>
                    <DatabaseBackupDetailPanel
                      detail={detailQuery.data}
                      isLoading={detailQuery.isLoading}
                      isError={detailQuery.isError}
                    />
                  </section>
                </div>
              ),
            },
            {
              key: "spec",
              label: "命名与升级规范",
              children: <DatabaseBackupSpecPanel />,
            },
          ]}
        />
      </Card>

      <DatabaseBackupNodeForm
        open={modalState !== null}
        mode={(modalState?.mode ?? "create-root") as DatabaseBackupNodeFormMode}
        initialValues={modalState?.mode === "edit" ? editInitialValues : undefined}
        submitting={createMutation.isPending || updateMutation.isPending}
        onCancel={() => setModalState(null)}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
