import type { SidebarTool, ToolManifest } from "../shared/api/types";

const builtinTools: SidebarTool[] = [
  {
    id: "home",
    title: "工具首页",
    description: "查看工具入口、最近运行与平台快捷操作。",
    route: "/",
    icon: "compass",
    category: "platform",
    enabled: true,
    order: 1,
    capabilities: ["overview"],
    section: "platform",
  },
  {
    id: "runs",
    title: "运行记录",
    description: "统一查看平台内不同工具的运行状态与历史结果。",
    route: "/runs",
    icon: "history",
    category: "platform",
    enabled: true,
    order: 20,
    capabilities: ["runs"],
    section: "platform",
  },
  {
    id: "files",
    title: "文件中心",
    description: "集中管理上传文件、导出文件与后续工具产物。",
    route: "/files",
    icon: "folder",
    category: "platform",
    enabled: true,
    order: 22,
    capabilities: ["files"],
    section: "platform",
  },
  {
    id: "settings",
    title: "系统设置",
    description: "查看模型配置与维护任务默认参数。",
    route: "/settings",
    icon: "setting",
    category: "platform",
    enabled: true,
    order: 25,
    capabilities: ["settings"],
    section: "platform",
  },
];

export function buildSidebarTools(remoteTools: ToolManifest[]): SidebarTool[] {
  const merged: SidebarTool[] = [
    ...remoteTools
      .filter((tool) => tool.enabled)
      .map((tool) => ({ ...tool, section: "tool" as const })),
    ...builtinTools,
  ];

  return merged.sort((left, right) => left.order - right.order);
}
