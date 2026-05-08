export const databaseBackupSpec = {
  title: "UAT 快照规范",
  intro:
    "数据库备份库用于沉淀主线版本、UAT 目录和可复测快照。目录只组织业务域和需求，快照必须绑定 Odoo 原生 zip。",
  sections: [
    {
      title: "UAT 树结构",
      items: [
        "`UAT`、业务域、需求是目录节点，不绑定 zip。",
        "快照节点必须挂在需求目录下，并绑定 Odoo 原生数据库备份 zip。",
        "业务域必须使用标准清单，“模版”不作为 UAT 业务域。",
      ],
    },
    {
      title: "快照命名规范",
      items: [
        "基线使用 `基线快照 - YYYY-MM-DD`。",
        "问题复现使用 `ISSUE-编号 复现现场`。",
        "回归复测使用 `ISSUE-编号 回归复测`。",
      ],
    },
    {
      title: "复测交付规则",
      items: [
        "UAT 测试计划必须记录快照节点 ID 和 sha256。",
        "恢复 Odoo worktree 时只使用快照节点生成的 `.env` 片段。",
        "快照创建后不替换 zip；需要新现场时创建新的快照节点。",
      ],
    },
  ],
} as const;
