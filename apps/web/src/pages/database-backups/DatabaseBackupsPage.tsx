import {
  CopyOutlined,
  DeleteOutlined,
  DownloadOutlined,
  FileZipOutlined,
  FolderOpenOutlined,
  PlusOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Empty, Form, Input, Spin, Tabs, Tag, Tree, Typography, message } from "antd";
import type { DataNode } from "antd/es/tree";
import { useEffect, useMemo, useState, type ReactNode } from "react";

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
  | { mode: "create-child"; parentId: string };

type DetailFormValues = {
  name: string;
  note: string;
};

function flattenTree(nodes: DatabaseBackupTreeNodeRecord[]): DatabaseBackupTreeNodeRecord[] {
  return nodes.flatMap((node) => [node, ...flattenTree(node.children)]);
}

function findNodeById(
  nodes: DatabaseBackupTreeNodeRecord[],
  nodeId: string | null,
): DatabaseBackupTreeNodeRecord | undefined {
  if (!nodeId) {
    return undefined;
  }

  for (const node of nodes) {
    if (node.id === nodeId) {
      return node;
    }
    const child = findNodeById(node.children, nodeId);
    if (child) {
      return child;
    }
  }

  return undefined;
}

function treeContainsNode(root: DatabaseBackupTreeNodeRecord, nodeId: string | null) {
  return Boolean(findNodeById([root], nodeId));
}

