import { ConfigProvider, theme } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import zhCN from "antd/locale/zh_CN";
import { BrowserRouter } from "react-router-dom";

import { AppRoutes } from "../routes";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: {
            colorPrimary: "#c57a3f",
            colorInfo: "#16324b",
            colorSuccess: "#2c7a66",
            colorWarning: "#d6924c",
            colorError: "#ba4b45",
            colorBgBase: "#f3ede3",
            colorTextBase: "#12263a",
            borderRadius: 20,
            fontFamily: '"Avenir Next", "PingFang SC", "Microsoft YaHei", sans-serif',
            boxShadowSecondary: "0 18px 42px rgba(9, 24, 39, 0.12)",
          },
          components: {
            Layout: {
              bodyBg: "transparent",
              siderBg: "#081a2a",
              headerBg: "transparent",
            },
            Card: {
              bodyPadding: 22,
            },
            Menu: {
              darkItemBg: "transparent",
              darkSubMenuItemBg: "transparent",
              darkItemSelectedBg: "transparent",
              darkItemHoverBg: "transparent",
            },
            Table: {
              headerBg: "#eef1f2",
              headerColor: "#17324b",
              rowHoverBg: "#f7f2ec",
              borderColor: "#d8cfc0",
            },
          },
        }}
      >
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
