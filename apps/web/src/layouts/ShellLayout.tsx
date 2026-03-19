import {
  CompassOutlined,
  FolderOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  SettingOutlined,
  TranslationOutlined,
} from "@ant-design/icons";
import { Button, Layout, Menu, Spin, Typography } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { api } from "../shared/api/client";
import { buildSidebarTools } from "../tool-registry";

const { Header, Sider, Content } = Layout;
const SIDER_COLLAPSED_STORAGE_KEY = "odoo-toolbox:sider-collapsed";

function readStoredSiderState() {
  if (typeof window === "undefined") {
    return false;
  }

  const storage = window.localStorage;
  if (!storage || typeof storage.getItem !== "function") {
    return false;
  }

  return storage.getItem(SIDER_COLLAPSED_STORAGE_KEY) === "true";
}

function persistSiderState(collapsed: boolean) {
  const storage = window.localStorage;
  if (!storage || typeof storage.setItem !== "function") {
    return;
  }

  storage.setItem(SIDER_COLLAPSED_STORAGE_KEY, String(collapsed));
}

function resolveIcon(icon: string) {
  if (icon === "compass") {
    return <CompassOutlined />;
  }
  if (icon === "folder") {
    return <FolderOutlined />;
  }
  if (icon === "history") {
    return <HistoryOutlined />;
  }
  if (icon === "setting") {
    return <SettingOutlined />;
  }
  return <TranslationOutlined />;
}

function resolveActiveTool(tools: ReturnType<typeof buildSidebarTools>, pathname: string) {
  return [...tools]
    .sort((left, right) => right.route.length - left.route.length)
    .find((tool) => (tool.route === "/" ? pathname === "/" : pathname.startsWith(tool.route)));
}

export function ShellLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [isSiderCollapsed, setIsSiderCollapsed] = useState(readStoredSiderState);

  const userQuery = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    retry: false,
  });
  const toolsQuery = useQuery({
    queryKey: ["tools"],
    queryFn: api.tools,
    retry: false,
  });

  useEffect(() => {
    persistSiderState(isSiderCollapsed);
  }, [isSiderCollapsed]);

  if (userQuery.isLoading || toolsQuery.isLoading) {
    return (
      <div className="center-screen">
        <Spin size="large" />
      </div>
    );
  }

  if (userQuery.isError) {
    return <Navigate to="/login" replace />;
  }

  const tools = buildSidebarTools(toolsQuery.data ?? []);
  const activeTool = resolveActiveTool(tools, location.pathname);
  const toolEntries = tools.filter((tool) => tool.section === "tool");
  const platformEntries = tools.filter((tool) => tool.section === "platform");

  return (
    <Layout className={`shell-layout${isSiderCollapsed ? " shell-layout-collapsed" : ""}`}>
      <Sider
        width={232}
        collapsedWidth={84}
        collapsed={isSiderCollapsed}
        trigger={null}
        className={`shell-sider${isSiderCollapsed ? " is-collapsed" : ""}`}
      >
        <div className={`brand-block${isSiderCollapsed ? " is-collapsed" : ""}`}>
          <div className="brand-mark">OT</div>
          {!isSiderCollapsed ? (
            <div className="brand-meta">
              <Typography.Title level={4} className="brand-title">
                Odoo Toolbox
              </Typography.Title>
              <Typography.Text className="brand-subtitle">开发工具箱</Typography.Text>
            </div>
          ) : null}
        </div>
        <div className="shell-nav-frame">
          {!isSiderCollapsed ? <div className="nav-section-label">工具</div> : null}
          <Menu
            className="shell-menu"
            theme="dark"
            mode="inline"
            inlineCollapsed={isSiderCollapsed}
            selectedKeys={activeTool ? [activeTool.route] : []}
            items={toolEntries.map((tool) => ({
              key: tool.route,
              icon: resolveIcon(tool.icon),
              label: tool.title,
              onClick: () => navigate(tool.route),
            }))}
          />
          {!isSiderCollapsed ? <div className="nav-section-label">平台</div> : null}
          <Menu
            className="shell-menu shell-menu-secondary"
            theme="dark"
            mode="inline"
            inlineCollapsed={isSiderCollapsed}
            selectedKeys={activeTool ? [activeTool.route] : []}
            items={platformEntries.map((tool) => ({
              key: tool.route,
              icon: resolveIcon(tool.icon),
              label: tool.title,
              onClick: () => navigate(tool.route),
            }))}
          />
        </div>
      </Sider>
      <Layout className="shell-main">
        <Header className="shell-header">
          <div className="header-primary">
            <Button
              type="text"
              className="shell-toggle"
              aria-label={isSiderCollapsed ? "展开侧边栏" : "收起侧边栏"}
              icon={isSiderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setIsSiderCollapsed((current) => !current)}
            />
            <Typography.Title level={4} className="header-title">
              {activeTool?.title ?? "工作台"}
            </Typography.Title>
          </div>
          <div className="header-actions">
            <div className="user-chip">
              <span className="user-dot" />
              <Typography.Text>{userQuery.data?.username}</Typography.Text>
            </div>
            <Button
              className="ghost-action"
              icon={<LogoutOutlined />}
              onClick={async () => {
                await api.logout();
                await queryClient.invalidateQueries({ queryKey: ["me"] });
                navigate("/login", { replace: true });
              }}
            >
              退出
            </Button>
          </div>
        </Header>
        <Content className="shell-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