function buildTreeData(
  nodes: DatabaseBackupTreeNodeRecord[],
  onCreateChild: (node: DatabaseBackupTreeNodeRecord) => void,
): DataNode[] {
  return nodes.map((node) => ({
    key: node.id,
    title: (
      <div className="database-backup-tree-title">
        <span className="database-backup-tree-title-copy">
          <span className="database-backup-tree-name">{node.name}</span>
          <span className="database-backup-tree-meta">
            {node.is_main_root ? "主线根节点" : formatNodeKind(node)}
            {node.domain ? ` · ${node.domain}` : ""}
          </span>
        </span>
        <Button
          type="text"
          size="small"
          className="database-backup-tree-action"
          icon={<PlusOutlined />}
          aria-label={`给 ${node.name} 新增子分支`}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onCreateChild(node);
          }}
        />
      </div>
    ),
    children: buildTreeData(node.children, onCreateChild),
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

function formatNodeKind(detail: Pick<DatabaseBackupDetailRecord, "node_kind">) {
  return detail.node_kind === "folder" ? "目录" : "快照";
}

function formatSnapshotType(value: DatabaseBackupDetailRecord["snapshot_type"]) {
  const labels: Record<string, string> = {
    baseline: "基线快照",
    issue_reproduction: "复现现场",
    regression: "回归复测",
    ad_hoc: "临时快照",
  };
  return value ? labels[value] ?? value : "未设置";
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

async function copyTextToClipboard(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textArea = document.createElement("textarea");
  textArea.value = value;
  textArea.setAttribute("readonly", "");
  textArea.style.position = "fixed";
  textArea.style.opacity = "0";
  document.body.append(textArea);
  textArea.select();

  const copied = document.execCommand("copy");
  textArea.remove();

  if (!copied) {
    throw new Error("copy-failed");
  }
}

function DetailField(props: { label: string; value: ReactNode; action?: ReactNode; valueClassName?: string }) {
  const { label, value, action, valueClassName } = props;
  const valueClassNames = ["database-backup-detail-field-value", valueClassName].filter(Boolean).join(" ");

  return (
    <div className="database-backup-detail-field">
      <div className="database-backup-detail-field-head">
        <span className="database-backup-detail-field-label">{label}</span>
        {action}
      </div>
      <strong className={valueClassNames}>{value}</strong>
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

function DatabaseBackupDetailEditor(props: {
  detail: DatabaseBackupDetailRecord;
  canDelete: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  branchActionLabel: string;
  isCopyingRestoreEnv: boolean;
  onSave: (values: DetailFormValues) => Promise<void>;
  onDelete: () => Promise<void>;
  onCreateBranch: () => void;
  onCopyRestoreEnv: () => Promise<void>;
}) {
  const {
    detail,
    canDelete,
    isSaving,
    isDeleting,
    branchActionLabel,
    isCopyingRestoreEnv,
    onSave,
    onDelete,
    onCreateBranch,
    onCopyRestoreEnv,
  } = props;
  const [form] = Form.useForm<DetailFormValues>();

  useEffect(() => {
    form.setFieldsValue({
      name: detail.name,
      note: detail.note,
    });
  }, [detail, form]);

  async function handleCopyNodeId() {
    try {
      await copyTextToClipboard(detail.id);
      message.success("节点 ID 已复制");
    } catch {
      message.error("复制失败，请稍后重试");
    }
  }

  return (
    <Form form={form} layout="vertical" className="database-backup-detail" onFinish={onSave}>
      <div className="database-backup-detail-header">
        <div className="database-backup-detail-title">
          <Typography.Title level={3} className="panel-title">
            {detail.name}
          </Typography.Title>
          <div className="database-backup-detail-tags">
            <Tag color={detail.node_kind === "folder" ? "cyan" : "purple"}>
              {formatNodeKind(detail)}
            </Tag>
            <Tag color={detail.is_main_root ? "gold" : "default"}>
              {detail.is_main_root ? "主线" : "分支"}
            </Tag>
            {detail.node_kind === "snapshot" ? (
              <Tag color="geekblue">{formatSnapshotType(detail.snapshot_type)}</Tag>
            ) : null}
          </div>
        </div>
        <div className="database-backup-detail-actions">
          <Button icon={<PlusOutlined />} aria-label={branchActionLabel} onClick={onCreateBranch}>
            {branchActionLabel}
          </Button>
          <Button htmlType="submit" type="primary" icon={<SaveOutlined />} loading={isSaving} aria-label="保存">
            保存
          </Button>
          {detail.zip ? (
            <>
              <Button icon={<DownloadOutlined />} href={api.databaseBackupZipUrl(detail.id)}>
                下载 Zip
              </Button>
              <Button loading={isCopyingRestoreEnv} onClick={() => void onCopyRestoreEnv()}>
                复制恢复配置
              </Button>
            </>
          ) : null}
          <Button
            danger
            icon={<DeleteOutlined />}
            disabled={!canDelete}
            loading={isDeleting}
            aria-label="删除节点"
            onClick={() => {
              void onDelete();
            }}
          >
            删除节点
          </Button>
        </div>
      </div>

      <div className="database-backup-detail-edit">
        <Form.Item name="name" label="节点名" rules={[{ required: true, message: "请输入节点名" }]}>
          <Input />
        </Form.Item>
        <Form.Item name="note" label="备注">
          <Input.TextArea rows={5} />
        </Form.Item>
      </div>

      <div className="database-backup-detail-grid">
        <DetailField
          label="节点 ID"
          value={<code>{detail.id}</code>}
          valueClassName="is-code"
          action={
            <Button
              type="text"
              size="small"
              className="database-backup-detail-copy"
              icon={<CopyOutlined />}
              aria-label="复制节点 ID"
              onClick={() => {
                void handleCopyNodeId();
              }}
            >
              复制 ID
            </Button>
          }
        />
        <DetailField label="节点类型" value={formatNodeKind(detail)} />
        <DetailField label="来源类型" value={formatSourceType(detail)} />
        <DetailField label="创建时间" value={formatDateTime(detail.created_at)} />
        {detail.domain ? <DetailField label="业务域" value={detail.domain} /> : null}
        {detail.requirement_title ? <DetailField label="需求" value={detail.requirement_title} /> : null}
        {detail.notion_url ? (
          <DetailField
            label="Notion"
            value={
              <a href={detail.notion_url} target="_blank" rel="noreferrer">
                {detail.notion_url}
              </a>
            }
            valueClassName="is-code"
          />
        ) : null}
      </div>

      <div className="database-backup-detail-zip">
        <div className="database-backup-detail-zip-icon">
          {detail.zip ? <FileZipOutlined /> : <FolderOpenOutlined />}
        </div>
        <div className="database-backup-detail-zip-body">
          {detail.zip ? (
            <>
              <strong>{detail.zip.filename}</strong>
              <span>
                {detail.zip.mime_type} · {formatFileSize(detail.zip.size)}
              </span>
              <code>{detail.zip.sha256}</code>
            </>
          ) : (
            <>
              <strong>目录节点</strong>
              <span>目录用于组织 UAT 业务域和需求，不绑定 zip 文件。</span>
            </>
          )}
        </div>
      </div>
    </Form>
  );
}

function DatabaseBackupDetailPanel(props: {
  detail: DatabaseBackupDetailRecord | undefined;
  isLoading: boolean;
  isError: boolean;
  canDelete: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  branchActionLabel: string;
  isCopyingRestoreEnv: boolean;
  onSave: (values: DetailFormValues) => Promise<void>;
  onDelete: () => Promise<void>;
  onCreateBranch: () => void;
  onCopyRestoreEnv: () => Promise<void>;
}) {
  const {
    detail,
    isLoading,
    isError,
    canDelete,
    isSaving,
    isDeleting,
    branchActionLabel,
    isCopyingRestoreEnv,
    onSave,
    onDelete,
    onCreateBranch,
    onCopyRestoreEnv,
  } = props;

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
    <DatabaseBackupDetailEditor
      detail={detail}
      canDelete={canDelete}
      isSaving={isSaving}
      isDeleting={isDeleting}
      branchActionLabel={branchActionLabel}
      isCopyingRestoreEnv={isCopyingRestoreEnv}
      onSave={onSave}
      onDelete={onDelete}
      onCreateBranch={onCreateBranch}
      onCopyRestoreEnv={onCopyRestoreEnv}
    />
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
  const [selectedRootId, setSelectedRootId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
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

    if (!treeQuery.data.items.length) {
      setSelectedRootId(null);
      setSelectedNodeId(null);
      return;
    }

    const rootStillExists = selectedRootId && treeQuery.data.items.some((node) => node.id === selectedRootId);
    const nextRootId = rootStillExists
      ? selectedRootId
      : pickDefaultNodeId(treeQuery.data.items, treeQuery.data.main_root_id);
    const nextRoot = treeQuery.data.items.find((node) => node.id === nextRootId);

    if (nextRootId !== selectedRootId) {
      setSelectedRootId(nextRootId);
    }

    if (!nextRoot) {
      setSelectedNodeId(null);
      return;
    }

    if (!treeContainsNode(nextRoot, selectedNodeId)) {
      setSelectedNodeId(nextRoot.id);
    }
  }, [selectedNodeId, selectedRootId, treeQuery.data]);

  const selectedRoot = useMemo(
    () => treeItems.find((node) => node.id === selectedRootId),
    [selectedRootId, treeItems],
  );

  useEffect(() => {
    if (!selectedRoot) {
      setExpandedKeys([]);
      return;
    }

    setExpandedKeys(flattenTree(selectedRoot.children).map((node) => node.id));
  }, [selectedRootId]);

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
      if (!payload.parent_id) {
        setSelectedRootId(payload.id);
      } else {
        setExpandedKeys((keys) => Array.from(new Set([...keys, payload.parent_id!])));
      }
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

  const deleteMutation = useMutation({
    mutationFn: (nodeId: string) => api.deleteDatabaseBackupNode(nodeId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["database-backups", "tree"] });
      message.success("备份节点已删除");
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

  const restoreEnvMutation = useMutation({
    mutationFn: (nodeId: string) => api.databaseBackupRestoreEnv(nodeId),
  });

  const selectedTreeNode = useMemo(
    () => findNodeById(treeItems, selectedNodeId),
    [selectedNodeId, treeItems],
  );
  const selectedNodeIsRoot = Boolean(selectedNodeId && selectedNodeId === selectedRootId);
  const canDeleteSelectedNode = Boolean(selectedTreeNode && selectedTreeNode.children.length === 0);
  const branchActionLabel = selectedNodeIsRoot ? "新增一级分支" : "新增子分支";

  function openCreateChild(parentId: string) {
    setSelectedNodeId(parentId);
    setModalState({ mode: "create-child", parentId });
  }

  const branchTreeData = useMemo(
    () =>
      buildTreeData(selectedRoot?.children ?? [], (node) => {
        openCreateChild(node.id);
      }),
    [selectedRoot],
  );

  function handleSelectRoot(root: DatabaseBackupTreeNodeRecord) {
    setSelectedRootId(root.id);
    setSelectedNodeId(root.id);
    setExpandedKeys(flattenTree(root.children).map((node) => node.id));
  }

  function handleCreateBranchFromSelectedNode() {
    if (!selectedNodeId) {
      return;
    }

    openCreateChild(selectedNodeId);
  }

  async function handleSaveDetail(values: DetailFormValues) {
    if (!detailQuery.data) {
      return;
    }

    await updateMutation.mutateAsync({
      nodeId: detailQuery.data.id,
      payload: {
        name: values.name,
        note: values.note,
      },
    });
  }

  async function handleDeleteDetail() {
    if (!detailQuery.data || !selectedTreeNode || !canDeleteSelectedNode) {
      return;
    }

    const nextSelectedNodeId = selectedTreeNode.parent_id;
    await deleteMutation.mutateAsync(detailQuery.data.id);
    setSelectedNodeId(nextSelectedNodeId);
    if (detailQuery.data.id === selectedRootId) {
      setSelectedRootId(null);
    }
  }

  async function handleCopyRestoreEnv() {
    if (!detailQuery.data || detailQuery.data.node_kind !== "snapshot") {
      return;
    }

    try {
      const payload = await restoreEnvMutation.mutateAsync(detailQuery.data.id);
      await copyTextToClipboard(payload.restore_env);
      message.success("恢复配置已复制");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "恢复配置复制失败");
    }
  }

  async function handleSubmit(values: DatabaseBackupNodeFormValues) {
    if (!modalState) {
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
            icon={<PlusOutlined />}
            aria-label={branchActionLabel}
            onClick={handleCreateBranchFromSelectedNode}
          >
            {branchActionLabel}
          </Button>
          <Button
            disabled={
              !detailQuery.data ||
              detailQuery.data.node_kind !== "snapshot" ||
              detailQuery.data.parent_id !== null ||
              detailQuery.data.is_main_root
            }
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
                  <section className="database-backup-panel database-backup-root-panel">
                    <div className="database-backup-panel-head">
                      <Typography.Text className="section-kicker">Roots</Typography.Text>
                      <Typography.Title level={3} className="panel-title">
                        根节点
                      </Typography.Title>
                    </div>

                    {treeQuery.isLoading ? (
                      <PanelLoading message="正在加载根节点..." />
                    ) : treeItems.length ? (
                      <div className="database-backup-root-list">
                        {treeItems.map((root) => (
                          <button
                            key={root.id}
                            type="button"
                            className={`database-backup-root-item${root.id === selectedRootId ? " is-active" : ""}`}
                            onClick={() => handleSelectRoot(root)}
                          >
                            <span>{root.name}</span>
                            <Tag color={root.node_kind === "folder" ? "cyan" : "purple"}>
                              {formatNodeKind(root)}
                            </Tag>
                            {root.is_main_root ? <Tag color="gold">主线</Tag> : null}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <div className="database-backup-panel-state">
                        <Empty description="当前还没有备份根节点。" />
                      </div>
                    )}
                  </section>

                  <section className="database-backup-panel database-backup-branch-tree-panel">
                    <div className="database-backup-panel-head">
                      <Typography.Text className="section-kicker">Branches</Typography.Text>
                      <Typography.Title level={3} className="panel-title">
                        分支树
                      </Typography.Title>
                      <Typography.Paragraph className="panel-copy">
                        选择左侧根节点后，在这里浏览它下面的升级分支。
                      </Typography.Paragraph>
                    </div>

                    {treeQuery.isLoading ? (
                      <PanelLoading message="正在加载分支树..." />
                    ) : selectedRoot?.children.length ? (
                      <Tree
                        className="database-backup-tree"
                        showLine
                        autoExpandParent={false}
                        selectedKeys={selectedNodeId && !selectedNodeIsRoot ? [selectedNodeId] : []}
                        expandedKeys={expandedKeys}
                        treeData={branchTreeData}
                        onExpand={(keys) => {
                          setExpandedKeys(keys.map(String));
                        }}
                        onSelect={(keys) => {
                          setSelectedNodeId((keys[0] as string | undefined) ?? selectedRoot.id);
                        }}
                      />
                    ) : (
                      <div className="database-backup-panel-state">
                        <Empty description="当前根节点还没有分支节点。" />
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
                      canDelete={canDeleteSelectedNode}
                      isSaving={updateMutation.isPending}
                      isDeleting={deleteMutation.isPending}
                      branchActionLabel={branchActionLabel}
                      isCopyingRestoreEnv={restoreEnvMutation.isPending}
                      onSave={handleSaveDetail}
                      onDelete={handleDeleteDetail}
                      onCreateBranch={handleCreateBranchFromSelectedNode}
                      onCopyRestoreEnv={handleCopyRestoreEnv}
                    />
                  </section>
                </div>
              ),
            },
            {
              key: "spec",
              label: "UAT 快照规范",
              children: <DatabaseBackupSpecPanel />,
            },
          ]}
        />
      </Card>

      <DatabaseBackupNodeForm
        open={modalState !== null}
        mode={(modalState?.mode ?? "create-root") as DatabaseBackupNodeFormMode}
        submitting={createMutation.isPending || updateMutation.isPending}
        onCancel={() => setModalState(null)}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
