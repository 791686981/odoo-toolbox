import { Navigate, Route, Routes } from "react-router-dom";

import { LoginPage } from "../features/auth/LoginPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { ShellLayout } from "../layouts/ShellLayout";
import { FilesPage } from "../pages/files/FilesPage";
import { HomePage } from "../pages/home/HomePage";
import { RunsPage } from "../pages/runs/RunsPage";
import { toolPageRegistrations } from "../tools/registry";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ShellLayout />}>
        <Route index element={<HomePage />} />
        {toolPageRegistrations.map(({ id, route, component: ToolPage }) => (
          <Route key={id} path={route} element={<ToolPage />} />
        ))}
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/jobs" element={<Navigate to="/runs" replace />} />
        <Route path="/files" element={<FilesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
