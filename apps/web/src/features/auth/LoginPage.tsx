import { Button, Card, Form, Input, Typography, message } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../../shared/api/client";

type LoginFormValues = {
  username: string;
  password: string;
};

export function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const loginMutation = useMutation({
    mutationFn: api.login,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate("/", { replace: true });
    },
    onError: (error: Error) => {
      message.error(error.message);
    },
  });

  return (
    <div className="login-screen">
      <Card className="login-card">
        <Typography.Text className="login-kicker">Deep Sea Operations</Typography.Text>
        <Typography.Title level={2} className="login-title">
          登录到工具箱
        </Typography.Title>
        <Typography.Paragraph className="login-copy">
          首版提供 CSV 翻译工作流，后续可以在相同框架下继续扩展其他 Odoo 开发工具。
        </Typography.Paragraph>
        <Form<LoginFormValues> layout="vertical" onFinish={(values) => loginMutation.mutate(values)}>
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input size="large" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password size="large" />
          </Form.Item>
          <Button
            block
            type="primary"
            size="large"
            htmlType="submit"
            loading={loginMutation.isPending}
          >
            进入工具箱
          </Button>
        </Form>
      </Card>
    </div>
  );
}
